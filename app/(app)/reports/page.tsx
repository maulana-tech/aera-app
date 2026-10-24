import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { api, idr, type RunRow } from "@/app/lib";
import { ReportFiles } from "@/components/report-files";
import { Empty, Metric, PageHeader, Section } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

const when = (t: string) =>
  new Date(t).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

export default async function ReportList() {
  const runs = (await api<{ runs: RunRow[] }>("runs"))?.runs;

  if (!runs) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">The agent service is not responding</h1>
      </main>
    );
  }

  const attention = runs.filter((r) => r.status === "running" || r.status === "held").length;
  const actions = runs.reduce((a, r) => a + (r.action_count ?? 0), 0);
  const steps = runs.reduce((a, r) => a + r.step_count, 0);
  const cost = runs.reduce((a, r) => a + (r.token_cost_idr || 0), 0);

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Reports"
        lead="Any handling can become a report: what happened, how the system reasoned, the
              actions taken and who approved them. Read it here, or take it away as a PDF, and
              as an Excel workbook when it holds tables."
      />

      <Section
        title="Operations report"
        note="Every handling rolled up: how much was handled, the value committed, and realized against predicted cost once outcomes are in."
      >
        <div className="flex flex-col gap-5 rounded-lg border p-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="grid flex-1 grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
            <Metric value={String(runs.length)} label="Handlings"
                    note={attention ? `${attention} need attention` : "none waiting"} />
            <Metric value={String(actions)} label="Actions raised" />
            <Metric value={String(steps)} label="Agent steps" />
            <Metric value={idr(cost)} label="Model time" />
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <ReportFiles base="portfolio" />
            <Button asChild size="sm">
              <Link href="/reports/portfolio">
                Open
                <ArrowRight />
              </Link>
            </Button>
          </div>
        </div>
      </Section>

      <Section
        title={`Handlings (${runs.length})`}
        note="One report per handling. The workbook is offered when the handling produced tables: actions, steps, or rows a tool read."
      >
        {runs.length === 0 ? (
          <Empty what="No handlings to report on yet." why="A report is written from a handled event, and none has been handled." />
        ) : (
          <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {runs.map((r) => (
              <li key={r.id} className="flex">
                <ReportCard r={r} />
              </li>
            ))}
          </ul>
        )}
      </Section>
    </main>
  );
}

/* The card reads top to bottom in fixed rows (kind and status, title, trigger,
 * three figures, then date and files) so a grid of them lines up. The whole
 * card opens the report; the file buttons sit above that link. */
function ReportCard({ r }: { r: RunRow }) {
  const hasTables = r.step_count > 0 || (r.action_count ?? 0) > 0;
  return (
    <article className="bg-card hover:border-foreground/40 group relative flex w-full flex-col rounded-lg border p-5 transition-colors">
      <div className="flex h-5 items-center justify-between gap-3">
        <span className="text-muted-foreground truncate font-mono text-xs">{r.kind.replace(/_/g, " ")}</span>
        <span className="flex shrink-0 items-center gap-1.5">
          {r.mode === "guided" && <StatusBadge status="guided" />}
          <StatusBadge status={r.status} />
        </span>
      </div>

      <h2 className="group-hover:text-primary mt-2.5 line-clamp-2 min-h-12 text-base font-semibold leading-6 tracking-tight transition-colors">
        <Link href={`/reports/${r.id}`} className="after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none">
          {r.title}
        </Link>
      </h2>
      <p className="text-muted-foreground mt-1 truncate font-mono text-xs">{r.trigger || "Direct trigger"}</p>

      <dl className="mt-4 grid grid-cols-3 divide-x rounded-md border">
        {[
          ["Steps", String(r.step_count)],
          ["Actions", String(r.action_count ?? 0)],
          ["Model time", r.token_cost_idr > 0 ? idr(r.token_cost_idr) : "-"],
        ].map(([k, v]) => (
          <div key={k} className="min-w-0 px-3 py-2">
            <dt className="text-muted-foreground text-[11px]">{k}</dt>
            <dd className="mt-0.5 truncate font-mono text-sm tabular-nums">{v}</dd>
          </div>
        ))}
      </dl>

      <div className="flex-1" />
      <div className="mt-4 flex items-center justify-between gap-3 border-t pt-3">
        <span className="text-muted-foreground font-mono text-[11px]">{when(r.started_at)}</span>
        <span className="relative z-10 flex items-center gap-1.5">
          <ReportFiles base={`reports/${r.id}`} excel={hasTables} size="xs" />
        </span>
      </div>
    </article>
  );
}
