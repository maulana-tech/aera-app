"use client";

import { useMemo, useState } from "react";
import { ChevronDown, Loader2 } from "lucide-react";
import { AgentBadge } from "@/components/agent-card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

export type OrchestrationStep = {
  seq: number;
  kind: "specialist_start" | "tool" | "specialist_done" | "summary" | string;
  agent: string;
  agent_name: string;
  target_agent?: string;
  target_name?: string;
  narrative: string;
  badge: string;
  detail: string;
  at: string;
};

export function OrchestrationTimeline({
  steps,
  duration,
  isRunning = false,
}: {
  steps: OrchestrationStep[];
  duration?: number;
  isRunning?: boolean;
}) {
  const [open, setOpen] = useState(true);

  const specialistsCount = useMemo(() => {
    const set = new Set<string>();
    for (const s of steps) {
      if (s.agent && s.agent !== "supervisor") set.add(s.agent_name || s.agent);
      if (s.target_agent && s.target_agent !== "supervisor") {
        set.add(s.target_name || s.target_agent);
      }
    }
    return set.size;
  }, [steps]);

  const checksCount = useMemo(
    () => steps.filter((s) => s.kind === "tool").length,
    [steps],
  );

  if (!steps.length && !isRunning) return null;

  const summaryTitle = specialistsCount > 0
    ? `Mengorkestrasi ${specialistsCount} spesialis${
        checksCount > 0 ? ` dan ${checksCount} pengecekan data` : ""
      }`
    : `Alur orkestrasi ${steps.length} langkah`;

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="bg-muted/30 mb-3 overflow-hidden rounded-lg border text-xs"
    >
      <CollapsibleTrigger className="hover:bg-muted/50 flex w-full items-center justify-between px-3.5 py-2.5 text-left transition-colors">
        <div className="flex items-center gap-2">
          {isRunning ? (
            <Loader2 className="text-primary size-3.5 animate-spin shrink-0" />
          ) : (
            <span className="bg-primary/20 text-primary flex size-3.5 items-center justify-center rounded-full text-[9px] font-bold">
              ✓
            </span>
          )}
          <span className="font-medium text-foreground">
            {summaryTitle}
            {duration !== undefined && (
              <span className="text-muted-foreground font-mono font-normal">
                {" "}
                ({duration.toFixed(1)}s)
              </span>
            )}
          </span>
        </div>
        <ChevronDown
          className={`text-muted-foreground size-4 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </CollapsibleTrigger>

      <CollapsibleContent className="border-t px-3.5 py-3">
        <ol className="relative ml-2.5 space-y-3.5 border-l border-border/80 pl-5">
          {steps.map((step, idx) => {
            const isLast = idx === steps.length - 1;
            const isStepActive = isRunning && isLast;

            return (
              <li key={`${step.seq}-${idx}`} className="group relative">
                {/* Node Avatar Icon on the Timeline Rail */}
                <span className="bg-background ring-border/80 absolute -left-[27px] top-0 flex size-5.5 items-center justify-center rounded-full ring-1 shadow-2xs">
                  <AgentBadge
                    nickname={step.agent_name || "Arya"}
                    size="xs"
                    showTooltip={false}
                  />
                </span>

                <div className="min-w-0 flex-1">
                  {/* Top Line: Action Narrative */}
                  <div className="flex items-center gap-1.5">
                    {step.kind === "specialist_start" && step.target_name ? (
                      <span className="text-muted-foreground inline-flex items-center gap-1 text-[11px] font-medium">
                        <span>{step.agent_name}</span>
                        <span>➔</span>
                        <AgentBadge
                          nickname={step.target_name}
                          size="xs"
                          showTooltip={false}
                        />
                      </span>
                    ) : null}

                    <p className="text-foreground text-xs leading-snug">
                      {step.narrative}
                    </p>

                    {isStepActive && (
                      <Loader2 className="text-primary size-3 animate-spin shrink-0" />
                    )}
                  </div>

                  {/* Bottom Line: Metadata Chip / Detail */}
                  <div className="text-muted-foreground mt-0.5 flex flex-wrap items-center gap-1 text-[11px]">
                    <span className="text-muted-foreground/50 select-none">└─</span>
                    <span className="bg-background border-border/60 text-foreground/90 inline-flex items-center rounded border px-1.5 py-0.2 font-mono text-[10px] font-medium">
                      {step.badge}
                    </span>
                    {step.detail && (
                      <span className="text-muted-foreground/80 truncate font-mono text-[10px]">
                        {step.detail}
                      </span>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </CollapsibleContent>
    </Collapsible>
  );
}
