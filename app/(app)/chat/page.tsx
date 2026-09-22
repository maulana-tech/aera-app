import { ambil, saya, type Agent, type RingkasAgent } from "@/app/lib";
import Percakapan from "@/app/(app)/agent/[kode]/Percakapan";
import { Lencana } from "@/components/kartu-agent";

export const dynamic = "force-dynamic";

const CONTOH = [
  "Ada gangguan apa yang belum ditangani?",
  "Material mana yang paling kritis minggu ini?",
  "Kalau Ningbo tutup seminggu lagi, apa dampaknya?",
];

export default async function Chat() {
  const [tim, aku] = await Promise.all([
    ambil<{ agent: Agent[]; ringkas: RingkasAgent }>("agent"),
    saya(),
  ]);
  const arya = tim?.agent.find((a) => a.ketua);
  const ahli = tim?.agent.filter((a) => !a.ketua) ?? [];

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Percakapan
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Tanya Arya</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Arya ketua timnya. Dia yang memutuskan ahli mana yang perlu dipanggil untuk
          menjawab — kamu tidak perlu tahu harus bertanya ke siapa.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground mr-1 font-mono text-[10px] uppercase tracking-wider">
            bisa memanggil
          </span>
          {ahli.map((a) => (
            <span key={a.kode} title={`${a.panggilan} · ${a.nama}`}>
              <Lencana panggilan={a.panggilan} />
            </span>
          ))}
        </div>
      </header>

      <div className="mt-6 max-w-4xl">
        {arya && (
          <Percakapan kode={arya.kode} nama={arya.panggilan} contoh={CONTOH} masuk={!!aku} />
        )}
      </div>
    </main>
  );
}
