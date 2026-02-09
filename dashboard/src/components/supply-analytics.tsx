"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatPrice } from "@/lib/signals";

interface SupplyProduct {
  product_id: string;
  product_name: string;
  product_type: string;
  set_name: string;
  current_price: number | null;
  current_quantity: number | null;
  current_listings: number | null;
  quantity_7d_ago: number | null;
  quantity_30d_ago: number | null;
  quantity_90d_ago: number | null;
}

interface SupplyAnalyticsProps {
  products: SupplyProduct[];
}

type SortField = "depletion" | "quantity" | "sellout" | "name";

interface DepletionRow {
  product: SupplyProduct;
  depletionPerDay: number | null;
  daysUntilSellout: number | null;
  quantityChange: number | null;
  changePeriod: string;
}

function computeDepletion(p: SupplyProduct): DepletionRow {
  // Use the longest available period for best accuracy
  let quantityChange: number | null = null;
  let days = 0;
  let changePeriod = "";

  if (p.current_quantity !== null && p.quantity_90d_ago !== null) {
    quantityChange = p.quantity_90d_ago - p.current_quantity;
    days = 90;
    changePeriod = "90d";
  } else if (p.current_quantity !== null && p.quantity_30d_ago !== null) {
    quantityChange = p.quantity_30d_ago - p.current_quantity;
    days = 30;
    changePeriod = "30d";
  } else if (p.current_quantity !== null && p.quantity_7d_ago !== null) {
    quantityChange = p.quantity_7d_ago - p.current_quantity;
    days = 7;
    changePeriod = "7d";
  }

  const depletionPerDay =
    quantityChange !== null && days > 0 ? quantityChange / days : null;

  const daysUntilSellout =
    depletionPerDay !== null && depletionPerDay > 0 && p.current_quantity !== null
      ? Math.round(p.current_quantity / depletionPerDay)
      : null;

  return {
    product: p,
    depletionPerDay,
    daysUntilSellout,
    quantityChange,
    changePeriod,
  };
}

export function SupplyAnalytics({ products }: SupplyAnalyticsProps) {
  const [sortBy, setSortBy] = useState<SortField>("depletion");

  const rows = useMemo(() => {
    const computed = products
      .filter((p) => p.current_quantity !== null && p.current_quantity > 0)
      .map(computeDepletion);

    return computed.sort((a, b) => {
      switch (sortBy) {
        case "depletion":
          // Highest depletion first (most units leaving per day)
          if (a.depletionPerDay === null && b.depletionPerDay === null) return 0;
          if (a.depletionPerDay === null) return 1;
          if (b.depletionPerDay === null) return -1;
          return b.depletionPerDay - a.depletionPerDay;
        case "sellout":
          // Lowest days first (selling out soonest)
          if (a.daysUntilSellout === null && b.daysUntilSellout === null) return 0;
          if (a.daysUntilSellout === null) return 1;
          if (b.daysUntilSellout === null) return -1;
          return a.daysUntilSellout - b.daysUntilSellout;
        case "quantity":
          return (a.product.current_quantity ?? 0) - (b.product.current_quantity ?? 0);
        case "name":
          return a.product.product_name.localeCompare(b.product.product_name);
        default:
          return 0;
      }
    });
  }, [products, sortBy]);

  // Summary stats
  const totalUnits = products.reduce(
    (sum, p) => sum + (p.current_quantity ?? 0),
    0
  );
  const depleting = rows.filter(
    (r) => r.depletionPerDay !== null && r.depletionPerDay > 0
  );
  const criticalCount = rows.filter(
    (r) => r.daysUntilSellout !== null && r.daysUntilSellout <= 90
  ).length;
  const hasHistoricalData = rows.some((r) => r.depletionPerDay !== null);

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Total Units Tracked
            </p>
            <p className="text-2xl font-bold tabular-nums">
              {totalUnits.toLocaleString()}
            </p>
            <p className="text-xs text-muted-foreground">
              across {rows.length} products
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Depleting Products
            </p>
            <p className="text-2xl font-bold tabular-nums text-amber-400">
              {hasHistoricalData ? depleting.length : "--"}
            </p>
            <p className="text-xs text-muted-foreground">
              {hasHistoricalData
                ? "supply actively declining"
                : "needs multi-day data"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Critical (&lt;90 days)
            </p>
            <p className="text-2xl font-bold tabular-nums text-red-400">
              {hasHistoricalData ? criticalCount : "--"}
            </p>
            <p className="text-xs text-muted-foreground">
              {hasHistoricalData
                ? "estimated to sell out within 90 days"
                : "needs multi-day data"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Depletion Rankings Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">
            Supply Depletion Rankings
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!hasHistoricalData && (
            <div className="px-4 py-2 text-xs text-amber-400 bg-amber-500/10 border-b border-border">
              Depletion rates require multiple days of quantity data. Keep running the daily scraper — estimates will appear automatically.
            </div>
          )}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>Set</TableHead>
                <TableHead
                  className="text-right cursor-pointer hover:text-foreground"
                  onClick={() => setSortBy("quantity")}
                >
                  Qty Available{sortBy === "quantity" ? " ↑" : ""}
                </TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead
                  className="text-right cursor-pointer hover:text-foreground"
                  onClick={() => setSortBy("depletion")}
                >
                  Depletion/Day{sortBy === "depletion" ? " ↓" : ""}
                </TableHead>
                <TableHead
                  className="text-right cursor-pointer hover:text-foreground"
                  onClick={() => setSortBy("sellout")}
                >
                  Est. Sell-out{sortBy === "sellout" ? " ↑" : ""}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center text-muted-foreground"
                  >
                    No products with quantity data found.
                  </TableCell>
                </TableRow>
              ) : (
                rows.slice(0, 30).map((row) => {
                  const urgencyColor =
                    row.daysUntilSellout !== null
                      ? row.daysUntilSellout <= 30
                        ? "text-red-400"
                        : row.daysUntilSellout <= 90
                          ? "text-amber-400"
                          : "text-muted-foreground"
                      : "text-muted-foreground";

                  return (
                    <TableRow key={row.product.product_id}>
                      <TableCell className="font-medium text-sm max-w-[200px] truncate">
                        {row.product.product_name}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-[120px] truncate">
                        {row.product.set_name}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {row.product.current_quantity?.toLocaleString() ?? "--"}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {formatPrice(row.product.current_price)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {row.depletionPerDay !== null ? (
                          <span
                            className={
                              row.depletionPerDay > 0
                                ? "text-red-400"
                                : row.depletionPerDay < 0
                                  ? "text-green-400"
                                  : "text-muted-foreground"
                            }
                          >
                            {row.depletionPerDay > 0 ? "-" : "+"}
                            {Math.abs(row.depletionPerDay).toFixed(1)}/day
                          </span>
                        ) : (
                          <span className="text-muted-foreground">--</span>
                        )}
                      </TableCell>
                      <TableCell className={`text-right font-mono text-sm ${urgencyColor}`}>
                        {row.daysUntilSellout !== null
                          ? `${row.daysUntilSellout}d`
                          : row.depletionPerDay !== null && row.depletionPerDay <= 0
                            ? "Growing"
                            : "--"}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
