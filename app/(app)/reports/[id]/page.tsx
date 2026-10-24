import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { StepSummary, stageLabel, stepAgentName } from "@/components/agent-activity";
import { Markdown } from "@/components/markdown";
import { api, idr, type Run, type Step } from "@/app/lib";
import { ReportFiles } from "@/components/report-files";
import { ReportSend } from "@/components/report-send";
import { Fact, Rail, Section } from "@/components/shell";
import { OriginBadge, StatusBadge } from "@/components/status-badge";
import { ReportActions } from "./Actions";

export const dynamic = "force-dynamic";

type ReportDoc = {
  run_id: string; title: string; markdown: string;
  summary_by: string | null; summary?: string | null;
  sheets?: { name: string; rows: number }[];
};

const when = (t: string) =>
  new Date(t).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

// The first steps show; the rest fold, so the decision and the actions are not
// pushed a long scroll down by a sixty-step handling.
const FIRST_STEPS = 12;

export default async function Report({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // Two reads of one record: the markdown is what leaves the building, the run
  // is what gets laid out here. Same source, so they cannot disagree.
  const [doc, run] = await Promise.all([
    api<ReportDoc>(`reports/${id}`),
    api<Run>(`runs/${id}`),
  ]);
  if (!doc || !run) notFound();

  const steps = run.steps ?? [];
  const actions = run.actions ?? [];
  const approvals = run.approvals ?? [];
  const tools = steps.filter((s) => s.stage === "TOOL").length;
  const sheets = doc.sheets ?? [];
  const tables = sheets.filter((s) => s.name !== "Summary");
  const took = run.finished_at
    ? Math.round((Date.parse(run.finished_at) - Date.parse(run.started_at)) / 1000) : null;
  const untrusted = run.decision?.untrusted_on_board ?? [];

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <Link href="/reports" className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs">
        <ArrowLeft className="size-3" />
        Reports
      </Link>

      <header className="mt-3 flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b pb-5 md:mt-5 md:pb-6">
        <div className="min-w-0 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={run.status} />
            {run.mode === "guided" && <StatusBadge status="guided">guided</StatusBadge>}
            <span className="text-muted-foreground font-mono text-xs">{run.kind}</span>
          </div>
          <h1 className="mt-2 text-xl font-semibold tracking-tight md:text-2xl">{run.title}</h1>
          <p className="text-muted-foreground mt-1.5 text-sm leading-relaxed">{run.trigger}</p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <ReportFiles base={`reports/${id}`} excel={tables.length > 0} sheets={sheets.length} primary />
          <ReportSend base={`reports/${id}`} title={run.title} excel={tables.length > 0} />
          <ReportActions markdown={doc.markdown} title={doc.title} />
        </div>
      </header>

      <dl className="grid grid-cols-2 gap-x-8 gap-y-4 border-b py-5 sm:grid-cols-3 xl:grid-cols-6">
        {[
          ["Started", when(run.started_at)],
          ["Took", took != null ? `${Math.floor(took / 60)}m ${took % 60}s` : "still running"],
          ["Steps", String(steps.length)],
          ["Tool calls", String(tools)],
          ["Actions", String(actions.length)],
          ["Model time", run.token_cost_idr > 0 ? idr(run.token_cost_idr) : "-"],
        ].map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="text-muted-foreground text-xs">{k}</dt>
            <dd className="mt-1 truncate font-mono text-sm tabular-nums">{v}</dd>
          </div>
        ))}
      </dl>

      <div className="grid gap-x-10 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0">
          {doc.summary && (
            <Section title="Summary" note="Phrased by the auxiliary model from the figures in this report. It was given no number to invent.">
              <div className="rounded-lg border p-5">
                <Markdown>{doc.summary}</Markdown>
              </div>
            </Section>
          )}

          <Section title="Decision">
            <div className="rounded-lg border p-5">
              <Markdown>{run.decision?.recommendation ?? run.decision?.reason ?? "No decision was recorded."}</Markdown>
              {untrusted.length > 0 && (
                <p className="text-muted-foreground mt-4 border-t pt-3 text-xs leading-relaxed">
                  Not yet trustworthy: {untrusted.join(", ")}
                </p>
              )}
            </div>
          </Section>

          <Section
            title={`How the system reasoned (${steps.length} steps)`}
            action={steps.length > 0 && (
              <Link href={`/log/${id}`} className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs">
                Open the full trace <ArrowRight className="size-3" />
              </Link>
            )}
          >
            {steps.length === 0 ? (
              <p className="text-muted-foreground rounded-lg border border-dashed p-5 text-sm leading-relaxed">
                No agent reasoned on this handling. Anything above was raised without one.
              </p>
            ) : (
              <div className="rounded-lg border">
                <ol className="divide-y">
                  {steps.slice(0, FIRST_STEPS).map((s) => <StepRow key={s.seq} s={s} />)}
                </ol>
                {steps.length > FIRST_STEPS && (
                  <details className="group border-t">
                    <summary className="text-muted-foreground hover:text-foreground cursor-pointer list-none px-5 py-3 text-xs">
                      <span className="group-open:hidden">Show the other {steps.length - FIRST_STEPS} steps</span>
                      <span className="hidden group-open:inline">Fold the steps</span>
                    </summary>
                    <ol className="divide-y border-t">
                      {steps.slice(FIRST_STEPS).map((s) => <StepRow key={s.seq} s={s} />)}
                    </ol>
                  </details>
                )}
              </div>
            )}
          </Section>
        </div>

        <aside className="min-w-0 space-y-6 xl:mt-10">
          <Rail title={`Actions (${actions.length})`}>
            {actions.length === 0 ? (
              <p className="text-muted-foreground px-4 py-3 text-xs">None were raised.</p>
            ) : (
              actions.map((a) => (
                <div key={a.id} className="px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate font-mono text-xs font-medium">{a.kind}</span>
                    <StatusBadge status={a.status} />
                  </div>
                  <div className="text-muted-foreground mt-1 flex items-center justify-between gap-3 text-xs">
                    <span>{a.autonomous === 1 ? "on its own authority" : "needs approval"}</span>
                    <span className="text-foreground font-mono tabular-nums">
                      {typeof a.payload.cost_idr === "number" ? idr(a.payload.cost_idr) : "-"}
                    </span>
                  </div>
                </div>
              ))
            )}
          </Rail>

          {approvals.length > 0 && (
            <Rail title={`Approvals (${approvals.length})`}>
              {approvals.map((p) => (
                <div key={p.id} className="px-4 py-3 text-xs">
                  <div className="flex items-center justify-between gap-3">
                    <StatusBadge status={p.decision === "escalated" ? "pending" : p.decision}>{p.decision}</StatusBadge>
                    <span className="text-muted-foreground font-mono text-[11px]">{when(p.at)}</span>
                  </div>
                  <p className="mt-1.5">{p.decided_by} <span className="text-muted-foreground">({p.role})</span></p>
                </div>
              ))}
            </Rail>
          )}

          {tables.length > 0 && (
            <div>
              <Rail title={`In the Excel file (${sheets.length} sheets)`}>
                {sheets.map((s) => (
                  <Fact key={s.name} label={s.name} value={`${s.rows.toLocaleString("en-US")} rows`} tone="quiet" />
                ))}
              </Rail>
              <p className="text-muted-foreground mt-2 px-1 text-[11px] leading-relaxed">
                Every table the handling produced: its actions and steps, any table in the decision,
                and each row a tool read, one sheet per tool with the step and source beside it.
              </p>
            </div>
          )}

          <Rail title="Related">
            <Link href={`/disruptions/${id}`} className="hover:bg-muted/50 flex items-center justify-between px-4 py-2.5 text-xs">
              The decision page <ArrowRight className="text-muted-foreground size-3" />
            </Link>
            {steps.length > 0 && (
              <Link href={`/log/${id}`} className="hover:bg-muted/50 flex items-center justify-between border-t px-4 py-2.5 text-xs">
                The trace <ArrowRight className="text-muted-foreground size-3" />
              </Link>
            )}
          </Rail>
        </aside>
      </div>

      <p className="text-muted-foreground mt-10 border-t pt-5 text-xs leading-relaxed">
        Assembled from the stored record, not re-summarised by a model, so it says exactly what the
        log says. The PDF and the workbook are built from the same record.
      </p>
    </main>
  );
}

function StepRow({ s }: { s: Step }) {
  return (
    <li className="grid grid-cols-[92px_minmax(0,1fr)] gap-4 px-5 py-3.5">
      <div>
        <p className="text-primary font-mono text-[11px] font-semibold">{stageLabel(s.stage)}</p>
        <p className="text-muted-foreground mt-1 text-[11px]">{stepAgentName(s)}</p>
      </div>
      <div className="min-w-0">
        <StepSummary step={s} />
        {s.origin && (
          <div className="mt-1.5">
            <OriginBadge origin={s.origin} source={s.source} />
          </div>
        )}
      </div>
    </li>
  );
}
