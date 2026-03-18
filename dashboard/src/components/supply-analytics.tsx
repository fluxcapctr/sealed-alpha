"use client";

import { useState, useMemo, useRef, useCallback } from "react";
import { Search, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatPrice } from "@/lib/signals";

interface SupplyProduct {
  product_id: string;
  product_name: string;
  product_type: string;
  set_name: string;
  set_id: string;
  language: string | null;
  current_price: number | null;
  current_quantity: number | null;
  current_listings: number | null;
  quantity_7d_ago: number | null;
  quantity_30d_ago: number | null;
  quantity_90d_ago: number | null;
}

interface SupplyAnalyticsProps {
  products: SupplyProduct[];
}

type SortField = "depletion" | "quantity" | "sellout" | "name";

interface DepletionRow {
  product: SupplyProduct;
  depletionPerDay: number | null;
  daysUntilSellout: number | null;
  quantityChange: number | null;
  changePeriod: string;
}

function computeDepletion(p: SupplyProduct): DepletionRow {
  let quantityChange: number | null = null;
  let days = 0;
  let changePeriod = "";

  if (p.current_quantity !== null && p.quantity_90d_ago !== null) {
    quantityChange = p.quantity_90d_ago - p.current_quantity;
    days = 90;
    changePeriod = "90d";
  } else if (p.current_quantity !== null && p.quantity_30d_ago !== null) {
    quantityChange = p.quantity_30d_ago - p.current_quantity;
    days = 30;
    changePeriod = "30d";
  } else if (p.current_quantity !== null && p.quantity_7d_ago !== null) {
    quantityChange = p.quantity_7d_ago - p.current_quantity;
    days = 7;
    changePeriod = "7d";
  }

  const depletionPerDay =
    quantityChange !== null && days > 0 ? quantityChange / days : null;

  const daysUntilSellout =
    depletionPerDay !== null && depletionPerDay > 0 && p.current_quantity !== null
      ? Math.round(p.current_quantity / depletionPerDay)
      : null;

  return {
    product: p,
    depletionPerDay,
    daysUntilSellout,
    quantityChange,
    changePeriod,
  };
}

