import Link from "next/link";

import { api, idr } from "@/app/lib";
import { OriginBadge, StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

type Step = {
  id: number; run_id: string; title: string; seq: number; stage: string;
  agent: string; agent_name: string; summary: string; tools: string[];
  origin: string | null; source: string | null; at: string;
};
type Action = {
  id: string; run_id: string; title: string; kind: string; status: string;
  autonomous: number; payload: Record<string, any>; created_at: string;
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
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Records
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Log</h1>
        <p className="text-muted-foreground mt-1 max-w-2xl text-sm leading-relaxed">
          What the system did, what it proposed, and who decided. Rows here are never
          edited — a correction is written as a new row.
        </p>
      </header>

      {empty && <p className="text-muted-foreground mt-8 text-sm">Nothing recorded yet.</p>}

      {d.approvals.length > 0 && (
        <section className="mt-8">
          <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
            Approvals · {d.approvals.length}
          </h2>
          <ul className="mt-3 divide-y rounded-xl border">
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
                  {when(a.at)} →
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {d.actions.length > 0 && (
        <section className="mt-8">
          <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
            Actions · {d.actions.length}
          </h2>
          <ul className="mt-3 divide-y rounded-xl border">
            {d.actions.map((a) => (
              <li key={a.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <StatusBadge status={a.status} />
                  <span className="font-mono text-sm">{a.kind}</span>
                  {a.autonomous === 1 && (
                    <span className="text-muted-foreground text-xs">ran autonomously</span>
                  )}
                  {typeof a.payload.cost_idr === "number" && (
                    <span className="font-mono text-xs tabular-nums">
                      {idr(a.payload.cost_idr)}
                    </span>
                  )}
                  <Link
                    href={`/disruptions/${a.run_id}`}
                    className="text-muted-foreground hover:text-foreground ml-auto font-mono text-[11px]"
                  >
                    {when(a.created_at)} →
                  </Link>
                </div>
                <p className="text-muted-foreground mt-1 break-words font-mono text-[11px]">
                  {a.title}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {d.steps.length > 0 && (
        <section className="mt-8">
          <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
            Agent steps · {d.steps.length}
          </h2>
          <ul className="mt-3 divide-y rounded-xl border">
            {d.steps.map((s) => (
              <li key={s.id} className="grid grid-cols-[84px_1fr] gap-4 px-4 py-3">
                <div>
                  <p className="text-primary font-mono text-[11px] font-semibold tracking-wider">
                    {s.stage}
                  </p>
                  <p className="text-muted-foreground mt-0.5 text-[11px]">{s.agent_name}</p>
                </div>
                <div className="min-w-0">
                  <p className="text-sm leading-relaxed">{s.summary}</p>
                  {s.tools.length > 0 && (
                    <p className="text-muted-foreground mt-1 break-words font-mono text-[11px]">
                      {s.tools.join(" · ")}
                    </p>
                  )}
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    {s.origin && <OriginBadge origin={s.origin} source={s.source} />}
                    <Link
                      href={`/disruptions/${s.run_id}`}
                      className="text-muted-foreground hover:text-foreground font-mono text-[11px]"
                    >
                      {when(s.at)} →
                    </Link>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
