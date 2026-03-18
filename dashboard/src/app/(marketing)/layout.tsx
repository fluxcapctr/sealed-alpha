import { StarsBackground } from "@/components/ui/stars-background";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative min-h-screen">
      <StarsBackground
        starDensity={0.0002}
        twinkleProbability={0.8}
        minTwinkleSpeed={0.4}
        maxTwinkleSpeed={1.2}
        className="pointer-events-none z-0"
      />
      <div className="relative z-10">{children}</div>
      <footer className="relative z-10 border-t border-zinc-800 mt-12 py-6 px-4 text-center text-xs text-zinc-500">
        <p>
          Sealed Alpha is for informational purposes only and does not
          constitute financial, investment, or trading advice. Past
          performance does not guarantee future results. Always do your own
          research before making purchasing decisions.
        </p>
        <p className="mt-3">
          Notice wrong data or want to see something added?{" "}
          <a
            href="https://instagram.com/kitakami_cards"
            target="_blank"
            rel="noopener noreferrer"
            className="text-zinc-400 underline hover:text-zinc-300"
          >
            @kitakami_cards on IG
          </a>
        </p>
      </footer>
    </div>
  );
}
