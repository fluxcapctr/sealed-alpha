import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { InfoTip } from "@/components/info-tip";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon?: LucideIcon;
  tooltip?: React.ReactNode;
  trend?: {
    value: string;
    positive: boolean;
  };
}

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  tooltip,
  trend,
}: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between p-4">
        <div className="space-y-1">
          {tooltip ? (
            <InfoTip
              label={<span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{title}</span>}
              side="bottom"
            >
              {tooltip}
            </InfoTip>
          ) : (
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {title}
            </p>
          )}
          <p className="text-2xl font-bold tabular-nums">{value}</p>
          {trend && (
            <p
              className={cn(
                "text-xs font-medium",
                trend.positive ? "text-green-400" : "text-red-400"
              )}
            >
              {trend.value}
            </p>
          )}
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
        {Icon && (
          <div className="rounded-lg bg-primary/10 p-2">
            <Icon className="h-5 w-5 text-primary" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
