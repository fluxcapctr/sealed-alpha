import { Resend } from "resend";
import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import type { Database } from "@/types/database";
import { readTextBody } from "@/lib/request-body";

const resend = process.env.RESEND_API_KEY
  ? new Resend(process.env.RESEND_API_KEY)
  : null;

const supabaseAdmin =
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY
    ? createClient<Database>(
        process.env.NEXT_PUBLIC_SUPABASE_URL,
        process.env.SUPABASE_SERVICE_ROLE_KEY
      )
    : null;

const SITE_URL = "https://sealedalpha.com";
const SENDER =
  process.env.DRIP_SENDER_EMAIL ?? "onboarding@resend.dev";

// --- Simple in-memory rate limiter ---
// NOTE: this state lives in a single server instance's memory. On serverless
// platforms (e.g. Vercel) every cold start / concurrent instance has its own
// map, so this is only best-effort abuse damping, not a global limit. Use a
// shared store (Redis/Upstash, Vercel KV, or a DB counter) for a real limit.
const rateLimitMap = new Map<string, { count: number; resetAt: number }>();
const RATE_LIMIT_WINDOW_MS = 60_000; // 1 minute
const RATE_LIMIT_MAX = 5; // 5 requests per minute per IP

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const entry = rateLimitMap.get(ip);

  if (!entry || now > entry.resetAt) {
    rateLimitMap.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return false;
  }

  entry.count++;
  return entry.count > RATE_LIMIT_MAX;
}

// Clean up stale entries every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [key, val] of rateLimitMap) {
    if (now > val.resetAt) rateLimitMap.delete(key);
  }
}, 300_000);

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// RFC 5321 maximum length of an email address.
const MAX_EMAIL_LENGTH = 254;
// The request body is just {"email": "..."}; refuse anything bigger.
const MAX_BODY_BYTES = 1024;
// Generic on purpose: never forward the provider's error message to the client.
const SEND_FAILED_MESSAGE =
  "We couldn't send your welcome email. Please try again in a few minutes.";

function welcomeEmailHtml(unsubscribeUrl: string): string {
  return `
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: #e5e5e5; padding: 0; margin: 0;">
        <div style="max-width: 560px; margin: 0 auto; padding: 32px 20px;">
            <div style="margin-bottom: 24px;">
                <span style="font-size: 20px; font-weight: 700; color: #f59e0b;">Sealed Alpha</span>
                <span style="color: #525252; font-size: 14px; margin-left: 8px;">Pokemon TCG Analytics</span>
            </div>
            <h1 style="font-size: 22px; color: #f5f5f5; margin-bottom: 16px;">Welcome to Sealed Alpha!</h1>
            <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
                You now have access to the most comprehensive Pokemon TCG sealed product tracker on the market.
            </p>
            <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">Here's what you can do right now:</p>
            <ul style="color: #a3a3a3; line-height: 2; font-size: 15px; padding-left: 20px;">
                <li><strong style="color: #e5e5e5;">Rip Scores</strong> — See the expected value of ripping any booster box</li>
                <li><strong style="color: #e5e5e5;">Supply Tracking</strong> — Watch inventory deplete in real time</li>
                <li><strong style="color: #e5e5e5;">Set Grades</strong> — Our investibility scores rank every set S through F</li>
                <li><strong style="color: #e5e5e5;">Price History</strong> — 2+ years of market data across 800+ products</li>
            </ul>
            <div style="margin: 24px 0;">
                <a href="${SITE_URL}" style="display: inline-block; padding: 12px 28px; background: #f59e0b; color: #0a0a0f; font-weight: 700; font-size: 14px; text-decoration: none; border-radius: 6px;">Explore the Dashboard</a>
            </div>
            <p style="color: #525252; font-size: 12px;">Data sourced from TCGPlayer. Not financial advice.</p>
            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #262626;">
                <p style="color: #525252; font-size: 11px; line-height: 1.5;">
                    You're receiving this because you signed up for Sealed Alpha.<br>
                    <a href="${unsubscribeUrl}" style="color: #525252; text-decoration: underline;">Unsubscribe</a>
                </p>
            </div>
        </div>
    </body>
    </html>
  `;
}

type AdminClient = NonNullable<typeof supabaseAdmin>;

function isoDate(daysFromNow: number): string {
  return new Date(Date.now() + daysFromNow * 86400000)
    .toISOString()
    .split("T")[0];
}

function jsonError(error: string, status: number) {
  return NextResponse.json({ error }, { status });
}

function withAccessCookie(resp: NextResponse): NextResponse {
  resp.cookies.set("sa_access", "1", {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 365, // 1 year
    path: "/",
  });
  return resp;
}

async function findSubscriber(db: AdminClient, email: string) {
  const { data, error } = await db
    .from("drip_subscribers")
    .select("id, current_step, opted_out, unsubscribe_token")
    .eq("email", email)
    .maybeSingle();

  // A real DB error must not be mistaken for "no such subscriber".
  if (error) throw error;
  return data;
}

