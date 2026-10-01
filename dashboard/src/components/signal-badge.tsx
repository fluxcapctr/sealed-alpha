import {
  getRecommendation,
  getSignalBgColor,
  getSignalColor,
  getSignalLabel,
  type Recommendation,
} from "@/lib/signals";
import { cn } from "@/lib/utils";

interface SignalBadgeProps {
  score: number | null;
  recommendation?: string | null;
  showScore?: boolean;
  size?: "sm" | "md";
}

export function SignalBadge({ score, recommendation, showScore = false, size = "sm" }: SignalBadgeProps) {
  const rec = (recommendation as Recommendation) ?? getRecommendation(score);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border font-mono font-medium uppercase tracking-wide",
        getSignalBgColor(rec),
        getSignalColor(rec),
        size === "md" ? "px-2.5 py-1 text-xs" : "px-1.5 py-0.5 text-[11px]"
      )}
    >
      {getSignalLabel(rec)}
      {showScore && score !== null && <span className="opacity-70 tabular-nums">{score > 0 ? "+" : ""}{score}</span>}
    </span>
  );
}
