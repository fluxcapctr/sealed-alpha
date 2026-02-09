"use client";

import { Area, AreaChart, CartesianGrid, Line, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useState, useMemo } from "react";
import { subDays, parseISO } from "date-fns";

interface PriceDataPoint {
  date: string;
  market_price: number | null;
  low_price: number | null;
  total_listings: number | null;
}

interface PriceChartProps {
  data: PriceDataPoint[];
  title?: string;
}

type TimeRange = "7d" | "30d" | "90d" | "1y" | "all";

const chartConfig = {
  market_price: {
    label: "Market Price",
    color: "var(--chart-1)",
  },
  ma30: {
    label: "30-Day MA",
    color: "var(--chart-5)",
  },
} satisfies ChartConfig;

export function PriceChart({ data, title = "Price History" }: PriceChartProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>("90d");

  const filteredData = useMemo(() => {
    if (timeRange === "all") return data;

    const daysMap: Record<TimeRange, number> = {
      "7d": 7,
      "30d": 30,
      "90d": 90,
      "1y": 365,
      all: 0,
    };
    const cutoff = subDays(new Date(), daysMap[timeRange]);
    return data.filter((d) => parseISO(d.date) >= cutoff);
  }, [data, timeRange]);

  // Smooth stale plateaus: null out middle points of 3+ consecutive identical prices
  const cleanedData = useMemo(() => {
    if (filteredData.length < 3) return filteredData;

    // Identify runs of identical market_price
    const result = filteredData.map((point) => ({ ...point }));
    let runStart = 0;

    for (let i = 1; i <= result.length; i++) {
      const samePrice =
        i < result.length &&
        result[i].market_price !== null &&
        result[runStart].market_price !== null &&
        result[i].market_price === result[runStart].market_price;

      if (!samePrice) {
        const runLen = i - runStart;
        // If 3+ consecutive identical prices, null out the middle ones
        if (runLen >= 3) {
          for (let j = runStart + 1; j < i - 1; j++) {
            result[j] = { ...result[j], market_price: null };
          }
        }
        runStart = i;
      }
    }

    return result;
  }, [filteredData]);

  // Compute 30-day moving average
  const chartData = useMemo(() => {
    return cleanedData.map((point, idx) => {
      let ma30: number | null = null;
      if (idx >= 29) {
        const window = cleanedData
          .slice(idx - 29, idx + 1)
          .map((d) => d.market_price)
          .filter((p): p is number => p !== null);
        if (window.length > 0) {
          ma30 = window.reduce((a, b) => a + b, 0) / window.length;
        }
      }

      return {
        date: point.date,
        market_price: point.market_price,
        ma30,
      };
    });
  }, [cleanedData]);

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{title}</CardTitle>
        </CardHeader>
        <CardContent className="flex h-64 items-center justify-center text-muted-foreground">
          No price data yet
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="pt-0">
      <CardHeader className="flex flex-row items-center justify-between border-b py-5">
        <CardTitle className="text-sm">{title}</CardTitle>
        <Tabs
          value={timeRange}
          onValueChange={(v) => setTimeRange(v as TimeRange)}
        >
          <TabsList className="h-7">
            {(["7d", "30d", "90d", "1y", "all"] as TimeRange[]).map((r) => (
              <TabsTrigger key={r} value={r} className="px-2 text-xs">
                {r.toUpperCase()}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </CardHeader>
      <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
        <ChartContainer
          config={chartConfig}
          className="aspect-auto h-[300px] w-full"
        >
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="fillMarketPrice" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor="var(--color-market_price)"
                  stopOpacity={0.8}
                />
                <stop
                  offset="95%"
                  stopColor="var(--color-market_price)"
                  stopOpacity={0.1}
                />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={60}
              tickFormatter={(value: string) => {
                const d = new Date(value + "T00:00:00");
                return d.toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                });
              }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `$${v}`}
              width={55}
              domain={["auto", "auto"]}
            />
            <ChartTooltip
              cursor={false}
              content={
                <ChartTooltipContent
                  labelFormatter={(value: string) => {
                    const d = new Date(value + "T00:00:00");
                    return d.toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    });
                  }}
                  formatter={((
                    value: number | string,
                  ) => {
                    if (value == null) return "—";
                    const num =
                      typeof value === "number" ? value : Number(value);
                    return (
                      <span className="font-mono font-semibold tabular-nums">
                        ${num.toFixed(2)}
                      </span>
                    );
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  }) as any}
                  indicator="dot"
                />
              }
            />
            <Area
              dataKey="market_price"
              type="natural"
              fill="url(#fillMarketPrice)"
              stroke="var(--color-market_price)"
              strokeWidth={2}
              connectNulls
            />
            {chartData.some((d) => d.ma30 !== null) && (
              <Line
                dataKey="ma30"
                type="natural"
                stroke="var(--color-ma30)"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                connectNulls
              />
            )}
            <ChartLegend content={<ChartLegendContent />} />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
