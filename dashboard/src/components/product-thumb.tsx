"use client";

import { useState } from "react";
import { Package } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Product photo. TCGPlayer's photos are studio shots on pure white, so they are shown as a white tile on the dark page.
 * Uses `imageUrl` (products.image_url) when set, falls back to the CDN URL derived from the TCGPlayer product id,
 * then to a placeholder tile.
 */
export function ProductThumb({
  tcgplayerProductId,
  imageUrl,
  name,
  size = 40,
  fill = false,
  className,
}: {
  tcgplayerProductId: number | null;
  imageUrl?: string | null;
  name: string;
  size?: number;
  /** Stretch to the parent's width as a square instead of using a fixed pixel size. */
  fill?: boolean;
  className?: string;
}) {
  const derived = tcgplayerProductId
    ? `https://product-images.tcgplayer.com/fit-in/${size > 100 ? 437 : 200}x${size > 100 ? 437 : 200}/${tcgplayerProductId}.jpg`
    : null;
  const sources = [imageUrl, derived].filter((s): s is string => !!s);
  const [i, setI] = useState(0);
  const box = fill ? undefined : { width: size, height: size };
  const shape = fill && "aspect-square w-full";

  if (i >= sources.length) {
    return (
      <span
        style={box}
        className={cn("flex shrink-0 items-center justify-center rounded-sm bg-muted text-muted-foreground", shape, className)}
      >
        <Package className="h-1/2 w-1/2" />
      </span>
    );
  }

  // The photo sits at 80% of the tile (10% white margin each side; sized, not padded, because CSS % padding follows the parent's width) so differently sized boxes never touch the edge.
  return (
    <span
      style={box}
      className={cn("flex shrink-0 items-center justify-center rounded-sm bg-white ring-1 ring-white/15", shape, className)}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={sources[i]}
        alt={name}
        loading="lazy"
        onError={() => setI((n) => n + 1)}
        className="h-4/5 w-4/5 object-contain"
      />
    </span>
  );
}
