"use client";

import Link from "next/link";
import { ProductThumb } from "@/components/product-thumb";

interface ProductCellProps {
  productId: string;
  tcgplayerProductId: number | null;
  imageUrl?: string | null;
  name: string;
  /** Muted second line, e.g. "SSP · Booster Box". */
  subtitle?: string;
  size?: number;
}

/** Table product cell: photo + name link (+ optional subtitle). */
export function ProductHoverImage({ productId, tcgplayerProductId, imageUrl, name, subtitle, size = 40 }: ProductCellProps) {
  return (
    <Link href={`/products/${productId}`} className="group flex items-center gap-3 whitespace-normal">
      <ProductThumb tcgplayerProductId={tcgplayerProductId} imageUrl={imageUrl} name={name} size={size} />
      <span className="min-w-0">
        <span className="block text-[13px] font-medium leading-snug group-hover:text-primary">{name}</span>
        {subtitle && <span className="block font-mono text-[11px] uppercase tracking-wide text-muted-foreground">{subtitle}</span>}
      </span>
    </Link>
  );
}
