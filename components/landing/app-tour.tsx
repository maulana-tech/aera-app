"use client";

import { Check, Landmark, Radar, Gauge, X } from "lucide-react";
import { useState } from "react";

import { Chip, Dot, Panel, type Tone } from "@/components/dort";
import { cn } from "@/lib/utils";

/* Three screens of the app, drawn small: what a person actually looks at while the team works. */

function Window({ path, children }: { path: string; children: React.ReactNode }) {
  return (
    <Panel className="overflow-hidden">
      <div className="bg-raised flex items-center gap-1.5 border-b px-3 py-2">
        <span className="size-2 rounded-full bg-[#d6e4fb]" /><span className="size-2 rounded-full bg-[#d6e4fb]" /><span className="size-2 rounded-full bg-[#d6e4fb]" />
        <span className="text-muted-foreground ml-3 truncate font-mono text-[11px]">aera.utdi.me{path}</span>
        <span className="text-muted-foreground ml-auto shrink-0 rounded-sm border px-1.5 text-[10px]">example data</span>
      </div>
      <div className="p-4 md:p-5">{children}</div>
    </Panel>
  );
}

function Leads() {
  const funnel = [["found", 24], ["written to", 11], ["answered", 4], ["won", 1]] as const;
  const rows: [string, string, string, Tone, string][] = [
    ["Rina S.", "Studio Kopi Digital", "answered", "info", "-"],
    ["Dewi P.", "Lumbung Creative", "written to", "info", "day 3"],
    ["Andre W.", "Nusantara Retail Lab", "found", "neutral", "approve first"],
    ["Maya L.", "Kedai Analytics", "won", "ok", "$15 paid"],
  ];
  return (
    <Window path="/leads">
      <div className="grid grid-cols-4 gap-2">
        {funnel.map(([k, n], i) => (
          <div key={k} className="bg-inner-grad rounded-md border px-2.5 py-2">
            <p className="text-fg font-mono text-[18px] tabular-nums">{n}</p>
            <p className="text-muted-foreground text-[11px]">{k}</p>
            <div className="bg-raised mt-1.5 h-1 rounded-full"><div className="bg-brand h-1 rounded-full" style={{ width: `${100 - i * 28}%` }} /></div>
          </div>
        ))}
      </div>
      <ul className="mt-3 divide-y rounded-md border">
        {rows.map(([who, co, stage, tone, next]) => (
          <li key={who} className="flex items-center gap-3 px-3 py-2 text-[12.5px]">
            <Chip tone={tone} className="w-[6.5rem] justify-start">{stage}</Chip>
            <span className="text-fg min-w-0 flex-1 truncate">{who} <span className="text-muted-foreground">· {co}</span></span>
            <span className="text-muted-foreground hidden font-mono text-[10.5px] sm:inline">{next}</span>
          </li>
        ))}
      </ul>
      <p className="text-muted-foreground mt-3 text-[11.5px]">Each lead carries the public page that shows its address. A stop is final.</p>
    </Window>
  );
}

function Approve() {
  const [decided, setDecided] = useState<null | "approved" | "rejected">(null);
  return (
    <Window path="/treasury">
      <div className="rounded-lg border p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone={decided === "approved" ? "ok" : decided === "rejected" ? "bad" : "warn"}>{decided ?? "pending"}</Chip>
          <span className="text-fg font-mono text-[14px]">$8.00</span>
          <span className="text-muted-foreground text-[12px]">payment to DataCo · vendor.testnet</span>
        </div>
        <p className="text-body mt-2 text-[12.5px]">Full regional dataset for the weekly coffee brief.</p>
        <ul className="mt-3 space-y-1 text-[12px]">
          <li className="flex items-center gap-2"><Dot tone="ok" /><span className="text-body">on record · allowlisted · paid before</span></li>
          <li className="flex items-center gap-2"><Dot tone="warn" /><span className="text-body">$8.00 is over the autonomous $5.00 per payment</span></li>
        </ul>
        {decided === null ? (
          <div className="mt-4 flex gap-2">
            <button type="button" onClick={() => setDecided("approved")}
              className="bg-brand inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-[12.5px] text-white hover:bg-[var(--brand-lit)]">
              <Check className="size-3.5" /> Approve
            </button>
            <button type="button" onClick={() => setDecided("rejected")}
              className="text-text hover:bg-raised inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-[12.5px]">
              <X className="size-3.5" /> Reject
            </button>
          </div>
        ) : (
          <div className="bg-inner-grad mt-4 rounded-md border px-3 py-2.5 text-[12.5px]">
            {decided === "approved" ? (
              <p className="text-body"><span className="text-fg">Approved in AERA.</span> The vault holds it until an approver signs
                <span className="font-mono"> approve(request_id)</span> with 1 yoctoNEAR in their own wallet.</p>
            ) : (
              <p className="text-body"><span className="text-fg">Rejected.</span> Nothing was sent; the team is told why on the run.</p>
            )}
            <button type="button" onClick={() => setDecided(null)} className="text-brand mt-1.5 text-[12px] underline-offset-2 hover:underline">try again</button>
          </div>
        )}
      </div>
      <p className="text-muted-foreground mt-3 text-[11.5px]">Approval limits come from your role: operator $100, approver $1,000, owner more.</p>
    </Window>
  );
}

