import { Badge } from "@/components/ui/badge";
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

export function SignalBadge({
  score,
  recommendation,
  showScore = false,
  size = "sm",
}: SignalBadgeProps) {
  const rec = (recommendation as Recommendation) ?? getRecommendation(score);
  const color = getSignalColor(rec);
  const bgColor = getSignalBgColor(rec);
  const label = getSignalLabel(rec);

  return (
    <Badge
      variant="outline"
      className={cn(
        "border font-semibold",
        bgColor,
        color,
        size === "md" ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs"
      )}
    >
      {label}
      {showScore && score !== null && (
        <span className="ml-1 opacity-70">({score > 0 ? "+" : ""}{score})</span>
      )}
    </Badge>
  );
}
