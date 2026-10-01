import type { createClient } from "@/lib/supabase/server";
import type { ProductAnalytics } from "@/types/database";

type Db = Awaited<ReturnType<typeof createClient>>;

/** Short product-type codes for tight spaces such as the ticker. */
const TYPE_CODES: Record<string, string> = {
  "Booster Box": "BB",
  "Booster Box Case": "BB CASE",
  "Elite Trainer Box": "ETB",
  "Pokemon Center Elite Trainer Box": "PC ETB",
  "Booster Bundle": "BNDL",
  "Booster Pack": "PACK",
  "Collection Box": "COLL",
};
export const typeCode = (t: string) => TYPE_CODES[t] ?? t.toUpperCase();

export type SeriesPoint = { date: string; value: number };

/** The most recent price date in the data. Shown as "as of" so a stalled pipeline can never look live. */
export function getAsOf(rows: Pick<ProductAnalytics, "last_price_date">[]): string | null {
  let best: string | null = null;
  for (const r of rows) if (r.last_price_date && (!best || r.last_price_date > best)) best = r.last_price_date;
  return best;
}

function daysBefore(iso: string, days: number) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

/**
 * Price series for many products. Queries are chunked so each stays under PostgREST's 1000-row default cap
 * (ids per chunk x days <= 900). Returns product_id -> ordered series.
 */
export async function getSeries(supabase: Db, ids: string[], asOf: string, days: number): Promise<Map<string, SeriesPoint[]>> {
  const out = new Map<string, SeriesPoint[]>();
  if (ids.length === 0) return out;
  const from = daysBefore(asOf, days);
  const per = Math.max(1, Math.floor(900 / (days + 1)));
  const chunks: string[][] = [];
  for (let i = 0; i < ids.length; i += per) chunks.push(ids.slice(i, i + per));
  const results = await Promise.all(
    chunks.map((chunk) =>
      supabase
        .from("price_snapshots")
        .select("product_id, snapshot_date, market_price")
        .in("product_id", chunk)
        .gte("snapshot_date", from)
        .order("snapshot_date")
    )
  );
  for (const { data } of results) {
    for (const r of (data ?? []) as { product_id: string; snapshot_date: string; market_price: number | null }[]) {
      if (r.market_price == null) continue;
      const arr = out.get(r.product_id) ?? [];
      arr.push({ date: r.snapshot_date, value: r.market_price });
      out.set(r.product_id, arr);
    }
  }
  return out;
}

/** Equal-weight index: every product rebased to 100 at the start of the window, then averaged per date. */
export function buildIndex(series: Map<string, SeriesPoint[]>): SeriesPoint[] {
  const byDate = new Map<string, number[]>();
  for (const pts of series.values()) {
    const base = pts.find((p) => p.value > 0)?.value;
    if (!base) continue;
    for (const p of pts) byDate.set(p.date, [...(byDate.get(p.date) ?? []), (p.value / base) * 100]);
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([date, v]) => ({ date, value: v.reduce((x, y) => x + y, 0) / v.length }));
}