export function SupplyAnalytics({ products }: SupplyAnalyticsProps) {
  const [sortBy, setSortBy] = useState<SortField>("depletion");
  const [search, setSearch] = useState("");
  const [filterSet, setFilterSet] = useState("all");
  const [filterType, setFilterType] = useState("all");
  const [filterLang, setFilterLang] = useState("all");
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [debouncedSearch, setDebouncedSearch] = useState("");

  const handleSearch = useCallback((value: string) => {
    setSearch(value);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(value);
    }, 300);
  }, []);

  // Derive filter options from products
  const setOptions = useMemo(() => {
    const sets = new Map<string, string>();
    for (const p of products) {
      if (p.current_quantity !== null && p.current_quantity > 0) {
        sets.set(p.set_id, p.set_name);
      }
    }
    return [...sets.entries()]
      .map(([id, name]) => ({ value: id, label: name }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [products]);

  const typeOptions = useMemo(() => {
    const types = new Set<string>();
    for (const p of products) {
      if (p.current_quantity !== null && p.current_quantity > 0) {
        types.add(p.product_type);
      }
    }
    return [...types].sort();
  }, [products]);

  const rows = useMemo(() => {
    const filtered = products.filter((p) => {
      if (p.current_quantity === null || p.current_quantity <= 0) return false;
      if (filterSet !== "all" && p.set_id !== filterSet) return false;
      if (filterType !== "all" && p.product_type !== filterType) return false;
      if (filterLang !== "all" && (p.language ?? "en") !== filterLang) return false;
      if (debouncedSearch) {
        const q = debouncedSearch.toLowerCase();
        if (
          !p.product_name.toLowerCase().includes(q) &&
          !p.set_name.toLowerCase().includes(q)
        )
          return false;
      }
      return true;
    });

    const computed = filtered.map(computeDepletion);

    return computed.sort((a, b) => {
      switch (sortBy) {
        case "depletion":
          if (a.depletionPerDay === null && b.depletionPerDay === null) return 0;
          if (a.depletionPerDay === null) return 1;
          if (b.depletionPerDay === null) return -1;
          return b.depletionPerDay - a.depletionPerDay;
        case "sellout":
          if (a.daysUntilSellout === null && b.daysUntilSellout === null) return 0;
          if (a.daysUntilSellout === null) return 1;
          if (b.daysUntilSellout === null) return -1;
          return a.daysUntilSellout - b.daysUntilSellout;
        case "quantity":
          return (a.product.current_quantity ?? 0) - (b.product.current_quantity ?? 0);
        case "name":
          return a.product.product_name.localeCompare(b.product.product_name);
        default:
          return 0;
      }
    });
  }, [products, sortBy, filterSet, filterType, filterLang, debouncedSearch]);

  // Summary stats (from filtered results)
  const totalUnits = rows.reduce(
    (sum, r) => sum + (r.product.current_quantity ?? 0),
    0
  );
  const depleting = rows.filter(
    (r) => r.depletionPerDay !== null && r.depletionPerDay > 0
  );
  const criticalCount = rows.filter(
    (r) => r.daysUntilSellout !== null && r.daysUntilSellout <= 90
  ).length;
  const hasHistoricalData = rows.some((r) => r.depletionPerDay !== null);

  const hasFilters =
    filterSet !== "all" || filterType !== "all" || filterLang !== "all" || search !== "";

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Total Units Tracked
            </p>
            <p className="text-2xl font-bold tabular-nums">
              {totalUnits.toLocaleString()}
            </p>
            <p className="text-xs text-muted-foreground">
              across {rows.length} products
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Depleting Products
            </p>
            <p className="text-2xl font-bold tabular-nums text-amber-400">
              {hasHistoricalData ? depleting.length : "--"}
            </p>
            <p className="text-xs text-muted-foreground">
              {hasHistoricalData
                ? "supply actively declining"
                : "needs multi-day data"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Critical (&lt;90 days)
            </p>
            <p className="text-2xl font-bold tabular-nums text-red-400">
              {hasHistoricalData ? criticalCount : "--"}
            </p>
            <p className="text-xs text-muted-foreground">
              {hasHistoricalData
                ? "estimated to sell out within 90 days"
                : "needs multi-day data"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center">
        <div className="relative w-full md:w-[220px]">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search products..."
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            className="h-8 pl-8 pr-8 text-xs"
          />
          {search && (
            <button
              onClick={() => { setSearch(""); setDebouncedSearch(""); }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <Select value={filterLang} onValueChange={setFilterLang}>
          <SelectTrigger className="w-full md:w-[140px] h-8 text-xs">
            <SelectValue placeholder="All Languages" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Languages</SelectItem>
            <SelectItem value="en">English</SelectItem>
            <SelectItem value="ja">Japanese</SelectItem>
          </SelectContent>
        </Select>

        <Select value={filterType} onValueChange={setFilterType}>
          <SelectTrigger className="w-full md:w-[170px] h-8 text-xs">
            <SelectValue placeholder="All Types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {typeOptions.map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={filterSet} onValueChange={setFilterSet}>
          <SelectTrigger className="w-full md:w-[200px] h-8 text-xs">
            <SelectValue placeholder="All Sets" />
          </SelectTrigger>
          <SelectContent className="max-h-[300px]">
            <SelectItem value="all">All Sets</SelectItem>
            {setOptions.map((s) => (
              <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        {hasFilters && (
          <button
            onClick={() => {
              setSearch("");
              setDebouncedSearch("");
              setFilterSet("all");
              setFilterType("all");
              setFilterLang("all");
            }}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors w-full md:w-auto text-center md:text-left"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Depletion Rankings Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm">
            Supply Depletion Rankings
          </CardTitle>
          <span className="text-xs text-muted-foreground tabular-nums">
            {rows.length} products
          </span>
        </CardHeader>
        <CardContent className="p-0">
          {!hasHistoricalData && (
            <div className="px-4 py-2 text-xs text-amber-400 bg-amber-500/10 border-b border-border">
              Depletion rates require multiple days of quantity data. Keep running the daily scraper.
            </div>
          )}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>Set</TableHead>
                <TableHead
                  className="text-right cursor-pointer hover:text-foreground"
                  onClick={() => setSortBy("quantity")}
                >
                  Qty{sortBy === "quantity" ? " ↑" : ""}
                </TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead
                  className="text-right cursor-pointer hover:text-foreground"
                  onClick={() => setSortBy("depletion")}
                >
                  Depletion/Day{sortBy === "depletion" ? " ↓" : ""}
                </TableHead>
                <TableHead
                  className="text-right cursor-pointer hover:text-foreground"
                  onClick={() => setSortBy("sellout")}
                >
                  Est. Sell-out{sortBy === "sellout" ? " ↑" : ""}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center text-muted-foreground"
                  >
                    No products with quantity data found.
                  </TableCell>
                </TableRow>
              ) : (
                rows.slice(0, 50).map((row) => {
                  const urgencyColor =
                    row.daysUntilSellout !== null
                      ? row.daysUntilSellout <= 30
                        ? "text-red-400"
                        : row.daysUntilSellout <= 90
                          ? "text-amber-400"
                          : "text-muted-foreground"
                      : "text-muted-foreground";

                  return (
                    <TableRow key={row.product.product_id}>
                      <TableCell className="font-medium text-sm max-w-[200px] truncate">
                        {row.product.product_name}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-[120px] truncate">
                        {row.product.set_name}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {row.product.current_quantity?.toLocaleString() ?? "--"}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {formatPrice(row.product.current_price)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {row.depletionPerDay !== null ? (
                          <span
                            className={
                              row.depletionPerDay > 0
                                ? "text-red-400"
                                : row.depletionPerDay < 0
                                  ? "text-green-400"
                                  : "text-muted-foreground"
                            }
                          >
                            {row.depletionPerDay > 0 ? "-" : "+"}
                            {Math.abs(row.depletionPerDay).toFixed(1)}/day
                          </span>
                        ) : (
                          <span className="text-muted-foreground">--</span>
                        )}
                      </TableCell>
                      <TableCell className={`text-right font-mono text-sm ${urgencyColor}`}>
                        {row.daysUntilSellout !== null
                          ? `${row.daysUntilSellout}d`
                          : row.depletionPerDay !== null && row.depletionPerDay <= 0
                            ? "Growing"
                            : "--"}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
