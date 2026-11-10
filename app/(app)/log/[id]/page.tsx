import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { apiResult, usd, when as stamp, type Trace } from "@/app/lib";
import { AutoRefresh } from "@/components/auto-refresh";
import { OriginBadge, StatusBadge } from "@/components/status-badge";
import TraceView from "@/components/trace-view";

export const dynamic = "force-dynamic";

const when = (t: string | null) => (t ? stamp(t, { seconds: true }) : "");

export default async function TracePage({
  params, searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const id = (await params).id;
  const seq = Number((await searchParams).seq) || null;
  const r = await apiResult<Trace>(`runs/${id}/trace`);
  if (!r.data) {
    if (r.error?.includes("not found")) notFound();
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">The trace could not be read</h1>
        <p className="text-muted-foreground mt-2 text-sm">{r.error}</p>
      </main>
    );
  }
  const t = r.data;
  const seconds = t.run.finished_at && t.run.started_at
    ? Math.round((Date.parse(t.run.finished_at) - Date.parse(t.run.started_at)) / 1000) : null;

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <Link href="/log" className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs">
        <ArrowLeft className="size-3" />
        Log
      </Link>

      <header className="mt-3 border-b pb-4 md:mt-5 md:pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={t.run.status} />
          <span className="text-muted-foreground font-mono text-xs">{t.run.kind}</span>
          <span className="text-muted-foreground font-mono text-xs">{t.run.id}</span>
          <AutoRefresh active={t.run.status === "running"} />
        </div>
        <h1 className="mt-2 text-xl font-semibold tracking-tight md:text-2xl">Trace · {t.run.title}</h1>
        <p className="text-muted-foreground mt-1.5 max-w-2xl text-sm leading-relaxed">{t.run.trigger}</p>
        {t.run.error && <p className="mt-2 font-mono text-xs text-rose-600 dark:text-rose-400">{t.run.error}</p>}

        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
          {[
            ["Started", when(t.run.started_at)],
            ["Took", seconds != null ? `${seconds}s` : "still running"],
            ["Steps", String(t.totals.steps)],
            ["Tool calls", `${t.totals.tool_calls}${t.totals.errors ? ` (${t.totals.errors} failed)` : ""}`],
            ["Agents · sources", `${t.totals.agents} · ${t.totals.sources}`],
            ["Model spend", t.run.cost_usd ? usd(t.run.cost_usd) : "-"],
          ].map(([k, v]) => (
            <div key={k}>
              <dt className="text-muted-foreground text-xs">{k}</dt>
              <dd suppressHydrationWarning className="mt-0.5 font-mono text-sm tabular-nums">{v}</dd>
            </div>
          ))}
        </dl>
        {Object.keys(t.totals.by_origin).length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="text-muted-foreground text-xs">What the tool calls read:</span>
            {Object.entries(t.totals.by_origin).map(([o, n]) =>
              ["live", "cached", "derived", "modelled", "missing"].includes(o)
                ? <OriginBadge key={o} origin={o} source={`${n}`} />
                : <span key={o} className="text-muted-foreground font-mono text-[11px]">{o} · {n}</span>)}
          </div>
        )}
        <Link href={`/work/${t.run.id}`} className="text-muted-foreground hover:text-foreground mt-3 inline-block text-xs underline underline-offset-2">
          The outcome, actions and proofs for this run
        </Link>
      </header>

      {t.calls.length === 0 ? (
        <p className="text-muted-foreground mt-8 text-sm">
          Nothing was recorded for this run: the team has not taken a step yet, or it was
          held before it started.
        </p>
      ) : (
        <TraceView trace={t} focusSeq={seq} />
      )}
    </main>
  );
}
