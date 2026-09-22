import { AsalBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";

export type Titik = {
  label: string;
  sub?: string;
  nilai: number;
  tulis: string;       // nilai yang ditampilkan, sudah diformat
  tekstur?: boolean;   // gagal syarat — ditandai arsiran, bukan warna lain
  tanda?: string;      // keterangan pendek di kanan
  judul?: string;      // muncul saat kursor berhenti di atas baris
};

/** Batang mendatar satu seri.
 *
 *  Satu rona saja. Kritis vs aman disampaikan lewat garis ambang, urutan
 *  baris, dan label langsung — bukan lewat merah/hijau: pasangan itu cuma
 *  terpisah ΔE 4,1 di mata deuteranopia, jauh di bawah batas 8. */
export function Batang({
  data, ambang, labelAmbang,
}: {
  data: Titik[];
  ambang?: number;
  labelAmbang?: string;
}) {
  const maks = Math.max(...data.map((d) => d.nilai), ambang ?? 0) || 1;
  const skala = (n: number) => `${Math.max((n / (maks * 1.04)) * 100, 0.8)}%`;

  return (
    <div className="viz">
      <div className="space-y-0.5">
        {data.map((d, i) => (
          <div
            key={`${d.label}-${i}`}
            title={d.judul}
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
              style={{ background: "var(--viz-alur)" }}
            >
              <div
                className="absolute inset-y-0 left-0 rounded-full"
                style={{
                  width: skala(d.nilai),
                  background: d.tekstur
                    ? "repeating-linear-gradient(45deg, var(--viz-seri) 0 2px, transparent 2px 5px)"
                    : "var(--viz-seri)",
                  boxShadow: d.tekstur ? "inset 0 0 0 1px var(--viz-seri)" : undefined,
                }}
              />
              {ambang !== undefined && (
                <span
                  aria-hidden
                  className="absolute -inset-y-1 w-0 border-l border-dashed"
                  style={{ left: skala(ambang), borderColor: "var(--viz-garis)" }}
                />
              )}
            </div>

            <span className="w-20 shrink-0 text-right font-mono text-xs tabular-nums">
              {d.tulis}
            </span>
            <span className="text-muted-foreground hidden w-32 shrink-0 truncate text-[10px] sm:block">
              {d.tanda}
            </span>
          </div>
        ))}
      </div>

      {ambang !== undefined && labelAmbang && (
        <p className="text-muted-foreground mt-2.5 flex items-center gap-1.5 font-mono text-[10px]">
          <span
            className="inline-block h-0 w-4 border-t border-dashed"
            style={{ borderColor: "var(--viz-garis)" }}
          />
          {labelAmbang}
        </p>
      )}
    </div>
  );
}

/** Pembungkus grafik: judul, asal data, dan tabel cadangan.
 *  Tabelnya selalu ada — angkanya harus terbaca walau grafiknya tidak. */
export function Bingkai({
  judul, jelas, asal, sumber, catatan, kosong, tabel, className, children,
}: {
  judul: string;
  jelas?: string;
  asal?: string;
  sumber?: string | null;
  catatan?: string;
  kosong?: string;
  tabel?: { kepala: string[]; baris: (string | number)[][] };
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <figure className={cn("rounded-xl border p-5", className)}>
      <figcaption className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-medium">{judul}</h3>
          {jelas && (
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">{jelas}</p>
          )}
        </div>
        {asal && <AsalBadge asal={asal} sumber={sumber} />}
      </figcaption>

      {kosong ? (
        <p className="text-muted-foreground mt-4 rounded-lg border border-dashed p-4 text-xs leading-relaxed">
          {kosong}
        </p>
      ) : (
        <div className="mt-4">{children}</div>
      )}

      {catatan && !kosong && (
        <p className="text-muted-foreground mt-3 text-xs leading-relaxed">{catatan}</p>
      )}

      {tabel && !kosong && (
        <details className="mt-3">
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer font-mono text-[10px]">
            lihat angkanya sebagai tabel
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b">
                  {tabel.kepala.map((h, i) => (
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
                {tabel.baris.map((r, i) => (
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
