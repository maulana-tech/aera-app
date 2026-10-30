import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { StepSummary, stageLabel, stepAgentName } from "@/components/agent-activity";
import { Markdown } from "@/components/markdown";
import { api, idr, me, wib, type ExplorationGraph, type Run } from "@/app/lib";
import { ActionPayload } from "@/components/action-payload";
import { AutoRefresh } from "@/components/auto-refresh";
import { ReasoningTabs } from "@/components/reasoning-tabs";
import { Empty, Section } from "@/components/shell";
import { OriginBadge, StatusBadge } from "@/components/status-badge";
import Decision from "./Decision";
import Outcome from "./Outcome";
import { OUTWARD, Outbound } from "./Outbound";

export const dynamic = "force-dynamic";

// Jakarta, like the PDF and the workbook of this same handling: the stamps are
// UTC, and a page in the reader's own zone put a different time on the event
// than its own download did.
const when = (t: string) => wib(t);

export default async function DisruptionDetail({ params }: { params: Promise<{ id: string }> }) {
  const id = (await params).id;
  const run = await api<Run>(`runs/${id}`);
  if (!run) notFound();
  const user = await me();
  // The exploration graph for this run (empty unless SIGAP_GRAPH was on).
  const graph = await api<ExplorationGraph>(`runs/${id}/graph`);

  const steps = run.steps ?? [];
  const actions = run.actions ?? [];
  const approvals = run.approvals ?? [];
  const waiting = actions.filter((a) => a.status === "pending");
  // `decided`, not `settled`: in engine/report.py "settled" means the outcome
  // has been recorded, which is a different and later thing than being decided.
  const decided = actions.filter((a) => a.status !== "pending");
  // Went out, and nobody has written down what came of it yet. The kinds mirror
  // store.AWAITS_OUTCOME; `notify` is absent there because an internal message
  // has no realized cost and chasing one teaches people to ignore the chase.
  const AWAITS_OUTCOME = ["stock_transfer", "draft_po", "monitor",
                          "customer_notice", "supplier_request"];
  const owed = actions.filter(
    (a) => !a.outcome && (a.status === "sent" || a.status === "approved")
            && AWAITS_OUTCOME.includes(a.kind),
  );

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <Link
        href="/"
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs"
      >
        <ArrowLeft className="size-3" />
        Decision queue
      </Link>

      <header className="mt-3 border-b pb-4 md:mt-5 md:pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={run.status} />
          {run.mode === "guided" && <StatusBadge status="guided">guided mode</StatusBadge>}
          <span className="text-muted-foreground font-mono text-xs">{run.kind}</span>
          <AutoRefresh active={run.status === "running"} />
          <Link
            href={`/log/${run.id}`}
            className="text-muted-foreground hover:text-foreground font-mono text-xs underline underline-offset-2"
          >
            trace
          </Link>
          {run.token_cost_idr > 0 && (
            <span className="text-muted-foreground font-mono text-xs tabular-nums">
              {idr(run.token_cost_idr)} of model time
            </span>
          )}
        </div>
        <h1 className="mt-2 text-xl font-semibold tracking-tight md:mt-3 md:text-2xl">{run.title}</h1>
        <p className="text-muted-foreground mt-1.5 max-w-2xl text-sm leading-relaxed">
          {run.trigger}
        </p>
        {run.signal_source && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {/* Where the signal came from is the one thing on this page that
                can already be live, so it says which. */}
            <OriginBadge
              origin={run.signal_source.startsWith("http") ? "live" : "modelled"}
              source={run.signal_source.replace(/^https?:\/\//, "")}
            />
          </div>
        )}
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
            <Markdown>{run.decision.recommendation}</Markdown>
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
        title={
          waiting.length
            ? `Waiting on you (${waiting.length})`
            : owed.length
              ? `Actions · ${owed.length} awaiting an outcome`
              : "Actions"
        }
        note={
          waiting.length && user
            ? `Your role approves up to ${idr(user.limit_idr)}. Anything above that escalates.`
            : owed.length
              ? "What was sent is only half the record. Close the loop below and the next incident learns from this one."
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
            {[...waiting, ...decided].map((a) => {
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
                        {/* The number is shown plainly either way. Calling it
                            "SAP ..." when no SAP took it would be the lie; the
                            mode is carried by issued_in and said in words on
                            the trace and in the report. */}
                        {a.sap_reference.startsWith("email")
                          ? a.sap_reference
                          : a.issued_in === "demo"
                            ? a.sap_reference
                            : `SAP ${a.sap_reference}`}
                      </span>
                    )}
                  </div>

                  <ActionPayload payload={a.payload} />

                  {a.delivery && (
                    <Outbound actionId={a.id} status={a.status} delivery={a.delivery}
                      mayResend={!!user && (OUTWARD[a.kind] ?? []).includes(user.role)} />
                  )}

                  {history.map((p) => (
                    <p key={p.id} className="text-muted-foreground mt-3 text-xs">
                      {p.decision} by {p.decided_by} ({p.role}) on {when(p.at)}
                      {p.note ? `. ${p.note}` : ""}
                    </p>
                  ))}

                  {/* What came of it. The form only where the store would accept
                      one; once recorded it reads back, never edits. */}
                  {(a.outcome || owed.some((o) => o.id === a.id)) && (
                    <Outcome
                      actionId={a.id}
                      predictedIdr={value}
                      outcome={a.outcome}
                      outcomeAt={a.outcome_at}
                      detail={a.outcome_detail}
                    />
                  )}

                  {a.status === "pending" &&
                    (user ? (
                      <Decision
                        actionId={a.id}
                        valueIdr={value}
                        limitIdr={user.limit_idr}
                        role={user.role}
                        approvers={OUTWARD[a.kind]}
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

      <Section title="How the system reasoned">
        {steps.length === 0 && !(graph && graph.nodes.length) ? (
          <Empty
            what="No reasoning to show."
            why={
              run.status === "held"
                ? "The system stopped before it called a single agent, rather than guessing its way to an answer."
                : "Nothing has been recorded for this handling yet."
            }
          />
        ) : (
          <ReasoningTabs
            graph={graph}
            stepCount={steps.length}
            reasoning={
              steps.length === 0 ? (
                <Empty what="No step was recorded." why="The graph above holds what was found." />
              ) : (
                <ol className="max-w-4xl divide-y rounded-lg border">
                  {steps.map((s) => (
                    <li key={s.seq} className="grid grid-cols-[92px_minmax(0,1fr)] gap-4 px-5 py-4">
                      <div>
                        <p className="text-primary font-mono text-[11px] font-semibold">{stageLabel(s.stage)}</p>
                        <p className="text-muted-foreground mt-1 text-[11px]">{stepAgentName(s)}</p>
                      </div>
                      <div className="min-w-0">
                        <StepSummary step={s} />
                        {s.origin && (
                          <div className="mt-2">
                            <OriginBadge origin={s.origin} source={s.source} />
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              )
            }
          />
        )}
      </Section>
    </main>
  );
}
