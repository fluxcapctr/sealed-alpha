import { createClient } from "@/lib/supabase/server";
import { SignalBadge } from "@/components/signal-badge";
import { ProductHoverImage } from "@/components/product-hover-image";
import { ProductFilters } from "@/components/product-filters";
import { formatPrice, formatPct, getPctColor } from "@/lib/signals";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Link from "next/link";
import Image from "next/image";
import type { ProductAnalytics, Set } from "@/types/database";

export const revalidate = 300;

type SortField = "set_name" | "product_type" | "current_price" | "release_date";

function buildSortUrl(
  params: Record<string, string | undefined>,
  field: SortField
) {
  const current = params.sort ?? "release_date";
  const currentDir = params.dir ?? "desc";
  const nextDir =
    current === field
      ? currentDir === "asc"
        ? "desc"
        : "asc"
      : field === "current_price" || field === "release_date"
        ? "desc"
        : "asc";

  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) sp.set(k, v);
  }
  sp.set("sort", field);
  sp.set("dir", nextDir);
  return `/products?${sp.toString()}`;
}

function sortArrow(
  params: Record<string, string | undefined>,
  field: SortField
) {
  const currentSort = params.sort ?? "release_date";
  if (currentSort !== field) return "";
  return (params.dir ?? "desc") === "asc" ? " \u2191" : " \u2193";
}

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<{
    type?: string;
    set?: string;
    series?: string;
    signal?: string;
    q?: string;
    sort?: string;
    dir?: string;
  }>;
}) {
  const params = await searchParams;
  const supabase = await createClient();

  // Fetch all sets for filter options
  const { data: allSets } = await supabase
    .from("sets")
    .select("id, name, series")
    .order("release_date", { ascending: false });

  const setsForFilter = (allSets ?? []).map((s) => ({
    value: s.id,
    label: s.name,
    series: s.series,
  }));

  // Derive unique types and series for filter dropdowns
  const uniqueSeries = [...new Set((allSets ?? []).map((s) => s.series).filter(Boolean))] as string[];
  const seriesOptions = uniqueSeries.map((s) => ({ value: s, label: s }));

  // Filter sets list if a series is selected
  const filteredSets = params.series
    ? setsForFilter.filter((s) => s.series === params.series)
    : setsForFilter;

  // Build main query
  let query = supabase.from("product_analytics").select("*");

  if (params.type) {
    query = query.eq("product_type", params.type);
  }
  if (params.set) {
    query = query.eq("set_id", params.set);
  }
  if (params.series) {
    query = query.eq("series", params.series);
  }
  if (params.signal) {
    query = query.eq("signal_recommendation", params.signal);
  }
  if (params.q) {
    query = query.ilike("product_name", `%${params.q}%`);
  }

  // Fetch set info for header when filtered by set
  let setInfo: Set | null = null;
  if (params.set) {
    const { data: setData } = await supabase
      .from("sets")
      .select("*")
      .eq("id", params.set)
      .limit(1);
    setInfo = setData?.[0] ?? null;
  }

  // Default sort: release_date desc (newest first)
  const validSortFields = ["set_name", "product_type", "current_price", "release_date"] as const;
  const sortField = validSortFields.includes(params.sort as SortField)
    ? (params.sort as SortField)
    : "release_date";
  const ascending = params.dir === "asc";

  const { data: products } = await query
    .order(sortField, {
      ascending,
      nullsFirst: false,
    })
    .returns<ProductAnalytics[]>();

  const items = products ?? [];

  // Derive unique product types from the full dataset for filter options
  const uniqueTypes = [...new Set(items.map((p) => p.product_type))].sort();
  const typeOptions = uniqueTypes.map((t) => ({ value: t, label: t }));

  // If we don't have type options from filtered data, fetch all types
  let allTypeOptions = typeOptions;
  if (params.type || params.set || params.series) {
    const { data: allProducts } = await supabase
      .from("product_analytics")
      .select("product_type");
    const allTypes = [...new Set((allProducts ?? []).map((p) => p.product_type))].sort();
    allTypeOptions = allTypes.map((t) => ({ value: t, label: t }));
  }

  return (
    <div className="space-y-6">
      {setInfo ? (
        <Card>
          <CardContent className="p-6">
            <div className="flex items-start gap-6">
              {setInfo.image_url && (
                <div className="relative h-16 w-64 flex-shrink-0">
                  <Image
                    src={setInfo.image_url}
                    alt={`${setInfo.name} logo`}
                    fill
                    className="object-contain object-left"
                    sizes="256px"
                    unoptimized
                  />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold truncate">
                    {setInfo.name}
                  </h1>
                  {setInfo.code && (
                    <Badge
                      variant="outline"
                      className="text-xs uppercase flex-shrink-0"
                    >
                      {setInfo.code}
                    </Badge>
                  )}
                  <Badge
                    variant="outline"
                    className={`text-xs flex-shrink-0 ${
                      setInfo.is_in_rotation
                        ? "border-green-500/30 text-green-400"
                        : "border-red-500/30 text-red-400"
                    }`}
                  >
                    {setInfo.is_in_rotation ? "In Rotation" : "Out of Rotation"}
                  </Badge>
                </div>
                {setInfo.series && (
                  <p className="text-sm text-muted-foreground mt-0.5">
                    {setInfo.series}
                  </p>
                )}
                <div className="mt-3 flex items-baseline gap-6">
                  {setInfo.total_set_value && (
                    <div>
                      <p className="text-2xl font-mono font-bold text-primary">
                        {formatPrice(setInfo.total_set_value)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        master set value
                      </p>
                    </div>
                  )}
                  {setInfo.total_cards && (
                    <div>
                      <p className="text-2xl font-mono font-bold">
                        {setInfo.total_cards}
                      </p>
                      <p className="text-xs text-muted-foreground">cards</p>
                    </div>
                  )}
                  <div>
                    <p className="text-2xl font-mono font-bold">
                      {items.length}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      sealed products
                    </p>
                  </div>
                  {setInfo.release_date && (
                    <div>
                      <p className="text-sm font-medium">
                        {new Date(setInfo.release_date).toLocaleDateString(
                          "en-US",
                          { month: "long", day: "numeric", year: "numeric" }
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        release date
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div>
          <h1 className="text-2xl font-bold">Products</h1>
          <p className="text-sm text-muted-foreground">
            {items.length} sealed products tracked across{" "}
            {new Set(items.map((p) => p.set_id)).size} sets
          </p>
        </div>
      )}

      {/* Filter Bar */}
      <ProductFilters
        types={allTypeOptions}
        sets={filteredSets.map((s) => ({ value: s.value, label: s.label }))}
        series={seriesOptions}
      />

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm">
            Product Catalog
          </CardTitle>
          <span className="text-xs text-muted-foreground tabular-nums">
            {items.length} items
          </span>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>
                  <Link
                    href={buildSortUrl(params, "set_name")}
                    className="hover:text-foreground"
                  >
                    Set{sortArrow(params, "set_name")}
                  </Link>
                </TableHead>
                <TableHead>
                  <Link
                    href={buildSortUrl(params, "product_type")}
                    className="hover:text-foreground"
                  >
                    Type{sortArrow(params, "product_type")}
                  </Link>
                </TableHead>
                <TableHead className="text-right">
                  <Link
                    href={buildSortUrl(params, "current_price")}
                    className="hover:text-foreground"
                  >
                    Price{sortArrow(params, "current_price")}
                  </Link>
                </TableHead>
                <TableHead className="text-right">7d</TableHead>
                <TableHead className="text-right">30d</TableHead>
                <TableHead className="text-right">Qty</TableHead>
                <TableHead className="text-right">Signal</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={8}
                    className="text-center text-muted-foreground"
                  >
                    No products found matching your filters.
                  </TableCell>
                </TableRow>
              ) : (
                items.map((p) => (
                  <TableRow key={p.product_id}>
                    <TableCell>
                      <ProductHoverImage
                        productId={p.product_id}
                        tcgplayerProductId={p.tcgplayer_product_id}
                        name={p.product_name}
                      />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {p.set_name}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {p.product_type}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatPrice(p.current_price)}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono text-sm ${getPctColor(p.price_change_7d_pct)}`}
                    >
                      {formatPct(p.price_change_7d_pct)}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono text-sm ${getPctColor(p.price_change_30d_pct)}`}
                    >
                      {formatPct(p.price_change_30d_pct)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {p.current_quantity != null
                        ? p.current_quantity.toLocaleString()
                        : "--"}
                    </TableCell>
                    <TableCell className="text-right">
                      <SignalBadge
                        score={p.signal_score}
                        recommendation={p.signal_recommendation}
                      />
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
