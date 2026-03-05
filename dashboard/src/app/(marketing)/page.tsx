import Image from "next/image";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { HoverGlowButton } from "@/components/hover-glow-button";
import { HIDDEN_SUBSETS } from "@/lib/constants";

export default async function LandingPage() {
  const supabase = await createClient();

  // Pull live stats for data teasers
  const { count: productCount } = await supabase
    .from("products")
    .select("*", { count: "exact", head: true })
    .eq("is_active", true);

  const { data: allSets } = await supabase
    .from("sets")
    .select("name");
  const setCount = (allSets ?? []).filter((s) => !HIDDEN_SUBSETS.has(s.name)).length;

  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center px-5 py-12 sm:px-6 sm:py-16">
      <div className="mx-auto w-full max-w-2xl text-center">
        <Image
          src="/logo-sealed-alpha.png"
          alt="Sealed Alpha"
          width={120}
          height={154}
          className="mx-auto mb-6 w-[80px] rotate-[20deg] sm:mb-8 sm:w-[120px]"
          priority
        />

        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl">
          Pokemon TCG Sealed Product
          <br />
          <span className="text-primary">Investment Tracker</span>
        </h1>

        <p className="mt-3 text-base text-muted-foreground sm:mt-4 sm:text-lg">
          Track {productCount ?? 800} sealed products across {setCount ?? 80}{" "}
          modern sets. Real-time pricing, buy/sell signals, rip scores, supply
          depletion, and lifecycle analytics.
        </p>

        <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:mt-8 sm:flex-row sm:gap-4">
          <Link href="/signup" className="w-full sm:w-auto">
            <HoverGlowButton variant="primary" className="w-full sm:w-auto">
              Get Free Access
            </HoverGlowButton>
          </Link>
          <Link href="/overview" className="w-full sm:w-auto">
            <HoverGlowButton variant="outline" className="w-full sm:w-auto">
              Browse Dashboard
            </HoverGlowButton>
          </Link>
        </div>

        {/* Feature grid */}
        <div className="mt-10 grid grid-cols-2 gap-3 text-left sm:mt-16 sm:grid-cols-3 sm:gap-4">
          {[
            {
              title: "Buy/Sell Signals",
              desc: "AI-powered composite scores from 6 market indicators",
            },
            {
              title: "Price History",
              desc: "Daily tracking with 30-day MA and historical backfill",
            },
            {
              title: "Rip Scores",
              desc: "Expected value calculations based on pull rates and card prices",
            },
            {
              title: "Supply Tracking",
              desc: "Monitor quantity depletion and estimate sell-out dates",
            },
            {
              title: "Lifecycle Comparison",
              desc: "Compare price trajectories across products and eras",
            },
            {
              title: `${setCount ?? 80} Modern Sets`,
              desc: "XY through Scarlet & Violet — every sealed product tracked",
            },
          ].map((feature) => (
            <div
              key={feature.title}
              className="rounded-lg border border-border/50 bg-card/50 p-3 sm:p-4"
            >
              <h3 className="text-xs font-semibold sm:text-sm">
                {feature.title}
              </h3>
              <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground sm:text-xs">
                {feature.desc}
              </p>
            </div>
          ))}
        </div>

        <p className="mt-8 text-xs text-muted-foreground sm:mt-12">
          <Link href="/about" className="hover:underline">
            About
          </Link>
          {" · "}
          <Link href="/privacy" className="hover:underline">
            Privacy Policy
          </Link>
          {" · "}
          <Link href="/terms" className="hover:underline">
            Terms of Service
          </Link>
        </p>
      </div>
    </div>
  );
}
