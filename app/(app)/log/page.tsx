import Link from "next/link";

import { ambil, rupiah } from "@/app/lib";
import { AsalBadge, StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

type Langkah = {
  id: number; jalan_id: string; judul: string; urutan: number; tahap: string;
  agent: string; agent_nama: string; ringkas: string; alat: string[];
  asal: string | null; sumber: string | null; waktu: string;
};
type Aksi = {
  id: string; jalan_id: string; judul: string; jenis: string; status: string;
  otonom: number; muatan: Record<string, any>; dibuat: string;
};
type Setuju = {
  id: number; aksi_id: string; jalan_id: string; jenis_aksi: string;
  oleh: string; peran: string; putusan: string; waktu: string;
};

const waktu = (t: string) =>
  new Date(t).toLocaleString("id-ID", { dateStyle: "short", timeStyle: "medium" });

export default async function Log() {
  const d = await ambil<{ langkah: Langkah[]; aksi: Aksi[]; persetujuan: Setuju[] }>("log");

  if (!d) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">Layanan agent tidak merespons</h1>
      </main>
    );
  }

  const kosong = !d.langkah.length && !d.aksi.length && !d.persetujuan.length;

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Catatan
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Log</h1>
        <p className="text-muted-foreground mt-1 max-w-2xl text-sm leading-relaxed">
          Apa yang dikerjakan sistem, apa yang diajukan, dan siapa yang memutuskan.
          Baris di sini tidak pernah diubah — koreksi ditulis sebagai baris baru.
        </p>
      </header>

      {kosong && (
        <p className="text-muted-foreground mt-8 text-sm">Belum ada catatan.</p>
      )}

      {d.persetujuan.length > 0 && (
        <section className="mt-8">
          <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
            Persetujuan · {d.persetujuan.length}
          </h2>
          <ul className="mt-3 divide-y rounded-xl border">
            {d.persetujuan.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 text-sm">
                <StatusBadge status={s.putusan === "dinaikkan" ? "menunggu" : s.putusan} />
                <span className="font-mono text-xs">{s.jenis_aksi}</span>
                <span className="text-muted-foreground">oleh</span>
                <span>{s.oleh}</span>
                <span className="text-muted-foreground font-mono text-xs">({s.peran})</span>
                <Link
                  href={`/gangguan/${s.jalan_id}`}
                  className="text-muted-foreground hover:text-foreground ml-auto font-mono text-[11px]"
                >
                  {waktu(s.waktu)} →
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {d.aksi.length > 0 && (
        <section className="mt-8">
          <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
            Aksi · {d.aksi.length}
          </h2>
          <ul className="mt-3 divide-y rounded-xl border">
            {d.aksi.map((a) => (
              <li key={a.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <StatusBadge status={a.status} />
                  <span className="font-mono text-sm">{a.jenis}</span>
                  {a.otonom === 1 && (
                    <span className="text-muted-foreground text-xs">dijalankan sendiri</span>
                  )}
                  {typeof a.muatan.biaya_idr === "number" && (
                    <span className="font-mono text-xs tabular-nums">
                      {rupiah(a.muatan.biaya_idr)}
                    </span>
                  )}
                  <Link
                    href={`/gangguan/${a.jalan_id}`}
                    className="text-muted-foreground hover:text-foreground ml-auto font-mono text-[11px]"
                  >
                    {waktu(a.dibuat)} →
                  </Link>
                </div>
                <p className="text-muted-foreground mt-1 break-words font-mono text-[11px]">
                  {a.judul}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {d.langkah.length > 0 && (
        <section className="mt-8">
          <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
            Langkah agent · {d.langkah.length}
          </h2>
          <ul className="mt-3 divide-y rounded-xl border">
            {d.langkah.map((l) => (
              <li key={l.id} className="grid grid-cols-[84px_1fr] gap-4 px-4 py-3">
                <div>
                  <p className="text-primary font-mono text-[11px] font-semibold tracking-wider">
                    {l.tahap}
                  </p>
                  <p className="text-muted-foreground mt-0.5 text-[11px]">{l.agent_nama}</p>
                </div>
                <div className="min-w-0">
                  <p className="text-sm leading-relaxed">{l.ringkas}</p>
                  {l.alat.length > 0 && (
                    <p className="text-muted-foreground mt-1 break-words font-mono text-[11px]">
                      {l.alat.join(" · ")}
                    </p>
                  )}
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    {l.asal && <AsalBadge asal={l.asal} sumber={l.sumber} />}
                    <Link
                      href={`/gangguan/${l.jalan_id}`}
                      className="text-muted-foreground hover:text-foreground font-mono text-[11px]"
                    >
                      {waktu(l.waktu)} →
                    </Link>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
