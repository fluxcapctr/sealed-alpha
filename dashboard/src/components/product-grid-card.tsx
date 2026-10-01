import Link from "next/link";
import { ProductThumb } from "@/components/product-thumb";
import { SignalMeter } from "@/components/signal-meter";
import { formatPrice, formatPct, getPctColor } from "@/lib/signals";
import { typeCode } from "@/lib/market";
import type { ProductAnalytics } from "@/types/database";

/** Image-first card for the grid view. The photo leads, but price, both trends and the verdict stay on the card. */
export function ProductGridCard({ product: p }: { product: ProductAnalytics }) {
  return (
    <Link
      href={`/products/${p.product_id}`}
      className="group flex flex-col overflow-hidden rounded-md border border-border bg-card transition-colors hover:border-primary/50 focus-visible:border-primary focus-visible:outline-none"
    >
      <div className="relative bg-background/50 p-3">
        <ProductThumb
          fill
          size={200}
          tcgplayerProductId={p.tcgplayer_product_id}
          imageUrl={p.product_image}
          name={p.product_name}
          className="transition-transform duration-150 group-hover:scale-[1.04]"
        />
        <span className="absolute left-2 top-2 rounded-sm bg-background/80 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          {typeCode(p.product_type)}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2 border-t border-border p-3">
        <div>
          <p className="line-clamp-2 min-h-[2.4em] text-[13px] font-medium leading-snug group-hover:text-primary">{p.product_name}</p>
          <p className="mt-0.5 truncate font-mono text-[10.5px] uppercase tracking-wide text-muted-foreground">{p.set_code ?? p.set_name}</p>
        </div>
        <div className="mt-auto flex items-end justify-between gap-2">
          <p className="text-base font-semibold tabular-nums">{formatPrice(p.current_price)}</p>
          <div className="text-right font-mono text-[11px] leading-snug tabular-nums">
            <p className={getPctColor(p.price_change_7d_pct)}>
              {formatPct(p.price_change_7d_pct)} <span className="text-muted-foreground">7d</span>
            </p>
            <p className={getPctColor(p.price_change_30d_pct)}>
              {formatPct(p.price_change_30d_pct)} <span className="text-muted-foreground">30d</span>
            </p>
          </div>
        </div>
        <SignalMeter score={p.signal_score} recommendation={p.signal_recommendation} showLabel="score" block={4} />
      </div>
    </Link>
  );
}
