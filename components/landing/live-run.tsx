"use client";

import { BadgeCheck, Pause, Play } from "lucide-react";
import { useEffect, useState } from "react";

import { Chip, Dot, Panel, type Tone } from "@/components/dort";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "./motion";

/* One order, as AERA works it. Drawn from a run on testnet; the times are its real shape, compressed. */
const STEPS: { who: string; what: string; tone: Tone; at: string }[] = [
  { who: "Vault", what: "15 USDC received, revenue split on chain", tone: "ok", at: "00:00" },
  { who: "Supervisor", what: "plans the brief, delegates research", tone: "info", at: "00:04" },
  { who: "Researcher", what: "6 sources read as untrusted text", tone: "info", at: "03:12" },
  { who: "Writer", what: "5-page brief, every claim sourced", tone: "info", at: "21:40" },
  { who: "Quality Review", what: "PASS: scope, sources, no other client's data", tone: "ok", at: "24:18" },
  { who: "Guardian", what: "recipient is the payer · allow", tone: "ok", at: "24:30" },
  { who: "Fulfilment", what: "delivered · hash written to the vault", tone: "ok", at: "55:10" },
];
const STEP_MS = 1300;
const HOLD_MS = 3200;

export function LiveRun() {
  const reduced = useReducedMotion();
  const [step, setStep] = useState(3);
  const [paused, setPaused] = useState(false);
  const shown = reduced ? STEPS.length : step;
  const done = shown >= STEPS.length;

  useEffect(() => {
    if (reduced || paused) return;
    const t = setTimeout(() => setStep((n) => (n >= STEPS.length ? 3 : n + 1)), done ? HOLD_MS : STEP_MS);
    return () => clearTimeout(t);
  }, [step, paused, reduced, done]);

  return (
    <Panel className="w-full overflow-hidden">
      <div className="bg-raised h-1 w-full">
        <div className="bg-brand h-full transition-[width] duration-700 ease-out" style={{ width: `${(shown / STEPS.length) * 100}%` }} />
      </div>
      <div className="p-5 md:p-6">
        <div className="flex items-center gap-2">
          <Chip tone={done ? "ok" : "info"}>
            {done ? "done" : (
              <span className="inline-flex items-center gap-1.5">
                running
                <span className="relative inline-flex size-1.5">
                  <span className="bg-info absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 motion-reduce:hidden" />
                </span>
              </span>
            )}
          </Chip>
          <span className="text-muted-foreground truncate font-mono text-[11px]">order · market brief · $15.00</span>
          {!reduced && (
            <button type="button" onClick={() => setPaused((p) => !p)} aria-label={paused ? "Play the run" : "Pause the run"}
              className="text-muted-foreground hover:text-fg hover:bg-raised ml-auto inline-flex size-7 items-center justify-center rounded-md">
              {paused ? <Play className="size-3.5" /> : <Pause className="size-3.5" />}
            </button>
          )}
        </div>
        <p className="text-fg mt-3 text-[16px]">Market brief: specialty coffee, Indonesia</p>
        <ol className="mt-2" aria-live="polite">
          {STEPS.map((s, i) => {
            const on = i < shown;
            const current = i === shown - 1 && !done;
            return (
              <li key={s.who}
                className={cn("flex items-start gap-3 border-t py-2.5 transition-[opacity,transform] duration-500 first:border-t-0",
                  on ? "translate-y-0 opacity-100" : "pointer-events-none -translate-y-1 opacity-0")}>
                <Dot tone={s.tone} className={cn("mt-[7px]", current && "ring-info/25 ring-4")} />
                <p className="text-fg min-w-0 flex-1 text-[13.5px]"><span className="text-text">{s.who}</span> · {s.what}</p>
                <span className="text-muted-foreground shrink-0 font-mono text-[11px] tabular-nums">{s.at}</span>
              </li>
            );
          })}
        </ol>
        <div className={cn("bg-inner-grad mt-3 rounded-lg border px-3.5 py-3 transition-opacity duration-500", done ? "opacity-100" : "opacity-60")}>
          <div className="flex items-center gap-2 text-[12.5px]">
            <BadgeCheck className="text-brand size-4 shrink-0" />
            <span className="text-text">Every model call ran in a TEE: attestation and signature verified</span>
          </div>
        </div>
      </div>
    </Panel>
  );
}
