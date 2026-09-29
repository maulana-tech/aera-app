import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { api, idr, me, type Run } from "@/app/lib";
import { ActionPayload } from "@/components/action-payload";
import { AutoRefresh } from "@/components/auto-refresh";
import { Empty, Section } from "@/components/shell";
import { OriginBadge, StatusBadge } from "@/components/status-badge";
import Decision from "./Decision";

export const dynamic = "force-dynamic";

const when = (t: string) => new Date(t).toLocaleString("en-GB");

export default async function DisruptionDetail({ params }: { params: Promise<{ id: string }> }) {
  const run = await api<Run>(`runs/${(await params).id}`);
  if (!run) notFound();
  const user = await me();

  const steps = run.steps ?? [];
  const actions = run.actions ?? [];
  const approvals = run.approvals ?? [];
  const waiting = actions.filter((a) => a.status === "pending");
  const settled = actions.filter((a) => a.status !== "pending");

  return (
    <main className="w-full px-6 py-8">
      <Link
        href="/"
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs"
      >
        <ArrowLeft className="size-3" />
        Decision queue
      </Link>

      <header className="mt-5 border-b pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={run.status} />
          {run.mode === "guided" && <StatusBadge status="guided">guided mode</StatusBadge>}
          <span className="text-muted-foreground font-mono text-xs">{run.kind}</span>
          <AutoRefresh active={run.status === "running"} />
          {run.token_cost_idr > 0 && (
            <span className="text-muted-foreground font-mono text-xs tabular-nums">
              {idr(run.token_cost_idr)} of model time
            </span>
          )}
        </div>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight">{run.title}</h1>
        <p className="text-muted-foreground mt-1.5 max-w-2xl text-sm leading-relaxed">
          {run.trigger}
        </p>
      </header>

      {/* Why it stopped comes before anything else, because it explains the rest. */}
      {run.status === "held" && run.decision?.reason && (
        <div className="mt-8 max-w-3xl rounded-lg border border-dashed p-5">
          <p className="text-sm font-medium">Held before reasoning</p>
          <p className="text-muted-foreground mt-1.5 text-sm leading-relaxed">
            {run.decision.reason}
          </p>
        </div>
      )}

      {run.decision?.recommendation && (
        <Section title="Recommendation">
          <div className="max-w-3xl rounded-lg border p-5">
            <p className="whitespace-pre-line text-sm leading-relaxed">
              {run.decision.recommendation}
            </p>
            {Array.isArray(run.decision.untrusted_on_board) &&
              run.decision.untrusted_on_board.length > 0 && (
                <p className="text-muted-foreground mt-4 border-t pt-3 text-xs leading-relaxed">
                  Not yet trustworthy: {run.decision.untrusted_on_board.join(", ")}
                </p>
              )}
          </div>
        </Section>
      )}

      {/* The decision a person owes comes next, at full width. It used to sit in
          a 360px rail while an empty reasoning panel took the main column. */}
      <Section
        title={waiting.length ? `Waiting on you (${waiting.length})` : "Actions"}
        note={
          waiting.length && user
            ? `Your role approves up to ${idr(user.limit_idr)}. Anything above that escalates.`
            : undefined
        }
      >
        {actions.length === 0 ? (
          <Empty
            what="No action was raised."
            why="Nothing reached the point of proposing a change to SAP."
          />
        ) : (
          <ul className="max-w-4xl space-y-3">
            {[...waiting, ...settled].map((a) => {
              const history = approvals.filter((p) => p.action_id === a.id);
              const value = Number(a.payload.cost_idr ?? 0);
              return (
                <li key={a.id} className="rounded-lg border p-5">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <span className="font-mono text-sm font-medium">{a.kind}</span>
                    <StatusBadge status={a.status} />
                    {a.autonomous === 1 && (
                      <span className="text-muted-foreground text-xs">
                        ran on its own authority, under the limit
                      </span>
                    )}
                    {a.sap_reference && (
                      <span className="text-muted-foreground ml-auto font-mono text-xs">
                        SAP {a.sap_reference}
                      </span>
                    )}
                  </div>

                  <ActionPayload payload={a.payload} />

                  {history.map((p) => (
                    <p key={p.id} className="text-muted-foreground mt-3 text-xs">
                      {p.decision} by {p.decided_by} ({p.role}) on {when(p.at)}
                      {p.note ? `. ${p.note}` : ""}
                    </p>
                  ))}

                  {a.status === "pending" &&
                    (user ? (
                      <Decision
                        actionId={a.id}
                        valueIdr={value}
                        limitIdr={user.limit_idr}
                      />
                    ) : (
                      <p className="text-muted-foreground mt-4 border-t pt-3 text-xs">
                        Sign in to approve. The decision is recorded against your account.
                      </p>
                    ))}
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      <Section title={`How the system reasoned (${steps.length} steps)`}>
        {steps.length === 0 ? (
          <Empty
            what="No reasoning to show."
            why={
              run.status === "held"
                ? "The system stopped before it called a single agent, rather than guessing its way to an answer."
                : "Nothing has been recorded for this handling yet."
            }
          />
        ) : (
          <ol className="max-w-4xl divide-y rounded-lg border">
            {steps.map((s) => (
              <li key={s.seq} className="grid grid-cols-[92px_minmax(0,1fr)] gap-4 px-5 py-4">
                <div>
                  <p className="text-primary font-mono text-[11px] font-semibold">{s.stage}</p>
                  <p className="text-muted-foreground mt-1 text-[11px]">{s.agent_name}</p>
                </div>
                <div className="min-w-0">
                  <p className="text-sm leading-relaxed">{s.summary}</p>
                  {s.tools.length > 0 && (
                    <p className="text-muted-foreground mt-1.5 break-words font-mono text-[11px]">
                      {s.tools.join(", ")}
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
      </Section>
    </main>
  );
}
