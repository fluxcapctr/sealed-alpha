import Link from "next/link";
import { LayoutGrid, Rows3 } from "lucide-react";
import { cn } from "@/lib/utils";

export type ProductView = "list" | "grid";

/** `?view=grid` opts into the image grid; anything else is the dense list. */
export function parseView(value: string | undefined): ProductView {
  return value === "grid" ? "grid" : "list";
}

const OPTIONS = [
  { value: "list", label: "List", Icon: Rows3 },
  { value: "grid", label: "Grid", Icon: LayoutGrid },
] as const;

/**
 * List / Grid switch for the product catalog. Plain links, so it keeps every filter and sort already in the URL,
 * works without JS and the chosen view is shareable. The default view (list) is left out of the URL.
 */
export function ViewToggle({ params, view }: { params: Record<string, string | undefined>; view: ProductView }) {
  const hrefFor = (next: ProductView) => {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v && k !== "view") sp.set(k, v);
    if (next !== "list") sp.set("view", next);
    const qs = sp.toString();
    return qs ? `/products?${qs}` : "/products";
  };

  return (
    <nav aria-label="Product view" className="inline-flex rounded-md border border-border p-0.5">
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = view === value;
        return (
          <Link
            key={value}
            href={hrefFor(value)}
            aria-current={active ? "true" : undefined}
            aria-label={`${label} view`}
            title={`${label} view`}
            className={cn(
              "inline-flex h-6 items-center gap-1.5 rounded-sm px-2 font-mono text-[11px] uppercase tracking-wide transition-colors",
              active ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            <span className="hidden sm:inline">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
