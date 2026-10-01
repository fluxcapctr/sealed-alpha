import Link from "next/link";
import { ChevronRight } from "lucide-react";

export interface Crumb {
  label: string;
  href?: string;
}

const LANGUAGE_LABELS: Record<string, string> = { en: "English", ja: "Japanese" };

/** Language crumb: links to the sets list filtered to that language. */
export function languageCrumb(language: string | null | undefined): Crumb {
  const lang = language ?? "en";
  return {
    label: LANGUAGE_LABELS[lang] ?? lang.toUpperCase(),
    href: lang === "en" ? "/sets" : `/sets?lang=${lang}`,
  };
}

/** Small TCGPlayer-style trail, e.g. English > 151 > Booster Box. The last crumb is the current page. */
export function Breadcrumb({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="font-mono text-[11px] text-muted-foreground">
      <ol className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-1">
        {items.map((c, i) => {
          const last = i === items.length - 1;
          return (
            <li key={i} className="flex min-w-0 items-center gap-x-1.5">
              {last || !c.href ? (
                <span aria-current={last ? "page" : undefined} className={last ? "truncate text-foreground" : "truncate"}>
                  {c.label}
                </span>
              ) : (
                <Link href={c.href} className="truncate hover:text-primary">
                  {c.label}
                </Link>
              )}
              {!last && <ChevronRight aria-hidden className="size-3 shrink-0 opacity-60" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
