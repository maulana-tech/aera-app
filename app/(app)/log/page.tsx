import Link from "next/link";

import { StepSummary, stageLabel, stepAgentName } from "@/components/agent-activity";
import { api, usd, when as stamp, type Action, type RunRow, type Step } from "@/app/lib";
import { Empty, PageHeader, Section } from "@/components/shell";
import { OriginBadge, StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

type LogStep = Step & { id: number; run_id: string; title: string; work_kind: string };

// With seconds: in a log the order of two things a second apart is the point.
const when = (t: string) => stamp(t, { seconds: true, mark: false });

export default async function Log() {
  const [d, runsPayload] = await Promise.all([
    api<{ steps: LogStep[]; actions: Action[] }>("log"),
    api<{ runs: RunRow[] }>("runs"),
  ]);
  const traced = (runsPayload?.runs ?? []).filter((r) => r.step_count > 0);

  if (!d) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">The agent service is not responding</h1>
      </main>
    );
  }
  const empty = !d.steps.length && !d.actions.length;

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Log"
        lead="What the team did, what it proposed, and who decided. Rows here are never edited; a correction is written as a new row. Times are UTC."
      />

      <div className="mt-8 space-y-10">
        {traced.length > 0 && (
          <Section title={`Traces (${traced.length})`} className="mt-0"
            note="Each run as a graph: the supervisor, the specialists it asked, every tool they called and the source each figure came from.">
            <ul className="divide-y rounded-lg border">
              {traced.map((r) => (
                <li key={r.id}>
                  <Link href={`/log/${r.id}`} className="hover:bg-muted/50 flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3">
                    <StatusBadge status={r.status} />
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">{r.title}</span>
                    <span className="text-muted-foreground font-mono text-[11px] tabular-nums">
                      {r.step_count} steps · {r.tool_count} tool calls{r.cost_usd > 0 ? ` · ${usd(r.cost_usd)}` : ""}
                    </span>
                    <span className="text-muted-foreground font-mono text-[11px]">{when(r.started_at)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {empty && <Empty what="Nothing recorded yet." why="The team has not worked on anything, so there is no trail to show." />}

        {d.actions.length > 0 && (
          <Section title={`Actions (${d.actions.length})`} className="mt-0">
            <ul className="divide-y rounded-lg border">
              {d.actions.map((a) => (
                <li key={a.id} className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 px-4 py-3.5">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                      <StatusBadge status={a.status} />
                      <span className="font-mono text-sm">{a.kind}</span>
                      {a.autonomous && <span className="text-muted-foreground text-xs">ran on its own authority</span>}
                    </div>
                    <Link href={`/work/${a.run_id}`} className="text-muted-foreground hover:text-foreground mt-1 block truncate text-xs">
                      {a.work_title}
                    </Link>
                  </div>
                  <div className="shrink-0 text-right">
                    {a.value_usd > 0 && <p className="font-mono text-sm tabular-nums">{usd(a.value_usd)}</p>}
                    <p className="text-muted-foreground mt-0.5 font-mono text-[11px]">{when(a.created_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          </Section>
        )}

        <Section title={`Agent steps (${d.steps.length})`} className="mt-0">
          {d.steps.length === 0 ? (
            <Empty what="No agent has reasoned yet."
              why="Runs without a model key are held before the team reasons, so there is no chain of reasoning to show."
              fix="set NEARAI_API_KEY, then give the team a request on the Work page" />
          ) : (
            <ul className="divide-y rounded-lg border">
              {d.steps.map((s) => (
                <li key={s.id} className="grid grid-cols-[84px_1fr] gap-4 px-4 py-3">
                  <div>
                    <p className="text-primary font-mono text-[11px] font-semibold tracking-wider">{stageLabel(s.stage)}</p>
                    <p className="text-muted-foreground mt-0.5 text-[11px]">{stepAgentName(s)}</p>
                  </div>
                  <div className="min-w-0">
                    <StepSummary step={s} />
                    <div className="mt-1.5 flex flex-wrap items-center gap-2">
                      {s.origin && <OriginBadge origin={s.origin} source={s.source} />}
                      <Link href={`/log/${s.run_id}?seq=${s.seq}#seq-${s.seq}`} className="text-muted-foreground hover:text-foreground font-mono text-[11px]">
                        {when(s.at)} · {s.title}
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
