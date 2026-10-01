import { getRecommendation, getSignalColor, getSignalLabel, type Recommendation } from "@/lib/signals";
import { cn } from "@/lib/utils";

/**
 * Diverging pixel meter: ten blocks with zero in the middle. Sell fills leftward, buy fills rightward, and each block
 * is worth 20 points of composite score, so the shape of the bar reads before the label does. Colourless on purpose
 * (see getSignalColor): hold is grey, buy/sell are light.
 */
export function SignalMeter({
  score,
  recommendation,
  showLabel = true,
  block = 5,
  className,
}: {
  score: number | null;
  recommendation?: string | null;
  /** true: word + score, "score": score only, false: bars only */
  showLabel?: boolean | "score";
  block?: number;
  className?: string;
}) {
  const rec = (recommendation as Recommendation) ?? getRecommendation(score);
  const s = score ?? 0;
  const n = Math.min(5, Math.round(Math.abs(s) / 20));
  const positive = s >= 0;
  const on = rec === "HOLD" ? "bg-muted-foreground" : "bg-foreground/90";
  return (
    <span className={cn("inline-flex items-center gap-2", className)} title={`${getSignalLabel(rec)} (${s > 0 ? "+" : ""}${Math.round(s)})`}>
      <span className="inline-flex gap-px" aria-hidden>
        {Array.from({ length: 10 }, (_, i) => {
          const filled = positive ? i >= 5 && i < 5 + n : i < 5 && i >= 5 - n;
          return (
            <i
              key={i}
              style={{ width: block, height: block * 2 }}
              className={cn("block", filled ? on : "bg-white/10", i === 4 && "mr-px")}
            />
          );
        })}
      </span>
      {showLabel && (
        <span className={cn("font-mono text-[11px] font-medium uppercase tracking-wide tabular-nums", showLabel === true ? "w-[7.6rem]" : "w-7 text-right", getSignalColor(rec))}>
          {showLabel === true && <>{getSignalLabel(rec)} </>}
          {score !== null ? `${s > 0 ? "+" : ""}${Math.round(s)}` : ""}
        </span>
      )}
    </span>
  );
}
