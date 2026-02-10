import { createClient } from "@/lib/supabase/server";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatPrice } from "@/lib/signals";
import { HIDDEN_SUBSETS } from "@/lib/constants";
import Link from "next/link";
import Image from "next/image";
import type { ProductAnalytics } from "@/types/database";
import { LanguageToggle } from "@/components/language-toggle";

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
    .order("release_date", { ascending: false });

  // Get product counts per set from analytics
  const { data: analytics } = await supabase
    .from("product_analytics")
    .select("*")
    .returns<ProductAnalytics[]>();

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
          <h1 className="text-2xl font-bold">Sets</h1>
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((set) => {
            const stats = setStats.get(set.id);
            return (
              <Link key={set.id} href={`/sets/${set.id}`}>
                <div className="relative overflow-hidden rounded-xl border border-border group transition-all hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5">
                  {/* Background card art */}
                  {set.top_card_image_url ? (
                    <div className="absolute inset-0 overflow-hidden">
                      <img
                        src={set.top_card_image_url}
                        alt=""
                        className="h-full w-full object-cover object-center blur-[2px] opacity-40 scale-125 transition-all duration-500 ease-out group-hover:opacity-55 group-hover:scale-[1.3]"
                      />
                    </div>
                  ) : (
                    <div className="absolute inset-0 bg-gradient-to-br from-muted/50 to-muted/20" />
                  )}

                  {/* Dark gradient overlay */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/60 to-black/30" />

                  {/* Content */}
                  <div className="relative z-10 p-5 min-h-[200px] flex flex-col">
                    {/* Top row: logo + code badge */}
                    <div className="flex items-start justify-between mb-auto">
                      {set.image_url ? (
                        <div className="relative h-16 w-full flex-1">
                          <Image
                            src={set.image_url}
                            alt={set.name}
                            fill
                            className="object-contain object-left drop-shadow-md"
                            sizes="320px"
                            unoptimized
                          />
                        </div>
                      ) : (
                        <h3 className="text-lg font-bold text-white drop-shadow-md flex-1">
                          {set.name}
                        </h3>
                      )}
                      {set.code && (
                        <Badge
                          variant="outline"
                          className="text-[10px] uppercase border-white/20 text-white/70 ml-2 flex-shrink-0"
                        >
                          {set.code}
                        </Badge>
                      )}
                    </div>

                    {/* Bottom section */}
                    <div className="mt-4 space-y-2">
                      {/* Master set value */}
                      {set.total_set_value ? (
                        <div>
                          <p className="text-2xl font-mono font-bold text-white drop-shadow-sm">
                            {formatPrice(set.total_set_value)}
                          </p>
                          <p className="text-[11px] text-white/50 font-medium uppercase tracking-wider">
                            master set value
                          </p>
                        </div>
                      ) : (
                        <p className="text-sm text-white/40 italic">
                          No value data
                        </p>
                      )}

                      {/* Stats row */}
                      <div className="flex items-center gap-2 text-xs text-white/50">
                        {set.release_date && (
                          <span>
                            {new Date(set.release_date).toLocaleDateString(
                              "en-US",
                              { month: "short", year: "numeric" }
                            )}
                          </span>
                        )}
                        {set.total_cards && (
                          <>
                            <span className="text-white/25">&middot;</span>
                            <span>{set.total_cards} cards</span>
                          </>
                        )}
                        <span className="text-white/25">&middot;</span>
                        <span>
                          {stats?.productCount ?? set.total_products} products tracked
                        </span>
                      </div>

                      {/* Rotation badge */}
                      <Badge
                        variant="outline"
                        className={`text-[10px] border-white/10 ${
                          set.is_in_rotation
                            ? "text-green-300/80"
                            : "text-red-300/60"
                        }`}
                      >
                        {set.is_in_rotation ? "In Rotation" : "Out of Rotation"}
                      </Badge>
                    </div>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
