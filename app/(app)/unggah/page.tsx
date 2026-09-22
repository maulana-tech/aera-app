import { ambil, saya, type Unggahan } from "@/app/lib";
import Unggah from "./Unggah";
import { HapusUnggahan } from "./Hapus";

export const dynamic = "force-dynamic";

export default async function HalamanUnggah() {
  const [d, aku] = await Promise.all([
    ambil<{ unggahan: Unggahan[] }>("unggahan"),
    saya(),
  ]);

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Data
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Unggah data</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Selama SAP belum tersambung, data perusahaan bisa dimasukkan lewat CSV. Ini bukan
          pengganti sambungan SAP — begitu <span className="font-mono">SAP_API_KEY</span> diisi,
          alat memakai data langsung dan unggahan diabaikan.
        </p>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <Unggah masuk={!!aku} />

        <aside>
          <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
            Unggahan · {d?.unggahan.length ?? 0}
          </h2>
          {!d?.unggahan.length ? (
            <p className="text-muted-foreground mt-3 rounded-xl border border-dashed p-5 text-sm">
              Belum ada. Sistem memakai data contoh.
            </p>
          ) : (
            <ul className="mt-3 divide-y rounded-xl border">
              {d.unggahan.map((u) => (
                <li key={u.id} className="flex items-start gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">{u.berkas}</p>
                    <p className="text-muted-foreground mt-0.5 font-mono text-[11px]">
                      {u.entitas} · {u.baris} baris · {u.oleh}
                    </p>
                    <p className="text-muted-foreground mt-0.5 font-mono text-[10px]">
                      {new Date(u.diunggah).toLocaleString("id-ID")}
                    </p>
                  </div>
                  {aku && <HapusUnggahan id={u.id} />}
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </main>
  );
}