// Returns the existing subscriber row untouched, or creates a new one at
// current_step = 0 / next_send_date = today. Step 0 means "welcome not yet
// delivered": if the send below fails, the daily Python drip job (which sends
// step 1 to anyone with next_send_date <= today and current_step < 6) can still
// deliver the welcome as a fallback, and a retry from the user is not treated
// as already subscribed.
async function getOrCreateSubscriber(db: AdminClient, email: string) {
  const existing = await findSubscriber(db, email);
  if (existing) return existing;

  const today = isoDate(0);
  const { data: created, error } = await db
    .from("drip_subscribers")
    .insert({
      email,
      signup_date: today,
      current_step: 0,
      next_send_date: today,
    })
    .select("id, current_step, opted_out, unsubscribe_token")
    .single();

  if (!error) return created;

  // Unique violation: a concurrent request created the row first.
  if (error.code === "23505") {
    const raced = await findSubscriber(db, email);
    if (raced) return raced;
  }
  throw error;
}

export async function POST(request: Request) {
  try {
    // Rate limit by IP (best-effort, per instance; see note on the limiter above)
    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
      request.headers.get("x-real-ip") ??
      "unknown";

    if (isRateLimited(ip)) {
      return jsonError("Too many requests", 429);
    }

    const rawBody = await readTextBody(request, MAX_BODY_BYTES);
    if (rawBody === null) {
      return jsonError("Request too large", 413);
    }

    let body: unknown;
    try {
      body = JSON.parse(rawBody);
    } catch {
      return jsonError("Valid email required", 400);
    }

    // Normalize BEFORE validating, deduping or storing.
    const rawEmail = (body as { email?: unknown } | null)?.email;
    const email =
      typeof rawEmail === "string" ? rawEmail.trim().toLowerCase() : "";

    if (!email || email.length > MAX_EMAIL_LENGTH || !EMAIL_REGEX.test(email)) {
      return jsonError("Valid email required", 400);
    }

    // --- Find or create the drip subscriber (step 0 until the welcome is sent) ---
    const db = supabaseAdmin;
    let subscriber: Awaited<ReturnType<typeof getOrCreateSubscriber>> | null =
      null;

    if (db) {
      subscriber = await getOrCreateSubscriber(db, email);

      // Already welcomed (or opted out): leave the row exactly as it is.
      if (subscriber.opted_out || subscriber.current_step >= 1) {
        return withAccessCookie(
          NextResponse.json({ success: true, already_subscribed: true })
        );
      }
    }

    // Skip email if no API key (dev mode)
    if (!resend) {
      console.log(`[Welcome Email] Would send to ${email} (no API key)`);
      return NextResponse.json({ success: true, skipped: true });
    }

    const unsubscribeToken = subscriber?.unsubscribe_token ?? null;
    const unsubscribeUrl = unsubscribeToken
      ? `${SITE_URL}/api/unsubscribe?token=${unsubscribeToken}`
      : `${SITE_URL}/api/unsubscribe`;

    let resendId: string | null = null;
    try {
      const { data: emailResp, error } = await resend.emails.send({
        from: `Sealed Alpha <${SENDER}>`,
        to: email,
        subject: "Welcome to Sealed Alpha - Your Pokemon TCG Edge",
        html: welcomeEmailHtml(unsubscribeUrl),
        // RFC 8058 one-click unsubscribe (POST /api/unsubscribe?token=...)
        ...(unsubscribeToken
          ? {
              headers: {
                "List-Unsubscribe": `<${unsubscribeUrl}>`,
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
              },
            }
          : {}),
      });

      if (error) {
        // Log the provider error server-side only; the client gets a generic message.
        console.error("[Welcome Email] Resend error:", error);
        return jsonError(SEND_FAILED_MESSAGE, 502);
      }
      resendId = emailResp?.id ?? null;
    } catch (sendErr) {
      console.error("[Welcome Email] Send threw:", sendErr);
      return jsonError(SEND_FAILED_MESSAGE, 502);
    }

    // --- Only after a successful send: record that step 1 (welcome) went out ---
    if (db && subscriber) {
      const { error: stepError } = await db
        .from("drip_subscribers")
        .update({ current_step: 1, next_send_date: isoDate(3) })
        .eq("id", subscriber.id)
        .eq("current_step", 0); // never move an already-advanced row

      if (stepError) {
        // The email was delivered, so still succeed; the row stays at step 0 and
        // the drip job may re-send the welcome. Surface it loudly in the logs.
        console.error("[Welcome Email] Failed to advance drip step:", stepError);
      }

      const { error: logError } = await db.from("drip_log").insert({
        subscriber_id: subscriber.id,
        step: 1,
        template_key: "welcome",
        resend_id: resendId,
      });

      if (logError) {
        console.error("[Welcome Email] Failed to write drip_log:", logError);
      }
    }

    return withAccessCookie(NextResponse.json({ success: true }));
  } catch (err) {
    console.error("[Welcome Email] Unexpected error:", err);
    return jsonError("Internal server error", 500);
  }
}
