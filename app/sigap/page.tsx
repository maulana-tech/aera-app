import fs from "node:fs/promises";
import path from "node:path";

type Langkah = {
  urutan: number; tahap: string; agent: string; agent_nama: string;
  ringkas: string; alat: string[]; asal: string | null; sumber: string | null;
  detail: Record<string, unknown>; waktu: string;
};
type Jejak = {
  judul: string; pemicu: string; mode: "otonom" | "runut"; mulai: string;
  agent_terpakai: string[]; jumlah_langkah: number; langkah: Langkah[];
  keputusan: Record<string, any>;
};

const ASAL: Record<string, { label: string; cls: string }> = {
  live:     { label: "langsung", cls: "border-emerald-500/40 text-emerald-300 bg-emerald-500/10" },
  cached:   { label: "simpanan", cls: "border-sky-500/40 text-sky-300 bg-sky-500/10" },
  derived:  { label: "hitungan", cls: "border-violet-500/40 text-violet-300 bg-violet-500/10" },
  modelled: { label: "contoh",   cls: "border-amber-500/50 text-amber-300 bg-amber-500/10" },
  missing:  { label: "tidak ada", cls: "border-rose-500/50 text-rose-300 bg-rose-500/10" },
};

const rupiah = (n: number) => "Rp " + n.toLocaleString("id-ID");

async function baca(): Promise<Jejak | null> {
  try {
    const f = path.join(process.cwd(), "app", "sigap", "jejak.json");
    return JSON.parse(await fs.readFile(f, "utf8"));
  } catch {
    return null;
  }
}

