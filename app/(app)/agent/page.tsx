import { ArrowDown, ArrowLeftRight, Database } from "lucide-react";

import { ambil, type Agent, type RingkasAgent } from "@/app/lib";
import { KartuAgent, Lencana } from "@/components/kartu-agent";
import { StatusBadge } from "@/components/status-badge";
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
  const ketua = agent.find((a) => a.ketua)!;
  const penanganan = agent.filter((a) => !a.ketua && a.kode !== "exposure");
  const pencegahan = agent.filter((a) => a.kode === "exposure");
  const persen = Math.round((ringkas.alat_terpasang / ringkas.alat_total) * 100);

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Tim agent
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          Satu ketua, sepuluh ahli
        </h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Arya memanggil ahli yang relevan berdasarkan temuan sebelumnya — urutannya
          diputuskan saat itu juga, bukan ditulis di awal. Kalau masalahnya selesai dengan
          memindahkan stok antar pabrik, Clint tidak pernah dipanggil sama sekali.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-x-8 gap-y-3">
          <div className="min-w-40">
            <p className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">
              Alat terpasang
            </p>
            <p className="mt-1 font-mono text-lg font-semibold tabular-nums">
              {ringkas.alat_terpasang}
              <span className="text-muted-foreground text-sm">/{ringkas.alat_total}</span>
            </p>
            <Progress value={persen} className="mt-1.5 h-1" />
          </div>
          <StatusBadge status={ringkas.model_siap ? "selesai" : "ditahan"}>
            {ringkas.model_siap ? "Bedrock siap" : "AWS_REGION belum diisi"}
          </StatusBadge>
          <StatusBadge status={ringkas.sap_siap ? "selesai" : "ditahan"}>
            {ringkas.sap_siap ? "SAP tersambung" : "SAP_API_KEY belum diisi"}
          </StatusBadge>
        </div>
      </header>

      {/* ---------------- ketua ---------------- */}
      <section className="mt-8">
        <div className="bg-muted/40 flex flex-wrap items-center gap-4 rounded-xl border p-5">
          <Lencana panggilan={ketua.panggilan} besar />
          <div className="min-w-60 flex-1">
            <h2 className="font-semibold">
              {ketua.panggilan}
              <span className="text-muted-foreground ml-2 text-sm font-normal">{ketua.nama}</span>
            </h2>
            <p className="text-muted-foreground mt-1 text-sm leading-relaxed">{ketua.peran}</p>
          </div>
          <a
            href={`/agent/${ketua.kode}`}
            className="text-muted-foreground hover:text-foreground font-mono text-xs"
          >
            buka →
          </a>
        </div>

        <p className="text-muted-foreground mt-3 flex flex-wrap items-center justify-center gap-x-6 gap-y-1 font-mono text-[11px] uppercase tracking-[0.12em]">
          <span className="flex items-center gap-1.5">
            <ArrowDown className="size-3" /> memanggil sesuai temuan
          </span>
          <span className="flex items-center gap-1.5">
            <ArrowLeftRight className="size-3" /> ahli bisa saling oper
          </span>
        </p>
      </section>

      {/* ---------------- ahli penanganan ---------------- */}
      <section className="mt-3">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {penanganan.map((a) => (
            <KartuAgent key={a.kode} a={a} />
          ))}
        </div>
      </section>

      {/* ---------------- papan bersama ---------------- */}
      <section className="mt-3">
        <div className="text-muted-foreground flex flex-wrap items-start gap-3 rounded-xl border border-dashed p-4">
          <Database className="mt-0.5 size-4 shrink-0" />
          <div className="min-w-60 flex-1">
            <p className="text-foreground font-mono text-[11px] uppercase tracking-[0.12em]">
              Papan bersama
            </p>
            <p className="mt-1 text-xs leading-relaxed">
              Semua ahli menulis dan membaca di sini, dan tiap temuan membawa label asalnya.
              Inilah yang membuat Iris bisa mengoper tahanan mutu langsung ke Elsa — tanggal
              habis stok dihitung ulang tanpa lewat Arya.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------- mode cegah ---------------- */}
      <section className="mt-8">
        <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
          Mode Cegah · belum dibangun
        </h2>
        <p className="text-muted-foreground mt-1 max-w-2xl text-xs leading-relaxed">
          Bekerja tanpa menunggu gangguan: mencari risiko yang belum terjadi, terjadwal mingguan.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {pencegahan.map((a) => (
            <KartuAgent key={a.kode} a={a} />
          ))}
        </div>
      </section>
    </main>
  );
}
