import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const DEFAULT_NEXT = "/overview";

/**
 * Only allow same-site relative paths. `next` is appended to `origin`, so a value
 * like "@evil.com" would yield "https://site.com@evil.com" (userinfo trick), and
 * "//evil.com" / "/\evil.com" are treated as protocol-relative by browsers.
 * Accept only a single leading "/" followed by something other than "/" or "\".
 */
function safeNextPath(next: string | null): string {
  if (
    !next ||
    !next.startsWith("/") ||
    next.startsWith("//") ||
    next.startsWith("/\\") ||
    /[\u0000-\u001f\u007f]/.test(next)
  ) {
    return DEFAULT_NEXT;
  }
  return next;
}

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = safeNextPath(searchParams.get("next"));

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  return NextResponse.redirect(`${origin}/login?error=auth_failed`);
}
