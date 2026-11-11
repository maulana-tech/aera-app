"use client";

import { ArrowRight, Landmark, ShieldCheck, Users } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ago, explorer, usd, type ActivityEvent, type ActivityNow, type ActivityPayload, type ActivitySince,
} from "@/app/lib";
import { AgentBadge } from "@/components/agent-card";
import { Dot } from "@/components/dort";
import { cn } from "@/lib/utils";

/* The team at work, without asking it (core/activity.py). It refreshes itself: every few seconds
 * while something is running, more slowly when the team is idle, and not at all in a hidden tab. */

const SEEN_KEY = "aera.activity.seen";
const NOT_AGENTS = new Set(["Team", "Vault"]);
const FILTERS = [
  { key: "", label: "Everything" }, { key: "team", label: "Team" }, { key: "money", label: "Money" },
  { key: "guardian", label: "Guardian" }, { key: "work", label: "Work" },
] as const;

function readSeen(): string | null {
  try { return window.localStorage.getItem(SEEN_KEY); } catch { return null; }
}
function writeSeen(v: string) {
  try { window.localStorage.setItem(SEEN_KEY, v); } catch { /* blocked storage: no "since" card, nothing else lost */ }
}

function Who({ name, size = "sm" }: { name: string; size?: "xs" | "sm" }) {
  const box = size === "xs" ? "size-4" : "size-7";
  if (name === "Vault") return <span className={cn("bg-raised text-brand flex shrink-0 items-center justify-center rounded-md", box)}><Landmark className="size-3.5" /></span>;
  if (NOT_AGENTS.has(name) || name.includes("@") || name.includes(":")) {
    return <span className={cn("bg-raised text-brand flex shrink-0 items-center justify-center rounded-md", box)}><Users className="size-3.5" /></span>;
  }
  return <AgentBadge nickname={name} size={size === "xs" ? "xs" : "sm"} showTooltip={false} />;
}

