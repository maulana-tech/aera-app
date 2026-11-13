"use client";

import { useMemo, useState } from "react";

import { Dot } from "@/components/dort";
import { cn } from "@/lib/utils";

/* The Composer's rules (core/team.py, pick_roles), on a handful of switches. The same answers always give the
 * same team; the three core roles are always there and locked. */

type Trait = { id: string; label: string; adds: string[] };
const TRAITS: Trait[] = [
  { id: "docs", label: "Sells documents (PDF, XLSX)", adds: ["researcher", "writer", "qa", "ops"] },
  { id: "prospect", label: "Finds its own customers", adds: ["prospector", "sales"] },
  { id: "talk", label: "Answers customers by e-mail or chat", adds: ["support"] },
  { id: "money", label: "Takes payments", adds: ["finance"] },
  { id: "spend", label: "May spend on its own", adds: ["procurement"] },
  { id: "content", label: "Publishes free samples", adds: ["marketing"] },
  { id: "data", label: "Holds clients' material", adds: ["compliance"] },
];

const ROLES: Record<string, { name: string; may: string; core?: boolean }> = {
  supervisor: { name: "Supervisor", may: "Delegates one step at a time; writes the outcome. Moves no money.", core: true },
  guardian: { name: "Guardian", may: "Rules on every payment, message and counterparty. Final block; can freeze.", core: true },
  treasurer: { name: "Treasurer", may: "The only one who pays: vendors on record, through the vault.", core: true },
  prospector: { name: "Lead Researcher", may: "Finds businesses that fit; saves leads with the page that shows them." },
  sales: { name: "Sales", may: "Writes to leads, follows up on schedule, answers replies." },
  researcher: { name: "Researcher", may: "Sources every claim from the open web, read as untrusted text." },
  writer: { name: "Writer", may: "Writes the deliverable in the business's voice." },
  qa: { name: "Quality Review", may: "PASS or FAIL against the offering and its sources." },
  ops: { name: "Fulfilment", may: "Delivers only to the customer who paid." },
  support: { name: "Customer Support", may: "Resolves order questions; proposes, never grants, refunds." },
  finance: { name: "Finance", may: "Receipts, reports, reconciliation with the vault." },
  procurement: { name: "Procurement", may: "Finds vendors and other AERA businesses to buy from." },
  marketing: { name: "Marketing", may: "Publishes samples after the code checks pass." },
  compliance: { name: "Legal & Compliance", may: "Checks what goes out; keeps the personal-data register." },
};

const PRESETS: { label: string; on: string[] }[] = [
  { label: "Research shop", on: ["docs", "money", "content"] },
  { label: "Agency that finds clients", on: ["prospect", "talk", "money", "data"] },
  { label: "Data seller that buys inputs", on: ["docs", "money", "spend"] },
];

export function TeamComposer() {
  const [on, setOn] = useState<string[]>(PRESETS[1]!.on);
  const team = useMemo(() => {
    const picked = ["supervisor", "guardian", "treasurer"];
    for (const t of TRAITS) if (on.includes(t.id)) for (const r of t.adds) if (!picked.includes(r)) picked.push(r);
    return picked;
  }, [on]);
  const toggle = (id: string) => setOn((xs) => (xs.includes(id) ? xs.filter((x) => x !== id) : [...xs, id]));

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <div>
        <p className="text-on-canvas-dim text-[13px]">Start from</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {PRESETS.map((p) => {
            const active = p.on.length === on.length && p.on.every((x) => on.includes(x));
            return (
              <button key={p.label} type="button" onClick={() => setOn(p.on)}
                className={cn("h-8 rounded-md border px-3 text-[13px] transition-colors",
                  active ? "border-white bg-white text-brand" : "border-white/20 text-white hover:bg-white/10")}>
                {p.label}
              </button>
            );
          })}
        </div>
        <p className="text-on-canvas-dim mt-6 text-[13px]">The business…</p>
        <div className="mt-2 space-y-1.5">
          {TRAITS.map((t) => {
            const active = on.includes(t.id);
            return (
              <button key={t.id} type="button" role="switch" aria-checked={active} onClick={() => toggle(t.id)}
                className={cn("flex w-full items-center gap-3 rounded-lg border px-3.5 py-2.5 text-left text-[14px] transition-colors",
                  active ? "border-white/40 bg-white/[0.14] text-white" : "border-white/10 text-white/75 hover:bg-white/[0.07]")}>
                <span className={cn("relative h-[18px] w-8 shrink-0 rounded-full transition-colors", active ? "bg-white" : "bg-white/20")}>
                  <span className={cn("absolute top-[3px] size-3 rounded-full transition-[left,background-color]",
                    active ? "bg-brand left-[17px]" : "left-[3px] bg-white")} />
                </span>
                {t.label}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <div className="flex items-baseline gap-2">
          <p className="font-mono text-[28px] text-white tabular-nums">{team.length}</p>
          <p className="text-on-canvas-dim text-[13px]">agents, composed from these answers</p>
        </div>
        <ul className="mt-3 grid gap-2.5 sm:grid-cols-2">
          {team.map((code) => {
            const r = ROLES[code]!;
            return (
              <li key={code} className="bg-card-grad animate-in fade-in zoom-in-95 rounded-lg border p-3.5 duration-300">
                <div className="flex items-center gap-2">
                  <Dot tone={r.core ? "solid" : "info"} />
                  <p className="text-fg text-[14px]">{r.name}</p>
                  {r.core && <span className="text-muted-foreground ml-auto font-mono text-[10.5px]">always · locked</span>}
                </div>
                <p className="text-body mt-1 text-[12.5px] leading-relaxed">{r.may}</p>
              </li>
            );
          })}
        </ul>
        <p className="text-on-canvas-dim mt-3 text-[11.5px] leading-relaxed">
          Capabilities, not tools, are granted. Treasury, guardian and supervisor are locked to their roles in code
          and re-checked on every call.
        </p>
      </div>
    </div>
  );
}
