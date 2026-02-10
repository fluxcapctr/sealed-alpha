"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";

interface ProductHoverImageProps {
  productId: string;
  tcgplayerProductId: number | null;
  name: string;
}

export function ProductHoverImage({
  productId,
  tcgplayerProductId,
  name,
}: ProductHoverImageProps) {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const ref = useRef<HTMLDivElement>(null);

  const imageUrl = tcgplayerProductId
    ? `https://product-images.tcgplayer.com/fit-in/200x200/${tcgplayerProductId}.jpg`
    : null;

  const handleEnter = useCallback(() => {
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      // Show above the element; if too close to top, show below
      const showAbove = rect.top > 220;
      setPos({
        top: showAbove ? rect.top - 210 : rect.bottom + 4,
        left: rect.left,
      });
    }
    setShow(true);
  }, []);

  return (
    <div
      ref={ref}
      className="relative inline-block"
      onMouseEnter={handleEnter}
      onMouseLeave={() => setShow(false)}
    >
      <Link
        href={`/products/${productId}`}
        className="font-medium hover:underline"
      >
        {name}
      </Link>
      {show && imageUrl && (
        <div
          className="fixed z-50 rounded-lg border border-border bg-card p-1 shadow-xl pointer-events-none"
          style={{ top: pos.top, left: pos.left }}
        >
          <img
            src={imageUrl}
            alt={name}
            width={200}
            height={200}
            className="rounded"
            loading="eager"
          />
        </div>
      )}
    </div>
  );
}
