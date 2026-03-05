import Link from "next/link";

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-3xl font-bold">Terms of Service</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Last updated: March 2026
      </p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-muted-foreground">
        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Service Description
          </h2>
          <p>
            Sealed Alpha is a free Pokemon TCG sealed product analytics tool. It
            provides price history, market signals, rip scores, supply tracking,
            and investment analytics for informational purposes only.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Not Financial Advice
          </h2>
          <p>
            The information provided by Sealed Alpha, including buy/sell signals,
            rip scores, set grades, and price data, is for informational and
            entertainment purposes only. It does not constitute financial,
            investment, or trading advice. Past performance does not guarantee
            future results. You should not make purchasing decisions based solely
            on the data provided by this tool. Always do your own research.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Data Accuracy
          </h2>
          <p>
            Pricing and supply data is sourced from TCGPlayer and other
            third-party sources. While we strive for accuracy, we cannot
            guarantee that all data is current, complete, or error-free.
            Historical prices, especially for low-volume products, may not
            reflect actual market conditions. Data is updated daily but may be
            delayed.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Email Communications
          </h2>
          <p>
            By providing your email address, you consent to receiving a series
            of onboarding emails about Sealed Alpha features and related
            products. You can unsubscribe at any time using the link at the
            bottom of any email. We will never sell or share your email address
            with third parties.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Acceptable Use
          </h2>
          <ul className="list-disc space-y-1 pl-5">
            <li>You must provide a valid email address to sign up</li>
            <li>
              Do not use automated tools to scrape or bulk-access the service
            </li>
            <li>Do not attempt to interfere with the service or its infrastructure</li>
            <li>
              We reserve the right to block access that violates these terms
            </li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Third-Party Links
          </h2>
          <p>
            Sealed Alpha may contain links to third-party websites, including
            TCGPlayer and Kitakami Cards. We are not responsible for the content,
            policies, or practices of any third-party sites.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Limitation of Liability
          </h2>
          <p>
            Sealed Alpha is provided &quot;as is&quot; without warranties of any
            kind, either express or implied. We are not responsible for any
            financial losses incurred from decisions made using this tool. Use at
            your own risk.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Changes to Terms
          </h2>
          <p>
            We may update these terms from time to time. Continued use of the
            service after changes constitutes acceptance of the new terms.
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
