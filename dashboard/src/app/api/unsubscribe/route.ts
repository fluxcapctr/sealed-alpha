import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import type { Database } from "@/types/database";

const supabaseAdmin =
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY
    ? createClient<Database>(
        process.env.NEXT_PUBLIC_SUPABASE_URL,
        process.env.SUPABASE_SERVICE_ROLE_KEY
      )
    : null;

function htmlPage(message: string, success: boolean): string {
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
    <p class="message">${message}</p>
    <p style="margin-top: 24px;"><a href="https://sealedalpha.com">Back to Sealed Alpha</a></p>
  </div>
</body>
</html>`;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const token = searchParams.get("token");

  if (!token) {
    return new NextResponse(
      htmlPage("Invalid unsubscribe link.", false),
      { status: 400, headers: { "Content-Type": "text/html" } }
    );
  }

  if (!supabaseAdmin) {
    return new NextResponse(
      htmlPage("Service unavailable. Please try again later.", false),
      { status: 500, headers: { "Content-Type": "text/html" } }
    );
  }

  const { data: sub, error } = await supabaseAdmin
    .from("drip_subscribers")
    .select("id, email, opted_out")
    .eq("unsubscribe_token", token)
    .single();

  if (error || !sub) {
    return new NextResponse(
      htmlPage("This unsubscribe link is invalid or has expired.", false),
      { status: 404, headers: { "Content-Type": "text/html" } }
    );
  }

  if (sub.opted_out) {
    return new NextResponse(
      htmlPage("You've already been unsubscribed. No further emails will be sent.", true),
      { status: 200, headers: { "Content-Type": "text/html" } }
    );
  }

  await supabaseAdmin
    .from("drip_subscribers")
    .update({ opted_out: true })
    .eq("id", sub.id);

  return new NextResponse(
    htmlPage("You've been unsubscribed from Sealed Alpha emails. You won't receive any more messages from us.", true),
    { status: 200, headers: { "Content-Type": "text/html" } }
  );
}
