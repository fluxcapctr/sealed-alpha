import Image from "next/image";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { HoverGlowButton } from "@/components/hover-glow-button";

export default async function LandingPage() {
  const supabase = await createClient();

  // Pull live stats for data teasers
  const { count: productCount } = await supabase
    .from("products")
    .select("*", { count: "exact", head: true })
    .eq("is_active", true);

  const { count: setCount } = await supabase
    .from("sets")
    .select("*", { count: "exact", head: true });

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="mx-auto max-w-2xl text-center">
        <Image
          src="/logo-sealed-alpha.png"
          alt="Sealed Alpha"
          width={120}
          height={154}
          className="mx-auto mb-8 rotate-[20deg]"
          priority
        />

        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          Pokemon TCG Sealed Product
          <br />
          <span className="text-primary">Investment Tracker</span>
        </h1>

        <p className="mt-4 text-lg text-muted-foreground">
          Track {productCount ?? 800} sealed products across {setCount ?? 80}{" "}
          modern sets. Real-time pricing, buy/sell signals, rip scores, supply
          depletion, and lifecycle analytics.
        </p>

        <div className="mt-8 flex items-center justify-center gap-4">
          <Link href="/signup">
            <HoverGlowButton variant="primary">
              Get Free Access
            </HoverGlowButton>
          </Link>
          <Link href="/login">
            <HoverGlowButton variant="outline">
              Sign In
            </HoverGlowButton>
          </Link>
        </div>

        {/* Feature grid */}
        <div className="mt-16 grid grid-cols-1 gap-4 sm:grid-cols-3 text-left">
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
              className="rounded-lg border border-border/50 bg-card/50 p-4"
            >
              <h3 className="text-sm font-semibold">{feature.title}</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                {feature.desc}
              </p>
            </div>
          ))}
        </div>

        <p className="mt-12 text-xs text-muted-foreground">
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
