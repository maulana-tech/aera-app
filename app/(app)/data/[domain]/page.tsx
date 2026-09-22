import { notFound } from "next/navigation";

import { ambil, saya, type Agent, type Pandangan, type RingkasAgent } from "@/app/lib";
import Percakapan from "@/app/(app)/agent/[kode]/Percakapan";
import { Lencana } from "@/components/kartu-agent";
import { TabelData } from "@/components/tabel-data";

export const dynamic = "force-dynamic";

const JUDUL: Record<string, { judul: string; jelas: string; contoh: string[] }> = {
  permintaan: {
    judul: "Permintaan",
    jelas: "Seberapa cepat bahan dipakai, dan apakah permintaan sedang bergerak.",
    contoh: ["Pemakaian M-4471 di KRW1 naik nggak?", "Material mana yang paling cepat habis?"],
  },
  stok: {
    judul: "Stok",
    jelas: "Berapa yang tercatat, berapa yang benar-benar bisa dipakai, dan kapan habis.",
    contoh: ["Ada stok yang ditahan mutu?", "Material mana yang paling kritis?"],
  },
  sumber: {
    judul: "Sumber pasokan",
    jelas: "Pilihan pengganti, beserta yang gugur karena aturan — bukan karena harga.",
    contoh: ["Kenapa opsi E ditolak?", "Mana yang paling cepat tiba?"],
  },
  logistik: {
    judul: "Logistik",
    jelas: "Tanggal tiba yang tahan uji: bongkar pelabuhan, pindah kapal, bea cukai.",
    contoh: ["Kiriman mana yang paling mundur?", "Realistisnya opsi B tiba kapan?"],
  },
  perhitungan: {
    judul: "Perhitungan",
    jelas: "Biaya tiap pilihan dan kombinasinya. Deterministik — bukan tebakan model.",
    contoh: ["Kombinasi mana yang paling murah dan tetap aman?", "Berapa hematnya?"],
  },
  eksekusi: {
    judul: "Eksekusi",
    jelas: "Apa yang sudah dijalankan, apa yang menunggu persetujuan.",
    contoh: ["Aksi apa yang menunggu?", "Sudah ada yang mendarat di SAP?"],
  },
};

export default async function HalamanDomain({ params }: { params: Promise<{ domain: string }> }) {
  const { domain } = await params;
  const meta = JUDUL[domain];
  if (!meta) notFound();

  const [d, tim, aku] = await Promise.all([
    ambil<Pandangan>(`data/${domain}`),
    ambil<{ agent: Agent[]; ringkas: RingkasAgent }>("agent"),
    saya(),
  ]);
  if (!d) notFound();

  const a = tim?.agent.find((x) => x.kode === d.agent);

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Data
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{meta.judul}</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          {meta.jelas}
        </p>
      </header>

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <section>
          <TabelData
            kolom={d.kolom}
            baris={d.baris}
            asal={d.asal}
            sumber={d.sumber}
            catatan={d.catatan}
            sorot={(b) => b.terpilih === true || b.layak === false}
          />
        </section>

        <aside>
          {a && (
            <>
              <div className="mb-3 flex items-center gap-2.5">
                <Lencana panggilan={a.panggilan} />
                <div>
                  <p className="text-sm font-medium leading-none">{a.panggilan}</p>
                  <p className="text-muted-foreground mt-1 text-xs">
                    yang memegang {meta.judul.toLowerCase()}
                  </p>
                </div>
              </div>
              <Percakapan
                kode={a.kode}
                nama={a.panggilan}
                contoh={meta.contoh}
                masuk={!!aku}
              />
            </>
          )}
        </aside>
      </div>
    </main>
  );
}
