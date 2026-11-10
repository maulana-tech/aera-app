"use client";

import { ArrowRight, ChevronRight, ListFilter } from "lucide-react";
import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";

import { ActionPayload } from "@/components/action-payload";
import { AgentBadge } from "@/components/agent-card";
import { Markdown } from "@/components/markdown";
import { OriginBadge, StatusBadge } from "@/components/status-badge";
import { CallDetail, KIND_LABEL, brief } from "@/components/trace-calls";
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { WIB, wib, type Trace, type TraceCall, type TraceEdge, type TraceNode } from "@/app/lib";

/* A trace node opened in a drawer, the way a node of the exploration graph
 * opens on the disruption page: what the node is, its numbers, what it is
 * connected to (each one a click away), and every step that went through it,
 * each expandable to its full arguments and result.
 *
 * The drawer is the app's Sheet, always mounted so it slides out on close, and
 * it keeps the last node it showed while it does. */

const SWATCH: Record<string, string> = {
  event: "bg-slate-400", agent: "bg-sky-500", tool: "bg-zinc-400", action: "bg-rose-500",
  upload: "bg-cyan-500", fixture: "bg-amber-500", profile: "bg-amber-400",
  rules: "bg-orange-500", engine: "bg-violet-500", record: "bg-fuchsia-500",
  model: "bg-indigo-500", external: "bg-teal-500",
};

const swatchOf = (n: TraceNode) =>
  SWATCH[n.kind === "source" ? n.source_kind ?? "external" : n.kind] ?? "bg-zinc-400";

const kindOf = (n: TraceNode) =>
  n.kind === "agent" ? (n.agent === "supervisor" ? "Team lead" : "Specialist")
    : n.kind === "source" ? "Data source"
    : n.kind === "tool" ? "Tool" : n.kind === "action" ? "Action" : "Event";

// What each kind of source is, in the words a buyer would use.
const SOURCE_WHAT: Record<string, string> = {
  upload: "A file someone uploaded on the Data page.",
  fixture: "Sample data that ships with AERA, not a company record. Upload a file to replace it.",
  profile: "An assumed value from the company profile, not a reading.",
  rules: "The rule tables AERA checks against: TKDN, LARTAS, contract clauses.",
  engine: "A calculation in AERA's own code, made from figures read elsewhere.",
  record: "AERA's own records: past handlings, events and actions.",
  model: "An answer written by a language model, not a system of record.",
  external: "A public outside feed.",
};

// An agent's state, in the colours a run's status already uses.
const STATE_STATUS: Record<string, string> = { working: "running", unfinished: "skipped", "no tool": "held" };

// How an edge reads from the node's side, by direction.
const REL_IN: Record<TraceEdge["rel"], string> = {
  triggers: "Triggered by", delegates: "Asked by", calls: "Called by", reads: "Read by", raises: "Raised by",
};
const REL_OUT: Record<TraceEdge["rel"], string> = {
  triggers: "Triggers", delegates: "Asks", calls: "Calls", reads: "Reads from", raises: "Raises",
};

