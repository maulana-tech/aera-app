import { ambil, saya, type Kontak } from "@/app/lib";
import { DaftarKontak, TambahKontak } from "./Kelola";

export const dynamic = "force-dynamic";

export default async function HalamanKontak() {
  const [d, aku] = await Promise.all([
    ambil<{ kontak: Kontak[] }>("kontak"),
    saya(),
  ]);

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Pengaturan
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Kontak</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Siapa yang dihubungi Bram saat ada gangguan. Produk ini bekerja karena kejadian —
          rekomendasi harus mendatangi orangnya, bukan menunggu dibuka.
        </p>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        {aku ? (
          <TambahKontak />
        ) : (
          <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
            Masuk dulu untuk menambah kontak.
          </p>
        )}
        <aside>
          <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
            Penerima · {d?.kontak.length ?? 0}
          </h2>
          <DaftarKontak kontak={d?.kontak ?? []} bisaHapus={!!aku} />
          <p className="text-muted-foreground mt-3 text-xs leading-relaxed">
            Pengiriman email belum tersambung. Daftar ini yang akan dipakai begitu
            layanan surat dipasang.
          </p>
        </aside>
      </div>
    </main>
  );
}
