import Link from "next/link";
import { notFound } from "next/navigation";
import { ambil, ASAL, rupiah, saya, STATUS, type Jalan } from "../lib";
import { Status, Tag } from "../ui/Twenty";
import Putusan from "./Putusan";

export const dynamic = "force-dynamic";

export default async function Detail({ params }: { params: Promise<{ id: string }> }) {
  const j = await ambil<Jalan>(`jalan/${(await params).id}`);
  if (!j) notFound();
  const aku = await saya();

  const langkah = j.langkah ?? [];
  const aksi = j.aksi ?? [];
  const setuju = j.persetujuan ?? [];

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-8">
      <Link href="/sigap" className="font-mono text-xs text-muted hover:text-foreground">← antrean</Link>

      <header className="mt-4 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">{j.jenis}</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">{j.judul}</h1>
          <p className="mt-1 text-sm text-muted">{j.pemicu}</p>
        </div>
        <div className="flex flex-wrap gap-2 font-mono text-[11px]">
          {j.mode === "runut" && (
            <span className="rounded-full border border-amber-500/50 bg-amber-500/10 px-3 py-1 text-amber-300">
              mode runut — bukan penalaran agent
            </span>
          )}
          <Status color={j.status === "gagal" ? "red" : j.status === "selesai" ? "green" : "yellow"}>
            {j.status}
          </Status>
          {j.biaya_token_idr > 0 && (
            <span className="rounded-full border border-line px-3 py-1 text-muted">{rupiah(j.biaya_token_idr)}</span>
          )}
        </div>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_340px]">
        <section className="rounded-xl border border-line">
          <div className="border-b border-line px-5 py-3">
            <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted">
              Jalan pikiran sistem · {langkah.length} langkah
            </p>
          </div>
          {langkah.length === 0 ? (
            <p className="px-5 py-8 text-sm text-muted">
              {j.status === "ditahan"
                ? "Tidak ada langkah — sistem berhenti sebelum menalar."
                : "Belum ada langkah tercatat."}
            </p>
          ) : (
            <ol className="divide-y divide-line">
              {langkah.map((l) => {
                const a = l.asal ? ASAL[l.asal] : null;
                return (
                  <li key={l.urutan} className="grid grid-cols-[86px_1fr] gap-4 px-5 py-4">
                    <div>
                      <p className="font-mono text-[11px] font-semibold tracking-wider text-accent">{l.tahap}</p>
                      <p className="mt-1 text-[11px] text-muted">{l.agent_nama}</p>
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm leading-relaxed">{l.ringkas}</p>
                      {l.alat.length > 0 && (
                        <p className="mt-1.5 break-words font-mono text-[11px] text-muted">{l.alat.join(" · ")}</p>
                      )}
                      {a && (
                        <span className={`mt-2 inline-block rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${a.cls}`}>
                          {a.label}{l.sumber ? ` · ${l.sumber}` : ""}
                        </span>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </section>

        <aside className="space-y-5">
          {j.keputusan && (
            <div className={`rounded-xl border p-5 ${
              j.status === "ditahan" ? "border-amber-500/50 bg-amber-500/5" : "border-accent/60 bg-accent/5"}`}>
              <p className="font-mono text-[11px] uppercase tracking-wider text-accent">
                {j.status === "ditahan" ? "Ditahan" : "Rekomendasi"}
              </p>
              <p className="mt-2 whitespace-pre-line text-sm leading-relaxed">
                {j.keputusan.rekomendasi ?? j.keputusan.alasan ?? "—"}
              </p>
              {Array.isArray(j.keputusan.papan_tidak_tepercaya) && j.keputusan.papan_tidak_tepercaya.length > 0 && (
                <p className="mt-3 text-xs leading-relaxed text-amber-300">
                  Data belum tepercaya: {j.keputusan.papan_tidak_tepercaya.join(", ")}
                </p>
              )}
            </div>
          )}

          <div className="rounded-xl border border-line">
            <div className="border-b border-line px-5 py-3">
              <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted">Aksi · {aksi.length}</p>
            </div>
            {aksi.length === 0 ? (
              <p className="px-5 py-6 text-sm text-muted">Belum ada aksi yang diajukan.</p>
            ) : (
              <ul className="divide-y divide-line">
                {aksi.map((a) => {
                  const riwayat = setuju.filter((s) => s.aksi_id === a.id);
                  return (
                    <li key={a.id} className="px-5 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-mono text-sm">{a.jenis}</span>
                        <Tag color={
                          a.status === "ditolak" ? "red"
                          : a.status === "disetujui" || a.status === "terkirim" ? "green"
                          : "yellow"
                        }>{a.status}</Tag>
                      </div>
                      <p className="mt-1.5 break-words font-mono text-[11px] text-muted">
                        {Object.entries(a.muatan).map(([k, v]) => `${k}=${v}`).join(" · ")}
                      </p>
                      {a.otonom === 1 && (
                        <p className="mt-1 text-[11px] text-muted">dijalankan sendiri — di bawah batas wewenang</p>
                      )}
                      {riwayat.map((s) => (
                        <p key={s.id} className="mt-1.5 text-[11px] text-muted">
                          {s.putusan} oleh {s.oleh} ({s.peran}) · {new Date(s.waktu).toLocaleString("id-ID")}
                        </p>
                      ))}
                      {a.status === "menunggu" && (
                        aku ? (
                          <Putusan
                            aksiId={a.id}
                            nilaiIdr={Number(a.muatan.biaya_idr ?? 0)}
                            batasIdr={aku.batas_idr}
                          />
                        ) : (
                          <p className="mt-2 text-[11px] text-amber-300">
                            Masuk dulu untuk menyetujui.
                          </p>
                        )
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
