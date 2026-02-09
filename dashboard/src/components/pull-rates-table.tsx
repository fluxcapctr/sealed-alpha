"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Era = "sv" | "swsh" | "sm";

export type PullRateRow = {
  setName: string;
  releaseDate: string | null;
  series: string | null;
  rates: Record<string, { packsPerHit: number; cardsInSet: number | null }>;
};

// Rarity columns per era (in display order)
const ERA_COLUMNS: Record<Era, string[]> = {
  sv: [
    "Double Rare",
    "Ultra Rare",
    "ACE SPEC Rare",
    "Illustration Rare",
    "Special Illustration Rare",
    "Hyper Rare",
    "Shiny Rare",
    "Shiny Ultra Rare",
    "Poké Ball Foil",
    "Master Ball Foil",
  ],
  swsh: [
    "V",
    "VMAX/VSTAR",
    "Full Art V",
    "Full Art Pokemon",
    "Full Art Trainer",
    "Alt Art",
    "Alt Art VMAX",
    "Trainer Gallery",
    "Radiant Rare",
    "Rainbow Rare",
    "Secret Rare (Gold)",
    "Shiny Rare",
    "Shiny V/VMAX",
  ],
  sm: [
    "GX",
    "Full Art Pokemon",
    "Full Art Trainer",
    "Rainbow Rare",
    "Secret Rare (Gold)",
    "Secret Rare (Character)",
    "Prism Star",
    "Shiny",
    "Shiny Rare",
    "Shiny GX",
  ],
};

// Short column labels for tighter display
const SHORT_LABELS: Record<string, string> = {
  "Double Rare": "DR",
  "Ultra Rare": "UR",
  "ACE SPEC Rare": "ACE",
  "Illustration Rare": "IR",
  "Special Illustration Rare": "SIR",
  "Hyper Rare": "HR",
  "Shiny Rare": "Shiny",
  "Shiny Ultra Rare": "Shiny UR",
  "Poké Ball Foil": "Poké",
  "Master Ball Foil": "Master",
  "VMAX/VSTAR": "VMAX",
  "Full Art V": "FA V",
  "Full Art Pokemon": "FA Pkm",
  "Full Art Trainer": "FA Trn",
  "Alt Art": "Alt",
  "Alt Art VMAX": "Alt VX",
  "Trainer Gallery": "TG",
  "Radiant Rare": "Radiant",
  "Rainbow Rare": "RR",
  "Secret Rare (Gold)": "Gold",
  "Secret Rare (Character)": "Char",
  "Shiny V/VMAX": "Shiny V",
  "Shiny GX": "Shiny GX",
  "Prism Star": "Prism",
  "Signature Trainer": "Sig Trn",
  "Galarian Gallery": "GG",
  "Foil Energy": "Foil E",
  "Amazing Rare": "Amaze",
  "Rare Holo": "Holo",
};

const ERA_LABELS: Record<Era, string> = {
  sv: "Scarlet & Violet",
  swsh: "Sword & Shield",
  sm: "Sun & Moon",
};

const ERA_SERIES: Record<Era, string[]> = {
  sv: ["Scarlet & Violet"],
  swsh: ["Sword & Shield"],
  sm: ["Sun & Moon"],
};

function getRateColor(rate: number): string {
  if (rate <= 10) return "text-green-400";
  if (rate <= 30) return "text-yellow-400";
  if (rate <= 80) return "text-orange-400";
  return "text-red-400";
}

function getRateBg(rate: number): string {
  if (rate <= 10) return "bg-green-500/10";
  if (rate <= 30) return "bg-yellow-500/10";
  if (rate <= 80) return "bg-orange-500/10";
  return "bg-red-500/10";
}

export function PullRatesTable({ data }: { data: PullRateRow[] }) {
  const [era, setEra] = useState<Era>("sv");

  // Filter sets by era series
  const eraData = data.filter((row) =>
    ERA_SERIES[era].some((s) => row.series === s)
  );

  // Sort by release date (newest first)
  const sorted = [...eraData].sort((a, b) => {
    const da = a.releaseDate ?? "";
    const db = b.releaseDate ?? "";
    return db.localeCompare(da);
  });

  // Get all rarity columns that actually have data for this era
  const allColumns = ERA_COLUMNS[era];
  const activeColumns = allColumns.filter((col) =>
    sorted.some((row) => row.rates[col])
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <div>
            <CardTitle className="text-sm">Pull Rates by Set</CardTitle>
            <CardDescription>
              How many packs to open (on average) per hit — lower is better.
            </CardDescription>
          </div>
          <div className="flex gap-1 rounded-lg border border-border p-0.5">
            {(["sv", "swsh", "sm"] as Era[]).map((e) => (
              <button
                key={e}
                onClick={() => setEra(e)}
                className={`rounded-md px-3 py-1 text-xs transition-colors ${
                  era === e
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {e.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="sticky left-0 bg-background z-10 min-w-[140px]">
                Set
              </TableHead>
              {activeColumns.map((col) => (
                <TableHead
                  key={col}
                  className="text-center text-xs px-2 min-w-[60px]"
                  title={col}
                >
                  {SHORT_LABELS[col] ?? col}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={activeColumns.length + 1}
                  className="text-center text-muted-foreground"
                >
                  No pull rate data for this era.
                </TableCell>
              </TableRow>
            ) : (
              sorted.map((row) => (
                <TableRow key={row.setName}>
                  <TableCell className="sticky left-0 bg-background z-10 font-medium text-sm whitespace-nowrap">
                    {row.setName}
                  </TableCell>
                  {activeColumns.map((col) => {
                    const rate = row.rates[col];
                    if (!rate) {
                      return (
                        <TableCell
                          key={col}
                          className="text-center text-muted-foreground/30 text-xs"
                        >
                          —
                        </TableCell>
                      );
                    }
                    return (
                      <TableCell
                        key={col}
                        className={`text-center font-mono text-xs px-2 ${getRateBg(rate.packsPerHit)}`}
                        title={`${col}: 1 in ${rate.packsPerHit} packs${rate.cardsInSet ? ` (${rate.cardsInSet} cards)` : ""}`}
                      >
                        <span className={getRateColor(rate.packsPerHit)}>
                          {rate.packsPerHit % 1 === 0
                            ? rate.packsPerHit
                            : rate.packsPerHit.toFixed(1)}
                        </span>
                        {rate.cardsInSet !== null && (
                          <span className="block text-[10px] text-muted-foreground">
                            {rate.cardsInSet}
                          </span>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <div className="flex items-center gap-4 px-4 py-2 text-[10px] text-muted-foreground border-t border-border">
          <span>Top number = packs per hit</span>
          <span>Bottom number = cards of that rarity in set</span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-green-400" />
            ≤10
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-yellow-400" />
            11-30
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-orange-400" />
            31-80
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-red-400" />
            80+
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
