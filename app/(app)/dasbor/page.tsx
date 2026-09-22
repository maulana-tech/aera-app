import { ArrowRight, Clock, TriangleAlert, Wallet } from "lucide-react";
import Link from "next/link";

import { ambil, rupiah, type Pandangan, type Ringkasan } from "@/app/lib";
import { Batang, Bingkai, type Titik } from "@/components/grafik";
import { StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

/** Rupiah yang muat di ujung batang. */
const ringkas = (n: number) =>
  n >= 1e9
    ? `${(n / 1e9).toLocaleString("id-ID", { maximumFractionDigits: 2 })} M`
    : n >= 1e6
      ? `${(n / 1e6).toLocaleString("id-ID", { maximumFractionDigits: 0 })} jt`
      : n.toLocaleString("id-ID");

const angka = (n: number) => n.toLocaleString("id-ID", { maximumFractionDigits: 1 });

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
  const [d, stok, sumber, logistik, hitung] = await Promise.all([
    ambil<Ringkasan>("ringkasan"),
    ambil<Pandangan>("data/stok"),
    ambil<Pandangan>("data/sumber"),
    ambil<Pandangan>("data/logistik"),
    ambil<Pandangan>("data/perhitungan"),
  ]);

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

  // ---- cover stok: berapa hari lagi tiap material habis ----------------
  const barisStok = (stok?.baris ?? []).filter((r) => r.hari_tersisa != null);
  const titikStok: Titik[] = barisStok.map((r) => ({
    label: r.deskripsi || r.material,
    sub: `${r.material} · ${r.plant}`,
    nilai: Number(r.hari_tersisa),
    tulis: `${angka(Number(r.hari_tersisa))} hr`,
    tekstur: Number(r.hari_tersisa) < 14,
    tanda: r.habis ? `habis ${r.habis}` : undefined,
    judul: `${r.material} di ${r.plant} — sisa ${angka(Number(r.jumlah))} ${r.satuan ?? ""}, `
      + `terpakai ${angka(Number(r.pemakaian_harian))}/hari`,
  }));

  // ---- pilihan pasokan: biaya tambahan tiap opsi -----------------------
  const titikSumber: Titik[] = (sumber?.baris ?? []).map((r) => ({
    label: r.label,
    sub: `${r.supplier ?? "—"} · ${r.asal_negara ?? "—"}`,
    nilai: Number(r.biaya_idr ?? 0),
    tulis: `Rp ${ringkas(Number(r.biaya_idr ?? 0))}`,
    tekstur: r.layak === false,
    tanda: r.layak === false ? "ditolak aturan" : r.tiba ? `tiba ${r.tiba}` : undefined,
    judul: r.alasan || `Tiba ${r.tiba}, TKDN jadi ${r.tkdn ?? "—"}`,
  }));

  // ---- keterlambatan kiriman: PO yang mundur ---------------------------
  const barisPO = (logistik?.baris ?? []).filter(
    (r) => r.status !== "rencana" && Number(r.mundur_hari ?? 0) > 0,
  );
  const titikLogistik: Titik[] = barisPO.map((r) => ({
    label: r.purchase_order,
    sub: `${r.material} · ${r.pelabuhan ?? "—"}`,
    nilai: Number(r.mundur_hari),
    tulis: `${r.mundur_hari} hr`,
    tanda: `jadi ${r.tiba_revisi}`,
    judul: `Semula ${r.tiba_semula}, jadi ${r.tiba_revisi} — status ${r.status}`,
  }));

  // ---- perhitungan: biaya tiap kombinasi penanganan --------------------
  const titikHitung: Titik[] = (hitung?.baris ?? []).map((r) => ({
    label: r.kombinasi,
    nilai: Number(r.biaya_idr ?? 0),
    tulis: `Rp ${ringkas(Number(r.biaya_idr ?? 0))}`,
    tekstur: r.aman === false,
    tanda: r.terpilih ? "▸ dipilih" : r.aman === false ? "tak menutup celah" : undefined,
    judul: `${r.aman ? "Menutup celah pasokan" : "Masih kehabisan stok"}`
      + `${r.habis ? ` — habis ${r.habis}` : ""}${r.tkdn != null ? ` · TKDN ${r.tkdn}` : ""}`,
  }));

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
            berpura-pura membuatnya. Grafik di bawah tetap menandai asal tiap angkanya.
          </p>
        </div>
      )}

      <div className="mt-8 grid gap-4 xl:grid-cols-2">
        <Bingkai
          judul="Sisa cover stok"
          jelas="Berapa hari lagi tiap material habis dengan laju pemakaian sekarang. Batang berarsir sudah di bawah ambang."
          asal={stok?.asal}
          sumber={stok?.sumber}
          kosong={titikStok.length ? undefined : "Belum ada data stok yang bisa dihitung."}
          tabel={{
            kepala: ["Material", "Plant", "Hari tersisa", "Habis"],
            baris: barisStok.map((r) => [
              `${r.material} — ${r.deskripsi}`, r.plant,
              angka(Number(r.hari_tersisa)), r.habis ?? "—",
            ]),
          }}
        >
          <Batang data={titikStok} ambang={14} labelAmbang="ambang aman 14 hari" />
        </Bingkai>

        <Bingkai
          judul="Biaya tiap pilihan pasokan"
          jelas="Biaya tambahan tiap opsi pengganti. Batang berarsir ditolak Kira karena melanggar aturan TKDN atau LARTAS — dan itu tidak bisa dikalahkan oleh harga."
          asal={sumber?.asal}
          sumber={sumber?.sumber}
          kosong={titikSumber.length ? undefined : "Belum ada opsi pasokan pengganti."}
          tabel={{
            kepala: ["Pilihan", "Tiba", "Biaya", "Lolos aturan"],
            baris: (sumber?.baris ?? []).map((r) => [
              r.label, r.tiba ?? "—", rupiah(Number(r.biaya_idr ?? 0)),
              r.layak === false ? "tidak" : "ya",
            ]),
          }}
        >
          <Batang data={titikSumber} />
        </Bingkai>

        <Bingkai
          judul="Kiriman yang mundur"
          jelas="Selisih hari antara tanggal tiba yang dijanjikan dan tanggal tiba yang sekarang berlaku."
          asal={logistik?.asal}
          sumber={logistik?.sumber}
          kosong={titikLogistik.length ? undefined : "Tidak ada kiriman yang mundur."}
          tabel={{
            kepala: ["Referensi", "Semula", "Jadi", "Mundur"],
            baris: barisPO.map((r) => [
              r.purchase_order, r.tiba_semula, r.tiba_revisi, `${r.mundur_hari} hr`,
            ]),
          }}
        >
          <Batang data={titikLogistik} />
        </Bingkai>

        <Bingkai
          judul="Biaya tiap kombinasi penanganan"
          jelas="Hasil mesin hitung Tara. Batang berarsir tetap kehabisan stok, jadi murahnya tidak berarti."
          asal={hitung?.asal}
          sumber={hitung?.sumber}
          catatan={hitung?.catatan}
          kosong={
            titikHitung.length
              ? undefined
              : hitung?.catatan || "Mesin hitung menolak berhitung karena masukannya belum tepercaya."
          }
          tabel={{
            kepala: ["Kombinasi", "Biaya", "Menutup celah", "Habis"],
            baris: (hitung?.baris ?? []).map((r) => [
              r.kombinasi, rupiah(Number(r.biaya_idr ?? 0)),
              r.aman ? "ya" : "tidak", r.habis ?? "—",
            ]),
          }}
        >
          <Batang data={titikHitung} />
        </Bingkai>
      </div>

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
