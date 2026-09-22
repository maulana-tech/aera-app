import Link from "next/link";
import { notFound } from "next/navigation";

import { api } from "@/app/lib";
import { ReportActions } from "./Actions";

export const dynamic = "force-dynamic";

export default async function Report({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const d = await api<{ run_id: string; title: string; markdown: string }>(`reports/${id}`);
  if (!d) notFound();

  return (
    <main className="w-full px-6 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link href="/reports" className="text-muted-foreground hover:text-foreground font-mono text-xs">
          ← reports
        </Link>
        <ReportActions markdown={d.markdown} title={d.title} />
      </div>

      <div className="mt-6 max-w-4xl overflow-x-auto rounded-xl border">
        <pre className="whitespace-pre-wrap p-6 font-mono text-xs leading-relaxed">
          {d.markdown}
        </pre>
      </div>

      <p className="text-muted-foreground mt-3 max-w-4xl text-xs leading-relaxed">
        The report is assembled from the stored record, not re-summarised by a model — so
        it says exactly what the log says.
      </p>
    </main>
  );
}
