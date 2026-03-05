import Link from "next/link";

export const metadata = {
  title: "About",
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-3xl font-bold">About Sealed Alpha</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        What we track, how we track it, and why
      </p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-muted-foreground">
        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            What This Is
          </h2>
          <p>
            Sealed Alpha is a free analytics tool for Pokemon TCG sealed
            products. We track daily prices, supply levels, sales velocity, and
            card values across every modern set — then compute buy/sell signals,
            rip scores, and lifecycle comparisons so you can make more informed
            decisions about what to buy, hold, or open.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Why Modern Sets Only
          </h2>
          <p>
            We focus on the XY era (2014) through the current Scarlet & Violet
            era. This isn&apos;t arbitrary — these eras share a consistent
            product structure (booster boxes, ETBs, collection boxes, bundles)
            and follow predictable market cycles tied to print runs, rotation,
            and collector demand.
          </p>
          <p className="mt-3">
            Vintage products (Base Set through Black & White) operate on
            completely different dynamics. Prices are driven by nostalgia,
            scarcity of sealed inventory, and grading speculation rather than
            the supply-and-demand patterns we can meaningfully track. Including
            vintage alongside modern sets would distort the signals and
            comparisons that make this tool useful.
          </p>
          <p className="mt-3">
            By keeping the scope to XY and newer, every product in the database
            has comparable pull rate structures, similar box configurations, and
            overlapping collector demographics — which means cross-set and
            cross-era comparisons actually tell you something useful.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Our Data Sources
          </h2>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong className="text-foreground">Pricing & Supply:</strong>{" "}
              TCGPlayer market prices and listing counts, updated daily
            </li>
            <li>
              <strong className="text-foreground">Card Values:</strong>{" "}
              Individual card prices aggregated into master set values, used for
              rip score calculations
            </li>
            <li>
              <strong className="text-foreground">Sales Data:</strong>{" "}
              90-day sales velocity and volume from TCGPlayer transaction history
            </li>
            <li>
              <strong className="text-foreground">Pull Rates:</strong>{" "}
              Community-verified pull rate data for rarity tiers across each set
            </li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            How Signals Work
          </h2>
          <p>
            Buy/sell signals are composite scores derived from six market
            indicators: price momentum (30-day trend), supply depletion rate,
            price relative to historical range, days since release, sales
            velocity, and rip score. No single metric drives the signal — it&apos;s
            the combination that matters.
          </p>
          <p className="mt-3">
            These signals are informational, not prescriptive. They highlight
            products where multiple indicators align, but they can&apos;t account
            for upcoming reprints, market sentiment shifts, or other factors
            outside the data. Use them as one input alongside your own research.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Rip Scores Explained
          </h2>
          <p>
            A rip score tells you the expected value of opening a sealed product
            relative to its purchase price. It&apos;s calculated by combining
            pull rates with current card values for each rarity tier, then
            dividing by the product&apos;s market price. A rip score above 1.0
            means the cards inside are worth more than the sealed product — in
            theory.
          </p>
          <p className="mt-3">
            In practice, rip scores assume average luck and don&apos;t account
            for the cost of selling individual cards. They&apos;re most useful for
            comparing relative value across products, not as a guarantee of
            profit.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Japanese Products
          </h2>
          <p>
            We also track Japanese Pokemon TCG sealed products separately.
            Japanese sets follow different release schedules, product types, and
            pricing dynamics than their English counterparts. The dashboard lets
            you toggle between English and Japanese markets to compare
            independently.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Limitations
          </h2>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              Prices are sourced from TCGPlayer and may not reflect prices on
              other marketplaces or local game stores
            </li>
            <li>
              Low-volume products may show more volatile or unreliable pricing
            </li>
            <li>
              Pull rates are community-sourced estimates, not official data from
              The Pokemon Company
            </li>
            <li>
              Signals cannot predict reprints, bans, or external market events
            </li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Get in Touch
          </h2>
          <p>
            Notice incorrect data, have a feature request, or just want to talk
            sealed product?{" "}
            <a
              href="mailto:eric@kitakamicards.com"
              className="text-foreground underline hover:text-primary"
            >
              Shoot me an email
            </a>
            .
          </p>
        </section>
      </div>

      <div className="mt-12">
        <Link
          href="/"
          className="text-sm text-primary hover:underline"
        >
          &larr; Back to home
        </Link>
      </div>
    </div>
  );
}
