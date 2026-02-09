"use client";

import { Info } from "lucide-react";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";

export function InfoTip({
  children,
  label,
  side = "top",
}: {
  children: React.ReactNode;
  label: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
}) {
  return (
    <HoverCard openDelay={100} closeDelay={200}>
      <HoverCardTrigger asChild>
        <span className="inline-flex items-center gap-1 cursor-help">
          {label}
          <Info className="h-3 w-3 text-muted-foreground/60" />
        </span>
      </HoverCardTrigger>
      <HoverCardContent side={side} className="text-xs leading-relaxed">
        {children}
      </HoverCardContent>
    </HoverCard>
  );
}
