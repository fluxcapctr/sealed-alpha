const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * True if `value` looks like a UUID. Use before passing user-controlled strings
 * (URL params, query strings) to a UUID column: Postgres rejects malformed values
 * with an error (22P02) instead of returning no rows.
 */
export function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_REGEX.test(value);
}
