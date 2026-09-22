import { OriginBadge } from "@/components/status-badge";
import type { Column } from "@/app/lib";

const idr = (n: number) => "Rp " + n.toLocaleString("en-US");

function cell(v: any, c: Column) {
  if (v === null || v === undefined || v === "")
    return <span className="text-muted-foreground">—</span>;
  if (typeof v === "boolean")
    return (
      <span className={v ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400"}>
        {v ? "yes" : "no"}
      </span>
    );
  if (c.rp && typeof v === "number") return <span className="tabular-nums">{idr(v)}</span>;
  if (c.n) return <span className="tabular-nums">{v}</span>;
  return <>{v}</>;
}

export function DataTable({
  columns, rows, origin, source, note, highlight,
}: {
  columns: Column[]; rows: Record<string, any>[]; origin: string; source: string;
  note?: string; highlight?: (row: Record<string, any>) => boolean;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <OriginBadge origin={origin} source={source} />
        <span className="text-muted-foreground font-mono text-[11px]">{rows.length} rows</span>
      </div>

      {note && (
        <p className="text-muted-foreground max-w-3xl text-xs leading-relaxed">{note}</p>
      )}

      {rows.length === 0 ? (
        <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
          Nothing to show here.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                {columns.map((c) => (
                  <th
                    key={c.k}
                    className={`text-muted-foreground px-4 py-2.5 font-mono text-[10px] font-medium uppercase tracking-wider ${
                      c.n || c.rp ? "text-right" : "text-left"
                    }`}
                  >
                    {c.l}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((row, i) => (
                <tr key={i} className={highlight?.(row) ? "bg-muted/50" : undefined}>
                  {columns.map((c) => (
                    <td
                      key={c.k}
                      className={`px-4 py-2.5 ${c.n || c.rp ? "text-right" : "text-left"}`}
                    >
                      {cell(row[c.k], c)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
