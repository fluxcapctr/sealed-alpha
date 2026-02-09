import { createClient } from "@/lib/supabase/server";
import { StatCard } from "@/components/stat-card";
import { SignalBadge } from "@/components/signal-badge";
import { formatPrice, formatPct, getPctColor } from "@/lib/signals";
import { Package, Layers, TrendingUp, BarChart3 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Link from "next/link";
import type { ProductAnalytics } from "@/types/database";

export const revalidate = 300;

export default async function OverviewPage() {
  const supabase = await createClient();

  const { data: analytics } = await supabase
    .from("product_analytics")
    .select("*")
    .order("current_price", { ascending: false })
    .returns<ProductAnalytics[]>();

  const products = analytics ?? [];

  const totalProducts = products.length;
  const totalSets = new Set(products.map((p) => p.set_id)).size;
  const buySignals = products.filter(
    (p) =>
      p.signal_recommendation === "BUY" ||
      p.signal_recommendation === "STRONG_BUY"
  ).length;
  const sellSignals = products.filter(
    (p) =>
      p.signal_recommendation === "SELL" ||
      p.signal_recommendation === "STRONG_SELL"
  ).length;

  const movers = [...products]
    .filter((p) => p.price_change_7d_pct !== null)
    .filter((p) => (p.total_price_points ?? 0) >= 10)
    .filter((p) => {
      // Exclude stale-plateau products where historical prices are frozen
      if (p.price_7d_ago && p.price_30d_ago && p.price_90d_ago) {
        if (p.price_7d_ago === p.price_30d_ago && p.price_30d_ago === p.price_90d_ago) return false;
      }
      return true;
    })
    .filter((p) => Math.abs(p.price_change_7d_pct!) <= 200)
    .sort(
      (a, b) =>
        Math.abs(b.price_change_7d_pct!) - Math.abs(a.price_change_7d_pct!)
    )
    .slice(0, 10);

  const topBuys = [...products]
    .filter((p) => p.signal_score !== null && p.signal_score > 0)
    .sort((a, b) => (b.signal_score ?? 0) - (a.signal_score ?? 0))
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Overview</h1>
        <p className="text-sm text-muted-foreground">
          Pokemon TCG sealed product investment tracker
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Products Tracked"
          value={totalProducts.toString()}
          icon={Package}
        />
        <StatCard
          title="Sets Tracked"
          value={totalSets.toString()}
          icon={Layers}
        />
        <StatCard
          title="Buy Signals"
          value={buySignals.toString()}
          icon={TrendingUp}
          trend={
            buySignals > 0
              ? { value: `${buySignals} opportunities`, positive: true }
              : undefined
          }
        />
        <StatCard
          title="Sell Signals"
          value={sellSignals.toString()}
          icon={BarChart3}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Top Movers (7d)</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="text-right">7d Change</TableHead>
                  <TableHead className="text-right">Signal</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {movers.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={4}
                      className="text-center text-muted-foreground"
                    >
                      No price data yet. Run the scraper to start tracking.
                    </TableCell>
                  </TableRow>
                ) : (
                  movers.map((p) => (
                    <TableRow key={p.product_id}>
                      <TableCell>
                        <Link
                          href={`/products/${p.product_id}`}
                          className="font-medium hover:underline"
                        >
                          {p.product_name}
                        </Link>
                        <span className="block text-xs text-muted-foreground">
                          {p.set_name}
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatPrice(p.current_price)}
                      </TableCell>
                      <TableCell
                        className={`text-right font-mono ${getPctColor(p.price_change_7d_pct)}`}
                      >
                        {formatPct(p.price_change_7d_pct)}
                      </TableCell>
                      <TableCell className="text-right">
                        <SignalBadge
                          score={p.signal_score}
                          recommendation={p.signal_recommendation}
                        />
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Top Buy Signals</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {topBuys.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={3}
                      className="text-center text-muted-foreground"
                    >
                      No buy signals yet
                    </TableCell>
                  </TableRow>
                ) : (
                  topBuys.map((p) => (
                    <TableRow key={p.product_id}>
                      <TableCell>
                        <Link
                          href={`/products/${p.product_id}`}
                          className="font-medium hover:underline"
                        >
                          {p.product_name}
                        </Link>
                        <span className="block text-xs text-muted-foreground">
                          {p.set_name} &middot; {p.product_type}
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatPrice(p.current_price)}
                      </TableCell>
                      <TableCell className="text-right">
                        <SignalBadge
                          score={p.signal_score}
                          recommendation={p.signal_recommendation}
                          showScore
                        />
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
