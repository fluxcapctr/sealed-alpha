import type { ProductAnalytics } from "@/types/database";

export type Recommendation =
  | "STRONG_BUY"
  | "BUY"
  | "HOLD"
  | "SELL"
  | "STRONG_SELL";

export interface SignalBreakdown {
  compositeScore: number;
  recommendation: Recommendation;
}

export function getRecommendation(score: number | null): Recommendation {
  if (score === null) return "HOLD";
  if (score >= 60) return "STRONG_BUY";
  if (score >= 30) return "BUY";
  if (score <= -60) return "STRONG_SELL";
  if (score <= -30) return "SELL";
  return "HOLD";
}

// Verdicts are deliberately colourless: green/red are reserved for price direction, and a verdict often disagrees
// with it (a dip can be a BUY). The word and which side the meter fills carry buy vs sell; brightness carries strength.
export function getSignalColor(recommendation: Recommendation): string {
  switch (recommendation) {
    case "STRONG_BUY":
    case "STRONG_SELL":
      return "text-foreground";
    case "BUY":
    case "SELL":
      return "text-foreground/85";
    case "HOLD":
      return "text-muted-foreground";
  }
}

export function getSignalBgColor(recommendation: Recommendation): string {
  switch (recommendation) {
    case "STRONG_BUY":
    case "STRONG_SELL":
      return "bg-foreground/15 border-foreground/40";
    case "BUY":
    case "SELL":
      return "bg-foreground/10 border-foreground/25";
    case "HOLD":
      return "bg-transparent border-border";
  }
}

export function getSignalLabel(recommendation: Recommendation): string {
  switch (recommendation) {
    case "STRONG_BUY":
      return "Strong Buy";
    case "BUY":
      return "Buy";
    case "HOLD":
      return "Hold";
    case "SELL":
      return "Sell";
    case "STRONG_SELL":
      return "Strong Sell";
  }
}

export function formatPrice(price: number | null): string {
  if (price === null || price === undefined) return "--";
  return `$${price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatPct(pct: number | null): string {
  if (pct === null || pct === undefined) return "--";
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

export function getPctColor(pct: number | null): string {
  if (pct === null) return "text-muted-foreground";
  if (pct > 0) return "text-green-400";
  if (pct < 0) return "text-red-400";
  return "text-muted-foreground";
}
