import { createClient } from "@/lib/supabase/server";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/lib/signals";
import { HIDDEN_SUBSETS } from "@/lib/constants";
import Link from "next/link";
import Image from "next/image";
import type { ProductAnalytics } from "@/types/database";
import { LanguageToggle } from "@/components/language-toggle";
import { GradeBadge } from "@/components/set-score-card";

export const revalidate = 300;

export default async function SetsPage({
  searchParams,
}: {
  searchParams: Promise<{ lang?: string }>;
}) {
  const params = await searchParams;
  const lang = params.lang ?? "en"; // Default to English
  const supabase = await createClient();

  const { data: sets } = await supabase
    .from("sets")
    .select("*")
    .eq("language", lang)
    .order("release_date", { ascending: false, nullsFirst: false });

  // Get product counts per set from analytics + set scores
  const [{ data: analytics }, { data: scoresData }] = await Promise.all([
    supabase
      .from("product_analytics")
      .select("*")
      .returns<ProductAnalytics[]>(),
    supabase.from("set_scores").select("set_id, overall_grade"),
  ]);

  const gradeMap = new Map<string, string>();
  if (scoresData) {
    for (const s of scoresData) {
      gradeMap.set(s.set_id, s.overall_grade);
    }
  }

  const setStats = new Map<
    string,
    { productCount: number; avgSignal: number | null }
  >();

  if (analytics) {
    for (const row of analytics) {
      const existing = setStats.get(row.set_id) ?? {
        productCount: 0,
        avgSignal: null,
      };
      existing.productCount++;
      if (row.signal_score !== null) {
        const scores = analytics
          .filter((a) => a.set_id === row.set_id && a.signal_score !== null)
          .map((a) => a.signal_score!);
        existing.avgSignal =
          scores.reduce((a, b) => a + b, 0) / scores.length;
      }
      setStats.set(row.set_id, existing);
    }
  }

  const items = (sets ?? []).filter((s) => !HIDDEN_SUBSETS.has(s.name));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-pixel text-2xl font-semibold tracking-wide">Sets</h1>
          <p className="text-sm text-muted-foreground">
            {items.length} Pokemon TCG sets tracked
          </p>
        </div>
        <LanguageToggle />
      </div>

      {items.length === 0 ? (
        <Card>
          <CardContent className="flex h-48 items-center justify-center text-muted-foreground">
            No sets found. Run the seeding scripts to populate data.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Set</TableHead>
                  <TableHead>Released</TableHead>
                  <TableHead>Grade</TableHead>
                  <TableHead className="text-right">Master set value</TableHead>
                  <TableHead className="text-right">Cards</TableHead>
                  <TableHead className="text-right">Products</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((set) => {
                  const stats = setStats.get(set.id);
                  return (
                    <TableRow key={set.id} className="group">
                      <TableCell>
                        <Link href={`/sets/${set.id}`} className="flex items-center gap-4">
                          <span className="relative block h-8 w-28 shrink-0">
                            {set.image_url ? (
                              <Image src={set.image_url} alt="" fill sizes="112px" className="object-contain object-left" unoptimized />
                            ) : null}
                          </span>
                          <span>
                            <span className="block text-[13px] font-medium group-hover:text-primary">{set.name}</span>
                            <span className="block font-mono text-[11px] uppercase tracking-wide text-muted-foreground">{set.code} &middot; {set.series}</span>
                          </span>
                        </Link>
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{set.release_date ?? "--"}</TableCell>
                      <TableCell>{gradeMap.has(set.id) ? <GradeBadge grade={gradeMap.get(set.id)!} /> : <span className="text-muted-foreground">--</span>}</TableCell>
                      <TableCell className="text-right text-[13px] font-medium tabular-nums">{set.total_set_value ? formatPrice(set.total_set_value) : "--"}</TableCell>
                      <TableCell className="text-right text-[13px] tabular-nums text-muted-foreground">{set.total_cards ?? "--"}</TableCell>
                      <TableCell className="text-right text-[13px] tabular-nums text-muted-foreground">{stats?.productCount ?? set.total_products}</TableCell>
                      <TableCell>
                        <span className={cn("font-mono text-[11px] uppercase tracking-wide", set.is_in_rotation ? "text-up" : "text-muted-foreground")}>
                          {set.is_in_rotation ? "In rotation" : "Rotated out"}
                        </span>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
