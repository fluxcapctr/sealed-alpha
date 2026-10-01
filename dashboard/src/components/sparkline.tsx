import { cn } from "@/lib/utils";

/** Tiny inline price trend. Colour follows direction over the window; the last point is marked with a square. */
export function Sparkline({
  values,
  width = 76,
  height = 22,
  className,
}: {
  values: number[];
  width?: number;
  height?: number;
  className?: string;
}) {
  if (values.length < 2) return <span className="text-muted-foreground">--</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = 2;
  const x = (i: number) => pad + (i / (values.length - 1)) * (width - pad * 2);
  const y = (v: number) => height - pad - ((v - min) / span) * (height - pad * 2);
  const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  const up = values[values.length - 1] >= values[0];
  const color = up ? "var(--color-up)" : "var(--color-down)";
  const lastX = x(values.length - 1);
  const lastY = y(values[values.length - 1]);
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("block overflow-visible", className)}
      role="img"
      aria-label={`${values.length}-point price trend, ${up ? "up" : "down"}`}
    >
      <polygon points={`${pad},${height} ${pts.join(" ")} ${width - pad},${height}`} fill={color} opacity="0.12" />
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <rect x={lastX - 2} y={lastY - 2} width="4" height="4" fill={color} />
    </svg>
  );
}
