import Link from "next/link";
import { notFound } from "next/navigation";

import { ambil } from "@/app/lib";
import { AksiLaporan } from "./Aksi";

export const dynamic = "force-dynamic";

export default async function Laporan({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const d = await ambil<{ jalan_id: string; judul: string; markdown: string }>(`laporan/${id}`);
  if (!d) notFound();

  return (
    <main className="w-full px-6 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link href="/laporan" className="text-muted-foreground hover:text-foreground font-mono text-xs">
          ← laporan
        </Link>
        <AksiLaporan markdown={d.markdown} judul={d.judul} />
      </div>

      <div className="mt-6 max-w-4xl overflow-x-auto rounded-xl border">
        <pre className="whitespace-pre-wrap p-6 font-mono text-xs leading-relaxed">
          {d.markdown}
        </pre>
      </div>

      <p className="text-muted-foreground mt-3 max-w-4xl text-xs leading-relaxed">
        Laporan disusun dari catatan yang tersimpan, bukan diringkas ulang oleh model —
        jadi isinya sama persis dengan yang tercatat di log.
      </p>
    </main>
  );
}
