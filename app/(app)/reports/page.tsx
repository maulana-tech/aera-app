import Link from "next/link";

import { api, idr, type Run } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

export default async function ReportList() {
  const d = await api<{ runs: Run[] }>("runs");

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Reports
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Write up a handling</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Any handling can become a report: what happened, how the system reasoned, the
          actions taken, and who approved them.
        </p>
      </header>

      {!d?.runs.length ? (
        <p className="text-muted-foreground mt-6 rounded-xl border border-dashed p-6 text-sm">
          No handlings to report on yet.
        </p>
      ) : (
        <ul className="mt-6 grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          {d.runs.map((r) => (
            <li key={r.id}>
              <Link
                href={`/reports/${r.id}`}
                className="hover:border-foreground/30 block rounded-xl border p-4 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="min-w-0 font-medium">{r.title}</p>
                  <StatusBadge status={r.status} />
                </div>
                <p className="text-muted-foreground mt-1 text-sm">{r.trigger}</p>
                <p className="text-muted-foreground mt-2 font-mono text-[11px]">
                  {new Date(r.started_at).toLocaleString("en-GB")}
                  {r.token_cost_idr > 0 && ` · ${idr(r.token_cost_idr)}`}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
