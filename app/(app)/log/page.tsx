import Link from "next/link";

import { StepSummary, stageLabel, stepAgentName } from "@/components/agent-activity";
import { api, idr } from "@/app/lib";
import { Empty, PageHeader, Section } from "@/components/shell";
import { OriginBadge, StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

type Step = {
  id: number; run_id: string; title: string; seq: number; stage: string;
  agent: string; agent_name: string; summary: string; tools: string[];
  origin: string | null; source: string | null; at: string;
};
type Action = {
  id: string; run_id: string; title: string; kind: string; status: string;
  autonomous: number; payload: Record<string, unknown>; created_at: string;
};
type Approval = {
  id: number; action_id: string; run_id: string; action_kind: string;
  decided_by: string; role: string; decision: string; at: string;
};

const when = (t: string) =>
  new Date(t).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "medium" });

export default async function Log() {
  const d = await api<{ steps: Step[]; actions: Action[]; approvals: Approval[] }>("log");

  if (!d) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">The agent service is not responding</h1>
      </main>
    );
  }

  const empty = !d.steps.length && !d.actions.length && !d.approvals.length;

  return (
    <main className="w-full px-6 py-8">
      <PageHeader
        title="Log"
        lead="What the system did, what it proposed, and who decided. Rows here are never
              edited. A correction is written as a new row."
      />

      <div className="mt-8 space-y-10">
      {empty && (
        <Empty
          what="Nothing recorded yet."
          why="No event has been handled, so there is no trail to show."
        />
      )}

      {d.approvals.length > 0 && (
        <Section title={`Approvals (${d.approvals.length})`} className="mt-0">
          <ul className="divide-y rounded-lg border">
            {d.approvals.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 text-sm">
                <StatusBadge status={a.decision === "escalated" ? "pending" : a.decision} />
                <span className="font-mono text-xs">{a.action_kind}</span>
                <span className="text-muted-foreground">by</span>
                <span>{a.decided_by}</span>
                <span className="text-muted-foreground font-mono text-xs">({a.role})</span>
                <Link
                  href={`/disruptions/${a.run_id}`}
                  className="text-muted-foreground hover:text-foreground ml-auto font-mono text-[11px]"
                >
                  {when(a.at)}
                </Link>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {d.actions.length > 0 && (
        <Section title={`Actions (${d.actions.length})`} className="mt-0">
          <ul className="divide-y rounded-lg border">
            {d.actions.map((a) => (
              <li
                key={a.id}
                className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 px-4 py-3.5"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                    <StatusBadge status={a.status} />
                    <span className="font-mono text-sm">{a.kind}</span>
                    {a.autonomous === 1 && (
                      <span className="text-muted-foreground text-xs">
                        ran on its own authority
                      </span>
                    )}
                  </div>
                  <Link
                    href={`/disruptions/${a.run_id}`}
                    className="text-muted-foreground hover:text-foreground mt-1 block truncate text-xs"
                  >
                    {a.title}
                  </Link>
                </div>
                <div className="shrink-0 text-right">
                  {typeof a.payload.cost_idr === "number" && (
                    <p className="font-mono text-sm tabular-nums">
                      {idr(a.payload.cost_idr)}
                    </p>
                  )}
                  <p className="text-muted-foreground mt-0.5 font-mono text-[11px]">
                    {when(a.created_at)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title={`Agent steps (${d.steps.length})`} className="mt-0">
        {d.steps.length === 0 ? (
          <Empty
            what="No agent has reasoned yet."
            why="Every action above was raised by a person or by seed data. The team itself
                 has never run, so there is no chain of reasoning to show."
            fix="set AWS_REGION, then POST an event to /events"
          />
        ) : (
          <ul className="divide-y rounded-lg border">
            {d.steps.map((s) => (
              <li key={s.id} className="grid grid-cols-[84px_1fr] gap-4 px-4 py-3">
                <div>
                  <p className="text-primary font-mono text-[11px] font-semibold tracking-wider">
                    {stageLabel(s.stage)}
                  </p>
                  <p className="text-muted-foreground mt-0.5 text-[11px]">{stepAgentName(s)}</p>
                </div>
                <div className="min-w-0">
                  <StepSummary step={s} />
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    {s.origin && <OriginBadge origin={s.origin} source={s.source} />}
                    <Link
                      href={`/disruptions/${s.run_id}`}
                      className="text-muted-foreground hover:text-foreground font-mono text-[11px]"
                    >
                      {when(s.at)}
                    </Link>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>
      </div>
    </main>
  );
}
