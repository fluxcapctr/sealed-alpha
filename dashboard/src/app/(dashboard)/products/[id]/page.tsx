import { createClient } from "@/lib/supabase/server";
import { PriceChart } from "@/components/price-chart";
import { SignalBadge } from "@/components/signal-badge";
import { StatCard } from "@/components/stat-card";
import { formatPrice, formatPct } from "@/lib/signals";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ExternalLink, Calendar, Printer, RotateCcw } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { InfoTip } from "@/components/info-tip";
import type { ProductAnalytics, PriceSnapshot, Signal, SalesSnapshot } from "@/types/database";

export const revalidate = 300;

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: analyticsArr } = await supabase
    .from("product_analytics")
    .select("*")
    .eq("product_id", id)
    .returns<ProductAnalytics[]>();

  const product = analyticsArr?.[0];
  if (!product) return notFound();

  const { data: priceHistory } = await supabase
    .from("price_snapshots")
    .select("snapshot_date, market_price, low_price, total_listings")
    .eq("product_id", id)
    .order("snapshot_date")
    .returns<
      Pick<
        PriceSnapshot,
        "snapshot_date" | "market_price" | "low_price" | "total_listings"
      >[]
    >();

  const chartData = (priceHistory ?? []).map((p) => ({
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
    .returns<Signal[]>();

  const signal = signalArr?.[0] ?? null;

  // Fetch latest sales snapshot (90-day metrics from TCGPlayer)
  const { data: salesArr } = await supabase
    .from("sales_snapshots")
    .select("*")
    .eq("product_id", id)
    .order("snapshot_date", { ascending: false })
    .limit(1)
    .returns<SalesSnapshot[]>();

  const sales = salesArr?.[0] ?? null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{product.product_name}</h1>
          <div className="mt-1 flex items-center gap-3">
            <Link
              href={`/sets/${product.set_id}`}
              className="text-sm text-muted-foreground hover:underline"
            >
              {product.set_name}
            </Link>
            <Badge variant="outline" className="text-xs">
              {product.product_type}
            </Badge>
            {product.tcgplayer_url && (
              <a
                href={product.tcgplayer_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-blue-400 hover:underline"
              >
                TCGPlayer <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold font-mono tabular-nums">
            {formatPrice(product.current_price)}
          </p>
          <SignalBadge
            score={product.signal_score}
            recommendation={product.signal_recommendation}
            showScore
            size="md"
          />
        </div>
      </div>

      {/* Key Stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          title="7d Change"
          value={formatPct(product.price_change_7d_pct)}
        />
        <StatCard
          title="30d Change"
          value={formatPct(product.price_change_30d_pct)}
        />
        <StatCard
          title="All-Time Low"
          value={formatPrice(product.all_time_low)}
        />
        <StatCard
          title="All-Time High"
          value={formatPrice(product.all_time_high)}
        />
        <StatCard
          title="Qty Available"
          tooltip="Number of items for sale on TCGPlayer.com across all sellers."
          value={
            product.current_quantity != null
              ? product.current_quantity.toLocaleString()
              : "--"
          }
        />
        <StatCard
          title="Total Sold (90d)"
          tooltip="Total units sold on TCGPlayer in the last 90 days."
          value={
            sales?.total_sales != null
              ? sales.total_sales.toLocaleString()
              : "--"
          }
        />
        <StatCard
          title="Avg Daily Sold"
          tooltip="Average units sold per day on TCGPlayer over the last 90 days."
          value={
            sales?.sale_count_24h != null
              ? sales.sale_count_24h.toLocaleString()
              : "--"
          }
        />
        {sales?.min_sale_price != null && sales?.max_sale_price != null && (
          <StatCard
            title="Sale Range (90d)"
            tooltip="Lowest and highest sale prices on TCGPlayer in the last 90 days."
            value={`${formatPrice(sales.min_sale_price)} - ${formatPrice(sales.max_sale_price)}`}
          />
        )}
      </div>

      {/* Set Lifecycle Info */}
      <div className="flex flex-wrap gap-3">
        <div className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs">
          <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
          Released: {product.release_date ?? "Unknown"}
          {product.days_since_release !== null &&
            ` (${product.days_since_release}d ago)`}
        </div>
        <div className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs">
          <Printer className="h-3.5 w-3.5 text-muted-foreground" />
          {product.is_in_print ? "In Print" : "Out of Print"}
        </div>
        <div className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs">
          <RotateCcw className="h-3.5 w-3.5 text-muted-foreground" />
          {product.is_in_rotation ? "In Rotation" : "Rotated Out"}
        </div>
        {product.msrp && (
          <div className="rounded-md border border-border px-3 py-1.5 text-xs">
            MSRP: {formatPrice(product.msrp)}
          </div>
        )}
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

      {/* Moving Averages */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Moving Averages</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">7-Day MA</p>
              <p className="text-lg font-mono font-semibold">
                {formatPrice(product.ma_7d)}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">30-Day MA</p>
              <p className="text-lg font-mono font-semibold">
                {formatPrice(product.ma_30d)}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">90-Day MA</p>
              <p className="text-lg font-mono font-semibold">
                {formatPrice(product.ma_90d)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
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
  const color =
    val > 20
      ? "bg-green-500"
      : val < -20
        ? "bg-red-500"
        : "bg-amber-500";

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
        <span className="font-mono font-medium">
          {val > 0 ? "+" : ""}
          {val.toFixed(0)}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.max(2, pct)}%` }}
        />
      </div>
    </div>
  );
}
