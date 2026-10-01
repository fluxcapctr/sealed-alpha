export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-screen">
      <div className="dot-grid scanline-fade pointer-events-none absolute inset-0 z-0" aria-hidden />
      <div className="relative z-10">{children}</div>
      <footer className="relative z-10 mt-12 border-t border-border px-4 py-6 text-center text-xs text-muted-foreground">
        <p>
          Sealed Alpha is for informational purposes only and does not constitute financial, investment, or trading
          advice. Past performance does not guarantee future results. Always do your own research before making
          purchasing decisions.
        </p>
        <p className="mt-3">
          Notice wrong data or want to see something added?{" "}
          <a href="https://instagram.com/kitakami_cards" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
            @kitakami_cards on IG
          </a>
        </p>
      </footer>
    </div>
  );
}
