import { createClient } from "@/lib/supabase/server";
import { SignalBadge } from "@/components/signal-badge";
import { formatPrice, formatPct, getPctColor } from "@/lib/signals";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ProductHoverImage } from "@/components/product-hover-image";
import type { ProductAnalytics } from "@/types/database";

export const revalidate = 300;

export default async function SignalsPage() {
  const supabase = await createClient();

  const { data: analytics } = await supabase
    .from("product_analytics")
    .select("*")
    .not("signal_score", "is", null)
    .order("signal_score", { ascending: false })
    .returns<ProductAnalytics[]>();

  const products = analytics ?? [];

  const buys = products.filter(
    (p) =>
      p.signal_recommendation === "BUY" ||
      p.signal_recommendation === "STRONG_BUY"
  );
  const sells = products.filter(
    (p) =>
      p.signal_recommendation === "SELL" ||
      p.signal_recommendation === "STRONG_SELL"
  );
  const holds = products.filter(
    (p) => p.signal_recommendation === "HOLD"
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Signals</h1>
        <p className="text-sm text-muted-foreground">
          Buy/sell recommendations ranked by signal strength
        </p>
      </div>

      {/* Signal Distribution */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-green-400">{buys.length}</p>
            <p className="text-xs text-muted-foreground">Buy Signals</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-amber-400">{holds.length}</p>
            <p className="text-xs text-muted-foreground">Hold</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-red-400">{sells.length}</p>
            <p className="text-xs text-muted-foreground">Sell Signals</p>
          </CardContent>
        </Card>
      </div>

      {/* All Signals Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">
            All Signals ({products.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>Set</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">30d Change</TableHead>
                <TableHead className="text-right">Qty</TableHead>
                <TableHead className="text-right">Score</TableHead>
                <TableHead className="text-right">Signal</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={8}
                    className="text-center text-muted-foreground"
                  >
                    No signals computed yet. Run the signal engine after
                    collecting price data.
                  </TableCell>
                </TableRow>
              ) : (
                products.map((p) => (
                  <TableRow key={p.product_id}>
                    <TableCell>
                      <ProductHoverImage
                        productId={p.product_id}
                        tcgplayerProductId={p.tcgplayer_product_id}
                        name={p.product_name}
                      />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {p.set_name}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {p.product_type}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatPrice(p.current_price)}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono text-sm ${getPctColor(p.price_change_30d_pct)}`}
                    >
                      {formatPct(p.price_change_30d_pct)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {p.current_quantity != null
                        ? p.current_quantity.toLocaleString()
                        : "--"}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {p.signal_score !== null
                        ? `${p.signal_score > 0 ? "+" : ""}${p.signal_score}`
                        : "--"}
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
    </div>
  );
}
