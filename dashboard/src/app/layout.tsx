import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://sealedalpha.com"),
  title: {
    default: "Sealed Alpha - Pokemon TCG Sealed Product Investment Tracker",
    template: "%s | Sealed Alpha",
  },
  description:
    "Track 800+ Pokemon TCG sealed products across 80+ sets. Price history, buy/sell signals, rip scores, supply depletion, and more.",
  openGraph: {
    type: "website",
    siteName: "Sealed Alpha",
    title: "Sealed Alpha - Pokemon TCG Sealed Product Investment Tracker",
    description:
      "Track 800+ Pokemon TCG sealed products. Price history, buy/sell signals, rip scores, supply tracking, and more — all free.",
    url: "https://sealedalpha.com",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Sealed Alpha - Pokemon TCG Analytics",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Sealed Alpha - Pokemon TCG Investment Tracker",
    description:
      "Track 800+ Pokemon TCG sealed products. Price history, rip scores, supply tracking — all free.",
    images: ["/og-image.png"],
  },
};

const GA_ID = process.env.NEXT_PUBLIC_GA_ID;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
        {GA_ID && (
          <>
            <Script
              src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
              strategy="afterInteractive"
            />
            <Script id="google-analytics" strategy="afterInteractive">
              {`
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                gtag('consent', 'default', {
                  analytics_storage: 'granted'
                });
                gtag('config', '${GA_ID}');
              `}
            </Script>
          </>
        )}
      </body>
    </html>
  );
}
