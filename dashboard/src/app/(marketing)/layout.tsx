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
    </div>
  );
}
