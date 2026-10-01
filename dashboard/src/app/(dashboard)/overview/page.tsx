import { createClient } from "@/lib/supabase/server";
import { SignalMeter } from "@/components/signal-meter";
import { Sparkline } from "@/components/sparkline";
import { ProductHoverImage } from "@/components/product-hover-image";
import { formatPrice, formatPct, getPctColor } from "@/lib/signals";
import { buildIndex, getAsOf, getSeries, typeCode } from "@/lib/market";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { ProductAnalytics } from "@/types/database";

export const revalidate = 300;

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : null;
};

export default async function OverviewPage() {
  const supabase = await createClient();
  const { data: analytics } = await supabase
    .from("product_analytics")
    .select("*")
    .order("current_price", { ascending: false })
    .returns<ProductAnalytics[]>();
  const products = analytics ?? [];
  const asOf = getAsOf(products);

  const isBuy = (p: ProductAnalytics) => p.signal_recommendation === "BUY" || p.signal_recommendation === "STRONG_BUY";
  const isSell = (p: ProductAnalytics) => p.signal_recommendation === "SELL" || p.signal_recommendation === "STRONG_SELL";
  const buys = products.filter(isBuy).length;
  const sells = products.filter(isSell).length;
  const nearLows = products
    .filter((p) => p.current_price && p.all_time_low && p.all_time_low > 0 && (p.total_price_points ?? 0) >= 30)
    .map((p) => ({ p, gap: p.current_price! / p.all_time_low! - 1 }))
    .filter((x) => x.gap <= 0.05)
    .sort((a, b) => a.gap - b.gap);

  const movers = products
    .filter((p) => p.price_change_7d_pct !== null && (p.total_price_points ?? 0) >= 10 && (p.current_price ?? 0) >= 20)
    .filter((p) => !(p.price_7d_ago && p.price_30d_ago && p.price_90d_ago && p.price_7d_ago === p.price_30d_ago && p.price_30d_ago === p.price_90d_ago))
    .filter((p) => Math.abs(p.price_change_7d_pct!) <= 200)
    .sort((a, b) => Math.abs(b.price_change_7d_pct!) - Math.abs(a.price_change_7d_pct!))
    .slice(0, 10);
  const topBuys = products.filter((p) => (p.signal_score ?? 0) > 0).sort((a, b) => (b.signal_score ?? 0) - (a.signal_score ?? 0)).slice(0, 6);

  // Category indices: equal-weight, rebased to 100 at the start of a 90-day window.
  const idxFor = async (type: string) => {
    const ids = products.filter((p) => p.product_type === type && (p.total_price_points ?? 0) >= 60).map((p) => p.product_id);
    return buildIndex(asOf ? await getSeries(supabase, ids, asOf, 90) : new Map());
  };
  const [bbIdx, etbIdx, moverSeries] = await Promise.all([
    idxFor("Booster Box"),
    idxFor("Elite Trainer Box"),
    asOf ? getSeries(supabase, movers.map((p) => p.product_id), asOf, 30) : Promise.resolve(new Map()),
  ]);
  const idxStat = (idx: { value: number }[]) => {
    const now = idx[idx.length - 1]?.value ?? null;
    const m30 = idx[idx.length - 31]?.value ?? idx[0]?.value ?? null;
    return { now, pct: now && m30 ? (now / m30 - 1) * 100 : null };
  };
  const bb = idxStat(bbIdx);
  const etb = idxStat(etbIdx);
  const med30 = median(products.map((p) => p.price_change_30d_pct).filter((x): x is number => x != null));

  const kpis = [
    { label: "Booster box index", value: bb.now?.toFixed(1) ?? "--", pct: bb.pct, spark: bbIdx.map((x) => x.value), note: "90d, base 100" },
    { label: "ETB index", value: etb.now?.toFixed(1) ?? "--", pct: etb.pct, spark: etbIdx.map((x) => x.value), note: "90d, base 100" },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="font-pixel text-2xl font-semibold tracking-wide">Market overview</h1>
          <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.1em] text-muted-foreground">
            {products.length} sealed products &middot; price data as of {asOf ?? "unknown"}
          </p>
        </div>
      </div>

      {/* KPI strip: one panel, hairline dividers */}
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-md border bg-border lg:grid-cols-4">
        {kpis.map((k) => (
          <div key={k.label} className="flex items-end justify-between gap-3 bg-card p-4">
            <div className="min-w-0">
              <p className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground">{k.label}</p>
              <p className="mt-1.5 text-2xl font-semibold tabular-nums">{k.value}</p>
              <p className={cn("font-mono text-xs tabular-nums", getPctColor(k.pct))}>
                {k.pct != null ? `${k.pct >= 0 ? "▲" : "▼"} ${formatPct(Math.abs(k.pct)).replace("+", "")} 30d` : "--"}
              </p>
            </div>
            <Sparkline values={k.spark} width={84} height={34} className="hidden sm:block" />
          </div>
        ))}
        <div className="bg-card p-4">
          <p className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground">Verdicts</p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums">
            <span>{buys}</span>
            <span className="mx-2 text-base font-normal text-muted-foreground">buy</span>
            <span>{sells}</span>
            <span className="ml-2 text-base font-normal text-muted-foreground">sell</span>
          </p>
          <p className="font-mono text-xs text-muted-foreground">{products.length - buys - sells} hold</p>
        </div>
        <div className="bg-card p-4">
          <p className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground">Near all-time low</p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums">{nearLows.length}</p>
          <p className="font-mono text-xs text-muted-foreground">median 30d {med30 != null ? formatPct(med30) : "--"}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.9fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Top movers &middot; 7d</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="text-right">7d</TableHead>
                  <TableHead className="hidden md:table-cell">30d trend</TableHead>
                  <TableHead className="hidden md:table-cell">Verdict</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {movers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground">No price data yet.</TableCell>
                  </TableRow>
                ) : (
                  movers.map((p) => (
                    <TableRow key={p.product_id}>
                      <TableCell className="whitespace-normal">
                        <ProductHoverImage
                          productId={p.product_id}
                          tcgplayerProductId={p.tcgplayer_product_id}
                          imageUrl={p.product_image}
                          name={p.product_name}
                          subtitle={`${p.set_code ?? p.set_name} · ${typeCode(p.product_type)}`}
                          size={40}
                        />
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{formatPrice(p.current_price)}</TableCell>
                      <TableCell className={cn("text-right font-mono text-[13px] tabular-nums", getPctColor(p.price_change_7d_pct))}>{formatPct(p.price_change_7d_pct)}</TableCell>
                      <TableCell className="hidden md:table-cell"><Sparkline values={(moverSeries.get(p.product_id) ?? []).map((x: { value: number }) => x.value)} /></TableCell>
                      <TableCell className="hidden md:table-cell"><SignalMeter score={p.signal_score} recommendation={p.signal_recommendation} /></TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>Strongest buy signals</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {topBuys.length === 0 ? (
                <p className="text-sm text-muted-foreground">No buy signals right now.</p>
              ) : (
                topBuys.map((p) => (
                  <div key={p.product_id} className="flex items-center justify-between gap-3">
                    <ProductHoverImage productId={p.product_id} tcgplayerProductId={p.tcgplayer_product_id} imageUrl={p.product_image} name={p.product_name} subtitle={`${p.set_code ?? ""} · ${formatPrice(p.current_price)}`} size={36} />
                    <SignalMeter score={p.signal_score} recommendation={p.signal_recommendation} showLabel="score" block={4} />
                  </div>
                ))
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Closest to all-time low</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {nearLows.slice(0, 5).map(({ p, gap }) => (
                <div key={p.product_id} className="flex items-center justify-between gap-3">
                  <ProductHoverImage productId={p.product_id} tcgplayerProductId={p.tcgplayer_product_id} imageUrl={p.product_image} name={p.product_name} subtitle={`${p.set_code ?? ""} · low ${formatPrice(p.all_time_low)}`} size={36} />
                  <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">+{(gap * 100).toFixed(1)}%</span>
                </div>
              ))}
              {nearLows.length === 0 && <p className="text-sm text-muted-foreground">Nothing within 5% of its low.</p>}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
