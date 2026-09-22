import Link from "next/link";
import { notFound } from "next/navigation";

import { api, idr, me, type Run } from "@/app/lib";
import { AutoRefresh } from "@/components/auto-refresh";
import { OriginBadge, StatusBadge } from "@/components/status-badge";
import Decision from "./Decision";

export const dynamic = "force-dynamic";

export default async function DisruptionDetail({ params }: { params: Promise<{ id: string }> }) {
  const run = await api<Run>(`runs/${(await params).id}`);
  if (!run) notFound();
  const user = await me();

  const steps = run.steps ?? [];
  const actions = run.actions ?? [];
  const approvals = run.approvals ?? [];

  return (
    <main className="w-full px-6 py-8">
      <Link href="/" className="font-mono text-xs text-muted-foreground hover:text-foreground">
        ← queue
      </Link>

      <header className="mt-4 flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-primary">{run.kind}</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">{run.title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{run.trigger}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
          {run.mode === "guided" && (
            <StatusBadge status="guided" className="px-3 py-1">guided mode</StatusBadge>
          )}
          <AutoRefresh active={run.status === "running"} />
          <StatusBadge status={run.status} />
          {run.token_cost_idr > 0 && (
            <span className="rounded-full border border-border px-3 py-1 text-muted-foreground">
              {idr(run.token_cost_idr)}
            </span>
          )}
        </div>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="rounded-xl border border-border">
          <div className="border-b border-border px-5 py-3">
            <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
              How the system reasoned · {steps.length} steps
            </p>
          </div>
          {steps.length === 0 ? (
            <p className="px-5 py-8 text-sm text-muted-foreground">
              {run.status === "held"
                ? "No steps — the system stopped before reasoning."
                : "No steps recorded yet."}
            </p>
          ) : (
            <ol className="divide-y divide-border">
              {steps.map((s) => (
                <li key={s.seq} className="grid grid-cols-[86px_1fr] gap-4 px-5 py-4">
                  <div>
                    <p className="font-mono text-[11px] font-semibold tracking-wider text-primary">
                      {s.stage}
                    </p>
                    <p className="mt-1 text-[11px] text-muted-foreground">{s.agent_name}</p>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm leading-relaxed">{s.summary}</p>
                    {s.tools.length > 0 && (
                      <p className="mt-1.5 break-words font-mono text-[11px] text-muted-foreground">
                        {s.tools.join(" · ")}
                      </p>
                    )}
                    {s.origin && (
                      <div className="mt-2">
                        <OriginBadge origin={s.origin} source={s.source} />
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>

        <aside className="space-y-5">
          {run.decision && (
            <div className="rounded-xl border p-5">
              <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                {run.status === "held" ? "Held" : "Recommendation"}
              </p>
              <p className="mt-2 whitespace-pre-line text-sm leading-relaxed">
                {run.decision.recommendation ?? run.decision.reason ?? "—"}
              </p>
              {Array.isArray(run.decision.untrusted_on_board) &&
                run.decision.untrusted_on_board.length > 0 && (
                  <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                    Data not yet trustworthy: {run.decision.untrusted_on_board.join(", ")}
                  </p>
                )}
            </div>
          )}

          <div className="rounded-xl border border-border">
            <div className="border-b border-border px-5 py-3">
              <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
                Actions · {actions.length}
              </p>
            </div>
            {actions.length === 0 ? (
              <p className="px-5 py-6 text-sm text-muted-foreground">
                No actions raised yet.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {actions.map((a) => {
                  const history = approvals.filter((p) => p.action_id === a.id);
                  return (
                    <li key={a.id} className="px-5 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-mono text-sm">{a.kind}</span>
                        <StatusBadge status={a.status} />
                      </div>
                      <p className="mt-1.5 break-words font-mono text-[11px] text-muted-foreground">
                        {Object.entries(a.payload).map(([k, v]) => `${k}=${v}`).join(" · ")}
                      </p>
                      {a.autonomous === 1 && (
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          ran autonomously — under the authority limit
                        </p>
                      )}
                      {history.map((p) => (
                        <p key={p.id} className="mt-1.5 text-[11px] text-muted-foreground">
                          {p.decision} by {p.decided_by} ({p.role}) ·{" "}
                          {new Date(p.at).toLocaleString("en-GB")}
                        </p>
                      ))}
                      {a.status === "pending" &&
                        (user ? (
                          <Decision
                            actionId={a.id}
                            valueIdr={Number(a.payload.cost_idr ?? 0)}
                            limitIdr={user.limit_idr}
                          />
                        ) : (
                          <p className="mt-2 text-[11px] text-muted-foreground">
                            Sign in to approve.
                          </p>
                        ))}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
