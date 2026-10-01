"use client";

import { useState } from "react";
import { Bell, Check } from "lucide-react";
import { Button } from "@/components/ui/button";

const RULES = [
  { id: "signal", label: "Verdict flips to buy or sell" },
  { id: "drop", label: "Price falls 10% or more in a week" },
  { id: "low", label: "New 90-day low" },
  { id: "print", label: "Set leaves print" },
];

/** Email capture at the moment it is useful: "tell me when this product changes". UI only; storage is not wired up. */
export function WatchButton({ productName }: { productName: string }) {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(false);
  const [email, setEmail] = useState("");

  return (
    <div className="relative">
      <Button type="button" size="sm" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="font-mono text-xs uppercase tracking-wider">
        <Bell className="size-3.5" /> Watch
      </Button>
      {open && (
        <div className="absolute right-0 top-10 z-30 w-[22rem] max-w-[calc(100vw-2rem)] rounded-md border bg-popover p-4 shadow-2xl shadow-black/50">
          {done ? (
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex size-5 items-center justify-center rounded-sm bg-emerald-400/15 text-emerald-400"><Check className="size-3.5" /></span>
              <p className="text-sm">Watching <b>{productName}</b>. You will get an email when any of your alerts fire.</p>
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setDone(true);
              }}
              className="space-y-3"
            >
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-muted-foreground">Alert me when</p>
              <div className="space-y-2">
                {RULES.map((r, i) => (
                  <label key={r.id} className="flex cursor-pointer items-center gap-2 text-sm">
                    <input type="checkbox" defaultChecked={i < 2} className="size-3.5 accent-[var(--primary)]" />
                    {r.label}
                  </label>
                ))}
              </div>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                aria-label="Email address"
                className="h-9 w-full rounded-sm border bg-background px-3 text-sm outline-none focus:border-primary"
              />
              <Button type="submit" className="w-full font-mono text-xs uppercase tracking-wider">Start watching</Button>
              <p className="text-[11px] text-muted-foreground">One email per change. Unsubscribe in one click.</p>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
