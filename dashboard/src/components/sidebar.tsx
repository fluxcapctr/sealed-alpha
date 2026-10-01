"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Package, Layers, BarChart3, Bell, Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

const NAV_ITEMS = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/products", label: "Products", icon: Package },
  { href: "/sets", label: "Sets", icon: Layers },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/alerts", label: "Alerts", icon: Bell },
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <>
      <Link href="/overview" onClick={onNavigate} className="flex h-10 items-center border-b border-border px-4">
        <Image src="/sealed-alpha-wordmark.svg" alt="Sealed Alpha" width={140} height={20} className="h-[19px] w-auto" priority unoptimized />
      </Link>

      <nav className="flex-1 space-y-0.5 px-2 py-3">
        <p className="px-3 pb-2 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/70">Markets</p>
        {NAV_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "relative flex items-center gap-3 rounded-sm px-3 py-2 text-[13px] font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary before:absolute before:left-0 before:top-1/2 before:h-4 before:w-[3px] before:-translate-y-1/2 before:bg-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <item.icon className="size-4" strokeWidth={1.75} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border px-4 py-3 font-mono text-[10px] uppercase leading-relaxed tracking-wider text-muted-foreground">
        Source TCGPlayer
        <br />
        Not investment advice
      </div>
    </>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden h-screen w-52 shrink-0 flex-col border-r border-border bg-sidebar md:flex">
      <SidebarContent />
    </aside>
  );
}

export function MobileSidebar() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <div className="fixed left-0 right-0 top-0 z-40 flex h-12 items-center border-b border-border bg-sidebar px-3 md:hidden">
        <Button variant="ghost" size="icon" onClick={() => setOpen(true)}>
          <Menu className="size-5" />
          <span className="sr-only">Open menu</span>
        </Button>
        <Link href="/overview" className="ml-2">
          <Image src="/sealed-alpha-wordmark.svg" alt="Sealed Alpha" width={120} height={16} className="h-[16px] w-auto" unoptimized />
        </Link>
      </div>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-56 bg-sidebar p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Navigation</SheetTitle>
          </SheetHeader>
          <div className="flex h-full flex-col">
            <SidebarContent onNavigate={() => setOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
