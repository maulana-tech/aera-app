"use client";

import { useMemo, useState } from "react";

import { AgentBadge } from "@/components/agent-card";
import { PanZoom } from "@/components/pan-zoom";
import { OriginBadge } from "@/components/status-badge";
import { useChartWidth } from "@/hooks/use-chart-width";
import { cn } from "@/lib/utils";
import { usd, type Trace, type TraceEdge, type TraceNode } from "@/app/lib";

/* One handling as a topology, read left to right the way the work flowed:
 *
 *   event → lead → specialists → tools → sources · actions
 *
 * Nodes are aggregated by the API (core/topology.py): a tool called nine times
 * is one node, and the edge into it says ×9. Clicking a node selects it, which
 * lights the whole path through it (everything upstream that asked for it,
 * everything downstream it read or raised) and opens it in the node drawer
 * (components/trace-node-detail.tsx), so every node leads back to the exact calls.
 *
 * Same drawing approach as the exploration graph: HTML nodes over one SVG edge
 * layer, inside the shared pan/zoom viewport. */

const COLUMNS: { title: string; take: (n: TraceNode) => boolean }[] = [
  { title: "Event", take: (n) => n.kind === "event" },
  { title: "Lead", take: (n) => n.kind === "agent" && n.agent === "supervisor" },
  { title: "Specialists", take: (n) => n.kind === "agent" && n.agent !== "supervisor" },
  { title: "Tools", take: (n) => n.kind === "tool" },
  { title: "Sources · actions", take: (n) => n.kind === "source" || n.kind === "action" },
];

const NODE_W = 196;
const NODE_H = 64;
const V_GAP = 12;
const COL_GAP = 96;
const HEAD = 30;
const PAD_Y = 10;

const STRIPE: Record<string, string> = {
  event: "border-l-slate-400 dark:border-l-slate-500",
  agent: "border-l-sky-500",
  tool: "border-l-zinc-400 dark:border-l-zinc-500",
  action: "border-l-rose-500",
  upload: "border-l-cyan-500",
  fixture: "border-l-amber-500",
  profile: "border-l-amber-400",
  rules: "border-l-orange-500",
  engine: "border-l-violet-500",
  record: "border-l-fuchsia-500",
  model: "border-l-indigo-500",
  external: "border-l-teal-500",
  chain: "border-l-emerald-500",
};

const ORIGIN_STROKE: Record<string, string> = {
  live: "stroke-emerald-500",
  cached: "stroke-sky-500",
  derived: "stroke-violet-500",
  modelled: "stroke-amber-500",
  missing: "stroke-rose-500",
};

const STATE_DOT: Record<string, string> = {
  working: "bg-sky-500", done: "bg-emerald-500", failed: "bg-rose-500",
  "no tool": "bg-amber-500", unfinished: "bg-zinc-400",
};

type Placed = TraceNode & { x: number; y: number; col: number };

