"use client";

import { Fragment, useState } from "react";
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

type Mode = "boosterBox" | "etb";

export type RipScoreRow = {
  setName: string;
  releaseDate: string | null;
  series: string | null;
  productPrice: number;
  boxEv: number;
  ripScore: number;
  evBreakdown: { rarity: string; ev: number; avgCardValue: number; expectedHits: number }[];
};

function getScoreColor(score: number): string {
  if (score >= 1.2) return "text-green-400";
  if (score >= 1.0) return "text-emerald-400";
  if (score >= 0.8) return "text-yellow-400";
  if (score >= 0.5) return "text-orange-400";
  return "text-red-400";
}

function getScoreBg(score: number): string {
  if (score >= 1.2) return "bg-green-500/10";
  if (score >= 1.0) return "bg-emerald-500/10";
  if (score >= 0.8) return "bg-yellow-500/10";
  if (score >= 0.5) return "bg-orange-500/10";
  return "bg-red-500/10";
}

function getVerdict(score: number): string {
  if (score >= 1.2) return "Strong Rip";
  if (score >= 1.0) return "Slight Edge";
  if (score >= 0.8) return "Marginal";
  if (score >= 0.5) return "Hold Sealed";
  return "Sealed Premium";
}

export function RipScoreCard({
  boxData,
  etbData,
}: {
  boxData: RipScoreRow[];
  etbData: RipScoreRow[];
}) {
  const [mode, setMode] = useState<Mode>("boosterBox");
  const [expandedSet, setExpandedSet] = useState<string | null>(null);

  const data = mode === "boosterBox" ? boxData : etbData;
  const sorted = [...data].sort((a, b) => b.ripScore - a.ripScore);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <div>
            <CardTitle className="text-sm">Box EV / Rip Score</CardTitle>
            <CardDescription>
              Expected value per box based on pull rates and card values.
              Score &gt; 1.0 = positive EV.
            </CardDescription>
          </div>
          <div className="flex gap-1 rounded-lg border border-border p-0.5">
            <button
              onClick={() => setMode("boosterBox")}
              className={`rounded-md px-3 py-1 text-xs transition-colors ${
                mode === "boosterBox"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Booster Box
            </button>
            <button
              onClick={() => setMode("etb")}
              className={`rounded-md px-3 py-1 text-xs transition-colors ${
                mode === "etb"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              ETB
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8 text-center">#</TableHead>
              <TableHead>Set</TableHead>
              <TableHead className="text-right">
                {mode === "boosterBox" ? "Box" : "ETB"} Price
              </TableHead>
              <TableHead className="text-right">Box EV</TableHead>
              <TableHead className="text-right">Rip Score</TableHead>
              <TableHead className="text-right">Verdict</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="text-center text-muted-foreground"
                >
                  No sets with both pull rates and rarity values.
                </TableCell>
              </TableRow>
            ) : (
              sorted.map((row, i) => {
                const isExpanded = expandedSet === row.setName;
                return (
                  <Fragment key={row.setName}>
                    <TableRow
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() =>
                        setExpandedSet(isExpanded ? null : row.setName)
                      }
                    >
                      <TableCell className="text-center text-muted-foreground text-xs">
                        {i + 1}
                      </TableCell>
                      <TableCell className="font-medium text-sm">
                        <span
                          className={`inline-flex items-center justify-center w-5 h-5 mr-2 rounded text-xs transition-transform ${
                            isExpanded
                              ? "bg-primary/20 text-primary"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {isExpanded ? "−" : "+"}
                        </span>
                        {row.setName}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        $
                        {row.productPrice.toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        $
                        {row.boxEv.toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </TableCell>
                      <TableCell
                        className={`text-right font-mono text-sm font-bold ${getScoreColor(row.ripScore)}`}
                      >
                        {row.ripScore.toFixed(2)}
                      </TableCell>
                      <TableCell
                        className={`text-right text-sm font-medium ${getScoreColor(row.ripScore)}`}
                      >
                        <span
                          className={`inline-block rounded px-1.5 py-0.5 text-xs ${getScoreBg(row.ripScore)}`}
                        >
                          {getVerdict(row.ripScore)}
                        </span>
                      </TableCell>
                    </TableRow>
                    {isExpanded && (
                      <TableRow>
                        <TableCell colSpan={6} className="p-0">
                          <div className="bg-muted/30 px-6 py-3 space-y-2">
                            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                              EV Breakdown by Rarity (
                              {mode === "boosterBox" ? "36" : "9"} packs)
                            </p>
                            <div className="space-y-1.5">
                              {row.evBreakdown
                                .filter((b) => b.ev > 0.01)
                                .sort((a, b) => b.ev - a.ev)
                                .map((b) => {
                                  const pct =
                                    row.boxEv > 0
                                      ? (b.ev / row.boxEv) * 100
                                      : 0;
                                  return (
                                    <div
                                      key={b.rarity}
                                      className="flex items-center gap-3 text-xs"
                                    >
                                      <span className="w-[180px] truncate text-muted-foreground">
                                        {b.rarity}
                                      </span>
                                      <div className="flex-1 h-3 bg-muted rounded overflow-hidden">
                                        <div
                                          className="h-full bg-primary/60 rounded"
                                          style={{
                                            width: `${Math.min(pct, 100)}%`,
                                          }}
                                        />
                                      </div>
                                      <span className="w-[70px] text-right font-mono">
                                        $
                                        {b.ev.toLocaleString(undefined, {
                                          minimumFractionDigits: 2,
                                          maximumFractionDigits: 2,
                                        })}
                                      </span>
                                      <span className="w-[45px] text-right text-muted-foreground">
                                        {pct.toFixed(1)}%
                                      </span>
                                      <span className="w-[100px] text-right text-muted-foreground">
                                        {b.expectedHits.toFixed(1)} hits @
                                        ${b.avgCardValue.toFixed(2)}
                                      </span>
                                    </div>
                                  );
                                })}
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })
            )}
          </TableBody>
        </Table>
        <div className="flex items-center gap-4 px-4 py-2 text-[10px] text-muted-foreground border-t border-border">
          <span>Click a row to see per-rarity EV breakdown</span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-green-400" />
            &ge;1.2 Strong Rip
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400" />
            1.0-1.2 Edge
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-yellow-400" />
            0.8-1.0 Marginal
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-orange-400" />
            0.5-0.8 Hold
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-red-400" />
            &lt;0.5 Sealed
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
