"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPrice } from "@/lib/signals";

interface ProductData {
  product_id: string;
  product_name: string;
  product_type: string;
  set_id: string;
  set_name: string;
  series: string | null;
  current_price: number | null;
}

interface PackPremiumCalculatorProps {
  products: ProductData[];
}

function getPackCount(productType: string, productName: string): number {
  const t = productType.toLowerCase();
  const name = productName.toLowerCase();
  if (t.includes("booster box") && name.includes("half")) return 18;
  if (t.includes("booster box")) return 36;
  if (t.includes("elite trainer box")) return 9;
  return 36;
}

function getProductLabel(productType: string): string {
  const t = productType.toLowerCase();
  if (t.includes("booster box")) return "Box";
  if (t.includes("elite trainer box")) return "ETB";
  return productType;
}

function isEligibleProduct(p: ProductData): boolean {
  const t = p.product_type.toLowerCase();
  const name = p.product_name.toLowerCase();
  if (name.includes("case")) return false;
  if (t.includes("pokemon center")) return false;
  if (!t.includes("booster box") && !t.includes("elite trainer box"))
    return false;
  return true;
}

function isLoosePack(p: ProductData): boolean {
  const t = p.product_type.toLowerCase();
  const name = p.product_name.toLowerCase();
  if (t !== "booster pack" && t !== "booster") return false;
  // Exclude bundles, cases, sets of N
  if (name.includes("case")) return false;
  if (name.includes("art bundle")) return false;
  if (name.includes("set of")) return false;
  if (name.includes("bundle")) return false;
  if (name.includes("blister")) return false;
  return true;
}

