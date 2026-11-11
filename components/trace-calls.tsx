"use client";

import { ChevronRight, Download, Loader2, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Markdown } from "@/components/markdown";
import { OriginBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";
import { usd, when, type Trace, type TraceCall, type TraceNode } from "@/app/lib";

/* Every step of a handling, in order, with what it carried in full.
 *
 * A tool call shows its arguments, its provenance (origin, source, the note
 * the source wrote, when it was read), how long it took, how many rows came
 * back and how many of those the model was shown. Its result comes in the
 * trace as a preview; "load all" fetches the step itself, every row. */

const KINDS: { k: string; label: string }[] = [
  { k: "all", label: "All" },
  { k: "tool", label: "Tool calls" },
  { k: "delegate", label: "Delegations" },
  { k: "finding", label: "Findings" },
];

export const KIND_LABEL: Record<string, string> = {
  delegate: "delegates", tool: "calls", finding: "reports", summary: "answers", fallback: "fallback",
};

const time = (t: string | null) =>
  t ? new Date(t).toLocaleTimeString("en-GB", {
    hour12: false,
    timeZone: "UTC",
  }) : "";



export function brief(c: TraceCall): string {
  if (c.kind === "tool") {
    const args = Object.entries(c.arguments ?? {})
      .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`).join(", ");
    return `${c.tool}(${args})`;
  }
  if (c.kind === "delegate") return c.task ?? "";
  return (c.summary ?? "").split("\n").find((l) => l.trim()) ?? "";
}

export function TraceCalls({
  trace, runId, nodeFilter, onClearNode, focusSeq,
}: {
  trace: Trace;
  runId: string;
  nodeFilter: string | null;
  onClearNode: () => void;
  focusSeq?: number | null;
}) {
  const [kind, setKind] = useState("all");
  const [origin, setOrigin] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Set<number>>(() => new Set(focusSeq ? [focusSeq] : []));

  const names = useMemo(() => {
    const m: Record<string, TraceNode> = {};
    for (const n of trace.nodes) if (n.kind === "agent" && n.agent) m[n.agent] = n;
    return m;
  }, [trace.nodes]);
  const node = nodeFilter ? trace.nodes.find((n) => n.id === nodeFilter) : null;

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return trace.calls.filter((c) =>
      (kind === "all" || c.kind === kind || (kind === "finding" && c.kind === "summary"))
      && (!origin || c.origin === origin || (origin === "error" && !!c.error))
      && (!nodeFilter || c.node_ids.includes(nodeFilter))
      && (!needle || JSON.stringify([c.tool, c.agent, c.task, c.summary, c.arguments, c.source, c.note])
        .toLowerCase().includes(needle)));
  }, [trace.calls, kind, origin, q, nodeFilter]);

  const toggle = (seq: number) => setOpen((o) => {
    const n = new Set(o);
    if (n.has(seq)) n.delete(seq); else n.add(seq);
    return n;
  });

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex overflow-hidden rounded-md border">
          {KINDS.map((x) => (
            <button key={x.k} type="button" onClick={() => setKind(x.k)}
                    className={cn("px-2.5 py-1 text-xs", kind === x.k ? "bg-foreground text-background" : "hover:bg-muted")}>
              {x.label}
            </button>
          ))}
        </div>
        {Object.entries(trace.totals.by_origin).map(([o, n]) => (
          <button key={o} type="button" onClick={() => setOrigin(origin === o ? null : o)}
                  className={cn("rounded-md border px-2 py-1 font-mono text-[11px]",
                    origin === o ? "bg-foreground text-background" : "hover:bg-muted")}>
            {o} {n}
          </button>
        ))}
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search tool, agent, note…"
               className="bg-background h-7 w-56 rounded-md border px-2 text-xs" />
        {node && (
          <span className="bg-muted inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs">
            <span className="text-muted-foreground">through</span>
            <span className="font-medium">{node.label}</span>
            <button type="button" onClick={onClearNode} aria-label="Clear the node filter">
              <X className="size-3" />
            </button>
          </span>
        )}
        <span className="text-muted-foreground ml-auto text-xs">{shown.length} of {trace.calls.length} steps</span>
      </div>

      <ol className="mt-3 divide-y rounded-lg border">
        {shown.map((c) => (
          <CallRow key={c.seq} c={c} runId={runId} open={open.has(c.seq)} onToggle={() => toggle(c.seq)}
                   who={names[c.agent]} by={c.by ? names[c.by] : undefined} focus={focusSeq === c.seq} />
        ))}
        {shown.length === 0 && <li className="text-muted-foreground px-4 py-6 text-sm">No step matches.</li>}
      </ol>
    </div>
  );
}

function CallRow({
  c, runId, open, onToggle, who, by, focus,
}: {
  c: TraceCall; runId: string; open: boolean; onToggle: () => void;
  who?: TraceNode; by?: TraceNode; focus: boolean;
}) {
  const ref = useRef<HTMLLIElement | null>(null);
  useEffect(() => { if (focus) ref.current?.scrollIntoView({ block: "center" }); }, [focus]);
  const nested = c.kind === "tool" && c.parent_seq != null;
  const failed = !!c.error;

  return (
    <li ref={ref} id={`seq-${c.seq}`} className={cn(focus && "bg-muted/40")}>
      <button type="button" onClick={onToggle}
              className="hover:bg-muted/50 grid w-full grid-cols-[18px_44px_64px_minmax(0,1fr)_auto] items-center gap-2 px-3 py-2 text-left">
        <ChevronRight className={cn("text-muted-foreground size-3.5 transition-transform", open && "rotate-90")} />
        <span className="text-muted-foreground font-mono text-[11px] tabular-nums">#{c.seq}</span>
        <span suppressHydrationWarning className="text-muted-foreground font-mono text-[11px] tabular-nums">{time(c.at)}</span>
        <span className={cn("flex min-w-0 items-center gap-2 text-xs", nested && "pl-4")}>
          <span className="shrink-0 font-medium">
            {c.kind === "delegate" ? `${by?.label ?? "Supervisor"} → ${who?.label ?? c.agent}` : who?.label ?? c.agent}
          </span>
          <span className="text-muted-foreground shrink-0 font-mono text-[10px]">{KIND_LABEL[c.kind] ?? c.kind}</span>
          <span className={cn("truncate", c.kind === "tool" && "font-mono text-[11px]", failed && "text-rose-600 dark:text-rose-400")}>
            {brief(c)}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {c.rows != null && <span className="text-muted-foreground font-mono text-[10px]">{c.rows} rows</span>}
          {c.ms != null && <span className="text-muted-foreground font-mono text-[10px]">{c.ms} ms</span>}
          {c.origin && <OriginBadge origin={c.origin} />}
          {failed && c.kind === "tool" && <span className="font-mono text-[10px] text-rose-600 dark:text-rose-400">error</span>}
        </span>
      </button>
      {open && <CallDetail c={c} runId={runId} />}
    </li>
  );
}

function Field({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[96px_minmax(0,1fr)] gap-3 py-1 text-xs">
      <span className="text-muted-foreground">{k}</span>
      <span className="min-w-0 break-words">{children}</span>
    </div>
  );
}

/** Everything one step carried. `compact` drops the left indent that lines it
 *  up under the list's columns, for the node drawer. */
export function CallDetail({ c, runId, compact = false }: { c: TraceCall; runId: string; compact?: boolean }) {
  const [full, setFull] = useState<unknown>(undefined);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function loadFull(): Promise<unknown> {
    if (full !== undefined) return full;
    setLoading(true);
    setErr(null);
    try {
      const r = await fetch(`/api/aera/runs/${runId}/steps/${c.seq}`);
      const body = await r.json();
      if (!r.ok) throw new Error(body.error ?? `HTTP ${r.status}`);
      const value = body.detail?.result;
      setFull(value);
      return value;
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      return undefined;
    } finally {
      setLoading(false);
    }
  }

  async function download() {
    const r = await fetch(`/api/aera/runs/${runId}/steps/${c.seq}`);
    const blob = new Blob([JSON.stringify(await r.json(), null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${runId}-step-${c.seq}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const result = full !== undefined ? full : c.result;
  return (
    <div className={cn("bg-muted/20 space-y-3 border-t px-4 py-3", !compact && "md:pl-[150px]")}>
      <div className="divide-y">
        {c.kind === "tool" && <Field k="tool"><span className="font-mono">{c.tool}</span></Field>}
        {c.origin && <Field k="origin"><OriginBadge origin={c.origin} /></Field>}
        {c.source && <Field k="source"><span className="font-mono">{c.source}</span></Field>}
        {c.note && <Field k="source note">{c.note}</Field>}
        {c.fetched_at && (
          <Field k="read at">
            <span suppressHydrationWarning>
              {when(c.fetched_at, { seconds: true })}
            </span>
          </Field>
        )}
        {c.ms != null && <Field k="took">{c.ms} ms{c.round ? ` · model turn ${c.round}` : ""}</Field>}
        {c.rows != null && (
          <Field k="rows">
            {c.rows}
            {c.rows_shown != null && c.rows_shown < c.rows && (
              <span className="text-amber-700 dark:text-amber-400"> · the model was shown the first {c.rows_shown}</span>
            )}
          </Field>
        )}
        {c.parent_seq != null && <Field k="for task"><a className="underline underline-offset-2" href={`#seq-${c.parent_seq}`}>#{c.parent_seq}</a></Field>}
        {typeof c.error === "string" && <Field k="error"><span className="font-mono text-rose-600 dark:text-rose-400">{c.error}</span></Field>}
        {c.stats && (
          <Field k="model">
            <span className="font-mono">{c.stats.model}</span>
            {c.stats.rounds != null && ` · ${c.stats.rounds} turn${c.stats.rounds === 1 ? "" : "s"}`}
            {c.stats.input_tokens != null && ` · ${c.stats.input_tokens.toLocaleString("en-US")} in / ${(c.stats.output_tokens ?? 0).toLocaleString("en-US")} out tokens`}
            {c.stats.usd != null && ` · ${usd(c.stats.usd)}`}
            {c.stats.seconds != null && ` · ${c.stats.seconds}s`}
          </Field>
        )}
        {c.stats?.by_model && (
          <Field k="by model">
            {Object.entries(c.stats.by_model).map(([m, v]) => (
              <div key={m} className="font-mono text-[11px]">{m}: {v.calls} calls · {usd(v.usd)}</div>
            ))}
          </Field>
        )}
      </div>

      {c.kind === "tool" && (
        <Block title="Arguments">
          <pre className="font-mono text-[11px] whitespace-pre-wrap">{JSON.stringify(c.arguments ?? {}, null, 2)}</pre>
        </Block>
      )}
      {c.kind === "delegate" && c.task && <Block title="Task"><p className="text-xs whitespace-pre-wrap">{c.task}</p></Block>}
      {(c.kind === "finding" || c.kind === "summary") && c.summary && (
        <Block title={c.kind === "summary" ? "Answer" : "Finding"}><Markdown>{c.summary}</Markdown></Block>
      )}

      {c.kind === "tool" && !c.error && (
        <Block
          title={`Result${c.truncated && full === undefined ? ` (first ${Array.isArray(c.result) ? c.result.length : "part"} of ${c.rows ?? "?"})` : ""}`}
          action={
            <span className="flex items-center gap-2">
              {c.truncated && full === undefined && (
                <button type="button" onClick={loadFull} disabled={loading}
                        className="hover:bg-muted inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px]">
                  {loading && <Loader2 className="size-3 animate-spin" />}Load all {c.rows ?? ""} rows
                </button>
              )}
              <button type="button" onClick={download}
                      className="hover:bg-muted inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px]">
                <Download className="size-3" />JSON
              </button>
            </span>
          }
        >
          {err && <p className="mb-2 text-xs text-rose-600">{err}</p>}
          <ResultView value={result} />
        </Block>
      )}

      {c.thinking && (
        <details className="text-xs">
          <summary className="text-muted-foreground cursor-pointer">Model reasoning before this step</summary>
          <p className="text-muted-foreground mt-2 whitespace-pre-wrap">{c.thinking}</p>
        </details>
      )}
    </div>
  );
}

function Block({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2">
        <p className="text-muted-foreground text-[11px] font-medium">{title}</p>
        {action}
      </div>
      <div className="bg-background max-h-[420px] overflow-auto rounded border p-2">{children}</div>
    </div>
  );
}

const cell = (v: unknown) =>
  v == null ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);

