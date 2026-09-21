import Link from "next/link";
import { ambil, rupiah, saya, STATUS, type Jalan } from "./lib";
import { Status, Tag } from "./ui/Twenty";

export const dynamic = "force-dynamic";

export default async function Antrean() {
  const data = await ambil<{ jalan: Jalan[] }>("jalan");
  const sehat = await ambil<Record<string, any>>("sehat");
  const aku = await saya();

  if (!data) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-24">
        <h1 className="text-xl font-semibold">Layanan agent tidak merespons</h1>
        <pre className="mt-4 rounded-lg border border-line bg-card p-4 font-mono text-sm">
          cd sigap/agent{"\n"}python3 api.py
        </pre>
      </main>
    );
  }

  const jalan = data.jalan;
  const menunggu = jalan.filter((j) => j.status === "berjalan" || j.status === "ditahan");

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">
            SIGAP · Antrean keputusan
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Gangguan pasokan</h1>
          <p className="mt-1 text-sm text-muted">
            {jalan.length} penanganan · {menunggu.length} perlu perhatian
          </p>
        </div>
        {sehat && (
          <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
            {aku ? (
              <span className="rounded-full border border-line px-3 py-1 text-muted">
                {aku.nama} · {aku.peran}
              </span>
            ) : (
              <Link href="/sigap/masuk" className="rounded-full border border-accent/60 px-3 py-1 text-accent">
                masuk
              </Link>
            )}
            <span className="rounded-full border border-line px-3 py-1 text-muted">
              {sehat.lingkungan}
            </span>
            <span className={`rounded-full border px-3 py-1 ${sehat.sap_siap ? STATUS.selesai : STATUS.ditahan}`}>
              SAP {sehat.sap_siap ? "tersambung" : "belum"}
            </span>
            <span className={`rounded-full border px-3 py-1 ${sehat.model_siap ? STATUS.selesai : STATUS.ditahan}`}>
              model {sehat.model_siap ? "siap" : "belum"}
            </span>
          </div>
        )}
      </header>

      {jalan.length === 0 ? (
        <div className="mt-10 rounded-xl border border-dashed border-line p-8">
          <p className="text-sm text-muted">Belum ada peristiwa. Kirim satu:</p>
          <pre className="mt-3 overflow-x-auto rounded-lg border border-line bg-card p-4 font-mono text-xs">
{`curl -X POST localhost:8787/peristiwa \\
  -H 'content-type: application/json' \\
  -d '{"jenis":"port_closure","judul":"Ningbo tutup 6 hari",
       "pemicu":"advisory maritim","muatan":{"pelabuhan":"CNNGB"}}'`}
          </pre>
        </div>
      ) : (
        <ul className="mt-6 space-y-3">
          {jalan.map((j) => (
            <li key={j.id}>
              <Link
                href={`/sigap/${j.id}`}
                className="block rounded-xl border border-line bg-card p-5 transition-colors hover:border-accent/50"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="font-medium">{j.judul}</h2>
                    <p className="mt-1 text-sm text-muted">{j.pemicu}</p>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2 font-mono text-[11px]">
                    {j.mode === "runut" && <Tag color="orange">runut</Tag>}
                    <Status color={
                      j.status === "gagal" ? "red" : j.status === "selesai" ? "green" : "yellow"
                    }>{j.status}</Status>
                  </div>
                </div>

                {j.keputusan?.rekomendasi && (
                  <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-muted">
                    {j.keputusan.rekomendasi}
                  </p>
                )}
                {j.status === "ditahan" && j.keputusan?.alasan && (
                  <p className="mt-3 text-sm leading-relaxed text-amber-300/90">
                    {j.keputusan.alasan}
                  </p>
                )}
                {j.galat && (
                  <p className="mt-3 font-mono text-xs text-rose-300">{j.galat}</p>
                )}

                <p className="mt-3 font-mono text-[11px] text-muted">
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
