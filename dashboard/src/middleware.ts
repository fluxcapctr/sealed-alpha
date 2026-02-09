import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Public routes that don't need auth
  const publicPaths = [
    "/",
    "/login",
    "/signup",
    "/privacy",
    "/terms",
    "/auth/callback",
  ];
  const isPublic =
    publicPaths.some((p) => pathname === p) ||
    pathname.startsWith("/api/") ||
    pathname.startsWith("/_next/") ||
    /\.(ico|png|jpg|svg|css|js|txt|xml)$/.test(pathname);

  // Create Supabase client with cookie forwarding
  let response = NextResponse.next({ request });
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => {
            request.cookies.set(name, value);
          });
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) => {
            response.cookies.set(name, value, options);
          });
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!isPublic && !user) {
    // Not authenticated — redirect to landing page
    return NextResponse.redirect(new URL("/", request.url));
  }

  if (
    user &&
    (pathname === "/" || pathname === "/login" || pathname === "/signup")
  ) {
    // Already authenticated — redirect to dashboard
    return NextResponse.redirect(new URL("/overview", request.url));
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