/** A list of flat records reads as a table; anything else as JSON. */
function ResultView({ value }: { value: unknown }) {
  const [asJson, setAsJson] = useState(false);
  const rows = Array.isArray(value) && value.length > 0 && value.every((r) => r && typeof r === "object" && !Array.isArray(r))
    ? (value as Record<string, unknown>[]) : null;
  if (value == null) return <p className="text-muted-foreground text-xs">No value: the tool returned nothing.</p>;
  if (Array.isArray(value) && value.length === 0) return <p className="text-muted-foreground text-xs">An empty list.</p>;
  const columns = rows ? Array.from(new Set(rows.flatMap((r) => Object.keys(r)))) : [];

  return (
    <div>
      {rows && (
        <div className="mb-2 flex gap-1">
          {["table", "json"].map((m) => (
            <button key={m} type="button" onClick={() => setAsJson(m === "json")}
                    className={cn("rounded px-1.5 py-0.5 font-mono text-[10px]",
                      (m === "json") === asJson ? "bg-foreground text-background" : "hover:bg-muted")}>
              {m}
            </button>
          ))}
        </div>
      )}
      {rows && !asJson ? (
        <table className="w-max min-w-full text-[11px]">
          <thead>
            <tr>
              <th className="text-muted-foreground px-1.5 py-1 text-right font-mono font-normal">#</th>
              {columns.map((k) => <th key={k} className="text-muted-foreground px-1.5 py-1 text-left font-mono font-normal">{k}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="text-muted-foreground px-1.5 py-1 text-right font-mono">{i + 1}</td>
                {columns.map((k) => <td key={k} className="max-w-[280px] truncate px-1.5 py-1 font-mono" title={cell(r[k])}>{cell(r[k])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <pre className="font-mono text-[11px] whitespace-pre-wrap break-words">
          {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
        </pre>
      )}
    </div>
  );
}
