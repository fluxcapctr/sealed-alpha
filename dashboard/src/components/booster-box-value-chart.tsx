"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  type ChartConfig,
} from "@/components/ui/chart";

export type BoxValueData = {
  setName: string;
  productPrice: number;
  masterSet: number;
  ratio: number;
  releaseDate: string | null;
};

type Mode = "boosterBox" | "etb";

const chartConfigs: Record<Mode, ChartConfig> = {
  boosterBox: {
    productPrice: {
      label: "Booster Box",
      color: "var(--chart-1)",
    },
    masterSet: {
      label: "Master Set Value",
      color: "var(--chart-2)",
    },
  },
  etb: {
    productPrice: {
      label: "Elite Trainer Box",
      color: "var(--chart-3)",
    },
    masterSet: {
      label: "Master Set Value",
      color: "var(--chart-2)",
    },
  },
};

const modeLabels: Record<Mode, string> = {
  boosterBox: "Booster Box",
  etb: "Elite Trainer Box",
};

function CustomTooltip({
  active,
  payload,
  label,
  productLabel,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string }>;
  label?: string;
  productLabel: string;
}) {
  if (!active || !payload?.length) return null;

  const product =
    payload.find((p) => p.dataKey === "productPrice")?.value ?? 0;
  const set = payload.find((p) => p.dataKey === "masterSet")?.value ?? 0;
  const ratio = set > 0 ? ((product / set) * 100).toFixed(1) : "N/A";

  return (
    <div className="border-border/50 bg-background rounded-lg border px-3 py-2 text-xs shadow-xl">
      <p className="font-medium mb-1.5">{label}</p>
      <div className="grid gap-1">
        <div className="flex items-center gap-2">
          <div
            className="h-2 w-2 rounded-[2px]"
            style={{ backgroundColor: "var(--color-productPrice)" }}
          />
          <span className="text-muted-foreground">{productLabel}:</span>
          <span className="font-mono font-medium ml-auto">
            $
            {product.toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div
            className="h-2 w-2 rounded-[2px]"
            style={{ backgroundColor: "var(--color-masterSet)" }}
          />
          <span className="text-muted-foreground">Master Set:</span>
          <span className="font-mono font-medium ml-auto">
            $
            {set.toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
        </div>
        <div className="border-t border-border/50 pt-1 mt-0.5">
          <span className="text-muted-foreground">Ratio:</span>
          <span className="font-mono font-medium ml-2">{ratio}%</span>
        </div>
      </div>
    </div>
  );
}

export function BoosterBoxValueChart({
  boxData,
  etbData,
}: {
  boxData: BoxValueData[];
  etbData: BoxValueData[];
}) {
  const [mode, setMode] = useState<Mode>("boosterBox");

  const data = mode === "boosterBox" ? boxData : etbData;
  const config = chartConfigs[mode];
  const label = modeLabels[mode];

  const avgRatio =
    data.length > 0
      ? data.reduce((sum, d) => sum + d.ratio, 0) / data.length
      : 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm">
              {label} Price vs Master Set Value
            </CardTitle>
            <CardDescription>
              {data.length > 0
                ? `Compare sealed ${label.toLowerCase()} prices against master set value. Lower ratio = better value to open. Average ratio: ${(avgRatio * 100).toFixed(1)}%`
                : `No ${label.toLowerCase()} data available.`}
            </CardDescription>
          </div>
          <div className="flex rounded-lg border border-border overflow-hidden text-xs">
            <button
              onClick={() => setMode("boosterBox")}
              className={`px-3 py-1.5 transition-colors ${
                mode === "boosterBox"
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted"
              }`}
            >
              Booster Box
            </button>
            <button
              onClick={() => setMode("etb")}
              className={`px-3 py-1.5 transition-colors ${
                mode === "etb"
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted"
              }`}
            >
              ETB
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <div className="flex h-48 items-center justify-center text-muted-foreground">
            No {label.toLowerCase()} data available for comparison.
          </div>
        ) : (
          <ChartContainer config={config} className="h-[400px] w-full">
            <BarChart
              accessibilityLayer
              data={data}
              margin={{ left: 12, right: 12 }}
            >
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="setName"
                tickLine={false}
                tickMargin={10}
                axisLine={false}
                angle={-45}
                textAnchor="end"
                height={100}
                interval={0}
                fontSize={10}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tickFormatter={(value: number) =>
                  `$${value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value}`
                }
              />
              <ChartTooltip
                content={<CustomTooltip productLabel={label} />}
              />
              <ChartLegend content={<ChartLegendContent />} />
              <Bar
                dataKey="productPrice"
                fill="var(--color-productPrice)"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="masterSet"
                fill="var(--color-masterSet)"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
