"use client";

import { useRef, useState, type MouseEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface HoverGlowButtonProps {
  children: ReactNode;
  className?: string;
  glowColor?: string;
  variant?: "primary" | "outline";
}

export function HoverGlowButton({
  children,
  className,
  glowColor = "#E8561C",
  variant = "primary",
}: HoverGlowButtonProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState({ x: 50, y: 50 });
  const [hovered, setHovered] = useState(false);

  const handleMouseMove = (e: MouseEvent<HTMLSpanElement>) => {
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      setPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    }
  };

  return (
    <span
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={cn(
        "relative inline-flex cursor-pointer items-center justify-center overflow-hidden rounded-lg px-6 py-3 text-sm font-semibold transition-colors duration-300",
        variant === "primary" &&
          "border border-orange-500/30 bg-orange-600/10 text-foreground hover:text-white",
        variant === "outline" &&
          "border border-border bg-transparent text-foreground hover:text-white",
        className
      )}
    >
      <span
        className="pointer-events-none absolute rounded-full transition-transform duration-500 ease-out"
        style={{
          left: pos.x,
          top: pos.y,
          width: 200,
          height: 200,
          transform: `translate(-50%, -50%) scale(${hovered ? 1.5 : 0})`,
          background: `radial-gradient(circle, ${glowColor} 0%, transparent 70%)`,
          opacity: 0.5,
        }}
      />
      <span className="relative z-10">{children}</span>
    </span>
  );
}
