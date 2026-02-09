import Link from "next/link";

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-3xl font-bold">Privacy Policy</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Last updated: February 2026
      </p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-muted-foreground">
        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            What We Collect
          </h2>
          <p>
            When you create an account, we collect your email address and an
            encrypted password. We do not collect personal financial information,
            payment details, or sensitive personal data.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            How We Use Your Data
          </h2>
          <ul className="list-disc space-y-1 pl-5">
            <li>To provide access to the dashboard</li>
            <li>To send a welcome email upon signup</li>
            <li>To send occasional product updates (you can unsubscribe)</li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Data Storage
          </h2>
          <p>
            Your data is stored securely on Supabase (hosted on AWS). Passwords
            are hashed and never stored in plain text. We use industry-standard
            security practices.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Cookies
          </h2>
          <p>
            We use essential cookies for authentication (keeping you logged in).
            We do not use tracking cookies or third-party advertising cookies.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Data Sharing
          </h2>
          <p>
            We do not sell, rent, or share your personal information with third
            parties. Your email is never shared with advertisers.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Your Rights
          </h2>
          <p>
            You can request deletion of your account and all associated data at
            any time by contacting us. You can also export your data upon
            request.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-foreground">
            Contact
          </h2>
          <p>
            For privacy-related questions, please reach out via the contact
            information on our website.
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