const rupiah = (n: number) => `Rp ${n.toLocaleString("en-US")}`;
const seconds = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`);
// Jakarta, with seconds: a trace is read for the order of things.
const when = (t: string | null | undefined) => (t ? wib(t, { seconds: true }) : "");
const time = (t: string | null) =>
  t ? new Date(t).toLocaleTimeString("en-GB", { hour12: false, timeZone: WIB }) : "";

// Long lists open short; the rest is one click away.
const FIRST_STEPS = 25;

export function TraceNodeDetail({
  trace, nodeId, runId, onSelect, onClose, onShowInList,
}: {
  trace: Trace;
  nodeId: string | null;
  runId: string;
  onSelect: (id: string) => void;
  onClose: () => void;
  /** Close the drawer and narrow the step list to this node's steps. */
  onShowInList: () => void;
}) {
  const byId = useMemo(() => Object.fromEntries(trace.nodes.map((n) => [n.id, n])), [trace.nodes]);
  const live = nodeId ? byId[nodeId] ?? null : null;
  // Remembered during render (not in an effect) so the slide-out still has it.
  const [shown, setShown] = useState<TraceNode | null>(live);
  if (live && live !== shown) setShown(live);
  const n = live ?? shown;

  return (
    <Sheet open={!!live} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 overflow-hidden p-0 data-[side=right]:w-full sm:data-[side=right]:max-w-xl lg:data-[side=right]:max-w-2xl"
      >
        {n && (
          <Body key={n.id} n={n} trace={trace} byId={byId} runId={runId}
                onSelect={onSelect} onShowInList={onShowInList} />
        )}
      </SheetContent>
    </Sheet>
  );
}

function Body({
  n, trace, byId, runId, onSelect, onShowInList,
}: {
  n: TraceNode; trace: Trace; byId: Record<string, TraceNode>; runId: string;
  onSelect: (id: string) => void; onShowInList: () => void;
}) {
  const steps = useMemo(() => trace.calls.filter((c) => c.node_ids.includes(n.id)), [trace.calls, n.id]);
  const incoming = trace.edges.filter((e) => e.to === n.id && byId[e.from]);
  const outgoing = trace.edges.filter((e) => e.from === n.id && byId[e.to]);

  return (
    <>
      {/* The header stays while the body scrolls, so the close button never scrolls away. */}
      <SheetHeader className="shrink-0 border-b px-5 py-4 pr-12">
        <SheetTitle className="flex items-center gap-2 text-sm">
          <span className={cn("h-4 w-1 rounded", swatchOf(n))} />
          <span className="text-muted-foreground font-mono text-[10px] uppercase tracking-wide">{kindOf(n)}</span>
          {n.kind === "agent" && n.state && <StatusBadge status={STATE_STATUS[n.state] ?? n.state}>{n.state}</StatusBadge>}
          {n.kind === "action" && n.status && <StatusBadge status={n.status} />}
          {n.kind === "event" && n.status && <StatusBadge status={n.status} />}
        </SheetTitle>
        <SheetDescription asChild>
          <div className="text-foreground flex min-w-0 items-center gap-2.5">
            {n.kind === "agent" && <AgentBadge nickname={n.label} size="sm" />}
            <div className="min-w-0">
              <p className={cn("break-words text-base font-semibold leading-snug", (n.kind === "tool" || n.kind === "action") && "font-mono text-sm")}>
                {n.label}
              </p>
              {n.sub && n.kind !== "action" && (
                <p className="text-muted-foreground mt-0.5 break-words font-mono text-[11px]">{n.sub}</p>
              )}
            </div>
            {n.origin && <span className="ml-auto shrink-0"><OriginBadge origin={n.origin} /></span>}
          </div>
        </SheetDescription>
      </SheetHeader>

      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5">
        <Overview n={n} trace={trace} steps={steps} incoming={incoming} runId={runId} />

        {(incoming.length > 0 || outgoing.length > 0) && (
          <Part title="Connected to">
            <div className="space-y-3">
              <Links edges={incoming} dir="in" byId={byId} onSelect={onSelect} />
              <Links edges={outgoing} dir="out" byId={byId} onSelect={onSelect} />
            </div>
          </Part>
        )}

        {n.kind === "agent" && <Story n={n} steps={steps} />}

        {steps.length > 0 && (
          <Part
            title={`Steps through this node (${steps.length})`}
            action={
              <button type="button" onClick={onShowInList}
                      className="hover:bg-muted text-muted-foreground hover:text-foreground inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px]">
                <ListFilter className="size-3" />Show in the step list
              </button>
            }
          >
            <Steps steps={steps} byId={byId} runId={runId} />
          </Part>
        )}
      </div>
    </>
  );
}

/** What the node is and its numbers, by kind. */
function Overview({
  n, trace, steps, incoming, runId,
}: { n: TraceNode; trace: Trace; steps: TraceCall[]; incoming: TraceEdge[]; runId: string }) {
  const tools = steps.filter((c) => c.kind === "tool");
  const rows = tools.reduce((a, c) => a + (c.rows ?? 0), 0);
  const hasRows = tools.some((c) => c.rows != null);

  if (n.kind === "agent") {
    const s = n.stats ?? {};
    return (
      <>
        {n.brief && <p className="text-muted-foreground text-sm leading-relaxed">{n.brief}</p>}
        <Tiles items={[
          ["Tool calls", n.calls],
          ["Failed", n.errors],
          ["Tasks received", n.agent === "supervisor" ? null : n.tasks ?? null],
          ["Time", s.seconds != null ? `${s.seconds} s` : null],
          ["Model cost", s.idr != null ? rupiah(s.idr) : null],
          ["Model turns", s.rounds ?? null],
        ]} />
        {s.model && (
          <Facts rows={[
            ["Model", <span key="m" className="font-mono">{s.models && s.models.length > 1 ? s.models.join(", ") : s.model}</span>],
            ...(s.input_tokens != null ? [["Tokens", `${s.input_tokens.toLocaleString("en-US")} in · ${(s.output_tokens ?? 0).toLocaleString("en-US")} out`] as [string, ReactNode]] : []),
          ]} />
        )}
      </>
    );
  }

  if (n.kind === "tool") {
    const done = n.calls - n.errors;
    return (
      <Tiles items={[
        ["Calls", n.calls],
        ["Failed", n.errors],
        ["Rows read", hasRows ? rows.toLocaleString("en-US") : null],
        ["Total time", n.ms ? seconds(n.ms) : null],
        ["Per call", n.ms && n.calls ? seconds(Math.round(n.ms / n.calls)) : null],
        ["Weakest origin", n.origin ?? (done ? null : "none read")],
      ]} />
    );
  }

  if (n.kind === "source") {
    return (
      <>
        <p className="text-muted-foreground text-sm leading-relaxed">
          {SOURCE_WHAT[n.source_kind ?? "external"] ?? SOURCE_WHAT.external}
        </p>
        <Tiles items={[
          ["Reads", n.calls],
          ["Tools reading it", incoming.length],
          ["Rows read", hasRows ? rows.toLocaleString("en-US") : null],
        ]} />
        {n.source && <Facts rows={[["Recorded as", <span key="s" className="font-mono">{n.source}</span>]]} />}
      </>
    );
  }

  if (n.kind === "action") {
    const pending = n.status === "pending";
    return (
      <>
        {n.title && <p className="text-sm leading-relaxed">{n.title}</p>}
        <Facts rows={[
          ["Value", typeof n.cost_idr === "number" ? rupiah(n.cost_idr) : "-"],
          ["Authority", n.autonomous ? "ran on its own authority, under the limit" : "needs a person's approval"],
          ...(n.created_at ? [["Raised", when(n.created_at)] as [string, ReactNode]] : []),
          ...(n.reference
            ? [["Document",
                <span key="r" className="font-mono">{n.reference}</span>] as [string, ReactNode]]
            : []),
        ]} />
        {n.payload && Object.keys(n.payload).length > 0 && (
          <Part title="What it does">
            <div className="rounded-md border px-3 pb-2"><ActionPayload payload={n.payload} /></div>
          </Part>
        )}
        {n.approvals && n.approvals.length > 0 && (
          <Part title="Decisions">
            <ul className="space-y-1.5">
              {n.approvals.map((p, i) => (
                <li key={i} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                  <StatusBadge status={p.decision === "escalated" ? "pending" : p.decision}>{p.decision}</StatusBadge>
                  <span>{p.decided_by}</span>
                  <span className="text-muted-foreground font-mono">({p.role})</span>
                  <span className="text-muted-foreground ml-auto font-mono text-[11px]">{when(p.at)}</span>
                  {p.note && <p className="text-muted-foreground w-full">{p.note}</p>}
                </li>
              ))}
            </ul>
          </Part>
        )}
        <Link href={`/disruptions/${runId}`}
              className={cn("inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium",
                pending ? "bg-foreground text-background hover:bg-foreground/90" : "hover:bg-muted")}>
          {pending ? "Decide on it in the decision queue" : "Open the decision for this handling"}
          <ArrowRight className="size-3" />
        </Link>
      </>
    );
  }

  // The event.
  return (
    <>
      {n.trigger && <p className="text-muted-foreground text-sm leading-relaxed">{n.trigger}</p>}
      <Facts rows={[
        ["Kind", <span key="k" className="font-mono">{n.sub}</span>],
        ...(n.started_at ? [["Started", when(n.started_at)] as [string, ReactNode]] : []),
        ["Steps", trace.totals.steps],
        ["Tool calls", trace.totals.tool_calls],
      ]} />
      <Link href={`/disruptions/${runId}`}
            className="hover:bg-muted inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium">
        Open the decision for this handling<ArrowRight className="size-3" />
      </Link>
    </>
  );
}

/** An agent's side of the conversation: what it was asked, and what it said back. */
function Story({ n, steps }: { n: TraceNode; steps: TraceCall[] }) {
  const tasks = steps.filter((c) => c.kind === "delegate" && c.agent === n.agent);
  const reports = steps.filter((c) =>
    (c.kind === "finding" || c.kind === "summary") && c.agent === n.agent && c.summary);
  return (
    <>
      {tasks.map((t) => (
        <Part key={t.seq} title={`Task #${t.seq}${t.by ? ` · asked by ${t.by === "supervisor" ? "the lead" : t.by}` : ""}`}>
          <Clamp long={(t.task ?? "").length > 700}>
            <p className="bg-muted/40 rounded-md border px-3 py-2.5 text-sm leading-relaxed whitespace-pre-wrap">{t.task}</p>
          </Clamp>
        </Part>
      ))}
      {reports.map((r) => (
        <Part key={r.seq} title={r.kind === "summary" ? `Final answer #${r.seq}` : `Finding #${r.seq}`}>
          <Clamp long={(r.summary ?? "").length > 700}>
            <div className="rounded-md border px-3 py-2.5"><Markdown>{r.summary ?? ""}</Markdown></div>
          </Clamp>
        </Part>
      ))}
    </>
  );
}

