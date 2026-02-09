"use client";

import { useState } from "react";
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

  const imageUrl = tcgplayerProductId
    ? `https://product-images.tcgplayer.com/fit-in/200x200/${tcgplayerProductId}.jpg`
    : null;

  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <Link
        href={`/products/${productId}`}
        className="font-medium hover:underline"
      >
        {name}
      </Link>
      {show && imageUrl && (
        <div className="absolute left-0 top-full z-50 mt-1 rounded-lg border border-border bg-card p-1 shadow-xl">
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
