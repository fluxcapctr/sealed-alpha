"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis, ReferenceLine } from "recharts";
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
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";

export type PackPremiumProduct = {
  name: string;
  shortName: string;
  productType: string;
  pricePerPack: number;
  totalPrice: number;
  packCount: number;
  eraAvgPremium: number | null;
  eraAvgPricePerPack: number | null;
};

export type PackPremiumSetData = {
  setId: string;
  setName: string;
  releaseDate: string | null;
  series: string | null;
  loosePackPrice: number;
  loosePackName: string;
  products: PackPremiumProduct[];
};

const chartConfig = {
  pricePerPack: {
    label: "$/Pack (Sealed)",
    color: "var(--chart-1)",
  },
  loosePack: {
    label: "Loose Pack",
    color: "var(--chart-4)",
  },
} satisfies ChartConfig;

function CustomTooltip({
  active,
  payload,
  label,
  series,
}: {
  active?: boolean;
  payload?: Array<{
    value: number;
    dataKey: string;
    payload: PackPremiumProduct & { loosePack: number };
  }>;
  label?: string;
  series?: string | null;
}) {
  if (!active || !payload?.length) return null;

  const item = payload[0]?.payload;
  if (!item) return null;

  const ppp = item.pricePerPack;
  const loose = item.loosePack;
  const premium = loose > 0 ? ((ppp - loose) / loose) * 100 : 0;
  const isSaving = ppp < loose;

  return (
    <div className="border-border/50 bg-background rounded-lg border px-3 py-2 text-xs shadow-xl max-w-[280px]">
      <p className="font-medium mb-1.5">{label}</p>
      <div className="grid gap-1">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Total price:</span>
          <span className="font-mono font-medium ml-auto">
            ${item.totalPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Packs inside:</span>
          <span className="font-mono font-medium ml-auto">
            {item.packCount}
          </span>
        </div>
        <div className="border-t border-border/50 pt-1 mt-0.5 grid gap-1">
          <div className="flex items-center gap-2">
            <div
              className="h-2 w-2 rounded-[2px]"
              style={{ backgroundColor: "var(--color-pricePerPack)" }}
            />
            <span className="text-muted-foreground">$/pack (sealed):</span>
            <span className="font-mono font-medium ml-auto">
              ${ppp.toFixed(2)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div
              className="h-2 w-2 rounded-[2px]"
              style={{ backgroundColor: "var(--color-loosePack)" }}
            />
            <span className="text-muted-foreground">Loose pack:</span>
            <span className="font-mono font-medium ml-auto">
              ${loose.toFixed(2)}
            </span>
          </div>
        </div>
        <div className="border-t border-border/50 pt-1 mt-0.5">
          <span className="text-muted-foreground">Premium:</span>
          <span
            className={`font-mono font-medium ml-2 ${
              isSaving ? "text-green-400" : "text-red-400"
            }`}
          >
            {premium > 0 ? "+" : ""}
            {premium.toFixed(1)}%
            {isSaving ? " (saving)" : ""}
          </span>
        </div>
        {item.eraAvgPricePerPack != null && item.eraAvgPremium != null && series && (
          <div className="border-t border-border/50 pt-1 mt-0.5">
            <span className="text-muted-foreground">
              {series} avg {item.productType === "Booster Box" ? "box" : "ETB"}:
            </span>
            <span
              className={`font-mono font-medium ml-2 ${
                ppp <= item.eraAvgPricePerPack ? "text-green-400" : "text-red-400"
              }`}
            >
              {ppp <= item.eraAvgPricePerPack ? "Below" : "Above"} avg (${item.eraAvgPricePerPack.toFixed(2)}/pk,{" "}
              {item.eraAvgPremium > 0 ? "+" : ""}
              {item.eraAvgPremium.toFixed(1)}%)
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function getTypeLabel(productType: string): string {
  if (productType === "Booster Box") return "Box";
  if (productType === "Elite Trainer Box") return "ETB";
  return productType;
}

export function PackPremiumChart({ sets, initialSetId }: { sets: PackPremiumSetData[]; initialSetId?: string }) {
  const [selectedSetId, setSelectedSetId] = useState<string>(initialSetId ?? "");

  const setNames = sets.map((s) => s.setName);
  const nameToId = new Map(sets.map((s) => [s.setName, s.setId]));

  const selectedSet = sets.find((s) => s.setId === selectedSetId);

  // Add loosePack value to each product for the chart
  const chartData = selectedSet
    ? selectedSet.products.map((p) => ({
        ...p,
        loosePack: selectedSet.loosePackPrice,
      }))
    : [];

  // Gather unique product types with era avg info for the info bar
  const eraAvgByType = new Map<string, { premium: number; pricePerPack: number }>();
  if (selectedSet) {
    for (const p of selectedSet.products) {
      if (p.eraAvgPremium != null && p.eraAvgPricePerPack != null && !eraAvgByType.has(p.productType)) {
        eraAvgByType.set(p.productType, { premium: p.eraAvgPremium, pricePerPack: p.eraAvgPricePerPack });
      }
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <div>
            <CardTitle className="text-sm">Pack Premium Calculator</CardTitle>
            <CardDescription>
              Compare the price per pack when buying sealed products vs loose
              packs.
            </CardDescription>
          </div>
          <div className="w-full max-w-[260px]">
            <Combobox
              items={setNames}
              value={selectedSet?.setName ?? null}
              onValueChange={(name) =>
                setSelectedSetId(name ? nameToId.get(name) ?? "" : "")
              }
            >
              <ComboboxInput
                placeholder="Search sets..."
                showClear
                className="text-xs"
              />
              <ComboboxContent>
                <ComboboxEmpty>No sets found.</ComboboxEmpty>
                <ComboboxList>
                  {(name) => (
                    <ComboboxItem key={name} value={name}>
                      {name}
                    </ComboboxItem>
                  )}
                </ComboboxList>
              </ComboboxContent>
            </Combobox>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {!selectedSet ? (
          <div className="flex h-48 items-center justify-center text-muted-foreground text-sm">
            Select a set to see the pack premium breakdown.
          </div>
        ) : chartData.length === 0 ? (
          <div className="flex h-48 items-center justify-center text-muted-foreground text-sm">
            No eligible sealed products found for this set.
          </div>
        ) : (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-muted-foreground">
              <span>
                Loose pack:{" "}
                <span className="font-mono font-medium text-foreground">
                  ${selectedSet.loosePackPrice.toFixed(2)}
                </span>
                <span className="ml-1">({selectedSet.loosePackName})</span>
              </span>
              {selectedSet.series && eraAvgByType.size > 0 && (
                <>
                  {Array.from(eraAvgByType.entries()).map(([type, avg]) => (
                    <span key={type}>
                      {selectedSet.series} avg {getTypeLabel(type)}:{" "}
                      <span
                        className={`font-mono font-medium ${
                          avg.premium > 0 ? "text-red-400" : "text-green-400"
                        }`}
                      >
                        {avg.premium > 0 ? "+" : ""}
                        {avg.premium.toFixed(1)}%
                      </span>
                      <span className="ml-1">
                        (${avg.pricePerPack.toFixed(2)}/pk)
                      </span>
                    </span>
                  ))}
                </>
              )}
            </div>
            <ChartContainer config={chartConfig} className="h-[350px] w-full">
              <BarChart
                accessibilityLayer
                data={chartData}
                margin={{ left: 12, right: 12 }}
              >
                <CartesianGrid vertical={false} />
                <XAxis
                  dataKey="shortName"
                  tickLine={false}
                  tickMargin={10}
                  axisLine={false}
                  interval={0}
                  fontSize={11}
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value: number) => `$${value.toFixed(0)}`}
                />
                <ReferenceLine
                  y={selectedSet.loosePackPrice}
                  stroke="var(--color-loosePack)"
                  strokeDasharray="4 4"
                  strokeWidth={2}
                  label={{ value: "Loose", position: "right", fontSize: 10, fill: "var(--color-loosePack)" }}
                />
                <ChartTooltip
                  content={
                    <CustomTooltip
                      series={selectedSet.series}
                    />
                  }
                />
                <ChartLegend content={<ChartLegendContent />} />
                <Bar
                  dataKey="pricePerPack"
                  fill="var(--color-pricePerPack)"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="loosePack"
                  fill="var(--color-loosePack)"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ChartContainer>
          </>
        )}
      </CardContent>
    </Card>
  );
}
