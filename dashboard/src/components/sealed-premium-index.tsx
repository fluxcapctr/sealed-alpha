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
import type { BoxValueData } from "@/components/booster-box-value-chart";

type Mode = "boosterBox" | "etb";

function getVerdict(ratio: number): {
  label: string;
  className: string;
} {
  if (ratio < 0.3) return { label: "Great Rip", className: "text-green-400" };
  if (ratio < 0.5) return { label: "Fair", className: "text-yellow-400" };
  if (ratio < 0.75)
    return { label: "Hold Sealed", className: "text-orange-400" };
  return { label: "Sealed Premium", className: "text-red-400" };
}

export function SealedPremiumIndex({
  boxData,
  etbData,
}: {
  boxData: BoxValueData[];
  etbData: BoxValueData[];
}) {
  const [mode, setMode] = useState<Mode>("boosterBox");

  const data = mode === "boosterBox" ? boxData : etbData;
  const sorted = [...data].sort((a, b) => a.ratio - b.ratio);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <div>
            <CardTitle className="text-sm">Sealed Premium Index</CardTitle>
            <CardDescription>
              Sets ranked by rip value — lower ratio means card value exceeds
              sealed price.
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
              <TableHead className="text-right">Master Set</TableHead>
              <TableHead className="text-right">Ratio</TableHead>
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
                  No data available.
                </TableCell>
              </TableRow>
            ) : (
              sorted.map((row, i) => {
                const verdict = getVerdict(row.ratio);
                return (
                  <TableRow key={row.setName}>
                    <TableCell className="text-center text-muted-foreground text-xs">
                      {i + 1}
                    </TableCell>
                    <TableCell className="font-medium text-sm">
                      {row.setName}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      ${row.productPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      ${row.masterSet.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {(row.ratio * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell
                      className={`text-right text-sm font-medium ${verdict.className}`}
                    >
                      {verdict.label}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
