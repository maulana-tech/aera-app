import Link from "next/link";

import { ambil, rupiah, type Jalan } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

export default async function DaftarLaporan() {
  const d = await ambil<{ jalan: Jalan[] }>("jalan");

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Laporan
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Susun laporan</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Tiap penanganan bisa dijadikan laporan: apa yang terjadi, jalan pikiran sistem,
          aksi yang diambil, dan siapa yang menyetujui.
        </p>
      </header>

      {!d?.jalan.length ? (
        <p className="text-muted-foreground mt-6 rounded-xl border border-dashed p-6 text-sm">
          Belum ada penanganan untuk dilaporkan.
        </p>
      ) : (
        <ul className="mt-6 grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          {d.jalan.map((j) => (
            <li key={j.id}>
              <Link
                href={`/laporan/${j.id}`}
                className="hover:border-foreground/30 block rounded-xl border p-4 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="min-w-0 font-medium">{j.judul}</p>
                  <StatusBadge status={j.status} />
                </div>
                <p className="text-muted-foreground mt-1 text-sm">{j.pemicu}</p>
                <p className="text-muted-foreground mt-2 font-mono text-[11px]">
                  {new Date(j.mulai).toLocaleString("id-ID")}
                  {j.biaya_token_idr > 0 && ` · ${rupiah(j.biaya_token_idr)}`}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
