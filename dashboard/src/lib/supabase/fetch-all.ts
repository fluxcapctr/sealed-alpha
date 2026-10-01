import type { PostgrestError } from "@supabase/supabase-js";

/** Safety valve against a runaway loop (1000 pages = 1M rows at the default size). */
const MAX_PAGES = 1000;

/**
 * PostgREST (Supabase) caps every response at the project's "max rows" setting,
 * 1000 by default, and does so SILENTLY: an unpaginated `select()` over a larger
 * table just returns the first 1000 rows with no error. `fetchAll` pages through
 * a query with `.range()` until a short page comes back and returns every row.
 *
 * `build` must return a FRESH query for the given inclusive row range (Supabase
 * query builders are single-use), e.g.
 *
 *   const rows = await fetchAll<ProductAnalytics>((from, to) =>
 *     supabase
 *       .from("product_analytics")
 *       .select("*")
 *       .order("current_price", { ascending: false })
 *       .order("product_id") // unique tiebreaker, see below
 *       .range(from, to)
 *       .returns<ProductAnalytics[]>()
 *   );
 *
 * Callers MUST supply a deterministic `.order()` that ends in a unique column
 * (id / product_id). Without a total order, Postgres may return ties in a
 * different order on each request, so rows can be skipped or duplicated across
 * page boundaries. If the query sorts ascending and you only want the newest
 * rows, do not rely on a limit: fetch everything, or sort descending.
 *
 * `pageSize` must not exceed the project's configured max rows (default 1000);
 * if the server returns fewer rows than `pageSize` for a full page, pagination
 * would stop early.
 *
 * Throws on any Supabase error (so a database failure surfaces as a Next.js
 * error rather than rendering an empty list), and if the result set is
 * implausibly large (guard against a runaway loop).
 */
export async function fetchAll<T>(
  build: (
    from: number,
    to: number
  ) => PromiseLike<{ data: T[] | null; error: PostgrestError | null }>,
  pageSize = 1000
): Promise<T[]> {
  if (!Number.isInteger(pageSize) || pageSize < 1) {
    throw new Error(`fetchAll: invalid pageSize ${pageSize}`);
  }

  const rows: T[] = [];

  for (let page = 0; page < MAX_PAGES; page++) {
    const from = page * pageSize;
    const { data, error } = await build(from, from + pageSize - 1);

    if (error) {
      // postgrest-js hands back a plain object here (not an Error instance), so
      // wrap it to get a stack trace and a readable message in Next's error logs.
      throw new Error(
        `Supabase query failed${error.code ? ` (${error.code})` : ""}: ${error.message}`,
        { cause: error }
      );
    }

    const batch = data ?? [];
    for (const row of batch) rows.push(row);

    if (batch.length < pageSize) return rows;
  }

  throw new Error(
    `fetchAll: exceeded ${MAX_PAGES} pages of ${pageSize} rows; aborting`
  );
}
