"use client";

import { cn } from "@/lib/utils";

/* A tooltip that stays on the chart.
 *
 * Positioned in percentages of the plot box, so it needs no measurement and
 * survives a resize. It flips to the other side of the cursor near an edge,
 * because a tooltip clipped by the container is worse than no tooltip: the
 * reader knows something was there and cannot get at it.
 *
 * pointer-events-none throughout. A tooltip that can intercept the pointer
 * fights the chart it is describing.
 */

export type TipRow = { label: string; value: string; quiet?: boolean };

export function ChartTooltip({
  x, y, title, subtitle, rows, footer,
}: {
  /** 0 to 100, as a percentage of the plot box. */
  x: number;
  y: number;
  title: string;
  subtitle?: string;
  rows: TipRow[];
  footer?: string;
}) {
  const flipX = x > 62;
  const flipY = y < 32;

  return (
    <div
      className="pointer-events-none absolute z-20"
      style={{
        left: `${x}%`,
        top: `${y}%`,
        transform: `translate(${flipX ? "calc(-100% - 14px)" : "14px"}, ${
          flipY ? "8px" : "calc(-100% - 8px)"
        })`,
      }}
    >
      <div className="bg-popover text-popover-foreground min-w-44 rounded-lg border p-3 shadow-lg">
        <p className="font-mono text-xs font-medium">{title}</p>
        {subtitle && (
          <p className="text-muted-foreground mt-0.5 text-[11px] leading-relaxed">
            {subtitle}
          </p>
        )}
        <dl className="mt-2 space-y-1">
          {rows.map((r) => (
            <div key={r.label} className="flex items-baseline justify-between gap-4">
              <dt className="text-muted-foreground text-[11px]">{r.label}</dt>
              <dd
                className={cn(
                  "font-mono text-[11px] tabular-nums",
                  r.quiet && "text-muted-foreground",
                )}
              >
                {r.value}
              </dd>
            </div>
          ))}
        </dl>
        {footer && (
          <p className="text-muted-foreground mt-2 border-t pt-2 text-[10px] leading-relaxed">
            {footer}
          </p>
        )}
      </div>
    </div>
  );
}
