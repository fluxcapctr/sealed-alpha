"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Package,
  Layers,
  TrendingUp,
  BarChart3,
  Bell,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LogoutButton } from "@/components/logout-button";

const NAV_ITEMS = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/products", label: "Products", icon: Package },
  { href: "/sets", label: "Sets", icon: Layers },
  { href: "/signals", label: "Signals", icon: TrendingUp },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/alerts", label: "Alerts", icon: Bell },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-56 flex-col border-r border-border bg-card">
      {/* Logo */}
      <Link href="/overview" className="flex items-center justify-center border-b border-border px-4 py-4">
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
    </aside>
  );
}
