import { createClient } from "@/lib/supabase/server";
import { SignalBadge } from "@/components/signal-badge";
import { ProductHoverImage } from "@/components/product-hover-image";
import { formatPrice, formatPct, getPctColor } from "@/lib/signals";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { InfoTip } from "@/components/info-tip";
import { SetScoreCard } from "@/components/set-score-card";
import type { ProductAnalytics, SetRarityValue, PullRate, SetScore } from "@/types/database";

export const revalidate = 300;

// Rarity alias mapping: pull_rates rarity → set_rarity_values rarity
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
  "GX": ["Rare Holo GX", "Ultra Rare"],
  "Prism Star": ["Prism Rare"],
  "Secret Rare (Character)": ["Rare Secret"],
  "Shiny": ["Shiny Holo Rare"],
  "Shiny GX": ["Shiny Holo Rare GX"],
  "Mega Hyper Rare": ["Mega Hyper Rare"],
  "MEGA_ATTACK_RARE": ["MEGA_ATTACK_RARE"],
  "Signature Trainer": ["Signature Rare"],
};

function getScoreColor(score: number): string {
  if (score >= 1.2) return "text-green-400";
  if (score >= 1.0) return "text-emerald-400";
  if (score >= 0.8) return "text-yellow-400";
  if (score >= 0.5) return "text-orange-400";
  return "text-red-400";
}

function getVerdict(score: number): string {
  if (score >= 1.2) return "Strong Rip";
  if (score >= 1.0) return "Slight Edge";
  if (score >= 0.8) return "Marginal";
  if (score >= 0.5) return "Hold Sealed";
  return "Sealed Premium";
}

function getScoreBg(score: number): string {
  if (score >= 1.2) return "bg-green-500/10";
  if (score >= 1.0) return "bg-emerald-500/10";
  if (score >= 0.8) return "bg-yellow-500/10";
  if (score >= 0.5) return "bg-orange-500/10";
  return "bg-red-500/10";
}

type EvBreakdownItem = {
  rarity: string;
  ev: number;
  avgCardValue: number;
  expectedHits: number;
};

function computeBoxEv(
  pullRates: PullRate[],
  rarityValues: SetRarityValue[],
  packsInProduct: number,
): { boxEv: number; breakdown: EvBreakdownItem[] } | null {
  if (pullRates.length === 0 || rarityValues.length === 0) return null;

  const rvMap = new Map(
    rarityValues.map((rv) => [rv.rarity, { totalValue: rv.total_value, cardCount: rv.card_count }])
  );

  const breakdown: EvBreakdownItem[] = [];
  let totalEv = 0;

  for (const pr of pullRates) {
    const aliases = RARITY_ALIASES[pr.rarity] ?? [pr.rarity];
    let matched: { totalValue: number; cardCount: number } | null = null;
    let matchedName = pr.rarity;

    for (const alias of aliases) {
      const rv = rvMap.get(alias);
      if (rv && rv.cardCount > 0) {
        matched = rv;
        matchedName = alias;
        break;
      }
    }

    if (!matched) {
      const rv = rvMap.get(pr.rarity);
      if (rv && rv.cardCount > 0) matched = rv;
    }

    if (!matched || matched.cardCount === 0) continue;

    const expectedHits = packsInProduct / pr.packs_per_hit;
    const avgCardValue = matched.totalValue / matched.cardCount;
    const ev = expectedHits * avgCardValue;

    totalEv += ev;
    breakdown.push({
      rarity: matchedName,
      ev: Math.round(ev * 100) / 100,
      avgCardValue: Math.round(avgCardValue * 100) / 100,
      expectedHits: Math.round(expectedHits * 100) / 100,
    });
  }

  if (totalEv === 0) return null;
  return { boxEv: Math.round(totalEv * 100) / 100, breakdown };
}