/** A long block opens folded to a screenful, with the rest one click away. */
function Clamp({ long, children }: { long: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  if (!long) return <>{children}</>;
  return (
    <div>
      <div className={cn("relative", !open && "max-h-72 overflow-hidden")}>
        {children}
        {!open && <div className="from-popover pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t to-transparent" />}
      </div>
      <button type="button" onClick={() => setOpen(!open)}
              className="text-muted-foreground hover:text-foreground mt-1.5 text-xs underline underline-offset-2">
        {open ? "Fold it" : "Read all of it"}
      </button>
    </div>
  );
}

/** Numbers as tiles. A null is a number nobody recorded, and is left out rather than shown as a dash. */
function Tiles({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {items.filter(([, v]) => v != null).map(([k, v]) => (
        <div key={k} className="rounded-md border px-3 py-2">
          <dt className="text-muted-foreground text-[11px]">{k}</dt>
          <dd className="mt-0.5 truncate font-mono text-sm tabular-nums">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <div className="divide-y rounded-md border px-3">
      {rows.map(([k, v]) => (
        <div key={k} className="grid grid-cols-[112px_minmax(0,1fr)] gap-3 py-2 text-xs">
          <span className="text-muted-foreground">{k}</span>
          <span className="min-w-0 break-words">{v}</span>
        </div>
      ))}
    </div>
  );
}

function Part({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-muted-foreground text-[11px] font-medium uppercase tracking-wide">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

/** The node's neighbours, grouped by how they connect, each one opening in turn. */
function Links({
  edges, dir, byId, onSelect,
}: {
  edges: TraceEdge[]; dir: "in" | "out"; byId: Record<string, TraceNode>; onSelect: (id: string) => void;
}) {
  const groups = new Map<TraceEdge["rel"], TraceEdge[]>();
  for (const e of edges) groups.set(e.rel, [...(groups.get(e.rel) ?? []), e]);
  return (
    <>
      {[...groups].map(([rel, list]) => (
        <div key={rel}>
          <p className="text-muted-foreground mb-1 text-[11px]">{(dir === "in" ? REL_IN : REL_OUT)[rel]}</p>
          <ul className="flex flex-wrap gap-1.5">
            {list.map((e) => {
              const o = byId[dir === "in" ? e.from : e.to];
              return (
                <li key={e.id}>
                  <button type="button" onClick={() => onSelect(o.id)}
                          title={o.sub ? `${o.label}\n${o.sub}` : o.label}
                          className="hover:bg-muted hover:border-foreground/30 inline-flex max-w-[260px] items-center gap-1.5 rounded-md border px-2 py-1 text-left text-xs transition-colors">
                    <span className={cn("h-3 w-0.5 shrink-0 rounded", swatchOf(o))} />
                    <span className={cn("truncate", o.kind === "tool" && "font-mono text-[11px]")}>{o.label}</span>
                    {e.count > 1 && <span className="text-muted-foreground shrink-0 font-mono text-[10px]">×{e.count}</span>}
                    {e.rel === "reads" && e.origin && <span className="shrink-0 origin-right scale-90"><OriginBadge origin={e.origin} /></span>}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </>
  );
}

/** Every step through the node, each one expanding to all it carried. */
function Steps({ steps, byId, runId }: { steps: TraceCall[]; byId: Record<string, TraceNode>; runId: string }) {
  const [open, setOpen] = useState<Set<number>>(() => new Set(steps.length === 1 ? [steps[0].seq] : []));
  const [all, setAll] = useState(steps.length <= FIRST_STEPS);
  const list = all ? steps : steps.slice(0, FIRST_STEPS);
  const name = (code?: string) => (code ? byId[`agent:${code}`]?.label ?? code : "");
  const toggle = (seq: number) => setOpen((o) => {
    const x = new Set(o);
    if (x.has(seq)) x.delete(seq); else x.add(seq);
    return x;
  });

  return (
    <>
      <ol className="divide-y overflow-hidden rounded-lg border">
        {list.map((c) => (
          <li key={c.seq}>
            <button type="button" onClick={() => toggle(c.seq)}
                    className="hover:bg-muted/50 grid w-full grid-cols-[14px_36px_minmax(0,1fr)_auto] items-center gap-2 px-3 py-2 text-left">
              <ChevronRight className={cn("text-muted-foreground size-3.5 transition-transform", open.has(c.seq) && "rotate-90")} />
              <span className="text-muted-foreground font-mono text-[11px] tabular-nums">#{c.seq}</span>
              <span className="min-w-0">
                <span className="flex items-center gap-1.5 text-xs">
                  <span className="shrink-0 font-medium">
                    {c.kind === "delegate" ? `${name(c.by) || "Arya"} → ${name(c.agent)}` : name(c.agent)}
                  </span>
                  <span className="text-muted-foreground shrink-0 font-mono text-[10px]">{KIND_LABEL[c.kind] ?? c.kind}</span>
                  <span className="text-muted-foreground ml-auto shrink-0 font-mono text-[10px] tabular-nums">{time(c.at)}</span>
                </span>
                <span className={cn("mt-0.5 block truncate text-xs", c.kind === "tool" && "font-mono text-[11px]",
                  c.error ? "text-rose-600 dark:text-rose-400" : "text-muted-foreground")}>
                  {brief(c)}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-1.5">
                {c.rows != null && <span className="text-muted-foreground font-mono text-[10px]">{c.rows} rows</span>}
                {c.origin && <OriginBadge origin={c.origin} />}
              </span>
            </button>
            {open.has(c.seq) && <CallDetail c={c} runId={runId} compact />}
          </li>
        ))}
      </ol>
      {!all && (
        <button type="button" onClick={() => setAll(true)}
                className="hover:bg-muted text-muted-foreground mt-2 w-full rounded-md border py-1.5 text-xs">
          Show the other {steps.length - FIRST_STEPS} steps
        </button>
      )}
    </>
  );
}
