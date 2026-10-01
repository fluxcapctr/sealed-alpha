/**
 * Environment checks for the Supabase clients.
 *
 * NOTE: `process.env.NEXT_PUBLIC_*` values are inlined by Next.js at build time
 * only when they are referenced as literal `process.env.NAME` expressions, so the
 * lookups below must stay literal (do not switch to `process.env[name]`).
 */

/** Returns `value`, or throws a clear error naming the missing variable. */
export function requireEnv(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. See dashboard/.env.example.`
    );
  }
  return value;
}

/** Public Supabase URL + anon key (safe for browser bundles). */
export function getSupabasePublicEnv(): { url: string; anonKey: string } {
  return {
    url: requireEnv(
      "NEXT_PUBLIC_SUPABASE_URL",
      process.env.NEXT_PUBLIC_SUPABASE_URL
    ),
    anonKey: requireEnv(
      "NEXT_PUBLIC_SUPABASE_ANON_KEY",
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    ),
  };
}
