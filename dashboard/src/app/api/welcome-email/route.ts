import { Resend } from "resend";
import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import type { Database } from "@/types/database";

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

export async function POST(request: Request) {
  try {
    // Rate limit by IP
    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
      request.headers.get("x-real-ip") ??
      "unknown";

    if (isRateLimited(ip)) {
      return NextResponse.json(
        { error: "Too many requests" },
        { status: 429 }
      );
    }

    const { email } = await request.json();

    if (!email || typeof email !== "string" || !EMAIL_REGEX.test(email)) {
      return NextResponse.json({ error: "Valid email required" }, { status: 400 });
    }

    // --- Check if already subscribed (skip duplicate sends) ---
    if (supabaseAdmin) {
      const { data: existing } = await supabaseAdmin
        .from("drip_subscribers")
        .select("id, current_step")
        .eq("email", email)
        .single();

      if (existing && existing.current_step >= 1) {
        return NextResponse.json({ success: true, already_subscribed: true });
      }
    }

    // --- Insert drip subscriber ---
    let unsubscribeToken: string | null = null;

    if (supabaseAdmin) {
      const today = new Date().toISOString().split("T")[0];
      const nextSendDate = new Date(Date.now() + 3 * 86400000)
        .toISOString()
        .split("T")[0];

      const { data: sub, error: dbError } = await supabaseAdmin
        .from("drip_subscribers")
        .upsert(
          {
            email,
            signup_date: today,
            current_step: 1,
            next_send_date: nextSendDate,
          },
          { onConflict: "email" }
        )
        .select("unsubscribe_token")
        .single();

      if (dbError) {
        console.error("[Drip] DB insert error:", dbError);
      } else {
        unsubscribeToken = sub?.unsubscribe_token ?? null;
      }
    }

    // Skip email if no API key (dev mode)
    if (!resend) {
      console.log(`[Welcome Email] Would send to ${email} (no API key)`);
      return NextResponse.json({ success: true, skipped: true });
    }

    const unsubscribeUrl = unsubscribeToken
      ? `${SITE_URL}/api/unsubscribe?token=${unsubscribeToken}`
      : `${SITE_URL}/api/unsubscribe`;

    const { data: emailResp, error } = await resend.emails.send({
      from: `Sealed Alpha <${SENDER}>`,
      to: email,
      subject: "Welcome to Sealed Alpha - Your Pokemon TCG Edge",
      html: welcomeEmailHtml(unsubscribeUrl),
    });

    if (error) {
      console.error("[Welcome Email] Error:", error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    // Log to drip_log
    if (supabaseAdmin && unsubscribeToken) {
      const { data: sub } = await supabaseAdmin
        .from("drip_subscribers")
        .select("id")
        .eq("email", email)
        .single();

      if (sub) {
        await supabaseAdmin.from("drip_log").insert({
          subscriber_id: sub.id,
          step: 1,
          template_key: "welcome",
          resend_id: emailResp?.id ?? null,
        });
      }
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("[Welcome Email] Unexpected error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
