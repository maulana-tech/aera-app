import { ArrowRight, Clock, TriangleAlert, Wallet } from "lucide-react";
import Link from "next/link";

import { ambil, rupiah, type Ringkasan } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

function Angka({
  label, nilai, jelas, ikon: Ikon,
}: { label: string; nilai: string; jelas?: string; ikon: React.ElementType }) {
  return (
    <div className="rounded-xl border p-4">
      <p className="text-muted-foreground flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider">
        <Ikon className="size-3" />
        {label}
      </p>
      <p className="mt-2 font-mono text-xl font-semibold tabular-nums">{nilai}</p>
      {jelas && <p className="text-muted-foreground mt-1 text-xs leading-relaxed">{jelas}</p>}
    </div>
  );
}

export default async function Dasbor() {
  const d = await ambil<Ringkasan>("ringkasan");
  if (!d) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">Layanan agent tidak merespons</h1>
      </main>
    );
  }

  const perluDiputuskan = d.aksi.menunggu ?? 0;
  const berjalan = d.jalan.berjalan ?? 0;
  const ditahan = d.jalan.ditahan ?? 0;

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Dasbor
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Ringkasan</h1>
      </header>

      <section className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Angka
          ikon={Clock}
          label="Perlu diputuskan"
          nilai={String(perluDiputuskan)}
          jelas={perluDiputuskan ? `senilai ${rupiah(d.nilai_menunggu_idr)}` : "tidak ada yang menunggu"}
        />
        <Angka
          ikon={Wallet}
          label="Sudah disetujui"
          nilai={rupiah(d.nilai_disetujui_idr)}
          jelas="nilai aksi yang lolos persetujuan"
        />
        <Angka
          ikon={TriangleAlert}
          label="Sedang ditangani"
          nilai={String(berjalan)}
          jelas={ditahan ? `${ditahan} ditahan` : undefined}
        />
        <Angka
          ikon={Wallet}
          label="Biaya model"
          nilai={rupiah(d.biaya_model_idr)}
          jelas="sejak awal"
        />
      </section>

      {(!d.model_siap || !d.sap_siap) && (
        <div className="mt-6 rounded-xl border p-4">
          <p className="text-sm font-medium">Belum tersambung penuh</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {!d.model_siap && <StatusBadge status="ditahan">AWS_REGION belum diisi</StatusBadge>}
            {!d.sap_siap && <StatusBadge status="ditahan">SAP_API_KEY belum diisi</StatusBadge>}
          </div>
          <p className="text-muted-foreground mt-2 text-xs leading-relaxed">
            Selama keduanya kosong, sistem tidak membuat keputusan apa pun — dan tidak
            berpura-pura membuatnya.
          </p>
        </div>
      )}

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section>
          <div className="flex items-baseline justify-between">
            <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
              Stok paling kritis
            </h2>
            <Link href="/data/stok" className="text-muted-foreground hover:text-foreground font-mono text-[11px]">
              semua →
            </Link>
          </div>
          {d.stok_kritis.length === 0 ? (
            <p className="text-muted-foreground mt-3 rounded-xl border border-dashed p-5 text-sm">
              Tidak ada material di bawah 14 hari cover.
            </p>
          ) : (
            <ul className="mt-3 divide-y rounded-xl border">
              {d.stok_kritis.map((s) => (
                <li key={`${s.material}-${s.plant}`} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">
                      <span className="font-mono">{s.material}</span>
                      <span className="text-muted-foreground ml-2">{s.deskripsi}</span>
                    </p>
                    <p className="text-muted-foreground mt-0.5 font-mono text-[11px]">
                      {s.plant} · habis {s.habis}
                    </p>
                  </div>
                  <span className="font-mono text-sm tabular-nums">
                    {s.hari_tersisa}
                    <span className="text-muted-foreground ml-1 text-xs">hari</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <div className="flex items-baseline justify-between">
            <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
              Penanganan terakhir
            </h2>
            <Link href="/" className="text-muted-foreground hover:text-foreground font-mono text-[11px]">
              antrean →
            </Link>
          </div>
          {d.terakhir.length === 0 ? (
            <p className="text-muted-foreground mt-3 rounded-xl border border-dashed p-5 text-sm">
              Belum ada penanganan.
            </p>
          ) : (
            <ul className="mt-3 divide-y rounded-xl border">
              {d.terakhir.map((t, i) => (
                <li key={i} className="flex items-center gap-3 px-4 py-3">
                  <StatusBadge status={t.status} />
                  <span className="min-w-0 flex-1 truncate text-sm">{t.judul}</span>
                  <ArrowRight className="text-muted-foreground size-3.5 shrink-0" />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
