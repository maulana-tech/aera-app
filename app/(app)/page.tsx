import Link from "next/link";
import { ambil, rupiah, type Jalan } from "@/app/lib";
import { Badge } from "@/components/ui/badge";
import { SegarkanOtomatis } from "@/components/segarkan-otomatis";
import { StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

export default async function Antrean() {
  const data = await ambil<{ jalan: Jalan[] }>("jalan");
  const sehat = await ambil<Record<string, any>>("sehat");

  if (!data) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">Layanan agent tidak merespons</h1>
        <pre className="mt-4 rounded-lg border border-border bg-card p-4 font-mono text-sm">
          cd sigap/agent{"\n"}python3 api.py
        </pre>
      </main>
    );
  }

  const jalan = data.jalan;
  const menunggu = jalan.filter((j) => j.status === "berjalan" || j.status === "ditahan");

  return (
    <main className="w-full px-6 py-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-primary">
            SIGAP · Antrean keputusan
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Gangguan pasokan</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {jalan.length} penanganan · {menunggu.length} perlu perhatian
          </p>
        </div>
        {sehat && (
          <div className="flex flex-wrap items-center gap-2">
            <SegarkanOtomatis aktif={jalan.some((j) => j.status === "berjalan")} />
            <Badge variant="outline" className="font-mono text-[10px]">{sehat.lingkungan}</Badge>
            <StatusBadge status={sehat.sap_siap ? "selesai" : "ditahan"}>
              SAP {sehat.sap_siap ? "tersambung" : "belum"}
            </StatusBadge>
            <StatusBadge status={sehat.model_siap ? "selesai" : "ditahan"}>
              model {sehat.model_siap ? "siap" : "belum"}
            </StatusBadge>
          </div>
        )}
      </header>

      {jalan.length === 0 ? (
        <div className="mt-10 rounded-xl border border-dashed border-border p-8">
          <p className="text-sm text-muted-foreground">Belum ada peristiwa. Kirim satu:</p>
          <pre className="mt-3 overflow-x-auto rounded-lg border border-border bg-card p-4 font-mono text-xs">
{`curl -X POST localhost:8787/peristiwa \\
  -H 'content-type: application/json' \\
  -d '{"jenis":"port_closure","judul":"Ningbo tutup 6 hari",
       "pemicu":"advisory maritim","muatan":{"pelabuhan":"CNNGB"}}'`}
          </pre>
        </div>
      ) : (
        <ul className="mt-6 grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          {jalan.map((j) => (
            <li key={j.id}>
              <Link
                href={`/gangguan/${j.id}`}
                className="block rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/50"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="font-medium">{j.judul}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">{j.pemicu}</p>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2 font-mono text-[11px]">
                    {j.mode === "runut" && <StatusBadge status="runut" />}
                    <StatusBadge status={j.status} />
                  </div>
                </div>

                {j.keputusan?.rekomendasi && (
                  <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
                    {j.keputusan.rekomendasi}
                  </p>
                )}
                {j.status === "ditahan" && j.keputusan?.alasan && (
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    {j.keputusan.alasan}
                  </p>
                )}
                {j.galat && (
                  <p className="mt-3 font-mono text-xs text-destructive">{j.galat}</p>
                )}

                <p className="mt-3 font-mono text-[11px] text-muted-foreground">
                  {new Date(j.mulai).toLocaleString("id-ID")}
                  {j.biaya_token_idr > 0 && ` · biaya ${rupiah(j.biaya_token_idr)}`}
                  {Array.isArray(j.keputusan?.agent_dipanggil) &&
                    ` · ${j.keputusan.agent_dipanggil.length} ahli dipanggil`}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
