import { createClient } from "@/lib/supabase/server";
import { StatCard } from "@/components/stat-card";
import { formatPrice } from "@/lib/signals";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  BoosterBoxValueChart,
  type BoxValueData,
} from "@/components/booster-box-value-chart";
import {
  LifecycleComparisonChart,
  type ProductOption,
  type InitialSelection,
} from "@/components/lifecycle-comparison-chart";
import {
  PackPremiumChart,
  type PackPremiumSetData,
} from "@/components/pack-premium-chart";
import { SealedPremiumIndex } from "@/components/sealed-premium-index";
import { PullRatesTable, type PullRateRow } from "@/components/pull-rates-table";
import { RipScoreCard, type RipScoreRow } from "@/components/rip-score-card";
import { TrendingUp, Package, Layers } from "lucide-react";
import { HIDDEN_SUBSETS } from "@/lib/constants";
import type { ProductAnalytics } from "@/types/database";

export const revalidate = 300;

export default async function AnalyticsPage() {
  const supabase = await createClient();

  const { data: analytics } = await supabase
    .from("product_analytics")
    .select(
      "product_id, product_name, product_type, set_id, set_name, series, release_date, is_in_print, current_price, current_quantity, current_listings, quantity_7d_ago, quantity_30d_ago, quantity_90d_ago, language"
    )
    .returns<
      Pick<
        ProductAnalytics,
        | "product_id"
        | "product_name"
        | "product_type"
        | "set_id"
        | "set_name"
        | "series"
        | "release_date"
        | "is_in_print"
        | "current_price"
        | "current_quantity"
        | "current_listings"
        | "quantity_7d_ago"
        | "quantity_30d_ago"
        | "quantity_90d_ago"
        | "language"
      >[]
    >();

  const products = analytics ?? [];

  // Fetch set values for booster box chart
  const { data: setsData } = await supabase
    .from("sets")
    .select("id, name, series, total_set_value, release_date")
    .not("total_set_value", "is", null)
    .order("release_date", { ascending: false });

  const setValueMap = new Map<
    string,
    { name: string; value: number; releaseDate: string | null; series: string | null }
  >();
  for (const s of setsData ?? []) {
    if (s.total_set_value) {
      setValueMap.set(s.id, {
        name: s.name,
        value: s.total_set_value,
        releaseDate: s.release_date,
        series: s.series,
      });
    }
  }

  // Fetch pull rates + all sets (unfiltered) for pull rate mapping
  const [{ data: pullRatesRaw }, { data: allSetsData }] = await Promise.all([
    supabase
      .from("pull_rates")
      .select("set_id, rarity, packs_per_hit, cards_in_set"),
    supabase
      .from("sets")
      .select("id, name, series, release_date")
      .order("release_date", { ascending: false }),
  ]);

  const allSetsMap = new Map(
    (allSetsData ?? []).map((s) => [s.id, s])
  );

  // Build pull rate rows keyed by set
  const pullRatesBySet = new Map<
    string,
    Record<string, { packsPerHit: number; cardsInSet: number | null }>
  >();
  for (const pr of pullRatesRaw ?? []) {
    const existing = pullRatesBySet.get(pr.set_id) ?? {};
    existing[pr.rarity] = {
      packsPerHit: pr.packs_per_hit,
      cardsInSet: pr.cards_in_set,
    };
    pullRatesBySet.set(pr.set_id, existing);
  }

  const pullRateRows: PullRateRow[] = [];
  for (const [setId, rates] of pullRatesBySet) {
    const setInfo = allSetsMap.get(setId);
    if (!setInfo) continue;
    pullRateRows.push({
      setName: setInfo.name,
      releaseDate: setInfo.release_date,
      series: setInfo.series,
      rates,
    });
  }

  // Fetch per-rarity values for EV computation
  const { data: rarityValuesRaw } = await supabase
    .from("set_rarity_values")
    .select("set_id, rarity, total_value, card_count");

  // Build rarity values by set: { setId: { rarity: { totalValue, cardCount } } }
  const rarityValuesBySet = new Map<
    string,
    Map<string, { totalValue: number; cardCount: number }>
  >();
  for (const rv of rarityValuesRaw ?? []) {
    if (!rarityValuesBySet.has(rv.set_id)) {
      rarityValuesBySet.set(rv.set_id, new Map());
    }
    rarityValuesBySet.get(rv.set_id)!.set(rv.rarity, {
      totalValue: rv.total_value,
      cardCount: rv.card_count,
    });
  }

  // Rarity name mapping: pull_rates rarity → set_rarity_values rarity
  // Pull rates may use different names than pokemontcg.io rarity labels
  const RARITY_ALIASES: Record<string, string[]> = {
    "Double Rare": ["Double Rare"],
    "Ultra Rare": ["Ultra Rare"],
    "Illustration Rare": ["Illustration Rare"],
    "Special Illustration Rare": ["Special Illustration Rare"],
    "Hyper Rare": ["Hyper Rare"],
    "ACE SPEC Rare": ["ACE SPEC Rare"],
    "Shiny Rare": ["Shiny Rare"],
    "Shiny Ultra Rare": ["Shiny Ultra Rare"],
    "Poké Ball Foil": ["Poké Ball Foil"],
    "Master Ball Foil": ["Master Ball Foil"],
    // SWSH era
    "V": ["Rare Holo V", "Ultra Rare"],
    "VMAX/VSTAR": ["Rare Holo VMAX", "Rare Holo VSTAR", "VMAX", "VSTAR"],
    "Full Art V": ["Rare Ultra"],
    "Full Art Pokemon": ["Rare Ultra"],
    "Full Art Trainer": ["Rare Ultra"],
    "Alt Art": ["Rare Ultra", "Special Art Rare"],
    "Alt Art VMAX": ["Rare Ultra", "Rare Rainbow"],
    "Trainer Gallery": ["Trainer Gallery Rare Holo"],
    "Radiant Rare": ["Radiant Rare"],
    "Rainbow Rare": ["Rare Rainbow"],
    "Secret Rare (Gold)": ["Rare Secret"],
    "Shiny V/VMAX": ["Shiny Holo Rare V", "Shiny Holo Rare VMAX"],
    // SM era
    "GX": ["Rare Holo GX", "Ultra Rare"],
    "Prism Star": ["Prism Rare"],
    "Secret Rare (Character)": ["Rare Secret"],
    "Shiny": ["Shiny Holo Rare"],
    "Shiny GX": ["Shiny Holo Rare GX"],
    // SV new types
    "Mega Hyper Rare": ["Mega Hyper Rare"],
    "MEGA_ATTACK_RARE": ["MEGA_ATTACK_RARE"],
    "Signature Trainer": ["Signature Rare"],
    // XY era
    "EX": ["Rare Holo EX"],
    "Full Art": ["Rare Ultra"],
    "Secret Rare": ["Rare Secret"],
  };

  // Compute Box EV for each set that has both pull rates and rarity values
  function computeBoxEv(
    setId: string,
    packsInProduct: number,
  ): { boxEv: number; breakdown: RipScoreRow["evBreakdown"] } | null {
    const pullRates = pullRatesBySet.get(setId);
    const rarityValues = rarityValuesBySet.get(setId);
    if (!pullRates || !rarityValues) return null;

    const breakdown: RipScoreRow["evBreakdown"] = [];
    let totalEv = 0;

    for (const [pullRarity, pullData] of Object.entries(pullRates)) {
      const aliases = RARITY_ALIASES[pullRarity] ?? [pullRarity];
      // Find matching rarity in set_rarity_values
      let matchedValue: { totalValue: number; cardCount: number } | null = null;
      let matchedRarityName = pullRarity;

      for (const alias of aliases) {
        const rv = rarityValues.get(alias);
        if (rv && rv.cardCount > 0) {
          matchedValue = rv;
          matchedRarityName = alias;
          break;
        }
      }

      // Also try exact match on pull rarity name
      if (!matchedValue) {
        const rv = rarityValues.get(pullRarity);
        if (rv && rv.cardCount > 0) {
          matchedValue = rv;
        }
      }

      if (!matchedValue || matchedValue.cardCount === 0) continue;

      const expectedHits = packsInProduct / pullData.packsPerHit;
      const avgCardValue = matchedValue.totalValue / matchedValue.cardCount;
      const ev = expectedHits * avgCardValue;

      totalEv += ev;
      breakdown.push({
        rarity: matchedRarityName,
        ev: Math.round(ev * 100) / 100,
        avgCardValue: Math.round(avgCardValue * 100) / 100,
        expectedHits: Math.round(expectedHits * 100) / 100,
      });
    }

    return { boxEv: Math.round(totalEv * 100) / 100, breakdown };
  }

  // Helper: find the standard product per set for a given type
  // Matches "{Set Name} Booster Box" or "{Set Name} Elite Trainer Box" pattern
  // Excludes cases, bundles, half boxes, set-of packs, and cross-set products
  function findProductPerSet(
    items: typeof products,
    productType: string,
  ): Map<string, number> {
    const result = new Map<string, number>();
    for (const p of items) {
      if (p.product_type !== productType) continue;
      if (p.current_price === null || p.current_price <= 0) continue;
      const name = p.product_name.toLowerCase();
      if (name.includes("case")) continue;
      if (name.includes("bundle")) continue;
      if (name.includes("set of")) continue;
      if (name.includes("half")) continue;
      // Verify product belongs to its set (reject cross-set contamination)
      const setInfo = setValueMap.get(p.set_id);
      if (!setInfo) continue;
      const setNameLower = setInfo.name.toLowerCase();
      if (!name.includes(setNameLower) && !name.startsWith(setNameLower)) continue;
      // Pick the cheapest matching product per set
      const existing = result.get(p.set_id);
      if (existing === undefined || p.current_price < existing) {
        result.set(p.set_id, p.current_price);
      }
    }
    return result;
  }

  const boxBySet = findProductPerSet(products, "Booster Box");
  const etbBySet = findProductPerSet(products, "Elite Trainer Box");

  function buildChartData(
    priceBySet: Map<string, number>,
  ): BoxValueData[] {
    const data: BoxValueData[] = [];
    for (const [setId, price] of priceBySet) {
      const setInfo = setValueMap.get(setId);
      if (!setInfo) continue;
      data.push({
        setName: setInfo.name,
        productPrice: price,
        masterSet: setInfo.value,
        ratio: setInfo.value > 0 ? price / setInfo.value : 0,
        releaseDate: setInfo.releaseDate,
      });
    }
    // Sort by release date, newest first
    data.sort((a, b) => {
      const da = a.releaseDate ?? "";
      const db = b.releaseDate ?? "";
      return db.localeCompare(da);
    });
    return data;
  }

  const boxValueData = buildChartData(boxBySet);
  const etbValueData = buildChartData(etbBySet);

  // Build Rip Score rows
  function buildRipScoreData(
    priceBySet: Map<string, number>,
    packsInProduct: number,
  ): RipScoreRow[] {
    const rows: RipScoreRow[] = [];
    for (const [setId, price] of priceBySet) {
      const evResult = computeBoxEv(setId, packsInProduct);
      if (!evResult || evResult.boxEv <= 0) continue;
      const setInfo = allSetsMap.get(setId);
      if (!setInfo) continue;
      rows.push({
        setName: setInfo.name,
        releaseDate: setInfo.release_date,
        series: setInfo.series,
        productPrice: price,
        boxEv: evResult.boxEv,
        ripScore: Math.round((evResult.boxEv / price) * 100) / 100,
        evBreakdown: evResult.breakdown,
      });
    }
    return rows;
  }

  const ripScoreBoxData = buildRipScoreData(boxBySet, 36);
  const ripScoreEtbData = buildRipScoreData(etbBySet, 9);

  // Total master set market cap
  const totalMasterSetValue = (setsData ?? []).reduce(
    (sum, s) => sum + (s.total_set_value ?? 0),
    0
  );
  const setsWithValues = (setsData ?? []).filter((s) => s.total_set_value && !HIDDEN_SUBSETS.has(s.name)).length;

  // Stats by product type
  const byType = new Map<
    string,
    { count: number; avgPrice: number; prices: number[] }
  >();
  for (const p of products) {
    const type = p.product_type;
    const existing = byType.get(type) ?? { count: 0, avgPrice: 0, prices: [] };
    existing.count++;
    if (p.current_price !== null) {
      existing.prices.push(p.current_price);
    }
    byType.set(type, existing);
  }
  for (const [, stats] of byType) {
    stats.avgPrice =
      stats.prices.length > 0
        ? stats.prices.reduce((a, b) => a + b, 0) / stats.prices.length
        : 0;
  }

  const typeStats = Array.from(byType.entries())
    .map(([type, stats]) => ({ type, ...stats }))
    .sort((a, b) => b.avgPrice - a.avgPrice);

  // Pack premium chart — build per-set product data
  // Find loose pack per set (cheapest standard pack)
  const loosePackBySet = new Map<string, { price: number; name: string }>();
  for (const p of products) {
    if (p.current_price === null || p.current_price <= 0) continue;
    if (p.product_type !== "Booster Pack") continue;
    const name = p.product_name.toLowerCase();
    if (name.includes("case") || name.includes("bundle") || name.includes("set of") || name.includes("blister") || name.includes("art")) continue;
    const setInfo = setValueMap.get(p.set_id);
    if (!setInfo) continue;
    if (!name.includes(setInfo.name.toLowerCase())) continue;
    const existing = loosePackBySet.get(p.set_id);
    if (!existing || p.current_price < existing.price) {
      loosePackBySet.set(p.set_id, { price: p.current_price, name: p.product_name });
    }
  }

  // Find all eligible sealed products per set
  function getPackCount(productType: string): number {
    if (productType === "Booster Box") return 36;
    if (productType === "Elite Trainer Box") return 9;
    if (productType === "Booster Bundle") return 6;
    if (productType === "Booster Bundle Case") return 60;
    return 0;
  }

  const eligibleSealedTypes = new Set([
    "Booster Box",
    "Elite Trainer Box",
    "Booster Bundle",
    "Booster Bundle Case",
  ]);

  function shortenName(fullName: string, setName: string): string {
    // Remove set name prefix to get a short label
    let short = fullName;
    if (short.toLowerCase().startsWith(setName.toLowerCase())) {
      short = short.slice(setName.length).trim();
    }
    return short || fullName;
  }

  const packPremiumSets: PackPremiumSetData[] = [];
  const setIds = new Set(products.map((p) => p.set_id));

  for (const setId of setIds) {
    const loosePack = loosePackBySet.get(setId);
    if (!loosePack) continue;
    const setInfo = setValueMap.get(setId);
    if (!setInfo) continue;

    const sealedProducts = products.filter((p) => {
      if (p.set_id !== setId) return false;
      if (p.current_price === null || p.current_price <= 0) return false;
      if (!eligibleSealedTypes.has(p.product_type)) return false;
      const name = p.product_name.toLowerCase();
      if (name.includes("set of") || name.includes("half")) return false;
      // For non-bundle types, exclude cases and bundles in the name
      if (p.product_type !== "Booster Bundle" && p.product_type !== "Booster Bundle Case") {
        if (name.includes("case") || name.includes("bundle")) return false;
      }
      if (!name.includes(setInfo.name.toLowerCase())) return false;
      return true;
    });

    if (sealedProducts.length === 0) continue;

    packPremiumSets.push({
      setId,
      setName: setInfo.name,
      releaseDate: setInfo.releaseDate,
      series: setInfo.series,
      loosePackPrice: loosePack.price,
      loosePackName: loosePack.name,
      products: sealedProducts.map((p) => ({
        name: p.product_name,
        shortName: shortenName(p.product_name, setInfo.name),
        productType: p.product_type,
        pricePerPack: Math.round((p.current_price! / getPackCount(p.product_type)) * 100) / 100,
        totalPrice: p.current_price!,
        packCount: getPackCount(p.product_type),
        eraAvgPremium: null, // computed below
        eraAvgPricePerPack: null, // computed below
      })).sort((a, b) => a.pricePerPack - b.pricePerPack),
    });
  }

  // Sort sets by release date, newest first
  packPremiumSets.sort((a, b) => {
    const da = a.releaseDate ?? "";
    const db = b.releaseDate ?? "";
    return db.localeCompare(da);
  });

  // Compute era average pack premium per series + product type
  // e.g. "Scarlet & Violet|Booster Box" → [premium1, premium2, ...]
  const eraPremiumBuckets = new Map<string, number[]>();
  for (const setData of packPremiumSets) {
    if (!setData.series) continue;
    for (const prod of setData.products) {
      const premium = ((prod.pricePerPack - setData.loosePackPrice) / setData.loosePackPrice) * 100;
      const key = `${setData.series}|${prod.productType}`;
      const arr = eraPremiumBuckets.get(key) ?? [];
      arr.push(premium);
      eraPremiumBuckets.set(key, arr);
    }
  }
  const eraAvgPremiums = new Map<string, number>();
  for (const [key, premiums] of eraPremiumBuckets) {
    eraAvgPremiums.set(key, premiums.reduce((a, b) => a + b, 0) / premiums.length);
  }
  // Assign per-product era avg premium and $/pack
  for (const setData of packPremiumSets) {
    if (!setData.series) continue;
    for (const prod of setData.products) {
      const key = `${setData.series}|${prod.productType}`;
      const avgPremium = eraAvgPremiums.get(key);
      if (avgPremium != null) {
        prod.eraAvgPremium = Math.round(avgPremium * 10) / 10;
        prod.eraAvgPricePerPack = Math.round(setData.loosePackPrice * (1 + avgPremium / 100) * 100) / 100;
      }
    }
  }

  // Supply depletion — compute server-side, render as static HTML
  const supplyRows = products
    .filter((p) => p.current_quantity !== null && p.current_quantity > 0)
    .map((p) => {
      let quantityChange: number | null = null;
      let days = 0;
      if (p.current_quantity !== null && p.quantity_90d_ago !== null) {
        quantityChange = p.quantity_90d_ago - p.current_quantity;
        days = 90;
      } else if (p.current_quantity !== null && p.quantity_30d_ago !== null) {
        quantityChange = p.quantity_30d_ago - p.current_quantity;
        days = 30;
      } else if (p.current_quantity !== null && p.quantity_7d_ago !== null) {
        quantityChange = p.quantity_7d_ago - p.current_quantity;
        days = 7;
      }
      const depletionPerDay =
        quantityChange !== null && days > 0 ? quantityChange / days : null;
      const daysUntilSellout =
        depletionPerDay !== null &&
        depletionPerDay > 0 &&
        p.current_quantity !== null
          ? Math.round(p.current_quantity / depletionPerDay)
          : null;
      return { ...p, depletionPerDay, daysUntilSellout };
    })
    .sort((a, b) => {
      if (a.depletionPerDay === null && b.depletionPerDay === null) return 0;
      if (a.depletionPerDay === null) return 1;
      if (b.depletionPerDay === null) return -1;
      return b.depletionPerDay - a.depletionPerDay;
    })
    .slice(0, 30);

  const totalUnits = products.reduce(
    (sum, p) => sum + (p.current_quantity ?? 0),
    0
  );
  const productsWithQty = products.filter(
    (p) => p.current_quantity !== null && p.current_quantity > 0
  ).length;
  const hasHistoricalData = supplyRows.some((r) => r.depletionPerDay !== null);
  const depletingCount = supplyRows.filter(
    (r) => r.depletionPerDay !== null && r.depletionPerDay > 0
  ).length;
  const criticalCount = supplyRows.filter(
    (r) => r.daysUntilSellout !== null && r.daysUntilSellout <= 90
  ).length;

  // Pick two EN products of the same type from different eras for lifecycle chart
  const lifecycleInitial = (() => {
    const enProducts = products.filter((p) => (p.language ?? "en") === "en");
    // Group EN products by type, only those with prices
    const byProductType = new Map<string, typeof enProducts>();
    for (const p of enProducts) {
      if (!p.current_price || p.current_price <= 0) continue;
      const name = p.product_name.toLowerCase();
      if (name.includes("case") || name.includes("bundle") || name.includes("set of")) continue;
      const arr = byProductType.get(p.product_type) ?? [];
      arr.push(p);
      byProductType.set(p.product_type, arr);
    }
    // Prefer Booster Box, then ETB — pick from different eras (series)
    const preferredTypes = ["Booster Box", "Elite Trainer Box"];
    for (const type of preferredTypes) {
      const items = byProductType.get(type);
      if (!items || items.length < 2) continue;
      // Group by series to pick from different eras
      const bySeries = new Map<string, typeof items>();
      for (const p of items) {
        const series = p.series ?? "Unknown";
        const arr = bySeries.get(series) ?? [];
        arr.push(p);
        bySeries.set(series, arr);
      }
      const seriesKeys = [...bySeries.keys()];
      if (seriesKeys.length < 2) continue;
      // Pick two random different eras
      const i1 = Math.floor(Math.random() * seriesKeys.length);
      let i2 = Math.floor(Math.random() * (seriesKeys.length - 1));
      if (i2 >= i1) i2++;
      const era1 = bySeries.get(seriesKeys[i1])!;
      const era2 = bySeries.get(seriesKeys[i2])!;
      const p1 = era1[Math.floor(Math.random() * era1.length)];
      const p2 = era2[Math.floor(Math.random() * era2.length)];
      if (p1 && p2) {
        return {
          slot1: { set_id: p1.set_id, product_id: p1.product_id },
          slot2: { set_id: p2.set_id, product_id: p2.product_id },
        };
      }
    }
    return undefined;
  })();

  // Pick a random set for pack premium chart
  const randomPremiumSetId = packPremiumSets.length > 0
    ? packPremiumSets[Math.floor(Math.random() * packPremiumSets.length)].setId
    : undefined;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Analytics</h1>
        <p className="text-sm text-muted-foreground">
          Market-wide insights and portfolio analysis
        </p>
      </div>

      {/* Market Overview */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          title="Master Set Market Cap"
          value={formatPrice(totalMasterSetValue)}
          subtitle={`across ${setsWithValues} sets`}
          icon={TrendingUp}
        />
        <StatCard
          title="Products Tracked"
          value={products.length.toString()}
          subtitle={`${(allSetsData ?? []).filter((s) => !HIDDEN_SUBSETS.has(s.name)).length} sets`}
          icon={Package}
        />
        <StatCard
          title="Product Types"
          value={byType.size.toString()}
          subtitle={Array.from(byType.keys()).slice(0, 3).join(", ") + (byType.size > 3 ? "..." : "")}
          icon={Layers}
        />
      </div>

      {/* Lifecycle Comparison Chart */}
      <LifecycleComparisonChart
        products={products.map((p) => ({
          product_id: p.product_id,
          product_name: p.product_name,
          set_id: p.set_id,
          set_name: p.set_name,
          release_date: p.release_date,
          language: p.language ?? "en",
        }))}
        initialSelections={lifecycleInitial}
      />

      {/* Pack Premium Chart */}
      <PackPremiumChart sets={packPremiumSets} initialSetId={randomPremiumSetId} />

      {/* Booster Box / ETB vs Master Set Value */}
      <BoosterBoxValueChart boxData={boxValueData} etbData={etbValueData} />

      {/* Sealed Premium Index — ranked table */}
      <SealedPremiumIndex boxData={boxValueData} etbData={etbValueData} />

      {/* Box EV / Rip Score */}
      <RipScoreCard boxData={ripScoreBoxData} etbData={ripScoreEtbData} />

      {/* Pull Rates Table */}
      <PullRatesTable data={pullRateRows} />

      {/* Supply Depletion — server-rendered */}
      <div className="space-y-4">
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
                across {productsWithQty} products
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Depleting Products
              </p>
              <p className="text-2xl font-bold tabular-nums text-amber-400">
                {hasHistoricalData ? depletingCount : "--"}
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

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              Supply Depletion Rankings
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {!hasHistoricalData && (
              <div className="px-4 py-2 text-xs text-amber-400 bg-amber-500/10 border-b border-border">
                Depletion rates require multiple days of quantity data. Keep
                running the daily scraper.
              </div>
            )}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Set</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="text-right">Depletion/Day</TableHead>
                  <TableHead className="text-right">Est. Sell-out</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {supplyRows.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="text-center text-muted-foreground"
                    >
                      No products with quantity data found.
                    </TableCell>
                  </TableRow>
                ) : (
                  supplyRows.map((row) => {
                    const urgencyColor =
                      row.daysUntilSellout !== null
                        ? row.daysUntilSellout <= 30
                          ? "text-red-400"
                          : row.daysUntilSellout <= 90
                            ? "text-amber-400"
                            : "text-muted-foreground"
                        : "text-muted-foreground";

                    return (
                      <TableRow key={row.product_id}>
                        <TableCell className="font-medium text-sm max-w-[200px] truncate">
                          {row.product_name}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground max-w-[120px] truncate">
                          {row.set_name}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {row.current_quantity?.toLocaleString() ?? "--"}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {formatPrice(row.current_price)}
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
                        <TableCell
                          className={`text-right font-mono text-sm ${urgencyColor}`}
                        >
                          {row.daysUntilSellout !== null
                            ? `${row.daysUntilSellout}d`
                            : row.depletionPerDay !== null &&
                                row.depletionPerDay <= 0
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

    </div>
  );
}
