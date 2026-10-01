import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import type { Database } from "@/types/database";
import { readTextBody } from "@/lib/request-body";
import { isUuid } from "@/lib/uuid";

const supabaseAdmin =
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY
    ? createClient<Database>(
        process.env.NEXT_PUBLIC_SUPABASE_URL,
        process.env.SUPABASE_SERVICE_ROLE_KEY
      )
    : null;

// The page URL carries the secret token, so don't cache it or leak it via Referer.
const HTML_HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
  "Cache-Control": "no-store",
  "Referrer-Policy": "no-referrer",
};
const TEXT_HEADERS = {
  "Content-Type": "text/plain; charset=utf-8",
  "Cache-Control": "no-store",
};

// RFC 8058 one-click bodies are tiny ("List-Unsubscribe=One-Click"); refuse anything big.
const MAX_BODY_BYTES = 2048;

// `extraHtml` is trusted, server-built markup (never user input) appended under the message.
function htmlPage(message: string, success: boolean, extraHtml = ""): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Unsubscribe - Sealed Alpha</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0a0a0f;
      color: #e5e5e5;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }
    .card {
      text-align: center;
      max-width: 420px;
      padding: 40px 32px;
    }
    .logo {
      font-size: 20px;
      font-weight: 700;
      color: #f59e0b;
      margin-bottom: 24px;
    }
    .message {
      color: ${success ? "#a3a3a3" : "#ef4444"};
      font-size: 15px;
      line-height: 1.7;
    }
    a {
      color: #f59e0b;
      text-decoration: none;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">Sealed Alpha</div>
    <p class="message">${message}</p>${extraHtml}
    <p style="margin-top: 24px;"><a href="https://sealedalpha.com">Back to Sealed Alpha</a></p>
  </div>
</body>
</html>`;
}

function htmlResponse(message: string, success: boolean, status: number, extraHtml = "") {
  return new NextResponse(htmlPage(message, success, extraHtml), {
    status,
    headers: HTML_HEADERS,
  });
}

function textResponse(body: string, status: number) {
  return new NextResponse(body, { status, headers: TEXT_HEADERS });
}

type UnsubscribeResult =
  | { kind: "ok" }
  | { kind: "already" }
  | { kind: "not_found" }
  | { kind: "unavailable" }
  | { kind: "error" };

// Performs the actual unsubscribe. Only ever called from POST: GET must stay free of
// side effects because mail scanners and link prefetchers fetch URLs from emails.
async function unsubscribeByToken(token: string): Promise<UnsubscribeResult> {
  if (!supabaseAdmin) return { kind: "unavailable" };

  const { data: sub, error } = await supabaseAdmin
    .from("drip_subscribers")
    .select("id, opted_out")
    .eq("unsubscribe_token", token)
    .maybeSingle();

  if (error) {
    console.error("[Unsubscribe] Lookup failed:", error);
    return { kind: "error" };
  }
  if (!sub) return { kind: "not_found" };
  if (sub.opted_out) return { kind: "already" };

  const { error: updateError } = await supabaseAdmin
    .from("drip_subscribers")
    .update({ opted_out: true })
    .eq("unsubscribe_token", token);

  if (updateError) {
    console.error("[Unsubscribe] Update failed:", updateError);
    return { kind: "error" };
  }
  return { kind: "ok" };
}

// GET only shows a confirmation form; it never changes state.
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const token = searchParams.get("token");

  if (!isUuid(token)) {
    return htmlResponse("Invalid unsubscribe link.", false, 400);
  }

  // `token` is a validated UUID (hex + dashes only), so it is safe to embed in HTML.
  const form = `
    <form method="POST" action="/api/unsubscribe" style="margin-top: 24px;">
      <input type="hidden" name="token" value="${token}">
      <button type="submit">Confirm unsubscribe</button>
    </form>`;

  return htmlResponse(
    "Click the button below to stop receiving emails from Sealed Alpha.",
    true,
    200,
    form
  );
}

// POST performs the unsubscribe. Accepts either:
//  - the confirmation form above (urlencoded body `token=<uuid>`), or
//  - an RFC 8058 one-click request: `POST /api/unsubscribe?token=<uuid>` with body
//    `List-Unsubscribe=One-Click` (sent by mail clients for the List-Unsubscribe-Post header).
export async function POST(request: Request) {
  const { searchParams } = new URL(request.url);

  let form = new URLSearchParams();
  try {
    const raw = await readTextBody(request, MAX_BODY_BYTES);
    if (raw === null) return textResponse("Request too large.", 413);
    form = new URLSearchParams(raw);
  } catch {
    // Unreadable body: fall through; the token may still be in the query string.
  }

  const oneClick = form.get("List-Unsubscribe")?.trim().toLowerCase() === "one-click";
  const token = searchParams.get("token") ?? form.get("token");

  if (!isUuid(token)) {
    return oneClick
      ? textResponse("Invalid unsubscribe link.", 400)
      : htmlResponse("Invalid unsubscribe link.", false, 400);
  }

  const result = await unsubscribeByToken(token);

  if (oneClick) {
    switch (result.kind) {
      case "ok":
      case "already":
        return textResponse("Unsubscribed.", 200);
      case "not_found":
        return textResponse("This unsubscribe link is invalid or has expired.", 404);
      case "unavailable":
        return textResponse("Service unavailable. Please try again later.", 500);
      default:
        return textResponse("Something went wrong. Please try again later.", 500);
    }
  }

  switch (result.kind) {
    case "ok":
      return htmlResponse(
        "You've been unsubscribed from Sealed Alpha emails. You won't receive any more messages from us.",
        true,
        200
      );
    case "already":
      return htmlResponse(
        "You've already been unsubscribed. No further emails will be sent.",
        true,
        200
      );
    case "not_found":
      return htmlResponse("This unsubscribe link is invalid or has expired.", false, 404);
    case "unavailable":
      return htmlResponse("Service unavailable. Please try again later.", false, 500);
    default:
      return htmlResponse("Something went wrong. Please try again later.", false, 500);
  }
}
