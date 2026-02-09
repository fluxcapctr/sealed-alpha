import Link from "next/link";

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-3xl font-bold">Terms of Service</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Last updated: February 2026
      </p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-muted-foreground">
        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Service Description
          </h2>
          <p>
            Sealed Alpha is a Pokemon TCG sealed product investment tracking
            tool. It provides price history, market signals, and analytics for
            informational purposes only.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Not Financial Advice
          </h2>
          <p>
            The information provided by Sealed Alpha, including buy/sell signals,
            rip scores, and price predictions, is for informational and
            entertainment purposes only. It does not constitute financial,
            investment, or trading advice. You should not make purchasing
            decisions based solely on the data provided by this tool.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Data Accuracy
          </h2>
          <p>
            Pricing data is sourced from TCGPlayer and other third-party
            sources. While we strive for accuracy, we cannot guarantee that all
            data is current, complete, or error-free. Historical prices,
            especially for low-volume products, may not reflect actual market
            conditions.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Account Terms
          </h2>
          <ul className="list-disc space-y-1 pl-5">
            <li>You must provide a valid email address to create an account</li>
            <li>You are responsible for maintaining your account security</li>
            <li>One account per person</li>
            <li>
              We reserve the right to suspend accounts that violate these terms
            </li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Limitation of Liability
          </h2>
          <p>
            Sealed Alpha is provided &quot;as is&quot; without warranties of any kind.
            We are not responsible for any financial losses incurred from
            decisions made using this tool. Use at your own risk.
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
