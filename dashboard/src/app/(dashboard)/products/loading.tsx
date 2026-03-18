import { Card, CardContent, CardHeader } from "@/components/ui/card";

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-muted/50 ${className ?? ""}`} />;
}

export default function ProductsLoading() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-32 mb-2" />
        <Skeleton className="h-4 w-48" />
      </div>

      {/* Filter bar */}
      <div className="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center">
        <Skeleton className="h-8 w-full md:w-[220px]" />
        <Skeleton className="h-8 w-full md:w-[140px]" />
        <Skeleton className="h-8 w-full md:w-[170px]" />
        <Skeleton className="h-8 w-full md:w-[180px]" />
        <Skeleton className="h-8 w-full md:w-[200px]" />
      </div>

      {/* Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-3 w-16" />
        </CardHeader>
        <CardContent className="space-y-2">
          {Array.from({ length: 15 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