export default async function SetDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const [
    { data: setData },
    { data: productsData },
    { data: rarityData },
    { data: pullRatesData },
    { data: scoreData },
  ] = await Promise.all([
    supabase.from("sets").select("*").eq("id", id).limit(1),
    supabase
      .from("product_analytics")
      .select("*")
      .eq("set_id", id)
      .order("current_price", { ascending: false, nullsFirst: false })
      .returns<ProductAnalytics[]>(),
    supabase
      .from("set_rarity_values")
      .select("*")
      .eq("set_id", id)
      .order("total_value", { ascending: false })
      .returns<SetRarityValue[]>(),
    supabase
      .from("pull_rates")
      .select("*")
      .eq("set_id", id)
      .order("packs_per_hit", { ascending: true })
      .returns<PullRate[]>(),
    supabase
      .from("set_scores")
      .select("*")
      .eq("set_id", id)
      .limit(1)
      .returns<SetScore[]>(),
  ]);

  const set = setData?.[0];
  if (!set) return notFound();

  const products = productsData ?? [];
  const rarityValues = rarityData ?? [];
  const pullRates = pullRatesData ?? [];
  const setScore = scoreData?.[0] ?? null;

  // Find standard booster box and ETB prices
  const setNameLower = set.name.toLowerCase();
  function findStandardProduct(productType: string): ProductAnalytics | null {
    const candidates = products.filter((p) => {
      if (p.product_type !== productType) return false;
      if (p.current_price === null || p.current_price <= 0) return false;
      const name = p.product_name.toLowerCase();
      if (name.includes("case") || name.includes("bundle") || name.includes("set of") || name.includes("half")) return false;
      if (!name.includes(setNameLower)) return false;
      return true;
    });
    if (candidates.length === 0) return null;
    return candidates.reduce((a, b) =>
      (a.current_price ?? Infinity) < (b.current_price ?? Infinity) ? a : b
    );
  }

  const boosterBox = findStandardProduct("Booster Box");
  const etb = findStandardProduct("Elite Trainer Box");

  // ETB pack count varies by era: SV = 9, SWSH/SM/XY = 8
  const etbPacks = set.series === "Scarlet & Violet" ? 9 : 8;

  // Determine flagship product: booster box if available, otherwise ETB
  const hasBoosterBox = boosterBox !== null;
  const primaryPacks = hasBoosterBox ? 36 : etbPacks;
  const primaryLabel = hasBoosterBox ? "Booster Box" : "Elite Trainer Box";
  const primaryProduct = hasBoosterBox ? boosterBox : etb;

  const primaryEv = computeBoxEv(pullRates, rarityValues, primaryPacks);
  const secondaryEv = hasBoosterBox ? computeBoxEv(pullRates, rarityValues, etbPacks) : null;

  const primaryRipScore = primaryEv && primaryProduct?.current_price
    ? Math.round((primaryEv.boxEv / primaryProduct.current_price) * 100) / 100
    : null;
  const secondaryRipScore = secondaryEv && etb?.current_price
    ? Math.round((secondaryEv.boxEv / etb.current_price) * 100) / 100
    : null;

  return (
    <div className="space-y-6">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-xl border border-border">
        {set.top_card_image_url ? (
          <div className="absolute inset-0 overflow-hidden">
            <img
              src={set.top_card_image_url}
              alt=""
              className="h-full w-full object-cover object-center blur-[2px] opacity-40 scale-125"
            />
          </div>
        ) : (
          <div className="absolute inset-0 bg-gradient-to-br from-muted/50 to-muted/20" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/60 to-black/30" />

        <div className="relative z-10 p-6 md:p-8">
          <div className="flex items-start justify-between mb-6">
            {set.image_url ? (
              <div className="relative h-20 w-full max-w-sm flex-1">
                <Image
                  src={set.image_url}
                  alt={set.name}
                  fill
                  className="object-contain object-left drop-shadow-md"
                  sizes="384px"
                  unoptimized
                />
              </div>
            ) : (
              <h1 className="text-3xl font-bold text-white drop-shadow-md flex-1">
                {set.name}
              </h1>
            )}
            {set.code && (
              <Badge
                variant="outline"
                className="ml-3 text-xs uppercase flex-shrink-0 border-white/20 text-white/70"
              >
                {set.code}
              </Badge>
            )}
          </div>

          <div className="flex flex-wrap items-baseline gap-6">
            {set.total_set_value ? (
              <div>
                <p className="text-3xl font-mono font-bold text-white drop-shadow-sm">
                  {formatPrice(set.total_set_value)}
                </p>
                <p className="text-[11px] text-white/50 font-medium uppercase tracking-wider">
                  master set value
                </p>
              </div>
            ) : null}
            {set.total_cards ? (
              <div>
                <p className="text-2xl font-mono font-bold text-white">
                  {set.total_cards}
                </p>
                <p className="text-[11px] text-white/50 font-medium uppercase tracking-wider">
                  cards
                </p>
              </div>
            ) : null}
            <div>
              <p className="text-2xl font-mono font-bold text-white">
                {products.length}
              </p>
              <p className="text-[11px] text-white/50 font-medium uppercase tracking-wider">
                products tracked
              </p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            {set.release_date && (
              <span className="text-xs text-white/50">
                {new Date(set.release_date).toLocaleDateString("en-US", {
                  month: "long",
                  day: "numeric",
                  year: "numeric",
                })}
              </span>
            )}
            <Badge
              variant="outline"
              className={`text-[10px] border-white/10 ${
                set.is_in_rotation
                  ? "text-green-300/80"
                  : "text-red-300/60"
              }`}
            >
              {set.is_in_rotation ? "In Rotation" : "Out of Rotation"}
            </Badge>
            <Badge
              variant="outline"
              className={`text-[10px] border-white/10 ${
                set.is_in_print
                  ? "text-green-300/80"
                  : "text-red-300/60"
              }`}
            >
              {set.is_in_print ? "In Print" : "Out of Print"}
            </Badge>
          </div>
        </div>
      </div>

      {/* Rip Score + Investibility Score side by side */}
      {(primaryEv || setScore) && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Rip Score */}
          {primaryEv ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  <InfoTip
                    label="EV / Rip Score"
                    side="right"
                  >
                    <p className="font-semibold mb-1">EV (Expected Value)</p>
                    <p className="mb-2">The estimated dollar value of cards you&apos;d pull from a sealed product, based on pull rates and current card prices.</p>
                    <p className="font-semibold mb-1">Rip Score</p>
                    <p>EV divided by the product&apos;s price. A score above 1.0 means you&apos;d expect to pull more value than you paid. Below 1.0 means the sealed product carries a premium.</p>
                  </InfoTip>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Primary product row */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">{primaryLabel} ({primaryPacks} packs)</span>
                    {primaryRipScore !== null && (
                      <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${getScoreBg(primaryRipScore)} ${getScoreColor(primaryRipScore)}`}>
                        {getVerdict(primaryRipScore)}
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <InfoTip label={<span className="text-xs text-muted-foreground">Price</span>} side="bottom">
                        Current TCGPlayer market price for this {primaryLabel.toLowerCase()}.
                      </InfoTip>
                      <p className="font-mono font-semibold">{primaryProduct ? formatPrice(primaryProduct.current_price) : "--"}</p>
                    </div>
                    <div>
                      <InfoTip label={<span className="text-xs text-muted-foreground">EV</span>} side="bottom">
                        Expected value of all cards pulled from {primaryPacks} packs, calculated from pull rates and average card values per rarity.
                      </InfoTip>
                      <p className="font-mono font-semibold">{formatPrice(primaryEv.boxEv)}</p>
                    </div>
                    <div>
                      <InfoTip label={<span className="text-xs text-muted-foreground">Rip Score</span>} side="bottom">
                        EV / Price. Above 1.0 = positive expected value (ripping is profitable on average). Below 1.0 = sealed product has a premium over raw card value.
                      </InfoTip>
                      <p className={`font-mono font-bold ${primaryRipScore !== null ? getScoreColor(primaryRipScore) : ""}`}>
                        {primaryRipScore?.toFixed(2) ?? "--"}
                      </p>
                    </div>
                  </div>
                  {/* EV breakdown bars */}
                  <div className="space-y-1.5 pt-2">
                    <InfoTip
                      label={<span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">EV by Rarity</span>}
                      side="right"
                    >
                      Each bar shows the expected value contribution from one rarity tier in {primaryPacks} packs. Calculated as: (packs / packs_per_hit) x avg card value for that rarity.
                    </InfoTip>
                    {primaryEv.breakdown
                      .filter((b) => b.ev > 0.01)
                      .sort((a, b) => b.ev - a.ev)
                      .map((b) => {
                        const pct = primaryEv.boxEv > 0 ? (b.ev / primaryEv.boxEv) * 100 : 0;
                        return (
                          <div key={b.rarity} className="flex items-center gap-2 text-xs">
                            <span className="w-[140px] truncate text-muted-foreground">{b.rarity}</span>
                            <div className="flex-1 h-2.5 bg-muted rounded overflow-hidden">
                              <div
                                className="h-full bg-primary/60 rounded"
                                style={{ width: `${Math.min(pct, 100)}%` }}
                              />
                            </div>
                            <span className="w-[55px] text-right font-mono">${b.ev.toFixed(2)}</span>
                          </div>
                        );
                      })}
                  </div>
                </div>

                {/* Secondary product row (ETB when primary is Booster Box) */}
                {hasBoosterBox && secondaryEv && (
                  <div className="space-y-2 pt-3 border-t border-border">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Elite Trainer Box ({etbPacks} packs)</span>
                      {secondaryRipScore !== null && (
                        <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${getScoreBg(secondaryRipScore)} ${getScoreColor(secondaryRipScore)}`}>
                          {getVerdict(secondaryRipScore)}
                        </span>
                      )}
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <InfoTip label={<span className="text-xs text-muted-foreground">Price</span>} side="bottom">
                          Current TCGPlayer market price for this Elite Trainer Box.
                        </InfoTip>
                        <p className="font-mono font-semibold">{etb ? formatPrice(etb.current_price) : "--"}</p>
                      </div>
                      <div>
                        <InfoTip label={<span className="text-xs text-muted-foreground">ETB EV</span>} side="bottom">
                          Expected value of all cards pulled from {etbPacks} packs, calculated from pull rates and average card values per rarity.
                        </InfoTip>
                        <p className="font-mono font-semibold">{formatPrice(secondaryEv.boxEv)}</p>
                      </div>
                      <div>
                        <InfoTip label={<span className="text-xs text-muted-foreground">Rip Score</span>} side="bottom">
                          ETB EV / Price. Above 1.0 = positive expected value. Below 1.0 = sealed product has a premium over raw card value.
                        </InfoTip>
                        <p className={`font-mono font-bold ${secondaryRipScore !== null ? getScoreColor(secondaryRipScore) : ""}`}>
                          {secondaryRipScore?.toFixed(2) ?? "--"}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : !setScore ? null : (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">EV / Rip Score</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {pullRates.length === 0
                    ? "No pull rate data available for this set yet. Pull rates are needed to calculate expected value."
                    : rarityValues.length === 0
                      ? "No rarity value data available for this set yet. Card prices per rarity are needed to calculate expected value."
                      : "Could not compute EV — rarity names in pull rates don\u2019t match the rarity value data for this set."}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Set Investibility Score */}
          {setScore && <SetScoreCard score={setScore} />}
        </div>
      )}

      {/* Rarity Breakdown + Pull Rates side by side */}
      {(rarityValues.length > 0 || pullRates.length > 0) && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Rarity Breakdown */}
          {rarityValues.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  <InfoTip label="Rarity Value Breakdown" side="right">
                    Total and average TCGPlayer market prices for each rarity tier in this set. Values are based on current market prices for every card in the set.
                  </InfoTip>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Rarity</TableHead>
                      <TableHead className="text-right">Cards</TableHead>
                      <TableHead className="text-right">Total Value</TableHead>
                      <TableHead className="text-right">
                        <InfoTip label="Avg / Card" side="left">
                          Average TCGPlayer market price across all cards of this rarity. Calculated as Total Value / Card Count.
                        </InfoTip>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rarityValues.map((rv) => (
                      <TableRow key={rv.id}>
                        <TableCell className="text-sm">{rv.rarity}</TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {rv.card_count}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {formatPrice(rv.total_value)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {formatPrice(
                            rv.card_count > 0
                              ? rv.total_value / rv.card_count
                              : null
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {/* Pull Rates */}
          {pullRates.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  <InfoTip label="Pull Rates" side="right">
                    How many packs you need to open on average to pull one card of each rarity. Lower = more common. Based on community-sourced data from TCGPlayer and YouTube case break samples.
                  </InfoTip>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Rarity</TableHead>
                      <TableHead className="text-right">Packs per Hit</TableHead>
                      <TableHead className="text-right">Cards in Set</TableHead>
                      <TableHead className="text-right">Source</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pullRates.map((pr) => (
                      <TableRow key={pr.id}>
                        <TableCell className="text-sm">{pr.rarity}</TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {pr.packs_per_hit.toFixed(2)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {pr.cards_in_set ?? "--"}
                        </TableCell>
                        <TableCell className="text-right text-xs text-muted-foreground">
                          {pr.source}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Products Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Sealed Products</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">7d</TableHead>
                <TableHead className="text-right">30d</TableHead>
                <TableHead className="text-right">Qty</TableHead>
                <TableHead className="text-right">Signal</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="text-center text-muted-foreground"
                  >
                    No products found for this set.
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
                      {p.product_type}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatPrice(p.current_price)}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono text-sm ${getPctColor(p.price_change_7d_pct)}`}
                    >
                      {formatPct(p.price_change_7d_pct)}
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