export function PackPremiumCalculator({
  products,
}: PackPremiumCalculatorProps) {
  const [selectedSetId, setSelectedSetId] = useState<string>("");

  // Pre-compute era averages: for each series + product type, average price-per-pack
  const eraAverages = useMemo(() => {
    const buckets = new Map<string, number[]>();
    for (const p of products) {
      if (!p.series || p.current_price === null) continue;
      if (!isEligibleProduct(p)) continue;
      const packCount = getPackCount(p.product_type, p.product_name);
      const pricePerPack = p.current_price / packCount;
      const key = `${p.series}|${getProductLabel(p.product_type)}`;
      const arr = buckets.get(key) ?? [];
      arr.push(pricePerPack);
      buckets.set(key, arr);
    }
    const avgs = new Map<string, number>();
    for (const [key, prices] of buckets) {
      avgs.set(key, prices.reduce((a, b) => a + b, 0) / prices.length);
    }
    return avgs;
  }, [products]);

  // Sets with at least one eligible box/ETB AND one loose pack with prices
  const eligibleSets = useMemo(() => {
    const setMap = new Map<
      string,
      { setId: string; setName: string; hasProduct: boolean; hasPack: boolean }
    >();
    for (const p of products) {
      if (p.current_price === null) continue;
      const entry = setMap.get(p.set_id) ?? {
        setId: p.set_id,
        setName: p.set_name,
        hasProduct: false,
        hasPack: false,
      };
      if (isEligibleProduct(p)) entry.hasProduct = true;
      if (isLoosePack(p)) entry.hasPack = true;
      setMap.set(p.set_id, entry);
    }
    return Array.from(setMap.values())
      .filter((s) => s.hasProduct && s.hasPack)
      .sort((a, b) => a.setName.localeCompare(b.setName));
  }, [products]);

  // Products for the selected set
  const setProducts = useMemo(() => {
    if (!selectedSetId)
      return { items: [], packs: [], series: null as string | null };
    const items = products.filter(
      (p) =>
        p.set_id === selectedSetId &&
        isEligibleProduct(p) &&
        p.current_price !== null
    );
    const packs = products.filter(
      (p) =>
        p.set_id === selectedSetId &&
        isLoosePack(p) &&
        p.current_price !== null
    );
    const series = items[0]?.series ?? packs[0]?.series ?? null;
    return { items, packs, series };
  }, [products, selectedSetId]);

  const packPrice = setProducts.packs[0]?.current_price ?? null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Pack Premium Calculator</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="mb-1 block text-xs text-muted-foreground">
            Select Set
          </label>
          <select
            value={selectedSetId}
            onChange={(e) => setSelectedSetId(e.target.value)}
            className="w-full max-w-sm rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">Choose a set...</option>
            {eligibleSets.map((s) => (
              <option key={s.setId} value={s.setId}>
                {s.setName}
              </option>
            ))}
          </select>
        </div>

        {selectedSetId &&
        setProducts.items.length > 0 &&
        packPrice !== null ? (
          <div className="space-y-3">
            {/* Loose pack reference */}
            <div className="rounded-md border border-border px-4 py-3">
              <p className="text-xs text-muted-foreground">Loose Pack Price</p>
              <p className="text-lg font-mono font-bold">
                {formatPrice(packPrice)}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {setProducts.packs[0].product_name}
              </p>
            </div>

            {/* Premium breakdown per item */}
            <div className="space-y-2">
              {setProducts.items.map((item) => {
                const itemPrice = item.current_price!;
                const packCount = getPackCount(item.product_type, item.product_name);
                const pricePerPack = itemPrice / packCount;
                const premium = pricePerPack - packPrice;
                const premiumPct = (premium / packPrice) * 100;
                const label = getProductLabel(item.product_type);

                // Era average price-per-pack for this product type
                const eraKey = setProducts.series
                  ? `${setProducts.series}|${label}`
                  : null;
                const eraAvg = eraKey
                  ? eraAverages.get(eraKey) ?? null
                  : null;

                // Green = this product's price-per-pack is below era avg (good value)
                // Red = above era avg (bad value)
                const isFavorable =
                  eraAvg !== null ? pricePerPack <= eraAvg : premium < 0;
                const barColor = isFavorable ? "bg-green-500" : "bg-red-500";
                const textColor = isFavorable
                  ? "text-green-400"
                  : "text-red-400";

                // How far from era avg (for bar width)
                const deviationPct =
                  eraAvg !== null && eraAvg > 0
                    ? Math.abs(((pricePerPack - eraAvg) / eraAvg) * 100)
                    : Math.abs(premiumPct);

                return (
                  <div
                    key={item.product_id}
                    className="rounded-md border border-border p-4"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-sm font-medium">
                          {item.product_name}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {label} price: {formatPrice(itemPrice)} &middot;{" "}
                          {packCount} packs
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-muted-foreground">
                          Price per Pack
                        </p>
                        <p className={`text-lg font-mono font-bold ${textColor}`}>
                          {formatPrice(pricePerPack)}
                        </p>
                        {eraAvg !== null && (
                          <p className="text-xs font-mono text-muted-foreground/60">
                            {setProducts.series} avg: {formatPrice(eraAvg)}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Comparison bar */}
                    <div className="mt-3">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-muted-foreground">
                          vs {setProducts.series} era avg
                        </span>
                        <span className={`font-mono font-medium ${textColor}`}>
                          {isFavorable ? "Below avg" : "Above avg"}
                          {eraAvg !== null &&
                            ` (${pricePerPack < eraAvg ? "" : "+"}${formatPrice(pricePerPack - eraAvg)})`}
                        </span>
                      </div>
                      <div className="relative h-2 w-full rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${barColor}`}
                          style={{
                            width: `${Math.min(100, Math.max(5, deviationPct * 2))}%`,
                          }}
                        />
                      </div>
                    </div>

                    <p className="mt-2 text-xs text-muted-foreground">
                      Pack premium: {formatPrice(premium)}/pack (
                      {premiumPct > 0 ? "+" : ""}
                      {premiumPct.toFixed(1)}% vs loose).{" "}
                      {isFavorable
                        ? `Good relative value for a ${setProducts.series} ${label.toLowerCase()}.`
                        : `Above average for a ${setProducts.series} ${label.toLowerCase()}.`}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        ) : selectedSetId && setProducts.items.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-6">
            No booster box or ETB found for this set with pricing data.
          </p>
        ) : selectedSetId && packPrice === null ? (
          <p className="text-sm text-muted-foreground text-center py-6">
            No loose booster pack found for this set with pricing data.
          </p>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-6">
            Select a set to calculate the pack premium.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
