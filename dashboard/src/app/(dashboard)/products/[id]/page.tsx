import { createClient } from "@/lib/supabase/server";
import { fetchAll } from "@/lib/supabase/fetch-all";
import { isUuid } from "@/lib/uuid";
import { PriceChart } from "@/components/price-chart";
import { SignalMeter } from "@/components/signal-meter";
import { WatchButton } from "@/components/watch-button";
import { formatPrice, formatPct, getPctColor } from "@/lib/signals";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ProductThumb } from "@/components/product-thumb";
import { InfoTip } from "@/components/info-tip";
import { Breadcrumb, languageCrumb } from "@/components/breadcrumb";
import type { ProductAnalytics, PriceSnapshot, Signal, SalesSnapshot } from "@/types/database";

export const revalidate = 300;

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  // Postgres errors (rather than returning no rows) on a malformed UUID.
  if (!isUuid(id)) return notFound();

  const { data: analyticsArr } = await supabase
    .from("product_analytics")
    .select("*")
    .eq("product_id", id)
    .returns<ProductAnalytics[]>()
    .throwOnError();

  const product = analyticsArr?.[0];
  if (!product) return notFound();

  // Full history, oldest first. Must be paginated: a plain limit would truncate
  // the NEWEST rows (ascending order) once a product exceeds 1000 snapshots.
  const priceHistory = await fetchAll((from, to) =>
    supabase
      .from("price_snapshots")
      .select("snapshot_date, market_price, low_price, total_listings")
      .eq("product_id", id)
      .order("snapshot_date")
      .order("id") // unique tiebreaker so pages never skip/duplicate rows
      .range(from, to)
      .returns<
        Pick<
          PriceSnapshot,
          "snapshot_date" | "market_price" | "low_price" | "total_listings"
        >[]
      >()
  );

  const chartData = priceHistory.map((p) => ({
    date: p.snapshot_date,
    market_price: p.market_price,
    low_price: p.low_price,
    total_listings: p.total_listings,
  }));

  const { data: signalArr } = await supabase
    .from("signals")
    .select("*")
    .eq("product_id", id)
    .order("signal_date", { ascending: false })
    .limit(1)
    .returns<Signal[]>()
    .throwOnError();

  const signal = signalArr?.[0] ?? null;

  // Fetch latest sales snapshot (90-day metrics from TCGPlayer)
  const { data: salesArr } = await supabase
    .from("sales_snapshots")
    .select("*")
    .eq("product_id", id)
    .order("snapshot_date", { ascending: false })
    .limit(1)
    .returns<SalesSnapshot[]>()
    .throwOnError();

  const sales = salesArr?.[0] ?? null;

  // Why the verdict is what it is: the strongest positive and negative components of the composite score.
  const parts = signal
    ? [
        ["Price vs MA", signal.price_vs_ma_score],
        ["Momentum", signal.momentum_score],
        ["Volatility", signal.volatility_score],
        ["Listings trend", signal.listings_score],
        ["Sales velocity", signal.sales_velocity_score],
        ["Set lifecycle", signal.lifecycle_score],
      ]
        .filter((x): x is [string, number] => x[1] != null)
        .sort((a, b) => b[1] - a[1])
    : [];
  const lifts = parts.filter(([, v]) => v >= 20).slice(0, 2);
  const drags = parts.filter(([, v]) => v <= -20).slice(-2).reverse();

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          languageCrumb(product.language),
          { label: product.set_name, href: `/sets/${product.set_id}` },
          { label: product.product_name },
        ]}
      />

      {/* Header */}
      <div className="grid gap-5 sm:grid-cols-[auto_minmax(0,1fr)] lg:grid-cols-[auto_minmax(0,1fr)_auto]">
        <div className="flex h-44 w-44 items-center justify-center rounded-md border bg-card dot-grid">
          <ProductThumb
            tcgplayerProductId={product.tcgplayer_product_id}
            imageUrl={product.product_image}
            name={product.product_name}
            size={150}
            className="max-h-[150px] max-w-[150px]"
          />
        </div>
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] uppercase tracking-[0.1em] text-muted-foreground">
            <Link href={`/sets/${product.set_id}`} className="text-foreground hover:text-primary">
              {product.set_code ?? product.set_name}
            </Link>
            <span>{product.product_type}</span>
            <span>{product.is_in_print ? "In print" : "Out of print"}</span>
            <span>{product.is_in_rotation ? "In rotation" : "Rotated out"}</span>
            {product.tcgplayer_url && (
              <a href={product.tcgplayer_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
                TCGPlayer <ExternalLink className="size-3" />
              </a>
            )}
          </div>
          <h1 className="text-2xl font-semibold leading-tight tracking-tight">{product.product_name}</h1>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <SignalMeter score={product.signal_score} recommendation={product.signal_recommendation} block={7} />
            <span className="font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
              {product.release_date ?? "Release unknown"}
              {product.days_since_release !== null && ` \u00B7 ${product.days_since_release}d old`}
              {product.msrp ? ` \u00B7 MSRP ${formatPrice(product.msrp)}` : ""}
            </span>
          </div>
          {(lifts.length > 0 || drags.length > 0) && (
            <p className="max-w-xl font-mono text-[11.5px] leading-relaxed text-muted-foreground">
              {lifts.length > 0 && (
                <>
                  <span className="text-foreground">Lifting</span> {lifts.map(([n, v]) => `${n} +${Math.round(v)}`).join(", ")}.{" "}
                </>
              )}
              {drags.length > 0 && (
                <>
                  <span className="text-foreground">Dragging</span> {drags.map(([n, v]) => `${n} ${Math.round(v)}`).join(", ")}.
                </>
              )}
            </p>
          )}
        </div>
        <div className="flex flex-col items-start gap-3 sm:col-span-2 sm:flex-row sm:items-start sm:justify-between lg:col-span-1 lg:flex-col lg:items-end">
          <div className="lg:text-right">
            <p className="text-4xl font-semibold tracking-tight tabular-nums">{formatPrice(product.current_price)}</p>
            <p className="mt-1 font-mono text-xs tabular-nums">
              <span className={getPctColor(product.price_change_7d_pct)}>{formatPct(product.price_change_7d_pct)} 7d</span>
              <span className="mx-2 text-muted-foreground">/</span>
              <span className={getPctColor(product.price_change_30d_pct)}>{formatPct(product.price_change_30d_pct)} 30d</span>
            </p>
          </div>
          <WatchButton productName={product.product_name} />
        </div>
      </div>

      {/* Key stats: one panel, hairline grid */}
      <div className="grid grid-cols-2 divide-x divide-y divide-border overflow-hidden rounded-md border bg-card lg:grid-cols-4 [&>*:nth-child(2n+1)]:border-l-0 lg:[&>*:nth-child(2n+1)]:border-l [&>*:nth-child(4n+1)]:lg:border-l-0">
        {[
          { t: "All-time low", v: formatPrice(product.all_time_low) },
          { t: "All-time high", v: formatPrice(product.all_time_high) },
          { t: "Qty available", v: product.current_quantity != null ? product.current_quantity.toLocaleString() : "--", tip: "Number of items for sale on TCGPlayer.com across all sellers." },
          { t: "Sold, 90d", v: sales?.total_sales != null ? sales.total_sales.toLocaleString() : "--", tip: "Total units sold on TCGPlayer in the last 90 days." },
          { t: "Avg daily sold", v: sales?.sale_count_24h != null ? sales.sale_count_24h.toLocaleString() : "--", tip: "Average units sold per day on TCGPlayer over the last 90 days." },
          { t: "Sale range, 90d", v: sales?.min_sale_price != null && sales?.max_sale_price != null ? `${formatPrice(sales.min_sale_price)} \u2013 ${formatPrice(sales.max_sale_price)}` : "--", tip: "Lowest and highest sale prices on TCGPlayer in the last 90 days." },
          { t: "7d MA", v: formatPrice(product.ma_7d) },
          { t: "30d MA", v: formatPrice(product.ma_30d) },
        ].map((c) => (
          <div key={c.t} className="px-4 py-3">
            <div className="flex h-4 items-center">
              {c.tip ? (
                <InfoTip label={<span className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground">{c.t}</span>} side="bottom">{c.tip}</InfoTip>
              ) : (
                <p className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground">{c.t}</p>
              )}
            </div>
            <p className="mt-1 text-lg font-semibold tabular-nums">{c.v}</p>
          </div>
        ))}
      </div>

      {/* Price Chart */}
      <PriceChart data={chartData} />

      {/* Signal Breakdown */}
      {signal && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              <InfoTip label="Signal Breakdown" side="right">
                A composite score from -100 to +100 that combines 6 market indicators.
                Positive scores suggest buying opportunities; negative scores suggest
                the product is overvalued. The recommendation (Strong Buy &rarr; Strong Sell)
                is derived from the composite score.
              </InfoTip>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
              <SignalComponent
                label="Price vs MA"
                score={signal.price_vs_ma_score}
                weight="35%"
                tooltip="Compares current price to 30-day and 90-day moving averages. Positive = price below average (undervalued). Negative = price above average (overvalued)."
              />
              <SignalComponent
                label="Momentum"
                score={signal.momentum_score}
                weight="20%"
                tooltip="Measures the 30-day price trend. For sealed products that appreciate over time, falling prices (positive score) signal a buying window. Rising prices (negative score) may mean you missed the dip."
              />
              <SignalComponent
                label="Volatility"
                score={signal.volatility_score}
                weight="10%"
                tooltip="Measures price stability. Positive = steady, predictable prices (lower risk). Negative = wild price swings (higher risk)."
              />
              <SignalComponent
                label="Listings Trend"
                score={signal.listings_score}
                weight="15%"
                tooltip="Tracks seller listing count on TCGPlayer. Positive = fewer listings (supply drying up). Negative = more listings (supply flooding in)."
              />
              <SignalComponent
                label="Sales Velocity"
                score={signal.sales_velocity_score}
                weight="10%"
                tooltip="Tracks how fast available units are being purchased. Positive = units selling quickly (strong demand). Negative = supply growing (weak demand)."
              />
              <SignalComponent
                label="Set Lifecycle"
                score={signal.lifecycle_score}
                weight="10%"
                tooltip="Accounts for print status and set age. Out-of-print and older sets score higher (scarcity). Newly released sets score lower (supply still flooding market)."
              />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function SignalComponent({
  label,
  score,
  weight,
  tooltip,
}: {
  label: string;
  score: number | null;
  weight: string;
  tooltip?: React.ReactNode;
}) {
  const val = score ?? 0;
  const pct = ((val + 100) / 200) * 100;
  // Colourless like every verdict: strong contributions are light, weak ones grey; the side it fills shows the sign.
  const color = Math.abs(val) > 20 ? "bg-foreground/85" : "bg-muted-foreground";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        {tooltip ? (
          <InfoTip
            label={<span className="text-muted-foreground">{label} <span className="opacity-50">({weight})</span></span>}
            side="top"
          >
            {tooltip}
          </InfoTip>
        ) : (
          <span className="text-muted-foreground">
            {label} <span className="opacity-50">({weight})</span>
          </span>
        )}
        <span className="tabular-nums font-medium">
          {val > 0 ? "+" : ""}
          {val.toFixed(0)}
        </span>
      </div>
      <div className="relative h-1.5 w-full bg-muted">
        <div className="absolute inset-y-0 left-1/2 w-px bg-foreground/30" />
        <div
          className={`absolute inset-y-0 ${color}`}
          style={val >= 0 ? { left: "50%", width: `${Math.max(1, val / 2)}%` } : { right: "50%", width: `${Math.max(1, Math.abs(val) / 2)}%` }}
        />
      </div>
    </div>
  );
}
