import { createClient } from "@/lib/supabase/server";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Link from "next/link";
import type { Alert } from "@/types/database";

export const revalidate = 60;

const ALERT_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  strong_buy: { label: "Strong Buy", color: "border-emerald-500/30 text-emerald-400" },
  buy: { label: "Buy", color: "border-green-500/30 text-green-400" },
  sell: { label: "Sell", color: "border-red-500/30 text-red-400" },
  strong_sell: { label: "Strong Sell", color: "border-red-600/30 text-red-500" },
  price_drop: { label: "Price Drop", color: "border-orange-500/30 text-orange-400" },
  price_spike: { label: "Price Spike", color: "border-blue-500/30 text-blue-400" },
  new_low: { label: "New Low", color: "border-amber-500/30 text-amber-400" },
  volume_spike: { label: "Volume Spike", color: "border-purple-500/30 text-purple-400" },
  end_of_print: { label: "End of Print", color: "border-pink-500/30 text-pink-400" },
};

export default async function AlertsPage() {
  const supabase = await createClient();

  const { data: alerts } = await supabase
    .from("alerts")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(100)
    .returns<Alert[]>();

  const items: Alert[] = alerts ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Alerts</h1>
        <p className="text-sm text-muted-foreground">
          Price and signal alert history
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">
            Recent Alerts ({items.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Product</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Message</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={4}
                    className="text-center text-muted-foreground"
                  >
                    No alerts yet. Alerts are generated after running the signal
                    engine.
                  </TableCell>
                </TableRow>
              ) : (
                items.map((alert) => {
                  const typeInfo = ALERT_TYPE_LABELS[alert.alert_type] ?? {
                    label: alert.alert_type,
                    color: "border-muted-foreground/30 text-muted-foreground",
                  };

                  return (
                    <TableRow key={alert.id}>
                      <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                        {new Date(alert.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        {alert.product_id ? (
                          <Link
                            href={`/products/${alert.product_id}`}
                            className="font-medium hover:underline"
                          >
                            View Product
                          </Link>
                        ) : (
                          <span className="text-muted-foreground">--</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${typeInfo.color}`}
                        >
                          {typeInfo.label}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        {alert.message ?? "--"}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
