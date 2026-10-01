import Image from "next/image";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { HoverGlowButton } from "@/components/hover-glow-button";
import { ProductHoverImage } from "@/components/product-hover-image";
import { Sparkline } from "@/components/sparkline";
import { SignalMeter } from "@/components/signal-meter";
import { HIDDEN_SUBSETS } from "@/lib/constants";
import { formatPrice, formatPct, getPctColor } from "@/lib/signals";
import { getAsOf, getSeries, typeCode } from "@/lib/market";
import { cn } from "@/lib/utils";
import type { ProductAnalytics } from "@/types/database";

const FEATURES = [
  { k: "Verdicts", v: "Six market indicators roll up into one score from -100 to +100 for every product, with the reasons shown." },
  { k: "Expected value", v: "Pull rates times card prices give a rip score per set, so you can see when a box is worth more sealed than opened." },
  { k: "Supply", v: "Listing and quantity trends show how fast sealed stock is draining, and where a sell-out may land." },
];

export default async function LandingPage() {
  const supabase = await createClient();
  const [{ data: rows }, { data: allSets }] = await Promise.all([
    supabase.from("product_analytics").select("*").returns<ProductAnalytics[]>(),
    supabase.from("sets").select("name"),
  ]);
  const products = rows ?? [];
  const setCount = (allSets ?? []).filter((s) => !HIDDEN_SUBSETS.has(s.name)).length;
  const asOf = getAsOf(products);

  const movers = products
    .filter((p) => p.price_change_7d_pct !== null && (p.total_price_points ?? 0) >= 10 && (p.current_price ?? 0) >= 20 && Math.abs(p.price_change_7d_pct!) <= 200)
    .sort((a, b) => Math.abs(b.price_change_7d_pct!) - Math.abs(a.price_change_7d_pct!))
    .slice(0, 6);
  const series = asOf ? await getSeries(supabase, movers.map((p) => p.product_id), asOf, 30) : new Map();

  return (
    <div className="mx-auto flex min-h-[100dvh] w-full max-w-6xl flex-col px-5 sm:px-8">
      <header className="flex h-16 items-center justify-between">
        <Image src="/sealed-alpha-wordmark.svg" alt="Sealed Alpha" width={170} height={24} className="h-[22px] w-auto" priority unoptimized />
        <Link href="/overview" className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-muted-foreground hover:text-foreground">
          Open the market <ArrowRight className="size-3.5" />
        </Link>
      </header>

      <section className="grid flex-1 items-center gap-10 py-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:py-16">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            <span className="mr-2 inline-block size-1.5 bg-primary align-middle" />
            Price data as of {asOf ?? "unknown"}
          </p>
          <h1 className="mt-4 font-pixel text-4xl font-semibold leading-[1.05] tracking-wide sm:text-5xl">
            Analysis for <span className="text-primary">sealed</span> Pokemon TCG
          </h1>
          <p className="mt-5 max-w-lg text-base leading-relaxed text-muted-foreground">
            Buy and sell signals, expected value and supply data for {products.length || "800+"} sealed products across {setCount || "80+"} sets. Free.
          </p>
          <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3">
            <Link href="/overview">
              <HoverGlowButton variant="primary" className="px-6">Open the market</HoverGlowButton>
            </Link>
            <Link href="/signup" className="font-mono text-xs uppercase tracking-wider text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">
              Get price alerts by email
            </Link>
          </div>
        </div>

        <div className="overflow-hidden rounded-md border bg-card shadow-2xl shadow-black/40">
          <div className="flex items-center justify-between border-b px-4 py-2.5 font-mono text-[11px] uppercase tracking-[0.1em] text-muted-foreground">
            <span>Top movers &middot; 7d</span>
            <span className="flex items-center gap-1.5"><span className="size-1.5 bg-primary" />{asOf ?? ""}</span>
          </div>
          <div className="divide-y divide-border">
            {movers.map((p) => (
              <div key={p.product_id} className="flex items-center gap-3 px-4 py-2">
                <div className="min-w-0 flex-1">
                  <ProductHoverImage
                    productId={p.product_id}
                    tcgplayerProductId={p.tcgplayer_product_id}
                    imageUrl={p.product_image}
                    name={p.product_name}
                    subtitle={`${p.set_code ?? ""} \u00B7 ${typeCode(p.product_type)}`}
                    size={40}
                  />
                </div>
                <div className="hidden sm:block"><Sparkline values={(series.get(p.product_id) ?? []).map((x: { value: number }) => x.value)} width={64} height={20} /></div>
                <div className="w-[4.6rem] text-right">
                  <p className="text-sm font-medium tabular-nums">{formatPrice(p.current_price)}</p>
                  <p className={cn("font-mono text-[11px] tabular-nums", getPctColor(p.price_change_7d_pct))}>{formatPct(p.price_change_7d_pct)}</p>
                </div>
                <div className="hidden md:block"><SignalMeter score={p.signal_score} recommendation={p.signal_recommendation} showLabel={false} block={4} /></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-px overflow-hidden rounded-md border bg-border sm:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.k} className="bg-card p-5">
            <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-primary">{f.k}</p>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.v}</p>
          </div>
        ))}
      </section>

      <p className="mt-8 text-center font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
        <Link href="/about" className="hover:text-foreground">About</Link> &middot; <Link href="/privacy" className="hover:text-foreground">Privacy</Link> &middot; <Link href="/terms" className="hover:text-foreground">Terms</Link>
      </p>
    </div>
  );
}
