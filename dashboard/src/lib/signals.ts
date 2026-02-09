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

export function getSignalColor(recommendation: Recommendation): string {
  switch (recommendation) {
    case "STRONG_BUY":
      return "text-emerald-400";
    case "BUY":
      return "text-green-400";
    case "HOLD":
      return "text-amber-400";
    case "SELL":
      return "text-red-400";
    case "STRONG_SELL":
      return "text-red-500";
  }
}

export function getSignalBgColor(recommendation: Recommendation): string {
  switch (recommendation) {
    case "STRONG_BUY":
      return "bg-emerald-500/15 border-emerald-500/30";
    case "BUY":
      return "bg-green-500/15 border-green-500/30";
    case "HOLD":
      return "bg-amber-500/15 border-amber-500/30";
    case "SELL":
      return "bg-red-500/15 border-red-500/30";
    case "STRONG_SELL":
      return "bg-red-600/15 border-red-600/30";
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
  return `$${price.toFixed(2)}`;
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
