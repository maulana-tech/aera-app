import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { api, idr, type Run } from "@/app/lib";
import { OriginBadge, StatusBadge } from "@/components/status-badge";
import { ReportActions } from "./Actions";

export const dynamic = "force-dynamic";

const when = (t: string) => new Date(t).toLocaleString("en-GB");

function Part({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t pt-6">
      <h2 className="text-muted-foreground text-xs font-medium">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export default async function Report({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // Two reads of one record: the markdown is what leaves the building, the run
  // is what gets laid out here. Same source, so they cannot disagree.
  const [doc, run] = await Promise.all([
    api<{ run_id: string; title: string; markdown: string }>(`reports/${id}`),
    api<Run>(`runs/${id}`),
  ]);
  if (!doc || !run) notFound();

  const steps = run.steps ?? [];
  const actions = run.actions ?? [];
  const approvals = run.approvals ?? [];

  return (
    <main className="w-full px-6 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/reports"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs"
        >
          <ArrowLeft className="size-3" />
          Reports
        </Link>
        <ReportActions markdown={doc.markdown} title={doc.title} />
      </div>

      <article className="mt-6 max-w-3xl space-y-8">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">{run.title}</h1>
          <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{run.trigger}</p>
          <dl className="mt-5 grid gap-x-8 gap-y-3 border-y py-4 sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground text-xs">Kind</dt>
              <dd className="mt-0.5 font-mono text-sm">{run.kind}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-xs">Started</dt>
              <dd className="mt-0.5 font-mono text-sm">{when(run.started_at)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-xs">Outcome</dt>
              <dd className="mt-1 flex flex-wrap items-center gap-2">
                <StatusBadge status={run.status} />
                {run.mode === "guided" && <StatusBadge status="guided">guided</StatusBadge>}
              </dd>
            </div>
          </dl>
        </header>

        <Part title="Decision">
          <p className="whitespace-pre-line text-sm leading-relaxed">
            {run.decision?.recommendation ?? run.decision?.reason ?? "No decision was recorded."}
          </p>
        </Part>

        <Part title={`Actions (${actions.length})`}>
          {actions.length === 0 ? (
            <p className="text-muted-foreground text-sm">None were raised.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-muted-foreground py-2 text-left text-xs font-normal">
                    Action
                  </th>
                  <th className="text-muted-foreground py-2 text-right text-xs font-normal">
                    Value
                  </th>
                  <th className="text-muted-foreground py-2 text-right text-xs font-normal">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {actions.map((a) => (
                  <tr key={a.id}>
                    <td className="py-2.5 font-mono text-xs">
                      {a.kind}
                      {a.autonomous === 1 && (
                        <span className="text-muted-foreground ml-2 font-sans">
                          on its own authority
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 text-right font-mono tabular-nums">
                      {typeof a.payload.cost_idr === "number" ? idr(a.payload.cost_idr) : "-"}
                    </td>
                    <td className="py-2.5 text-right">
                      <StatusBadge status={a.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Part>

        <Part title={`Reasoning (${steps.length} steps)`}>
          {steps.length === 0 ? (
            <p className="text-muted-foreground text-sm leading-relaxed">
              No agent reasoned on this handling. Anything above was raised without one.
            </p>
          ) : (
            <ol className="space-y-3">
              {steps.map((s) => (
                <li key={s.seq} className="grid grid-cols-[92px_minmax(0,1fr)] gap-4">
                  <span className="text-muted-foreground font-mono text-[11px]">
                    {s.stage}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm leading-relaxed">
                      <span className="text-muted-foreground">{s.agent_name}. </span>
                      {s.summary}
                    </p>
                    {s.origin && (
                      <div className="mt-1.5">
                        <OriginBadge origin={s.origin} source={s.source} />
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Part>

        {approvals.length > 0 && (
          <Part title={`Approvals (${approvals.length})`}>
            <ul className="space-y-2">
              {approvals.map((p) => (
                <li key={p.id} className="text-sm">
                  <span className="font-medium">{p.decision}</span>
                  <span className="text-muted-foreground">
                    {" "}by {p.decided_by} ({p.role}) on {when(p.at)}
                  </span>
                </li>
              ))}
            </ul>
          </Part>
        )}

        <p className="text-muted-foreground border-t pt-6 text-xs leading-relaxed">
          Assembled from the stored record, not re-summarised by a model, so it says
          exactly what the log says. Copy or download it above to send it on.
        </p>
      </article>
    </main>
  );
}
