import Link from "next/link";
import { SignalBadge } from "@/components/signal-badge";
import { formatPrice, formatPct, getPctColor } from "@/lib/signals";
import { Badge } from "@/components/ui/badge";
import type { ProductAnalytics } from "@/types/database";

export function ProductCardMobile({ product }: { product: ProductAnalytics }) {
  const p = product;

  return (
    <Link href={`/products/${p.product_id}`} className="block">
      <div className="rounded-lg border border-border bg-card p-4 transition-colors active:bg-muted/50">
        {/* Top row: Name + Signal */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="font-medium text-sm truncate">{p.product_name}</p>
            <p className="text-xs text-muted-foreground truncate mt-0.5">
              {p.set_name}
            </p>
          </div>
          <SignalBadge
            score={p.signal_score}
            recommendation={p.signal_recommendation}
          />
        </div>

        {/* Bottom row: Price + Change + Type */}
        <div className="flex items-end justify-between mt-3">
          <div>
            <p className="text-lg font-mono font-bold tabular-nums">
              {formatPrice(p.current_price)}
            </p>
            <span
              className={`text-xs font-mono ${getPctColor(p.price_change_7d_pct)}`}
            >
              {formatPct(p.price_change_7d_pct)} 7d
            </span>
          </div>
          <Badge
            variant="outline"
            className="text-[10px] text-muted-foreground"
          >
            {p.product_type}
          </Badge>
        </div>
      </div>
    </Link>
  );
}
