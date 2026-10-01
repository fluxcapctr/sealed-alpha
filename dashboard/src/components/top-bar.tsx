import Link from "next/link";
import { Search } from "lucide-react";
import { formatPct } from "@/lib/signals";

export type TickerItem = { id: string; code: string; label: string; price: number; pct: number };

/** Search + as-of stamp + scrolling movers. The as-of date is the data's real last price date, never "now". */
export function TopBar({ items, asOf }: { items: TickerItem[]; asOf: string | null }) {
  const row = items.map((t) => (
    <Link key={t.id} href={`/products/${t.id}`} className="flex shrink-0 items-center gap-2 border-r border-border px-4 py-2 font-mono text-[11px] hover:bg-accent">
      <span className="text-muted-foreground">{t.code}</span>
      <span className="uppercase">{t.label}</span>
      <span className="tabular-nums">${t.price.toLocaleString("en-US", { maximumFractionDigits: 0 })}</span>
      <span className={t.pct >= 0 ? "text-up tabular-nums" : "text-down tabular-nums"}>
        {t.pct >= 0 ? "▲" : "▼"} {formatPct(Math.abs(t.pct)).replace("+", "")}
      </span>
    </Link>
  ));
  return (
    <div className="hidden h-10 shrink-0 items-stretch border-b bg-background md:flex">
      <form action="/products" className="relative hidden w-56 shrink-0 border-r md:block">
        <Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          name="q"
          placeholder="Find a product"
          aria-label="Find a product"
          className="h-full w-full bg-transparent pl-9 pr-8 text-xs outline-none placeholder:text-muted-foreground focus:bg-accent/40"
        />
        <kbd className="absolute right-2 top-1/2 -translate-y-1/2 rounded-sm border px-1 font-mono text-[10px] text-muted-foreground">/</kbd>
      </form>
      <div className="ticker-wrap min-w-0 flex-1 overflow-hidden">
        <div className="ticker-track">
          {row}
          <span className="contents" aria-hidden>{row}</span>
        </div>
      </div>
      <div className="hidden shrink-0 items-center gap-2 border-l px-4 font-mono text-[11px] uppercase tracking-wider text-muted-foreground lg:flex">
        <span className="size-1.5 bg-primary" />
        As of {asOf ?? "unknown"}
      </div>
    </div>
  );
}