function Autonomy() {
  const touches: [string, number][] = [["approved a payment over the cap", 3], ["approved a first message", 2], ["ran work again", 1]];
  return (
    <Window path="/dashboard">
      <div className="flex items-end gap-3">
        <p className="text-fg font-mono text-[34px] leading-none tabular-nums">55.6%</p>
        <p className="text-muted-foreground pb-1 text-[12px]">of finished work needed no person · 30 days</p>
      </div>
      <div className="bg-raised mt-3 h-2 overflow-hidden rounded-full"><div className="bg-brand h-full rounded-full" style={{ width: "55.6%" }} /></div>
      <div className="mt-4 grid grid-cols-3 gap-2">
        {[["97.8%", "margin after AI"], ["0.92 h", "order to delivery"], ["$0.33", "AI per order"]].map(([v, l]) => (
          <div key={l} className="bg-inner-grad rounded-md border px-2.5 py-2">
            <p className="text-fg font-mono text-[15px] tabular-nums">{v}</p>
            <p className="text-muted-foreground text-[11px]">{l}</p>
          </div>
        ))}
      </div>
      <p className="text-text mt-4 text-[12.5px]">When a person stepped in</p>
      <ul className="mt-1.5 space-y-1 text-[12px]">
        {touches.map(([w, n]) => (
          <li key={w} className="flex items-center gap-2"><Dot tone="warn" /><span className="text-body flex-1">{w}</span><span className="text-fg font-mono">{n}</span></li>
        ))}
      </ul>
      <p className="text-muted-foreground mt-3 text-[11.5px]">Counted in code from the record; the Finance agent only adds commentary.</p>
    </Window>
  );
}

const TABS = [
  { id: "leads", label: "Find customers", icon: Radar, view: Leads, note: "The pipeline the Lead Researcher and Sales work, with the funnel and its cost." },
  { id: "approve", label: "Approve", icon: Landmark, view: Approve, note: "What waits for you, with the Guardian's reasons. Try it." },
  { id: "autonomy", label: "Autonomy", icon: Gauge, view: Autonomy, note: "How much ran alone, every time a person stepped in, and whether each order paid for itself." },
] as const;

export function AppTour() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("leads");
  const t = TABS.find((x) => x.id === tab)!;
  const View = t.view;
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,0.7fr)_minmax(0,1.3fr)]">
      <div role="tablist" aria-label="Screens of the app" className="flex gap-2 overflow-x-auto lg:flex-col">
        {TABS.map((x) => {
          const on = x.id === tab;
          const I = x.icon;
          return (
            <button key={x.id} type="button" role="tab" aria-selected={on} onClick={() => setTab(x.id)}
              className={cn("flex shrink-0 items-start gap-3 rounded-lg border px-4 py-3 text-left transition-colors lg:w-full",
                on ? "border-white bg-white text-fg shadow-float" : "border-white/15 bg-white/[0.06] text-white hover:bg-white/[0.12]")}>
              <I className={cn("mt-0.5 size-4 shrink-0", on ? "text-brand" : "text-white/80")} />
              <span>
                <span className="block text-[14px]">{x.label}</span>
                <span className={cn("mt-0.5 hidden text-[12px] leading-relaxed lg:block", on ? "text-body" : "text-white/65")}>{x.note}</span>
              </span>
            </button>
          );
        })}
      </div>
      <div role="tabpanel" key={tab} className="animate-in fade-in slide-in-from-bottom-2 duration-300">
        <View />
      </div>
    </div>
  );
}
