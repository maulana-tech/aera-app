import { OriginBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";

export type Datum = {
  label: string;
  sub?: string;
  value: number;
  display: string;       // the value as it should read
  hatched?: boolean;     // fails a condition — marked by texture, not another colour
  tag?: string;          // short note on the right
  title?: string;        // shown when the cursor rests on the row
};

/** A single-series horizontal bar chart.
 *
 *  One hue only. Critical vs safe is carried by the threshold line, the row
 *  order, and direct labels — not by red/green: that pair is only ΔE 4.1 apart
 *  under deuteranopia, far below the floor of 8. */
export function Bars({
  data, threshold, thresholdLabel,
}: {
  data: Datum[];
  threshold?: number;
  thresholdLabel?: string;
}) {
  const max = Math.max(...data.map((d) => d.value), threshold ?? 0) || 1;
  const scale = (n: number) => `${Math.max((n / (max * 1.04)) * 100, 0.8)}%`;

  return (
    <div className="viz">
      <div className="space-y-0.5">
        {data.map((d, i) => (
          <div
            key={`${d.label}-${i}`}
            title={d.title}
            className="hover:bg-muted/40 flex items-center gap-3 rounded-md px-1.5 py-1.5"
          >
            <div className="w-32 shrink-0 sm:w-44">
              <p className="truncate text-xs font-medium leading-tight">{d.label}</p>
              {d.sub && (
                <p className="text-muted-foreground truncate font-mono text-[10px] leading-tight">
                  {d.sub}
                </p>
              )}
            </div>

            <div
              className="relative h-2.5 min-w-0 flex-1 rounded-full"
              style={{ background: "var(--viz-track)" }}
            >
              <div
                className="absolute inset-y-0 left-0 rounded-full"
                style={{
                  width: scale(d.value),
                  background: d.hatched
                    ? "repeating-linear-gradient(45deg, var(--viz-series) 0 2px, transparent 2px 5px)"
                    : "var(--viz-series)",
                  boxShadow: d.hatched ? "inset 0 0 0 1px var(--viz-series)" : undefined,
                }}
              />
              {threshold !== undefined && (
                <span
                  aria-hidden
                  className="absolute -inset-y-1 w-0 border-l border-dashed"
                  style={{ left: scale(threshold), borderColor: "var(--viz-rule)" }}
                />
              )}
            </div>

            <span className="w-20 shrink-0 text-right font-mono text-xs tabular-nums">
              {d.display}
            </span>
            <span className="text-muted-foreground hidden w-32 shrink-0 truncate text-[10px] sm:block">
              {d.tag}
            </span>
          </div>
        ))}
      </div>

      {threshold !== undefined && thresholdLabel && (
        <p className="text-muted-foreground mt-2.5 flex items-center gap-1.5 font-mono text-[10px]">
          <span
            className="inline-block h-0 w-4 border-t border-dashed"
            style={{ borderColor: "var(--viz-rule)" }}
          />
          {thresholdLabel}
        </p>
      )}
    </div>
  );
}

/** Chart wrapper: title, data origin, and a fallback table.
 *  The table is always there — the numbers must be readable even if the chart isn't. */
export function Figure({
  title, blurb, origin, source, note, empty, table, className, children,
}: {
  title: string;
  blurb?: string;
  origin?: string;
  source?: string | null;
  note?: string;
  empty?: string;
  table?: { head: string[]; rows: (string | number)[][] };
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <figure className={cn("rounded-xl border p-5", className)}>
      <figcaption className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-medium">{title}</h3>
          {blurb && (
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">{blurb}</p>
          )}
        </div>
        {origin && <OriginBadge origin={origin} source={source} />}
      </figcaption>

      {empty ? (
        <p className="text-muted-foreground mt-4 rounded-lg border border-dashed p-4 text-xs leading-relaxed">
          {empty}
        </p>
      ) : (
        <div className="mt-4">{children}</div>
      )}

      {note && !empty && (
        <p className="text-muted-foreground mt-3 text-xs leading-relaxed">{note}</p>
      )}

      {table && !empty && (
        <details className="mt-3">
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer font-mono text-[10px]">
            show the numbers as a table
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b">
                  {table.head.map((h, i) => (
                    <th
                      key={h}
                      className={cn(
                        "text-muted-foreground py-1.5 font-mono text-[10px] font-normal uppercase tracking-wider",
                        i === 0 ? "text-left" : "text-right",
                      )}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {table.rows.map((r, i) => (
                  <tr key={i}>
                    {r.map((c, j) => (
                      <td
                        key={j}
                        className={cn("py-1.5", j === 0 ? "text-left" : "text-right tabular-nums")}
                      >
                        {c}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </figure>
  );
}
