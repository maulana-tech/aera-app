"use client";

import { Maximize2, Minus, Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { useChartWidth } from "@/hooks/use-chart-width";
import { OriginBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";
import type { ExplorationGraph, GraphEdge, GraphNode } from "@/app/lib";

/* The exploration graph as a layered DAG.
 *
 * SmartX renders its topology on an SVG canvas; here the nodes are HTML so they
 * can carry the one thing SIGAP's graph has that SmartX's does not — a fact's
 * provenance badge — and stay legible in both themes without fighting SVG fill
 * colours. The edges are a single SVG layer painted behind the nodes: React
 * renders every path, there is no d3.select touching the DOM.
 *
 * The layers read left to right the way the handling actually flows:
 *   event → lead → fact → option → ruling
 * which is the mitigation chain itself — a disruption opens leads, a lead
 * surfaces facts and options, a rule-giver rules on the options. Backward edges
 * (a ruling points back at its option; an option spawns a new lead) curve back,
 * so a deep chain is visible as the loop it is. */

const LAYERS: GraphNode["kind"][] = ["event", "lead", "fact", "option", "ruling"];

const KIND_STYLE: Record<GraphNode["kind"], string> = {
  event:  "border-l-slate-400 dark:border-l-slate-500",
  lead:   "border-l-sky-500",
  fact:   "border-l-zinc-400 dark:border-l-zinc-500",
  option: "border-l-violet-500",
  ruling: "border-l-amber-500",
};

// Lead state → a dot colour, with the word always written beside it.
const STATE_DOT: Record<string, string> = {
  open: "bg-amber-500", claimed: "bg-sky-500", worked: "bg-emerald-500",
  blocked: "bg-rose-500", failed: "bg-rose-500", capped: "bg-zinc-400", stopped: "bg-zinc-400",
};

const NODE_W = 168;
const NODE_H = 56;
const V_GAP = 14;
const PAD_Y = 8;

type Placed = GraphNode & { x: number; y: number; cx: number; cy: number };

function shortLabel(n: GraphNode): string {
  if (n.kind === "lead") return (n.lead_key ?? "").replace(/_/g, " ");
  if (n.kind === "fact") return (n.label ?? "").split(".").slice(-1)[0];
  if (n.kind === "option") return `option ${n.subject ?? ""}`;
  if (n.kind === "ruling") return `ruling ${n.subject ?? ""}`;
  return n.label ?? n.kind;
}

export function ExplorationGraph({ graph }: { graph: ExplorationGraph | null }) {
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const { ref: containerRef, width } = useChartWidth(760);

  const { placed, byId, height } = useMemo(() => {
    const nodes = graph?.nodes ?? [];
    const cols: Record<string, GraphNode[]> = {};
    for (const k of LAYERS) cols[k] = [];
    for (const n of nodes) (cols[n.kind] ??= []).push(n);

    const colCount = LAYERS.length;
    const colGap = Math.max(NODE_W + 24, (Math.max(width, 640) - NODE_W) / (colCount - 1));
    const tallest = Math.max(1, ...LAYERS.map((k) => cols[k].length));
    const height = Math.max(NODE_H + 2 * PAD_Y, tallest * (NODE_H + V_GAP) - V_GAP + 2 * PAD_Y);

    const placed: Placed[] = [];
    LAYERS.forEach((k, ci) => {
      const list = cols[k];
      const colH = list.length * (NODE_H + V_GAP) - V_GAP;
      const top = PAD_Y + (height - 2 * PAD_Y - colH) / 2;
      list.forEach((n, i) => {
        const x = ci * colGap;
        const y = top + i * (NODE_H + V_GAP);
        placed.push({ ...n, x, y, cx: x + NODE_W / 2, cy: y + NODE_H / 2 });
      });
    });
    const byId: Record<string, Placed> = {};
    for (const p of placed) byId[p.node_id] = p;
    return { placed, byId, height };
  }, [graph, width]);

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-sm">
        <p className="font-medium">The exploration graph was not recorded.</p>
        <p className="text-muted-foreground mt-1.5 leading-relaxed">
          It is written only when <code className="font-mono text-xs">SIGAP_GRAPH=1</code> is set
          for the agent service. With it on, this shows the leads, facts, options and rulings
          of the handling as the chain that produced them.
        </p>
      </div>
    );
  }

  const innerW = (LAYERS.length - 1) * Math.max(NODE_W + 24, (Math.max(width, 640) - NODE_W) / (LAYERS.length - 1)) + NODE_W;
  const sel = selected ? byId[selected] ?? null : null;

  return (
    <div ref={containerRef}>
      <PanZoom innerW={innerW} innerH={height} onBackgroundClick={() => setSelected(null)}>
        <svg className="pointer-events-none absolute inset-0" width={innerW} height={height}>
          {graph.edges.map((e, i) => {
            const a = byId[e.src];
            const b = byId[e.dst];
            if (!a || !b) return null;
            const forward = a.cx <= b.cx;
            const x1 = forward ? a.x + NODE_W : a.x;
            const x2 = forward ? b.x : b.x + NODE_W;
            const dx = Math.max(30, Math.abs(x2 - x1) / 2);
            const d = `M${x1},${a.cy} C${x1 + (forward ? dx : -dx)},${a.cy} ${x2 - (forward ? dx : -dx)},${b.cy} ${x2},${b.cy}`;
            const anchor = hover ?? selected;
            const lit = anchor && (e.src === anchor || e.dst === anchor);
            return (
              <path
                key={i}
                d={d}
                fill="none"
                className={cn("stroke-border", lit && "stroke-foreground")}
                strokeWidth={lit ? 1.75 : 1}
                strokeDasharray={e.rel === "rules_on" ? "4 3" : undefined}
                opacity={anchor && !lit ? 0.2 : 0.7}
              />
            );
          })}
        </svg>

        {placed.map((n) => {
          const anchor = hover ?? selected;
          const dim = anchor && anchor !== n.node_id
            && !graph.edges.some((e) =>
              (e.src === anchor && e.dst === n.node_id) || (e.dst === anchor && e.src === n.node_id));
          return (
            <button
              type="button"
              key={n.node_id}
              onMouseEnter={() => setHover(n.node_id)}
              onMouseLeave={() => setHover(null)}
              onClick={(ev) => { ev.stopPropagation(); setSelected(n.node_id); }}
              title={titleFor(n)}
              className={cn(
                "bg-card absolute flex flex-col justify-center gap-1 rounded-md border border-l-[3px] px-3 py-2 text-left shadow-sm transition-opacity",
                "hover:ring-ring/40 cursor-pointer hover:ring-2 focus:outline-none",
                KIND_STYLE[n.kind],
                selected === n.node_id && "ring-foreground ring-2",
                dim && "opacity-35",
              )}
              style={{ left: n.x, top: n.y, width: NODE_W, height: NODE_H }}
            >
              <div className="flex items-center gap-1.5">
                <span className="text-muted-foreground font-mono text-[9px] uppercase tracking-wide">
                  {n.kind}
                </span>
                {n.kind === "lead" && n.state && (
                  <span className="ml-auto inline-flex items-center gap-1 text-[10px]">
                    <span className={cn("size-1.5 rounded-full", STATE_DOT[n.state] ?? "bg-zinc-400")} />
                    {n.state}
                  </span>
                )}
                {n.kind === "ruling" && n.state && (
                  <span className={cn("ml-auto text-[10px] font-medium",
                    n.state === "blocked" ? "text-rose-600 dark:text-rose-400"
                      : "text-emerald-600 dark:text-emerald-400")}>
                    {n.state}
                  </span>
                )}
              </div>
              <p className="truncate text-xs font-medium leading-tight">{shortLabel(n)}</p>
              {n.kind === "fact" && n.origin && (
                <div className="-mb-0.5 origin-left scale-90">
                  <OriginBadge origin={n.origin} source={null} />
                </div>
              )}
            </button>
          );
        })}
      </PanZoom>
      <GraphLegend />

      {/* The detail opens as a drawer over the whole screen (the app's Sheet,
          so it slides in/out and dims the backdrop the same way every other
          drawer here does), not a pane inside the canvas — it reads the same at
          any zoom and never fights the graph for width. Always mounted so the
          slide-out animation plays on close. */}
      <NodeDetail
        node={sel}
        graph={graph}
        byId={byId}
        onSelect={setSelected}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

/* A pan + zoom viewport: scroll to zoom toward the cursor, drag the background
 * to pan. The content is transformed with a single CSS transform, so React
 * still owns every node and edge — d3 never touches the DOM. Node buttons keep
 * their own click (pointerdown on a node does not start a pan). */
const MIN_S = 0.3;
const MAX_S = 2.5;

function ZoomBtn({ onClick, label, children }: { onClick: () => void; label: string; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="bg-card hover:bg-muted text-muted-foreground hover:text-foreground flex size-7 items-center justify-center border-b last:border-b-0"
    >
      {children}
    </button>
  );
}

export function PanZoom({
  innerW, innerH, onBackgroundClick, children, height = 480, fit = false,
}: {
  innerW: number; innerH: number; onBackgroundClick: () => void; children: ReactNode;
  /** The viewport's height in CSS pixels. */
  height?: number;
  /** Start (and reset) zoomed out until the whole canvas is in view. */
  fit?: boolean;
}) {
  const vpRef = useRef<HTMLDivElement | null>(null);
  const [view, setView] = useState({ s: 1, x: 24, y: 8 });
  const [isPanning, setIsPanning] = useState(false);
  const pan = useRef<{ x: number; y: number; ox: number; oy: number; moved: boolean } | null>(null);

  const home = useCallback(() => {
    const el = vpRef.current;
    if (!fit || !el) return { s: 1, x: 24, y: 8 };
    const s = Math.max(MIN_S, Math.min(1, (el.clientWidth - 48) / innerW, (height - 24) / innerH));
    return { s, x: Math.max(24, (el.clientWidth - innerW * s) / 2), y: Math.max(8, (height - innerH * s) / 2) };
  }, [fit, innerW, innerH, height]);
  const reset = useCallback(() => setView(home()), [home]);
  // Fitted once the viewport has a size, which the observer's first report gives.
  useEffect(() => {
    const el = vpRef.current;
    if (!fit || !el) return;
    const ro = new ResizeObserver(() => { setView(home()); ro.disconnect(); });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fit, home]);
  const zoomBy = useCallback((factor: number) => setView((v) => {
    const el = vpRef.current;
    const cx = el ? el.clientWidth / 2 : 0;
    const cy = el ? el.clientHeight / 2 : 0;
    const s = Math.min(MAX_S, Math.max(MIN_S, v.s * factor));
    const k = s / v.s;
    return { s, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k };
  }), []);

  // Wheel-zoom toward the cursor. Attached natively so preventDefault works
  // (React's onWheel is passive and cannot stop the page from scrolling).
  useEffect(() => {
    const el = vpRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      setView((v) => {
        const s = Math.min(MAX_S, Math.max(MIN_S, v.s * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
        const k = s / v.s;
        return { s, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest("button")) return; // a node, not the canvas
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    pan.current = { x: e.clientX, y: e.clientY, ox: view.x, oy: view.y, moved: false };
    setIsPanning(true);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const p = pan.current;
    if (!p) return;
    const dx = e.clientX - p.x;
    const dy = e.clientY - p.y;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) p.moved = true;
    setView((v) => ({ ...v, x: p.ox + dx, y: p.oy + dy }));
  };
  const onPointerUp = () => {
    const p = pan.current;
    pan.current = null;
    setIsPanning(false);
    if (p && !p.moved) onBackgroundClick(); // a click on empty canvas clears selection
  };

  return (
    <div
      ref={vpRef}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerLeave={onPointerUp}
      className="bg-muted/20 relative w-full touch-none overflow-hidden rounded-lg border"
      style={{ height, cursor: isPanning ? "grabbing" : "grab" }}
    >
      <div
        className="absolute left-0 top-0 origin-top-left"
        style={{ width: innerW, height: innerH, transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})` }}
      >
        {children}
      </div>

      {/* zoom controls */}
      <div className="absolute right-2 top-2 flex flex-col overflow-hidden rounded-md border shadow-sm">
        <ZoomBtn onClick={() => zoomBy(1.2)} label="Zoom in"><Plus className="size-3.5" /></ZoomBtn>
        <ZoomBtn onClick={() => zoomBy(1 / 1.2)} label="Zoom out"><Minus className="size-3.5" /></ZoomBtn>
        <ZoomBtn onClick={reset} label="Reset view"><Maximize2 className="size-3.5" /></ZoomBtn>
      </div>
      <p className="text-muted-foreground pointer-events-none absolute bottom-2 left-2 text-[10px]">
        scroll to zoom · drag to pan · {Math.round(view.s * 100)}%
      </p>
    </div>
  );
}

function DetailRow({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[72px_minmax(0,1fr)] gap-2 py-1.5 text-xs">
      <span className="text-muted-foreground">{k}</span>
      <span className="min-w-0 break-words">{children}</span>
    </div>
  );
}

function EdgeList({
  title,
  edges,
  dir,
  byId,
  onSelect,
}: {
  title: string;
  edges: GraphEdge[];
  dir: "in" | "out";
  byId: Record<string, Placed>;
  onSelect: (id: string) => void;
}) {
  if (edges.length === 0) return null;
  return (
    <div className="mt-3">
      <p className="text-muted-foreground mb-1 text-[11px] font-medium">{title}</p>
      <ul className="space-y-1">
        {edges.map((e, i) => {
          const other = byId[dir === "in" ? e.src : e.dst];
          if (!other) return null;
          return (
            <li key={i}>
              <button
                type="button"
                onClick={() => onSelect(other.node_id)}
                className="hover:bg-muted flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-left text-xs"
              >
                <span className="text-muted-foreground font-mono text-[10px]">{e.rel}</span>
                <span className="truncate">{shortLabel(other)}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function NodeDetail({
  node, graph, byId, onSelect, onClose,
}: {
  node: Placed | null;
  graph: ExplorationGraph;
  byId: Record<string, Placed>;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  // Keep the last selected node while the drawer slides out, so its content
  // does not blank mid-animation when `node` becomes null on close.
  const [prevNode, setPrevNode] = useState<Placed | null>(node);
  const [shownNode, setShownNode] = useState<Placed | null>(node);
  if (node !== prevNode) {
    setPrevNode(node);
    if (node) {
      setShownNode(node);
    }
  }
  const n = node ?? shownNode;

  let payload: unknown = null;
  try { payload = n?.payload ? JSON.parse(n.payload) : null; } catch { payload = null; }
  const detail = payload && typeof payload === "object"
    ? ((payload as Record<string, unknown>).value
       ?? (payload as Record<string, unknown>).work
       ?? payload)
    : payload;
  const incoming = n ? graph.edges.filter((e) => e.dst === n.node_id) : [];
  const outgoing = n ? graph.edges.filter((e) => e.src === n.node_id) : [];

  return (
    <Sheet open={!!node} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 overflow-y-auto p-0 data-[side=right]:w-full sm:data-[side=right]:max-w-md"
      >
        {n && (
          <>
            <SheetHeader className="border-b px-5 py-3.5">
              <SheetTitle className="flex items-center gap-2 text-sm">
                <span className={cn("h-4 w-1 rounded", SWATCH[n.kind])} />
                <span className="font-mono text-[10px] uppercase tracking-wide">{n.kind}</span>
              </SheetTitle>
              <SheetDescription className="text-foreground text-sm font-medium leading-snug">
                {n.label ?? shortLabel(n)}
              </SheetDescription>
            </SheetHeader>

            <div className="px-5 py-4">
              <div className="divide-y">
                {n.subject && <DetailRow k="subject">{n.subject}</DetailRow>}
                {n.lead_key && <DetailRow k="lead">{n.lead_key}</DetailRow>}
                {n.state && (
                  <DetailRow k="state">
                    {n.kind === "lead" ? (
                      <span className="inline-flex items-center gap-1.5">
                        <span className={cn("size-1.5 rounded-full", STATE_DOT[n.state] ?? "bg-zinc-400")} />
                        {n.state}
                      </span>
                    ) : n.state}
                  </DetailRow>
                )}
                {n.origin && (
                  <DetailRow k="origin"><OriginBadge origin={n.origin} source={n.source} /></DetailRow>
                )}
                {typeof n.priority === "number" && <DetailRow k="priority">{n.priority}</DetailRow>}
              </div>

              {detail != null && (
                <div className="mt-3">
                  <p className="text-muted-foreground mb-1 text-[11px] font-medium">detail</p>
                  <pre className="bg-muted max-h-64 overflow-auto rounded p-2 text-[11px] leading-relaxed whitespace-pre-wrap break-words">
                    {typeof detail === "string" ? detail : JSON.stringify(detail, null, 2)}
                  </pre>
                </div>
              )}

              <EdgeList title="Comes from" edges={incoming} dir="in" byId={byId} onSelect={onSelect} />
              <EdgeList title="Leads to" edges={outgoing} dir="out" byId={byId} onSelect={onSelect} />
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function titleFor(n: GraphNode): string {
  const bits = [`${n.kind}${n.subject ? ` · ${n.subject}` : ""}`];
  if (n.label) bits.push(n.label);
  if (n.origin) bits.push(`origin: ${n.origin}${n.source ? ` (${n.source})` : ""}`);
  if (n.state) bits.push(`state: ${n.state}`);
  if (n.payload) {
    try {
      const p = JSON.parse(n.payload);
      const v = p.value ?? p.work ?? p;
      bits.push(JSON.stringify(v).slice(0, 240));
    } catch { /* ignore */ }
  }
  return bits.join("\n");
}

const SWATCH: Record<GraphNode["kind"], string> = {
  event: "bg-slate-400", lead: "bg-sky-500", fact: "bg-zinc-400",
  option: "bg-violet-500", ruling: "bg-amber-500",
};

function GraphLegend() {
  const kinds: { k: GraphNode["kind"]; label: string }[] = [
    { k: "event", label: "disruption" },
    { k: "lead", label: "lead (a line of investigation)" },
    { k: "fact", label: "fact (with its provenance)" },
    { k: "option", label: "candidate option" },
    { k: "ruling", label: "ruling (allowed / blocked)" },
  ];
  return (
    <div className="text-muted-foreground mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px]">
      {kinds.map(({ k, label }) => (
        <span key={k} className="inline-flex items-center gap-1.5">
          <span className={cn("h-3 w-0.5 rounded", SWATCH[k])} />
          {label}
        </span>
      ))}
      <span className="inline-flex items-center gap-1.5">
        <svg width="18" height="8"><path d="M0,4 H18" className="stroke-border" strokeDasharray="4 3" /></svg>
        rules-on edge
      </span>
    </div>
  );
}