const seconds = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`);

/** Everything a node touches, transitively, in both directions: the path through it. */
function pathThrough(id: string, edges: TraceEdge[]): Set<string> {
  const out = new Set([id]);
  const walk = (from: "from" | "to", to: "from" | "to") => {
    const queue = [id];
    while (queue.length) {
      const cur = queue.pop()!;
      for (const e of edges) {
        if (e[from] === cur && !out.has(e[to])) { out.add(e[to]); queue.push(e[to]); }
      }
    }
  };
  walk("from", "to");
  walk("to", "from");
  return out;
}

export function TraceTopology({
  trace, selected, onSelect,
}: {
  trace: Trace;
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const { ref, width } = useChartWidth(900);

  const { placed, byId, innerW, innerH } = useMemo(() => {
    const first: Record<string, number> = {};
    for (const e of trace.edges) {
      const s = Math.min(...(e.seqs.length ? e.seqs : [0]));
      first[e.to] = Math.min(first[e.to] ?? Infinity, s);
    }
    const cols = COLUMNS.map((c) => trace.nodes.filter(c.take));
    cols[2].sort((a, b) => (first[a.id] ?? 0) - (first[b.id] ?? 0));
    // Tools under the specialist that called them, in the order they were first used.
    const agentRank = Object.fromEntries(cols[2].map((n, i) => [n.agent, i]));
    cols[3].sort((a, b) =>
      ((a.agent === "supervisor" ? -1 : agentRank[a.agent ?? ""] ?? 99)
        - (b.agent === "supervisor" ? -1 : agentRank[b.agent ?? ""] ?? 99))
      || (first[a.id] ?? 0) - (first[b.id] ?? 0));
    // A source sits level with the tools that read it, which keeps edges short.
    const toolRank = Object.fromEntries(cols[3].map((n, i) => [n.id, i]));
    const centre: Record<string, number> = {};
    for (const n of cols[4]) {
      const ranks = trace.edges.filter((e) => e.to === n.id && e.from in toolRank)
        .map((e) => toolRank[e.from]);
      centre[n.id] = ranks.length ? ranks.reduce((a, b) => a + b, 0) / ranks.length : 1e6;
    }
    cols[4].sort((a, b) => centre[a.id] - centre[b.id]);

    const tallest = Math.max(1, ...cols.map((c) => c.length));
    const innerH = HEAD + PAD_Y * 2 + tallest * (NODE_H + V_GAP) - V_GAP;
    const gap = Math.max(COL_GAP, (Math.max(width, 900) - 48 - NODE_W * COLUMNS.length) / (COLUMNS.length - 1));
    const placed: Placed[] = [];
    cols.forEach((list, ci) => {
      const colH = list.length * (NODE_H + V_GAP) - V_GAP;
      const top = HEAD + PAD_Y + (innerH - HEAD - PAD_Y * 2 - colH) / 2;
      list.forEach((n, i) => placed.push({ ...n, col: ci, x: ci * (NODE_W + gap), y: top + i * (NODE_H + V_GAP) }));
    });
    const byId: Record<string, Placed> = {};
    for (const p of placed) byId[p.id] = p;
    return { placed, byId, innerW: (COLUMNS.length - 1) * (NODE_W + gap) + NODE_W, innerH };
  }, [trace, width]);

  const anchor = hover ?? selected;
  const lit = useMemo(() => (anchor ? pathThrough(anchor, trace.edges) : null), [anchor, trace.edges]);
  const colX = (ci: number) => placed.find((p) => p.col === ci)?.x;

  return (
    <div ref={ref}>
      {/* Tall enough that a twenty-tool handling opens readable, not as a thumbnail. */}
      <PanZoom innerW={innerW} innerH={innerH} height={Math.round(Math.min(860, Math.max(480, innerH * 0.62)))}
               fit onBackgroundClick={() => onSelect(null)}>
        {COLUMNS.map((c, ci) => {
          const x = colX(ci);
          return x === undefined ? null : (
            <p key={c.title} className="text-muted-foreground absolute font-mono text-[10px] uppercase tracking-wider"
               style={{ left: x, top: 4, width: NODE_W }}>
              {c.title}
            </p>
          );
        })}

        <svg className="pointer-events-none absolute inset-0 overflow-visible" width={innerW} height={innerH}>
          {trace.edges.map((e) => {
            const a = byId[e.from];
            const b = byId[e.to];
            if (!a || !b) return null;
            const ay = a.y + NODE_H / 2;
            const by = b.y + NODE_H / 2;
            let d: string;
            if (a.col === b.col) {
              // A specialist that asked another: an arc out to the right and back.
              const x = a.x + NODE_W;
              d = `M${x},${ay} C${x + 60},${ay} ${x + 60},${by} ${x},${by}`;
            } else {
              const x1 = a.x + NODE_W;
              const x2 = b.x;
              const dx = Math.max(30, (x2 - x1) / 2);
              d = `M${x1},${ay} C${x1 + dx},${ay} ${x2 - dx},${by} ${x2},${by}`;
            }
            const on = lit ? lit.has(e.from) && lit.has(e.to) : false;
            const w = 1 + Math.min(3.5, Math.log2(Math.max(1, e.count)));
            const stroke = e.rel === "reads" && e.origin ? ORIGIN_STROKE[e.origin] ?? "stroke-border"
              : e.rel === "raises" ? "stroke-rose-500"
              : e.rel === "delegates" ? "stroke-sky-500" : "stroke-border";
            const midX = a.col === b.col ? a.x + NODE_W + 45 : (a.x + NODE_W + b.x) / 2;
            const midY = (ay + by) / 2;
            return (
              <g key={e.id} opacity={lit && !on ? 0.12 : on ? 1 : 0.65}>
                <path d={d} fill="none" className={cn(stroke, on && e.rel === "calls" && "stroke-foreground")}
                      strokeWidth={on ? w + 0.75 : w}
                      strokeDasharray={e.rel === "raises" ? "5 3" : e.rel === "triggers" ? "2 3" : undefined} />
                {e.count > 1 && (
                  <text x={midX} y={midY - 3} textAnchor="middle"
                        className="fill-muted-foreground font-mono text-[10px]">×{e.count}</text>
                )}
              </g>
            );
          })}
        </svg>

        {placed.map((n) => (
          <button
            type="button"
            key={n.id}
            onMouseEnter={() => setHover(n.id)}
            onMouseLeave={() => setHover(null)}
            onClick={(ev) => { ev.stopPropagation(); onSelect(n.id); }}
            title={titleFor(n)}
            className={cn(
              "bg-card absolute flex flex-col justify-center gap-1 rounded-md border border-l-[3px] px-2.5 py-1.5 text-left shadow-sm transition-opacity",
              "hover:ring-ring/40 cursor-pointer hover:ring-2 focus:outline-none",
              STRIPE[n.kind === "source" ? n.source_kind ?? "external" : n.kind],
              selected === n.id && "ring-foreground ring-2",
              lit && !lit.has(n.id) && "opacity-30",
            )}
            style={{ left: n.x, top: n.y, width: NODE_W, height: NODE_H }}
          >
            <NodeBody n={n} />
          </button>
        ))}
      </PanZoom>
      <Legend />
    </div>
  );
}

function NodeBody({ n }: { n: TraceNode }) {
  if (n.kind === "agent") {
    return (
      <>
        <div className="flex min-w-0 items-center gap-1.5">
          <AgentBadge nickname={n.label} size="xs" />
          <span className="truncate text-xs font-semibold">{n.label}</span>
          <span className="text-muted-foreground truncate text-[10px]">{n.sub}</span>
          {n.state && (
            <span className="ml-auto inline-flex shrink-0 items-center gap-1 text-[10px]">
              <span className={cn("size-1.5 rounded-full", STATE_DOT[n.state] ?? "bg-zinc-400")} />
              {n.state}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground font-mono text-[10px]">
            {n.calls} tool call{n.calls === 1 ? "" : "s"}
            {n.stats?.seconds != null ? ` · ${n.stats.seconds}s` : ""}
            {n.stats?.usd ? ` · ${usd(n.stats.usd)}` : ""}
          </span>
          {n.origin && <span className="ml-auto origin-right scale-90"><OriginBadge origin={n.origin} /></span>}
        </div>
      </>
    );
  }
  if (n.kind === "tool") {
    return (
      <>
        <p className="truncate font-mono text-[11px] font-medium leading-tight">{n.label}</p>
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground font-mono text-[10px]">
            ×{n.calls}{n.ms ? ` · ${seconds(n.ms)}` : ""}
          </span>
          {n.errors > 0 && <span className="font-mono text-[10px] text-rose-600 dark:text-rose-400">{n.errors} failed</span>}
          {n.origin && <span className="ml-auto origin-right scale-90"><OriginBadge origin={n.origin} /></span>}
        </div>
      </>
    );
  }
  if (n.kind === "source") {
    return (
      <>
        <p className="truncate text-xs font-medium leading-tight">{n.label}</p>
        <div className="flex min-w-0 items-center gap-1.5">
          <span className="text-muted-foreground truncate font-mono text-[10px]">{n.sub}</span>
          {n.origin && <span className="ml-auto shrink-0 origin-right scale-90"><OriginBadge origin={n.origin} /></span>}
        </div>
      </>
    );
  }
  if (n.kind === "action") {
    return (
      <>
        <p className="truncate font-mono text-[11px] font-medium leading-tight">{n.label}</p>
        <p className="text-muted-foreground font-mono text-[10px]">
          {n.status}{n.autonomous ? " · on its own authority" : ""}
          {typeof n.value_usd === "number" ? ` · ${usd(n.value_usd)}` : ""}
        </p>
      </>
    );
  }
  return (
    <>
      <span className="text-muted-foreground font-mono text-[9px] uppercase tracking-wide">{n.sub || "event"}</span>
      <p className="line-clamp-2 text-xs font-medium leading-tight">{n.label}</p>
    </>
  );
}

function titleFor(n: TraceNode): string {
  const bits = [`${n.kind}: ${n.label}`];
  if (n.sub) bits.push(n.sub);
  if (n.kind === "source" && n.source) bits.push(n.source);
  if (n.origin) bits.push(`weakest origin: ${n.origin}`);
  if (n.calls) bits.push(`${n.calls} call${n.calls === 1 ? "" : "s"}`);
  if (n.stats?.model) bits.push(`model: ${n.stats.model}`);
  return bits.join("\n");
}

function Legend() {
  const items: { cls: string; label: string }[] = [
    { cls: "bg-cyan-500", label: "business file" },
    { cls: "bg-amber-500", label: "profile / sample" },
    { cls: "bg-emerald-500", label: "vault (chain)" },
    { cls: "bg-orange-500", label: "guardian rules" },
    { cls: "bg-teal-500", label: "outside feed" },
    { cls: "bg-violet-500", label: "engine (calculation)" },
    { cls: "bg-fuchsia-500", label: "AERA record" },
    { cls: "bg-rose-500", label: "action" },
  ];
  return (
    <div className="text-muted-foreground mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px]">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          <span className={cn("h-3 w-0.5 rounded", i.cls)} />
          {i.label}
        </span>
      ))}
      <span>· a read edge is coloured by the origin of what came back · ×n is how many calls</span>
    </div>
  );
}
