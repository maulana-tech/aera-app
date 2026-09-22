import { Crown, ShieldBan, Wrench } from "lucide-react";

import { ambil, type Agent, type RingkasAgent } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

export const dynamic = "force-dynamic";

export default async function TimAgent() {
  const d = await ambil<{ agent: Agent[]; ringkas: RingkasAgent }>("agent");

  if (!d) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">Layanan agent tidak merespons</h1>
        <pre className="bg-muted mt-4 rounded-lg border p-4 font-mono text-sm">
          cd sigap/agent{"\n"}python3 api.py
        </pre>
      </main>
    );
  }

  const { agent, ringkas } = d;
  const persen = Math.round((ringkas.alat_terpasang / ringkas.alat_total) * 100);

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Anatomi tim
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Tim agent</h1>
        <p className="text-muted-foreground mt-1 max-w-2xl text-sm leading-relaxed">
          Satu ketua dan sepuluh ahli. Ketua memanggil siapa yang relevan berdasarkan temuan
          sebelumnya — urutannya tidak ditulis di awal, jadi tidak semua ahli dipakai di
          tiap gangguan.
        </p>

        <div className="mt-5 grid max-w-2xl gap-4 sm:grid-cols-3">
          <div>
            <p className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">
              Alat terpasang
            </p>
            <p className="mt-1 font-mono text-lg font-semibold tabular-nums">
              {ringkas.alat_terpasang}
              <span className="text-muted-foreground text-sm">/{ringkas.alat_total}</span>
            </p>
            <Progress value={persen} className="mt-2 h-1.5" />
          </div>
          <div>
            <p className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">
              Mesin penalaran
            </p>
            <div className="mt-1.5">
              <StatusBadge status={ringkas.model_siap ? "selesai" : "ditahan"}>
                {ringkas.model_siap ? "Bedrock siap" : "AWS_REGION belum diisi"}
              </StatusBadge>
            </div>
          </div>
          <div>
            <p className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">
              Data perusahaan
            </p>
            <div className="mt-1.5">
              <StatusBadge status={ringkas.sap_siap ? "selesai" : "ditahan"}>
                {ringkas.sap_siap ? "SAP tersambung" : "SAP_API_KEY belum diisi"}
              </StatusBadge>
            </div>
          </div>
        </div>
      </header>

      {!ringkas.model_siap && (
        <p className="text-muted-foreground mt-5 text-sm leading-relaxed">
          Tanpa mesin penalaran, tidak ada satu pun agent di bawah ini yang pernah dijalankan.
          Yang ditampilkan adalah rancangannya, bukan riwayatnya.
        </p>
      )}

      <div className="mt-6 grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
        {agent.map((a) => (
          <article
            key={a.kode}
            className={`rounded-xl border p-5 ${a.ketua ? "bg-muted/40" : ""}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="flex items-center gap-1.5 font-medium">
                  {a.ketua && <Crown className="size-3.5 shrink-0" />}
                  {a.nama}
                </h2>
                <p className="text-muted-foreground mt-1 text-sm leading-relaxed">{a.peran}</p>
              </div>
              {a.veto && (
                <Badge variant="outline" className="shrink-0 gap-1 font-mono text-[10px]">
                  <ShieldBan className="size-3" />
                  veto
                </Badge>
              )}
            </div>

            <div className="text-muted-foreground mt-4 flex items-center gap-2 font-mono text-[11px]">
              <Wrench className="size-3" />
              {a.terpasang}/{a.total_alat} alat
              <span className="text-muted-foreground/60">·</span>
              effort {a.effort}
              {a.dipakai_di > 0 && (
                <>
                  <span className="text-muted-foreground/60">·</span>
                  dipakai di {a.dipakai_di} gangguan
                </>
              )}
            </div>

            <ul className="mt-2 space-y-1">
              {a.alat.map((t) => (
                <li
                  key={t.nama}
                  className={`flex items-baseline gap-2 font-mono text-[11px] ${
                    t.terpasang ? "text-muted-foreground" : "text-muted-foreground/45"
                  }`}
                >
                  <span aria-hidden className="shrink-0">
                    {t.terpasang ? "●" : "○"}
                  </span>
                  <span className="break-all">{t.nama}</span>
                  {!t.terpasang && <span className="shrink-0 italic">belum ada</span>}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </main>
  );
}