function Now({ runs, at }: { runs: ActivityNow[]; at: number }) {
  if (!runs.length) {
    return (
      <div className="bg-white flex items-center gap-3 rounded-lg border px-4 py-3">
        <Dot tone="neutral" />
        <p className="text-muted-foreground text-[13px]">The team is idle. New orders, goals and your requests start it on their own.</p>
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {runs.map((r) => (
        <li key={r.run_id}>
          <Link href={`/work/${r.run_id}`} className="bg-white border-brand/25 shadow-[0_0_0_3px_rgba(6,71,179,0.06)] hover:border-brand/40 flex items-center gap-3 rounded-lg border px-4 py-3 transition-colors">
            <span className="relative">
              <AgentBadge nickname={r.agent_name} size="sm" showTooltip={false} />
              <span className="absolute -right-0.5 -bottom-0.5 flex size-2.5">
                <span className="bg-info absolute inline-flex size-full animate-ping rounded-full opacity-70" />
                <span className="bg-info relative inline-flex size-2.5 rounded-full border-2 border-white" />
              </span>
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13.5px]"><span className="font-medium">{r.agent_name}</span> · {r.doing || "working"}</span>
              <span className="text-muted-foreground block truncate text-xs">{r.title}</span>
            </span>
            <span className="text-muted-foreground hidden shrink-0 text-right text-[11px] sm:block">
              <span className="block">{r.steps} steps · started {ago(r.started_at, at)}</span>
              <span className="block">{r.agents.length} agent{r.agents.length === 1 ? "" : "s"} involved</span>
            </span>
            <ArrowRight className="text-muted-foreground size-4 shrink-0" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Since({ s, at }: { s: ActivitySince; at: number }) {
  const items = [
    s.orders_paid ? `${s.orders_paid} order${s.orders_paid === 1 ? "" : "s"} paid (${usd(s.revenue_usd)})` : null,
    s.work_done ? `${s.work_done} piece${s.work_done === 1 ? "" : "s"} of work finished` : null,
    s.paid_out_usd ? `${usd(s.paid_out_usd)} paid out` : null,
    s.guardian_stops ? `${s.guardian_stops} action${s.guardian_stops === 1 ? "" : "s"} stopped by the Guardian` : null,
    s.held ? `${s.held} held or stopped early` : null,
  ].filter(Boolean) as string[];
  return (
    <div className="bg-raised rounded-lg px-4 py-3">
      <p className="text-[13px] font-medium">Since you were last here <span className="text-muted-foreground font-normal">· {ago(s.since, at)}</span></p>
      <p className="text-body mt-1 text-[13px] leading-relaxed">
        {items.length ? items.join(" · ") : "Nothing new."}
        {s.model_cost_usd > 0 && <span className="text-muted-foreground"> · model cost {usd(s.model_cost_usd)}</span>}
      </p>
      {s.waiting_now > 0 && (
        <Link href="/treasury" className="text-brand mt-1.5 inline-flex items-center gap-1 text-[13px] font-medium">
          {s.waiting_now} waiting for your decision <ArrowRight className="size-3.5" />
        </Link>
      )}
    </div>
  );
}

function Row({ e, at, network }: { e: ActivityEvent; at: number; network: string }) {
  const href = e.run_id ? `/work/${e.run_id}` : e.order_id ? "/orders" : e.action_id ? "/treasury" : null;
  return (
    <li className="flex items-start gap-3 px-4 py-2.5">
      <span className="pt-0.5"><Who name={e.agent} size="sm" /></span>
      <span className="min-w-0 flex-1">
        <span className="flex items-start gap-2">
          <Dot tone={e.tone === "info" ? "info" : e.tone} className="mt-[7px]" />
          <span className="min-w-0 text-[13px] leading-snug">{e.title}</span>
        </span>
        {e.detail && <span className="text-muted-foreground mt-0.5 block pl-3.5 text-xs leading-relaxed break-words">{e.detail}</span>}
      </span>
      <span className="flex shrink-0 flex-col items-end gap-0.5 text-[11px]">
        <span className="text-muted-foreground" title={e.at}>{ago(e.at, at)}</span>
        {e.tx && <a href={explorer(network, "txns", e.tx)} target="_blank" rel="noreferrer" className="underline underline-offset-2">tx</a>}
        {href && <Link href={href} className="underline underline-offset-2">open</Link>}
      </span>
    </li>
  );
}

export function TeamLive({ initial, network, compact = false, limit = 50 }: {
  initial: ActivityPayload; network: string; compact?: boolean; limit?: number;
}) {
  const [data, setData] = useState(initial);
  const [filter, setFilter] = useState("");
  const [since, setSince] = useState<ActivitySince | null>(null);
  const [at, setAt] = useState(() => new Date(initial.generated_at).getTime());
  const filterRef = useRef(filter);
  useEffect(() => { filterRef.current = filter; }, [filter]);

  const load = useCallback(async (category: string) => {
    try {
      const r = await fetch(`/api/aera/activity?limit=${limit}${category ? `&category=${category}` : ""}`, { cache: "no-store" });
      if (!r.ok) return;
      const d = (await r.json()) as ActivityPayload;
      if (category === filterRef.current) { setData(d); setAt(Date.now()); }
    } catch { /* the next tick tries again */ }
  }, [limit]);

  // "Since you were last here": what changed since the previous visit, then this visit becomes the mark.
  useEffect(() => {
    const seen = readSeen();
    if (seen) {
      fetch(`/api/aera/activity?limit=1&since=${encodeURIComponent(seen)}`, { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : null))
        .then((d: ActivityPayload | null) => d && setSince(d.since))
        .catch(() => {});
    }
    const t = setTimeout(() => writeSeen(new Date().toISOString()), 4000);
    return () => clearTimeout(t);
  }, []);

  const busy = data.now.length > 0;
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      if (document.visibilityState === "visible") void load(filterRef.current);
      timer = setTimeout(tick, busy ? 4000 : 20000);
    };
    timer = setTimeout(tick, busy ? 4000 : 20000);
    return () => clearTimeout(timer);
  }, [busy, load]);

  const events = compact ? data.events.slice(0, 8) : data.events;

  return (
    <div className="space-y-4">
      {since && !compact && <Since s={since} at={at} />}
      {since && compact && (since.orders_paid || since.work_done || since.guardian_stops || since.waiting_now) ? <Since s={since} at={at} /> : null}

      <div>
        <div className="mb-2 flex items-center gap-2">
          <h3 className="text-[14px] font-medium">Now</h3>
          {busy && <span className="text-info inline-flex items-center gap-1.5 text-[11px]"><Dot tone="info" className="animate-pulse" />live</span>}
        </div>
        <Now runs={data.now} at={at} />
      </div>

      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <h3 className="text-[14px] font-medium">What the team did</h3>
          {compact ? (
            <Link href="/activity" className="text-muted-foreground ml-auto inline-flex items-center gap-1 text-xs hover:text-fg">
              all activity <ArrowRight className="size-3" />
            </Link>
          ) : (
            <div className="ml-auto flex flex-wrap gap-1">
              {FILTERS.map((f) => (
                <button key={f.key} type="button" onClick={() => { filterRef.current = f.key; setFilter(f.key); void load(f.key); }}
                  className={cn("rounded-sm px-2.5 py-1 text-xs", filter === f.key ? "bg-primary text-primary-foreground" : "bg-raised text-text hover:bg-hover")}>
                  {f.key === "guardian" && <ShieldCheck className="mr-1 inline size-3" />}{f.label}
                </button>
              ))}
            </div>
          )}
        </div>
        {events.length ? (
          <ul className="bg-white divide-y rounded-lg border">
            {events.map((e, i) => <Row key={`${e.at}-${i}`} e={e} at={at} network={network} />)}
          </ul>
        ) : (
          <p className="text-muted-foreground rounded-lg border border-dashed px-4 py-6 text-sm">
            Nothing yet. When an order is paid or you give the team a request, every step shows up here.
          </p>
        )}
      </div>
    </div>
  );
}
