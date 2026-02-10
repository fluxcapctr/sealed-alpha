"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type FilterOption = { value: string; label: string };

export function ProductFilters({
  types,
  sets,
  series,
}: {
  types: FilterOption[];
  sets: FilterOption[];
  series: FilterOption[];
}) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const updateParam = useCallback(
    (key: string, value: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value && value !== "all") {
        params.set(key, value);
      } else {
        params.delete(key);
      }
      // Reset to first page when filters change
      params.delete("page");
      router.push(`/products?${params.toString()}`);
    },
    [router, searchParams],
  );

  const currentType = searchParams.get("type") ?? "all";
  const currentSet = searchParams.get("set") ?? "all";
  const currentSeries = searchParams.get("series") ?? "all";
  const currentLang = searchParams.get("lang") ?? "all";
  const currentSort = searchParams.get("sort") ?? "release_date";
  const currentDir = searchParams.get("dir") ?? "desc";
  const sortValue = `${currentSort}:${currentDir}`;

  const handleSortChange = useCallback(
    (value: string) => {
      const [field, dir] = value.split(":");
      const params = new URLSearchParams(searchParams.toString());
      params.set("sort", field);
      params.set("dir", dir);
      router.push(`/products?${params.toString()}`);
    },
    [router, searchParams],
  );

  const clearAll = useCallback(() => {
    router.push("/products");
  }, [router]);

  const hasFilters =
    currentType !== "all" || currentSet !== "all" || currentSeries !== "all" || currentLang !== "all";

  return (
    <div className="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center">
      <Select value={currentLang} onValueChange={(v) => updateParam("lang", v)}>
        <SelectTrigger className="w-full md:w-[140px] h-8 text-xs">
          <SelectValue placeholder="All Languages" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Languages</SelectItem>
          <SelectItem value="en">English</SelectItem>
          <SelectItem value="ja">Japanese</SelectItem>
        </SelectContent>
      </Select>

      <Select value={currentType} onValueChange={(v) => updateParam("type", v)}>
        <SelectTrigger className="w-full md:w-[170px] h-8 text-xs">
          <SelectValue placeholder="All Types" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Types</SelectItem>
          {types.map((t) => (
            <SelectItem key={t.value} value={t.value}>
              {t.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={currentSeries}
        onValueChange={(v) => {
          // Clear set filter when era changes (set may not exist in new era)
          const params = new URLSearchParams(searchParams.toString());
          params.delete("set");
          params.delete("page");
          if (v && v !== "all") {
            params.set("series", v);
          } else {
            params.delete("series");
          }
          router.push(`/products?${params.toString()}`);
        }}
      >
        <SelectTrigger className="w-full md:w-[180px] h-8 text-xs">
          <SelectValue placeholder="All Eras" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Eras</SelectItem>
          {series.map((s) => (
            <SelectItem key={s.value} value={s.value}>
              {s.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={currentSet} onValueChange={(v) => updateParam("set", v)}>
        <SelectTrigger className="w-full md:w-[200px] h-8 text-xs">
          <SelectValue placeholder="All Sets" />
        </SelectTrigger>
        <SelectContent className="max-h-[300px]">
          <SelectItem value="all">All Sets</SelectItem>
          {sets.map((s) => (
            <SelectItem key={s.value} value={s.value}>
              {s.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={sortValue} onValueChange={handleSortChange}>
        <SelectTrigger className="w-full md:w-[180px] h-8 text-xs">
          <SelectValue placeholder="Sort by..." />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="release_date:desc">Newest First</SelectItem>
          <SelectItem value="release_date:asc">Oldest First</SelectItem>
          <SelectItem value="current_price:desc">Price: High to Low</SelectItem>
          <SelectItem value="current_price:asc">Price: Low to High</SelectItem>
          <SelectItem value="set_name:asc">Set: A to Z</SelectItem>
          <SelectItem value="set_name:desc">Set: Z to A</SelectItem>
          <SelectItem value="product_type:asc">Type: A to Z</SelectItem>
        </SelectContent>
      </Select>

      {hasFilters && (
        <button
          onClick={clearAll}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors w-full md:w-auto text-center md:text-left"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