export default async function Page() {
  const j = await baca();

  if (!j) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-24">
        <h1 className="text-2xl font-semibold">Belum ada jejak</h1>
        <p className="mt-4 text-muted">Jalankan dulu:</p>
        <pre className="mt-3 rounded-lg border border-line bg-card p-4 font-mono text-sm">
          cd sigap/agent{"\n"}python3 main.py --anggap-langsung
        </pre>
      </main>
    );
  }

  const k = j.keputusan;
  const ditahan = k.status === "ditahan";

  return (
    <main className="mx-auto max-w-[1400px] px-6 py-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">
            SIGAP · Antrean keputusan
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">{j.judul}</h1>
          <p className="mt-1 text-sm text-muted">{j.pemicu}</p>
        </div>
        <div className="flex items-center gap-2">
          {j.mode === "runut" && (
            <span className="rounded-full border border-amber-500/50 bg-amber-500/10 px-3 py-1 font-mono text-[11px] uppercase tracking-wider text-amber-300">
              mode runut — bukan penalaran agent
            </span>
          )}
          <span className="rounded-full border border-line px-3 py-1 font-mono text-[11px] text-muted">
            {j.jumlah_langkah} langkah · {j.agent_terpakai.length} agent
          </span>
        </div>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[320px_1fr]">
        {/* ---------- kiri: antrean ---------- */}
        <aside className="space-y-3">
          <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted">
            Perlu diputuskan
          </p>

          <article className="rounded-xl border border-accent/60 bg-accent/5 p-4">
            <div className="flex items-start justify-between gap-3">
              <span className="text-sm font-medium">{j.judul}</span>
              <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-accent" />
            </div>
            <p className="mt-2 font-mono text-lg font-semibold tabular-nums">
              {ditahan ? "—" : rupiah(k.hemat_idr)}
            </p>
            <p className="mt-0.5 text-xs text-muted">
              {ditahan ? "angka ditahan" : `hemat vs ${k.pembanding} · ${k.hemat_pct}%`}
            </p>
          </article>

          {["Sertifikat TKDN supplier mau habis", "Antrean bongkar Priok memanjang"].map((t) => (
            <article key={t} className="rounded-xl border border-line bg-card p-4 opacity-50">
              <span className="text-sm">{t}</span>
              <p className="mt-2 font-mono text-sm text-muted">belum diselidiki</p>
            </article>
          ))}

          <p className="pt-2 text-[11px] leading-relaxed text-muted">
            Dua kartu terakhir adalah tempat kosong untuk mode Cegah (Tahap 8).
          </p>
        </aside>

        {/* ---------- kanan: jejak + keputusan ---------- */}
        <section className="space-y-6">
          <div className="rounded-xl border border-line">
            <div className="border-b border-line px-5 py-3">
              <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted">
                Jalan pikiran sistem
              </p>
            </div>
            <ol className="divide-y divide-line">
              {j.langkah.map((l) => {
                const a = l.asal ? ASAL[l.asal] : null;
                return (
                  <li key={l.urutan} className="grid grid-cols-[92px_1fr] gap-4 px-5 py-4">
                    <div>
                      <p className="font-mono text-[11px] font-semibold tracking-wider text-accent">
                        {l.tahap}
                      </p>
                      <p className="mt-1 text-[11px] text-muted">{l.agent_nama}</p>
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm leading-relaxed">{l.ringkas}</p>
                      {l.alat.length > 0 && (
                        <p className="mt-1.5 break-words font-mono text-[11px] text-muted">
                          {l.alat.join(" · ")}
                        </p>
                      )}
                      {a && (
                        <span
                          className={`mt-2 inline-block rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${a.cls}`}
                        >
                          {a.label}
                          {l.sumber ? ` · ${l.sumber}` : ""}
                        </span>
                      )}
                      {Array.isArray(l.detail.ditolak) && l.detail.ditolak.length > 0 && (
                        <ul className="mt-2 space-y-1">
                          {(l.detail.ditolak as string[]).map((id) => (
                            <li key={id} className="text-xs leading-relaxed text-rose-300">
                              <span className="font-mono">⛔ {id}</span>{" "}
                              {(l.detail.alasan as Record<string, string>)?.[id]}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>

          <div
            className={`rounded-xl border p-5 ${
              ditahan ? "border-amber-500/50 bg-amber-500/5" : "border-accent/60 bg-accent/5"
            }`}
          >
            {ditahan ? (
              <>
                <p className="font-mono text-[11px] uppercase tracking-wider text-amber-300">
                  Angka ditahan
                </p>
                <p className="mt-2 text-sm leading-relaxed">{k.alasan}</p>
              </>
            ) : (
              <>
                <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  <p className="font-mono text-[11px] uppercase tracking-wider text-accent">
                    Rekomendasi
                  </p>
                  <p className="font-mono text-lg font-semibold">{k.kombinasi}</p>
                  <p className="text-sm text-muted">
                    bukan {k.pembanding} yang {rupiah(k.pembanding_biaya_idr)}
                  </p>
                </div>
                <dl className="mt-4 grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4">
                  {[
                    ["Biaya", rupiah(k.biaya_idr)],
                    ["Hemat", `${rupiah(k.hemat_idr)} · ${k.hemat_pct}%`],
                    ["Terlindungi", rupiah(k.nilai_terlindungi_idr)],
                    ["TKDN", `${k.tkdn_sebelum}% → ${k.tkdn_sesudah}%`],
                  ].map(([t, v]) => (
                    <div key={t} className="bg-background px-4 py-3">
                      <dt className="font-mono text-[10px] uppercase tracking-wider text-muted">
                        {t}
                      </dt>
                      <dd className="mt-1 font-mono text-sm font-semibold tabular-nums">{v}</dd>
                    </div>
                  ))}
                </dl>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button className="rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background">
                    Setujui draf pesanan
                  </button>
                  <button className="rounded-full border border-line px-5 py-2 text-sm">
                    Naikkan ke procurement
                  </button>
                </div>
                <p className="mt-3 text-xs text-muted">
                  Pemindahan stok sudah dijalankan sendiri (di bawah Rp 50 juta). Yang menunggu
                  persetujuan hanya pesanan pembeliannya.
                </p>
              </>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
