"use client";

import * as React from "react";
import { Area, AreaChart, CartesianGrid, XAxis } from "recharts";
import { createClient } from "@/lib/supabase/client";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

export type ProductOption = {
  product_id: string;
  product_name: string;
  set_id: string;
  set_name: string;
  release_date: string | null;
  language?: string;
};

type DatePrice = { date: string; price: number };

type ChartPoint = {
  date: string;
  product1?: number;
  product2?: number;
};

function transformSnapshots(
  snapshots: { snapshot_date: string; market_price: number | null }[],
): DatePrice[] {
  return snapshots
    .filter((s) => s.market_price !== null)
    .map((s) => ({
      date: s.snapshot_date.slice(0, 10),
      price: s.market_price as number,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

function mergeData(
  data1: DatePrice[],
  data2: DatePrice[],
): ChartPoint[] {
  const map = new Map<string, ChartPoint>();

  for (const d of data1) {
    map.set(d.date, { date: d.date, product1: d.price });
  }
  for (const d of data2) {
    const existing = map.get(d.date);
    if (existing) {
      existing.product2 = d.price;
    } else {
      map.set(d.date, { date: d.date, product2: d.price });
    }
  }

  return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date));
}

export type InitialSelection = {
  set_id: string;
  product_id: string;
};

function LifecycleTooltip({
  active,
  payload,
  label,
  product1,
  product2,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string }>;
  label?: string;
  product1?: ProductOption;
  product2?: ProductOption;
}) {
  if (!active || !payload?.length) return null;

  const dateStr = typeof label === "string" ? label : "";
  const dateLabel = dateStr
    ? new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "";

  function getDaysOld(product?: ProductOption) {
    if (!dateStr || !product?.release_date) return null;
    const releaseMs = new Date(product.release_date).getTime();
    const dateMs = new Date(dateStr + "T00:00:00").getTime();
    return Math.floor((dateMs - releaseMs) / 86_400_000);
  }

  const entries = [
    { dataKey: "product1", product: product1, color: "var(--color-product1)" },
    { dataKey: "product2", product: product2, color: "var(--color-product2)" },
  ];

  return (
    <div className="border-border/50 bg-background rounded-lg border px-3 py-2 text-xs shadow-xl">
      <p className="font-medium mb-1.5">{dateLabel}</p>
      <div className="grid gap-1.5">
        {entries.map((entry) => {
          const match = payload.find((p) => p.dataKey === entry.dataKey);
          if (!match) return null;
          const daysOld = getDaysOld(entry.product);
          return (
            <div key={entry.dataKey}>
              <div className="flex items-center gap-2">
                <div
                  className="h-2 w-2 rounded-[2px]"
                  style={{ backgroundColor: entry.color }}
                />
                <span className="text-muted-foreground">
                  {entry.product?.product_name ?? "Product"}:
                </span>
                <span className="font-mono font-medium ml-auto">
                  ${match.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
              {daysOld !== null && (
                <p className="text-[10px] text-muted-foreground ml-4">
                  Day {daysOld.toLocaleString()} since release
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function LifecycleComparisonChart({
  products,
  initialSelections,
}: {
  products: ProductOption[];
  initialSelections?: { slot1: InitialSelection; slot2: InitialSelection };
}) {
  // Language toggle — default to EN
  const hasJp = products.some((p) => p.language === "ja");
  const [lang, setLang] = React.useState<"en" | "ja">("en");

  // Filter products by language
  const filteredProducts = React.useMemo(
    () => (hasJp ? products.filter((p) => (p.language ?? "en") === lang) : products),
    [products, lang, hasJp],
  );

  // Derive unique sets sorted alphabetically
  const sets = React.useMemo(() => {
    const setMap = new Map<string, string>();
    for (const p of filteredProducts) {
      if (!setMap.has(p.set_id)) {
        setMap.set(p.set_id, p.set_name);
      }
    }
    return Array.from(setMap.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [filteredProducts]);

  // Slot 1
  const [set1, setSet1] = React.useState(initialSelections?.slot1.set_id ?? "");
  const [product1Id, setProduct1Id] = React.useState(initialSelections?.slot1.product_id ?? "");
  const [data1, setData1] = React.useState<DatePrice[]>([]);
  const [loading1, setLoading1] = React.useState(false);

  // Slot 2
  const [set2, setSet2] = React.useState(initialSelections?.slot2.set_id ?? "");
  const [product2Id, setProduct2Id] = React.useState(initialSelections?.slot2.product_id ?? "");
  const [data2, setData2] = React.useState<DatePrice[]>([]);
  const [loading2, setLoading2] = React.useState(false);

  // Filtered products per slot
  const products1 = React.useMemo(
    () => filteredProducts.filter((p) => p.set_id === set1),
    [filteredProducts, set1],
  );
  const products2 = React.useMemo(
    () => filteredProducts.filter((p) => p.set_id === set2),
    [filteredProducts, set2],
  );

  const product1 = filteredProducts.find((p) => p.product_id === product1Id);
  const product2 = filteredProducts.find((p) => p.product_id === product2Id);

  // Fetch price data for a product
  const fetchPriceData = React.useCallback(
    async (productId: string) => {
      const supabase = createClient();
      const { data } = await supabase
        .from("price_snapshots")
        .select("snapshot_date, market_price")
        .eq("product_id", productId)
        .order("snapshot_date");

      if (!data) return [];
      return transformSnapshots(data);
    },
    [],
  );

  // Fetch when product 1 changes
  React.useEffect(() => {
    if (!product1Id) {
      setData1([]);
      return;
    }

    setLoading1(true);
    fetchPriceData(product1Id).then((d) => {
      setData1(d);
      setLoading1(false);
    });
  }, [product1Id, fetchPriceData]);

  // Fetch when product 2 changes
  React.useEffect(() => {
    if (!product2Id) {
      setData2([]);
      return;
    }

    setLoading2(true);
    fetchPriceData(product2Id).then((d) => {
      setData2(d);
      setLoading2(false);
    });
  }, [product2Id, fetchPriceData]);

  // Reset product when set changes
  const handleSet1Change = (val: string) => {
    setSet1(val);
    setProduct1Id("");
    setData1([]);
  };
  const handleSet2Change = (val: string) => {
    setSet2(val);
    setProduct2Id("");
    setData2([]);
  };

  // Reset all selections when language changes
  const handleLangChange = (val: string) => {
    if (!val) return; // ToggleGroup can fire empty when deselecting
    setLang(val as "en" | "ja");
    setSet1("");
    setProduct1Id("");
    setData1([]);
    setSet2("");
    setProduct2Id("");
    setData2([]);
  };

  // Merge chart data
  const chartData = React.useMemo(() => {
    if (data1.length === 0 && data2.length === 0) return [];
    if (data1.length > 0 && data2.length === 0) {
      return data1.map((d) => ({ date: d.date, product1: d.price } as ChartPoint));
    }
    if (data1.length === 0 && data2.length > 0) {
      return data2.map((d) => ({ date: d.date, product2: d.price } as ChartPoint));
    }
    return mergeData(data1, data2);
  }, [data1, data2]);

  const label1 = product1
    ? `${product1.product_name}`
    : "Product A";
  const label2 = product2
    ? `${product2.product_name}`
    : "Product B";

  const chartConfig: ChartConfig = {
    product1: {
      label: label1,
      color: "var(--chart-1)",
    },
    product2: {
      label: label2,
      color: "var(--chart-2)",
    },
  };

  const isLoading = loading1 || loading2;

  return (
    <Card className="pt-0">
      <CardHeader className="flex flex-col gap-4 border-b py-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle>Lifecycle Comparison</CardTitle>
            <CardDescription>
              Compare price trajectories of two products over calendar time
            </CardDescription>
          </div>
          {hasJp && (
            <ToggleGroup
              type="single"
              value={lang}
              onValueChange={handleLangChange}
              className="flex-shrink-0"
            >
              <ToggleGroupItem value="en" className="text-xs px-3 h-8">
                English
              </ToggleGroupItem>
              <ToggleGroupItem value="ja" className="text-xs px-3 h-8">
                Japanese
              </ToggleGroupItem>
            </ToggleGroup>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Slot 1 */}
          <div className="flex flex-col gap-2 sm:flex-row">
            <Select value={set1} onValueChange={handleSet1Change}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="Select set..." />
              </SelectTrigger>
              <SelectContent className="max-h-[300px]">
                {sets.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={product1Id}
              onValueChange={setProduct1Id}
              disabled={!set1}
            >
              <SelectTrigger className="w-full sm:flex-1">
                <SelectValue placeholder="Select product..." />
              </SelectTrigger>
              <SelectContent className="max-h-[300px]">
                {products1.map((p) => (
                  <SelectItem key={p.product_id} value={p.product_id}>
                    {p.product_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Slot 2 */}
          <div className="flex flex-col gap-2 sm:flex-row">
            <Select value={set2} onValueChange={handleSet2Change}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="Select set..." />
              </SelectTrigger>
              <SelectContent className="max-h-[300px]">
                {sets.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={product2Id}
              onValueChange={setProduct2Id}
              disabled={!set2}
            >
              <SelectTrigger className="w-full sm:flex-1">
                <SelectValue placeholder="Select product..." />
              </SelectTrigger>
              <SelectContent className="max-h-[300px]">
                {products2.map((p) => (
                  <SelectItem key={p.product_id} value={p.product_id}>
                    {p.product_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>

      <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
        {chartData.length === 0 && !isLoading && (
          <div className="flex h-[250px] items-center justify-center text-sm text-muted-foreground">
            Select two products above to compare their price lifecycles
          </div>
        )}

        {isLoading && (
          <div className="flex h-[250px] items-center justify-center text-sm text-muted-foreground">
            Loading price data...
          </div>
        )}

        {chartData.length > 0 && !isLoading && (
          <ChartContainer
            config={chartConfig}
            className="aspect-auto h-[300px] w-full"
          >
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="fillProduct1" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="var(--color-product1)"
                    stopOpacity={0.8}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--color-product1)"
                    stopOpacity={0.1}
                  />
                </linearGradient>
                <linearGradient id="fillProduct2" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="var(--color-product2)"
                    stopOpacity={0.8}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--color-product2)"
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
                  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
                }}
              />
              <ChartTooltip
                cursor={false}
                content={
                  <LifecycleTooltip product1={product1} product2={product2} />
                }
              />
              <Area
                dataKey="product1"
                type="natural"
                fill="url(#fillProduct1)"
                stroke="var(--color-product1)"
                connectNulls
              />
              <Area
                dataKey="product2"
                type="natural"
                fill="url(#fillProduct2)"
                stroke="var(--color-product2)"
                connectNulls
              />
              <ChartLegend content={<ChartLegendContent />} />
            </AreaChart>
          </ChartContainer>
        )}

        {chartData.length > 0 && !isLoading && (
          <p className="mt-2 text-center text-xs text-muted-foreground">
            Historical price data limited to ~2.8 years. Older products may show gaps before data begins.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
