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
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
  PaginationEllipsis,
} from "@/components/ui/pagination";
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
  const [page, setPage] = useState(1);
  const perPage = 20;

  const data = mode === "boosterBox" ? boxData : etbData;
  const sorted = [...data].sort((a, b) => a.ratio - b.ratio);
  const totalPages = Math.max(1, Math.ceil(sorted.length / perPage));
  const currentPage = Math.min(page, totalPages);
  const paged = sorted.slice((currentPage - 1) * perPage, currentPage * perPage);

  const handleModeChange = (m: Mode) => {
    setMode(m);
    setPage(1);
  };

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
              onClick={() => handleModeChange("boosterBox")}
              className={`rounded-md px-3 py-1 text-xs transition-colors ${
                mode === "boosterBox"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Booster Box
            </button>
            <button
              onClick={() => handleModeChange("etb")}
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
            {paged.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="text-center text-muted-foreground"
                >
                  No data available.
                </TableCell>
              </TableRow>
            ) : (
              paged.map((row, i) => {
                const verdict = getVerdict(row.ratio);
                const rank = (currentPage - 1) * perPage + i + 1;
                return (
                  <TableRow key={row.setName}>
                    <TableCell className="text-center text-muted-foreground text-xs">
                      {rank}
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

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="py-4">
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      setPage((p) => Math.max(1, p - 1));
                    }}
                    className={currentPage <= 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                  />
                </PaginationItem>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => {
                  // Show first, last, and pages near current
                  if (
                    p === 1 ||
                    p === totalPages ||
                    (p >= currentPage - 1 && p <= currentPage + 1)
                  ) {
                    return (
                      <PaginationItem key={p}>
                        <PaginationLink
                          href="#"
                          isActive={p === currentPage}
                          onClick={(e) => {
                            e.preventDefault();
                            setPage(p);
                          }}
                          className="cursor-pointer"
                        >
                          {p}
                        </PaginationLink>
                      </PaginationItem>
                    );
                  }
                  // Show ellipsis at boundaries
                  if (p === currentPage - 2 || p === currentPage + 2) {
                    return (
                      <PaginationItem key={p}>
                        <PaginationEllipsis />
                      </PaginationItem>
                    );
                  }
                  return null;
                })}
                <PaginationItem>
                  <PaginationNext
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      setPage((p) => Math.min(totalPages, p + 1));
                    }}
                    className={currentPage >= totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
