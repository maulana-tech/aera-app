import { Crown, ShieldBan, Wrench } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ambil, saya, type Agent, type RingkasAgent } from "@/app/lib";
import Percakapan from "./Percakapan";
import { Lencana } from "@/components/kartu-agent";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

/** Contoh pertanyaan per agent — mengurangi tatapan kosong di layar pertama. */
const CONTOH: Record<string, string[]> = {
  supervisor: ["Ada gangguan apa yang belum ditangani?", "Ringkas kondisi pasokan hari ini"],
  impact: ["Pesanan mana yang lewat Ningbo?", "Kapan M-4471 di KRW1 habis?"],
  demand: ["Berapa pemakaian harian M-4471 di KRW1?", "Ada lonjakan permintaan?"],
  inventory: ["Stok M-4471 di KRW1 ada yang ditahan mutu?", "Berapa cadangan minimumnya?"],
  sourcing: ["Ada sumber pengganti untuk M-4471?", "Supplier lokal mana yang bisa dipakai?"],
  logistics: ["Realistisnya opsi B tiba kapan?", "Berapa lama bongkar di Priok?"],
  compliance: ["Boleh pakai supplier Vietnam untuk M-4471?", "Opsi mana yang melanggar TKDN?"],
  simulation: ["Berapa biaya kombinasi B+C?", "Mana yang paling murah dan tetap aman?"],
  precedent: ["Pernah ada gangguan Ningbo sebelumnya?", "Bagaimana dulu ditangani?"],
  execution: ["Aksi apa yang menunggu persetujuan?", "Sudah ada yang dikirim ke SAP?"],
  exposure: ["Material mana yang cuma punya satu supplier?", "Sertifikat siapa yang mau habis?"],
};

export default async function HalamanAgent({ params }: { params: Promise<{ kode: string }> }) {
  const { kode } = await params;
  const [d, aku] = await Promise.all([
    ambil<{ agent: Agent[]; ringkas: RingkasAgent }>("agent"),
    saya(),
  ]);
  const a = d?.agent.find((x) => x.kode === kode);
  if (!a) notFound();

  const kurang = a.alat.filter((t) => !t.terpasang);

  return (
    <main className="w-full px-6 py-8">
      <Link href="/agent" className="text-muted-foreground hover:text-foreground font-mono text-xs">
        ← tim agent
      </Link>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_340px]">
        <section>
          <div className="flex flex-wrap items-center gap-3">
            <Lencana panggilan={a.panggilan} besar />
            <h1 className="text-2xl font-semibold tracking-tight">{a.panggilan}</h1>
            <span className="text-muted-foreground text-sm">{a.nama}</span>
            {a.ketua && <Crown className="size-4" />}
            {a.veto && (
              <Badge variant="outline" className="gap-1 font-mono text-[10px]">
                <ShieldBan className="size-3" />
                veto
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground mt-1 max-w-2xl text-sm leading-relaxed">{a.peran}</p>

          <div className="mt-5">
            <Percakapan kode={a.kode} nama={a.panggilan} contoh={CONTOH[a.kode] ?? []} masuk={!!aku} />
          </div>
        </section>

        <aside className="space-y-5">
          {!d!.ringkas.model_siap && (
            <div className="rounded-xl border p-4">
              <StatusBadge status="ditahan">mesin penalaran belum tersambung</StatusBadge>
              <p className="text-muted-foreground mt-2 text-xs leading-relaxed">
                Percakapan akan ditolak sampai <code className="font-mono">AWS_REGION</code> diisi.
                Agent tidak akan menjawab dengan tebakan.
              </p>
            </div>
          )}

          <div className="rounded-xl border">
            <div className="flex items-center gap-2 border-b px-4 py-3">
              <Wrench className="size-3.5" />
              <p className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
                Alat · {a.terpasang}/{a.total_alat}
              </p>
            </div>
            <ul className="divide-y">
              {a.alat.map((t) => (
                <li key={t.nama} className="px-4 py-3">
                  <p
                    className={`break-all font-mono text-xs ${
                      t.terpasang ? "" : "text-muted-foreground/50"
                    }`}
                  >
                    {t.nama}
                    {!t.terpasang && <span className="ml-2 italic">belum ada</span>}
                  </p>
                  {t.deskripsi && (
                    <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
                      {t.deskripsi}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>

          <div className="text-muted-foreground space-y-1.5 px-1 font-mono text-[11px]">
            <p>effort · {a.effort}</p>
            <p>dipakai di · {a.dipakai_di} gangguan</p>
            {kurang.length > 0 && <p>{kurang.length} alat belum ditulis</p>}
          </div>
        </aside>
      </div>
    </main>
  );
}
