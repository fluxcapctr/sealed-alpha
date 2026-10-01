import Link from "next/link";
import { SignalMeter } from "@/components/signal-meter";
import { ProductThumb } from "@/components/product-thumb";
import { formatPrice, formatPct, getPctColor } from "@/lib/signals";
import { typeCode } from "@/lib/market";
import type { ProductAnalytics } from "@/types/database";

export function ProductCardMobile({ product }: { product: ProductAnalytics }) {
  const p = product;
  return (
    <Link href={`/products/${p.product_id}`} className="block">
      <div className="flex gap-3 rounded-md border border-border bg-card p-3 transition-colors active:bg-accent">
        <ProductThumb tcgplayerProductId={p.tcgplayer_product_id} imageUrl={p.product_image} name={p.product_name} size={56} />
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-[13px] font-medium leading-snug">{p.product_name}</p>
          <p className="mt-0.5 font-mono text-[10.5px] uppercase tracking-wide text-muted-foreground">
            {p.set_code ?? p.set_name} &middot; {typeCode(p.product_type)}
          </p>
          <div className="mt-2 flex items-end justify-between gap-2">
            <div>
              <p className="text-base font-semibold tabular-nums">{formatPrice(p.current_price)}</p>
              <p className={`font-mono text-[11px] tabular-nums ${getPctColor(p.price_change_7d_pct)}`}>{formatPct(p.price_change_7d_pct)} 7d</p>
            </div>
            <SignalMeter score={p.signal_score} recommendation={p.signal_recommendation} showLabel="score" block={4} />
          </div>
        </div>
      </div>
    </Link>
  );
}
