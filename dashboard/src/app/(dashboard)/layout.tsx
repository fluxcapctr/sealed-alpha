import { Sidebar, MobileSidebar } from "@/components/sidebar";
import { TopBar, type TickerItem } from "@/components/top-bar";
import { createClient } from "@/lib/supabase/server";
import { getAsOf, typeCode } from "@/lib/market";
import type { ProductAnalytics } from "@/types/database";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const { data } = await supabase
    .from("product_analytics")
    .select("product_id, set_code, product_type, current_price, price_change_7d_pct, total_price_points, last_price_date")
    .returns<Pick<ProductAnalytics, "product_id" | "set_code" | "product_type" | "current_price" | "price_change_7d_pct" | "total_price_points" | "last_price_date">[]>();
  const rows = data ?? [];
  const items: TickerItem[] = rows
    .filter((p) => p.price_change_7d_pct != null && (p.current_price ?? 0) >= 30 && (p.total_price_points ?? 0) >= 10 && Math.abs(p.price_change_7d_pct) <= 200)
    .sort((a, b) => Math.abs(b.price_change_7d_pct!) - Math.abs(a.price_change_7d_pct!))
    .slice(0, 14)
    .map((p) => ({ id: p.product_id, code: p.set_code ?? "", label: typeCode(p.product_type), price: p.current_price!, pct: p.price_change_7d_pct! }));

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <MobileSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar items={items} asOf={getAsOf(rows)} />
        <main className="relative flex-1 overflow-y-auto overflow-x-hidden p-4 pt-16 md:p-6 md:pt-6">
          {children}
          <footer className="mt-12 border-t border-border px-1 py-6 text-center text-xs text-muted-foreground">
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
        </main>
      </div>
    </div>
  );
}
