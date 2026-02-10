"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Package,
  Layers,
  BarChart3,
  Bell,
  Menu,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LogoutButton } from "@/components/logout-button";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

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
      {/* Logo */}
      <Link
        href="/overview"
        onClick={onNavigate}
        className="flex items-center justify-center border-b border-border px-4 py-4"
      >
        <Image
          src="/logo-sealed-alpha.png"
          alt="Pokemon Sealed Tracker"
          width={102}
          height={131}
          className="h-auto w-[102px] rotate-[20deg] transition-transform duration-200 hover:-translate-y-1"
          priority
        />
      </Link>

      {/* Nav */}
      <nav className="flex-1 space-y-1 px-2 py-4">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-border px-4 py-3">
        <p className="text-[10px] text-muted-foreground">
          Data from TCGPlayer
        </p>
        <LogoutButton />
      </div>
    </>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden md:flex h-screen w-56 flex-col border-r border-border bg-card">
      <SidebarContent />
    </aside>
  );
}

export function MobileSidebar() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Fixed top bar on mobile */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 flex items-center border-b border-border bg-card px-4 h-14">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setOpen(true)}
        >
          <Menu className="h-5 w-5" />
          <span className="sr-only">Open menu</span>
        </Button>
        <Link href="/overview" className="ml-2">
          <Image
            src="/logo-sealed-alpha.png"
            alt="Sealed Alpha"
            width={32}
            height={41}
            className="h-8 w-auto rotate-[20deg]"
            unoptimized
          />
        </Link>
      </div>

      {/* Sheet overlay */}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-56 p-0 bg-card">
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
