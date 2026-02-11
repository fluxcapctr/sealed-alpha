"use client";

import { PolarAngleAxis, PolarGrid, Radar, RadarChart } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { InfoTip } from "@/components/info-tip";
import type { SetScore } from "@/types/database";

const BASE_GRADE_STYLES: Record<string, { text: string; bg: string; border: string; fill: string; stroke: string }> = {
  S: { text: "text-yellow-400", bg: "bg-yellow-500/15", border: "border-yellow-500/30", fill: "rgba(234, 179, 8, 0.25)", stroke: "rgb(234, 179, 8)" },
  A: { text: "text-emerald-400", bg: "bg-emerald-500/15", border: "border-emerald-500/30", fill: "rgba(16, 185, 129, 0.25)", stroke: "rgb(16, 185, 129)" },
  B: { text: "text-blue-400", bg: "bg-blue-500/15", border: "border-blue-500/30", fill: "rgba(59, 130, 246, 0.25)", stroke: "rgb(59, 130, 246)" },
  C: { text: "text-amber-400", bg: "bg-amber-500/15", border: "border-amber-500/30", fill: "rgba(245, 158, 11, 0.25)", stroke: "rgb(245, 158, 11)" },
  D: { text: "text-orange-400", bg: "bg-orange-500/15", border: "border-orange-500/30", fill: "rgba(249, 115, 22, 0.25)", stroke: "rgb(249, 115, 22)" },
  F: { text: "text-red-400", bg: "bg-red-500/15", border: "border-red-500/30", fill: "rgba(239, 68, 68, 0.25)", stroke: "rgb(239, 68, 68)" },
};

/** Look up style by base letter (A+/A/A- all use A's colors) */
function getGradeStyle(grade: string) {
  const base = grade.charAt(0);
  return BASE_GRADE_STYLES[base] ?? BASE_GRADE_STYLES.F;
}

const DIMENSIONS = [
  { key: "chase_card_score" as const, label: "Chase" },
  { key: "art_quality_score" as const, label: "Art" },
  { key: "nostalgia_score" as const, label: "Nostalgia" },
  { key: "fun_factor_score" as const, label: "Fun" },
  { key: "value_score" as const, label: "Value" },
  { key: "set_depth_score" as const, label: "Depth" },
];

const chartConfig = {
  score: {
    label: "Score",
    color: "hsl(217 91% 60%)",
  },
} satisfies ChartConfig;

export function SetScoreCard({ score }: { score: SetScore }) {
  const style = getGradeStyle(score.overall_grade);

  const chartData = DIMENSIONS.map((dim) => ({
    dimension: dim.label,
    score: score[dim.key],
    max: 10,
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">
          <InfoTip label="Set Investibility Score" side="right">
            <p className="font-semibold mb-1">How It Works</p>
            <p className="mb-2">
              A weighted grade based on six dimensions that drive sealed product
              investment value. Weights: Nostalgia (1.5x), Chase (1.4x), Art
              (1.2x), Depth (1.1x), Fun (1x), Value (1x).
            </p>
            <p className="font-semibold mb-1">Dimensions</p>
            <ul className="space-y-1 text-xs">
              <li><strong>Chase Card</strong> — How iconic/popular is the #1 card?</li>
              <li><strong>Art Quality</strong> — Overall IR/SIR/Alt Art roster quality</li>
              <li><strong>Nostalgia</strong> — Emotional pull, generational connection</li>
              <li><strong>Fun Factor</strong> — Pull rates + opening experience</li>
              <li><strong>Value</strong> — Master set value vs. booster box price ratio</li>
              <li><strong>Set Depth</strong> — Chase diversity beyond the #1 card</li>
            </ul>
          </InfoTip>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {/* Grade badge LEFT of radar chart */}
        <div className="flex items-center gap-2">
          <div className="flex flex-col items-center gap-1 flex-shrink-0">
            <div
              className={`flex h-16 ${score.overall_grade.length > 1 ? "w-20" : "w-16"} items-center justify-center rounded-xl border-2 ${style.bg} ${style.border}`}
            >
              <span className={`${score.overall_grade.length > 1 ? "text-3xl" : "text-4xl"} font-black ${style.text}`}>
                {score.overall_grade}
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground/70 font-medium uppercase tracking-wider">
              Overall Score
            </p>
          </div>

          {/* Radar chart — 20% larger */}
          <ChartContainer
            config={chartConfig}
            className="flex-1 aspect-square max-h-[290px]"
          >
            <RadarChart data={chartData} outerRadius="60%">
              <ChartTooltip
                cursor={false}
                content={
                  <ChartTooltipContent
                    hideLabel
                    formatter={(value, name) =>
                      name === "score" ? `${value ?? 0}/10` : null
                    }
                  />
                }
              />
              <PolarAngleAxis
                dataKey="dimension"
                tick={{ fontSize: 12, fill: "rgba(160, 170, 190, 0.7)" }}
              />
              <PolarGrid
                gridType="polygon"
                stroke="rgba(148, 163, 184, 0.15)"
              />
              {/* Filled hexagon background */}
              <Radar
                dataKey="max"
                fill="rgba(148, 163, 184, 0.06)"
                stroke="none"
                isAnimationActive={false}
                tooltipType="none"
              />
              {/* Data radar */}
              <Radar
                dataKey="score"
                fill={style.fill}
                stroke={style.stroke}
                strokeWidth={2}
                dot={{
                  r: 3.5,
                  fill: style.stroke,
                  strokeWidth: 0,
                  fillOpacity: 1,
                }}
                activeDot={{
                  r: 5,
                  fill: style.stroke,
                  strokeWidth: 2,
                  stroke: "rgba(0, 0, 0, 0.8)",
                }}
              />
            </RadarChart>
          </ChartContainer>
        </div>

        {/* Notes */}
        {score.notes && (
          <p className="text-xs text-muted-foreground/60 italic text-center mt-1">
            &ldquo;{score.notes}&rdquo;
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/** Small grade badge for the sets grid page */
export function GradeBadge({ grade }: { grade: string }) {
  const style = getGradeStyle(grade);
  return (
    <span
      className={`inline-flex h-6 ${grade.length > 1 ? "w-8 text-[9px]" : "w-6 text-xs"} items-center justify-center rounded font-black ${style.text} ${style.bg} ${style.border} border`}
    >
      {grade}
    </span>
  );
}
