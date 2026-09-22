import { AsalBadge } from "@/components/status-badge";
import type { Kolom } from "@/app/lib";

const rupiah = (n: number) => "Rp " + n.toLocaleString("id-ID");

function sel(v: any, k: Kolom) {
  if (v === null || v === undefined || v === "") return <span className="text-muted-foreground">—</span>;
  if (typeof v === "boolean")
    return (
      <span className={v ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400"}>
        {v ? "ya" : "tidak"}
      </span>
    );
  if (k.rp && typeof v === "number") return <span className="tabular-nums">{rupiah(v)}</span>;
  if (k.n) return <span className="tabular-nums">{v}</span>;
  return <>{v}</>;
}

export function TabelData({
  kolom, baris, asal, sumber, catatan, sorot,
}: {
  kolom: Kolom[]; baris: Record<string, any>[]; asal: string; sumber: string;
  catatan?: string; sorot?: (b: Record<string, any>) => boolean;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <AsalBadge asal={asal} sumber={sumber} />
        <span className="text-muted-foreground font-mono text-[11px]">{baris.length} baris</span>
      </div>

      {catatan && (
        <p className="text-muted-foreground max-w-3xl text-xs leading-relaxed">{catatan}</p>
      )}

      {baris.length === 0 ? (
        <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
          Tidak ada baris untuk ditampilkan.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                {kolom.map((k) => (
                  <th
                    key={k.k}
                    className={`text-muted-foreground px-4 py-2.5 font-mono text-[10px] font-medium uppercase tracking-wider ${
                      k.n || k.rp ? "text-right" : "text-left"
                    }`}
                  >
                    {k.l}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {baris.map((b, i) => (
                <tr key={i} className={sorot?.(b) ? "bg-muted/50" : undefined}>
                  {kolom.map((k) => (
                    <td
                      key={k.k}
                      className={`px-4 py-2.5 ${k.n || k.rp ? "text-right" : "text-left"}`}
                    >
                      {sel(b[k.k], k)}
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
