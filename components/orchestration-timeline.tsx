"use client";

import { useMemo, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronRight,
  Code2,
  Database,
  Lightbulb,
  Loader2,
  Sparkles,
} from "lucide-react";
import { AgentBadge } from "@/components/agent-card";
import { Markdown } from "@/components/markdown";
import { OriginBadge } from "@/components/status-badge";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

export type OrchestrationStep = {
  seq: number;
  kind: "init" | "specialist_start" | "tool" | "specialist_done" | "summary" | string;
  agent: string;
  agent_name: string;
  target_agent?: string;
  target_name?: string;
  narrative: string;
  badge: string;
  detail: string;
  full_detail?: string;
  thinking?: string | null;
  tool_name?: string;
  tool_label?: string;
  arguments?: Record<string, unknown>;
  result?: unknown;
  origin?: string;
  source?: string;
  error?: string;
  at: string;
};

export type OrchestrationTrailEntry = {
  kind: string;
  agent?: string;
  name?: string;
  task?: string;
  arguments?: Record<string, unknown>;
  result?: unknown;
  origin?: string;
  source?: string;
  error?: string;
  summary?: string;
  full_summary?: string;
  thinking?: string;
};

function stripTrailingChevron(text: string): string {
  return text.replace(/\s*[›>]+$/, "").trim();
}

function parseToolFromDetail(detail: string): {
  toolName: string;
  args: Record<string, string>;
} {
  const clean = stripTrailingChevron(detail);
  const match = clean.match(/^([a-z0-9_]+)(?:\s*\((.+)\))?$/i);
  if (!match) {
    return { toolName: clean, args: {} };
  }
  const toolName = match[1] ?? clean;
  const rawArgs = match[2] ?? "";
  const args: Record<string, string> = {};
  if (rawArgs) {
    for (const part of rawArgs.split("·")) {
      const idx = part.indexOf(":");
      if (idx > 0) {
        const k = part.slice(0, idx).trim();
        const v = part.slice(idx + 1).trim();
        if (k) args[k] = v;
      }
    }
  }
  return { toolName, args };
}

function formatStepTime(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function OrchestrationTimeline({
  steps,
  duration,
  isRunning = false,
  trail,
  board,
  finalAnswer,
}: {
  steps: OrchestrationStep[];
  duration?: number;
  isRunning?: boolean;
  trail?: OrchestrationTrailEntry[];
  board?: Record<string, { origin: string; source: string }>;
  finalAnswer?: string;
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  const specialistsList = useMemo(() => {
    const set = new Set<string>();
    for (const s of steps) {
      if (s.agent && s.agent !== "supervisor") set.add(s.agent_name || s.agent);
      if (s.target_agent && s.target_agent !== "supervisor") {
        set.add(s.target_name || s.target_agent);
      }
    }
    return Array.from(set);
  }, [steps]);

  const specialistsCount = specialistsList.length;

  const checksCount = useMemo(
    () => steps.filter((s) => s.kind === "tool").length,
    [steps],
  );

  // Group steps by participating agents to show squad overview
  const squadOverview = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of steps) {
      const name = s.agent_name || (s.agent === "supervisor" ? "Arya" : s.agent);
      if (name) counts[name] = (counts[name] ?? 0) + 1;
      if (s.target_name && s.target_name !== name) {
        counts[s.target_name] = (counts[s.target_name] ?? 0) + 1;
      }
    }
    return Object.entries(counts);
  }, [steps]);

  // Enrich steps with any extra data available in `trail` or `board` (for both new & historical messages)
  const enrichedSteps = useMemo(() => {
    return steps.map((step) => {
      const trailEntry =
        step.seq > 0 && trail && trail[step.seq - 1]
          ? trail[step.seq - 1]
          : undefined;

      const parsedTool =
        step.kind === "tool" ? parseToolFromDetail(step.detail) : null;
      const toolName =
        step.tool_name || trailEntry?.name || parsedTool?.toolName || "";
      const toolArgs =
        step.arguments && Object.keys(step.arguments).length > 0
          ? step.arguments
          : trailEntry?.arguments && Object.keys(trailEntry.arguments).length > 0
            ? trailEntry.arguments
            : parsedTool?.args && Object.keys(parsedTool.args).length > 0
              ? parsedTool.args
              : undefined;

      const boardKey =
        step.kind === "tool" && step.agent && toolName
          ? `${step.agent}.${toolName}`
          : "";
      const boardProvenance = boardKey && board ? board[boardKey] : undefined;

      const fullDetail =
        step.full_detail ||
        trailEntry?.full_summary ||
        trailEntry?.task ||
        trailEntry?.summary ||
        (step.kind === "summary" && finalAnswer ? finalAnswer : undefined) ||
        step.detail;

      return {
        ...step,
        tool_name: toolName || step.tool_name,
        arguments: toolArgs,
        result: step.result ?? trailEntry?.result,
        error: step.error ?? trailEntry?.error,
        origin: step.origin ?? trailEntry?.origin ?? boardProvenance?.origin,
        source: step.source ?? trailEntry?.source ?? boardProvenance?.source,
        thinking: step.thinking || trailEntry?.thinking || null,
        full_detail: fullDetail,
      };
    });
  }, [steps, trail, board, finalAnswer]);

  if (!steps.length && !isRunning) return null;

  const summaryTitle =
    isRunning && specialistsCount === 0
      ? "Analyzing and orchestrating agent team..."
      : specialistsCount > 0
        ? `Orchestrating ${specialistsCount} specialist${specialistsCount > 1 ? "s" : ""}${
            checksCount > 0
              ? ` and ${checksCount} data check${checksCount > 1 ? "s" : ""}`
              : ""
          }`
        : `Orchestration workflow (${steps.length} steps)`;

  const latestStep = enrichedSteps[enrichedSteps.length - 1];

  return (
    <>
      {/* Compact Trigger Bar in Chat */}
      <button
        type="button"
        onClick={() => setDrawerOpen(true)}
        className="bg-muted/30 hover:bg-muted/60 hover:border-foreground/25 group mb-3 flex w-full cursor-pointer items-center justify-between gap-3 overflow-hidden rounded-lg border px-3.5 py-2.5 text-left text-xs transition-all"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {isRunning ? (
              <Loader2 className="text-primary size-3.5 shrink-0 animate-spin" />
            ) : (
              <span className="bg-primary/20 text-primary flex size-3.5 shrink-0 items-center justify-center rounded-full">
                <Check className="size-2.5 stroke-[2.5]" />
              </span>
            )}
            <span className="text-foreground truncate font-medium">
              {summaryTitle}
              {duration !== undefined && (
                <span className="text-muted-foreground font-mono font-normal">
                  {" "}
                  ({duration.toFixed(1)}s)
                </span>
              )}
            </span>
          </div>

          {/* Live current step preview while running */}
          {isRunning && latestStep && (
            <div className="text-muted-foreground mt-1 flex items-center gap-1.5 pl-5.5 text-[11px]">
              <AgentBadge
                nickname={latestStep.agent_name || "Arya"}
                size="xs"
                showTooltip={false}
              />
              <span className="truncate">{latestStep.narrative}</span>
            </div>
          )}
        </div>

        <ChevronRight className="text-muted-foreground group-hover:text-foreground size-4 shrink-0 transition-transform duration-200 group-hover:translate-x-0.5" />
      </button>

      {/* Right Drawer Panel for Thinking & Orchestration Timeline */}
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent
          side="right"
          className="flex w-full data-[side=right]:w-full flex-col gap-0 p-0 sm:data-[side=right]:max-w-[560px]"
        >
          <SheetHeader className="bg-muted/20 shrink-0 border-b px-5 py-4 pr-12">
            <div className="flex items-center gap-2">
              {isRunning ? (
                <Loader2 className="text-primary size-3.5 shrink-0 animate-spin" />
              ) : (
                <span className="bg-primary/20 text-primary flex size-4 shrink-0 items-center justify-center rounded-full">
                  <Check className="size-2.5 stroke-[2.5]" />
                </span>
              )}
              <SheetTitle className="text-sm font-medium">
                {summaryTitle}
              </SheetTitle>
            </div>
            <SheetDescription className="flex flex-wrap items-center gap-2 text-xs">
              <span>
                {enrichedSteps.length} step{enrichedSteps.length === 1 ? "" : "s"}
              </span>
              {duration !== undefined && (
                <span className="font-mono">
                  · Thought for {duration.toFixed(1)}s
                </span>
              )}
            </SheetDescription>

            {/* Participating Agent Squad Strip */}
            {squadOverview.length > 0 && (
              <div className="border-border/60 mt-3 flex flex-wrap items-center gap-1.5 border-t pt-2.5">
                <span className="text-muted-foreground/60 mr-1 font-mono text-[10px] uppercase">
                  Squad:
                </span>
                {squadOverview.map(([agentName, count]) => (
                  <span
                    key={agentName}
                    className="bg-background inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium shadow-2xs"
                  >
                    <AgentBadge nickname={agentName} size="xs" showTooltip={false} />
                    <span>{agentName}</span>
                    <span className="text-muted-foreground font-mono text-[10px]">
                      ({count})
                    </span>
                  </span>
                ))}
              </div>
            )}
          </SheetHeader>

          {/* Drawer Body: Full Open Stream (No Hidden Collapsibles, Clean Typography Hierarchy) */}
          <div className="flex-1 overflow-y-auto px-5 py-5">
            <ol className="relative ml-3 space-y-7 border-l border-border/80 pl-6">
              {enrichedSteps.map((step, idx) => {
                const isLast = idx === enrichedSteps.length - 1;
                const isStepActive = isRunning && isLast;

                const cleanBadge = stripTrailingChevron(step.badge);
                const hasDetailedNarrative =
                  step.detail &&
                  step.detail !== step.narrative &&
                  stripTrailingChevron(step.detail) !== cleanBadge;

                const currentActor =
                  step.kind === "specialist_start" && step.target_name
                    ? step.target_name
                    : step.agent_name || "Arya";

                return (
                  <li key={`${step.seq}-${idx}`} className="group relative">
                    {/* Living Agent Avatar on the Timeline Rail */}
                    <span className="bg-background ring-border absolute -left-[37px] top-0.5 flex size-6.5 items-center justify-center rounded-full ring-1 shadow-xs">
                      {isStepActive ? (
                        <div className="relative flex size-full items-center justify-center">
                          <AgentBadge nickname={currentActor} size="xs" showTooltip={false} />
                          <span className="bg-background/90 absolute -right-1 -bottom-1 rounded-full p-0.5">
                            <Loader2 className="text-primary size-2.5 animate-spin" />
                          </span>
                        </div>
                      ) : (
                        <AgentBadge nickname={currentActor} size="xs" showTooltip={false} />
                      )}
                    </span>

                    <div className="min-w-0 flex-1 space-y-2">
                      {/* Step Header: Actor, Title, and Timestamp */}
                      <div className="flex items-baseline justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {step.kind === "specialist_start" && step.target_name ? (
                            <span className="text-muted-foreground inline-flex shrink-0 items-center gap-1 text-[11px] font-medium">
                              <span className="text-foreground font-semibold">
                                {step.agent_name || "Arya"}
                              </span>
                              <ArrowRight className="size-2.5" />
                              <span className="text-primary font-semibold">
                                {step.target_name}
                              </span>
                            </span>
                          ) : (
                            <span className="text-foreground text-xs font-semibold">
                              {currentActor}
                            </span>
                          )}

                          <span className="text-muted-foreground/40 select-none">·</span>

                          <h3 className="text-foreground text-xs sm:text-sm font-semibold leading-snug">
                            {step.narrative}
                          </h3>
                        </div>

                        {step.at && (
                          <span className="text-muted-foreground/50 shrink-0 font-mono text-[10px]">
                            {formatStepTime(step.at)}
                          </span>
                        )}
                      </div>

                      {/* Step Badge & Full Descriptive Detail (Placed below, full width without truncation) */}
                      <div className="space-y-1.5 pt-0.5">
                        <div>
                          <span className="text-foreground/90 bg-muted/60 inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-medium tracking-wide uppercase">
                            {cleanBadge}
                          </span>
                        </div>

                        {hasDetailedNarrative && (
                          <p className="text-muted-foreground text-xs leading-relaxed">
                            {stripTrailingChevron(step.detail)}
                          </p>
                        )}
                      </div>

                      {/* 1. Agent Thinking Section (Clean Editorial Prose) */}
                      {step.thinking && (
                        <div className="space-y-1 pt-1">
                          <span className="text-muted-foreground/60 flex items-center gap-1 text-[10px] font-semibold tracking-wider uppercase font-mono">
                            <Sparkles className="size-2.5" />
                            Thinking
                          </span>
                          <div className="text-muted-foreground leading-relaxed text-xs sm:text-sm">
                            <Markdown>{step.thinking}</Markdown>
                          </div>
                        </div>
                      )}

                      {/* 2. Init Overview (Specialist Team Breakdown) */}
                      {step.kind === "init" && specialistsList.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {specialistsList.map((sp) => (
                            <span
                              key={sp}
                              className="bg-muted/40 text-muted-foreground inline-flex items-center gap-1 rounded-md border border-border/50 px-2 py-0.5 text-[11px]"
                            >
                              <AgentBadge
                                nickname={sp}
                                size="xs"
                                showTooltip={false}
                              />
                              <span>{sp}</span>
                            </span>
                          ))}
                        </div>
                      )}

                      {/* 3. Specialist Delegation / Finding / Synthesis Content */}
                      {step.kind !== "init" &&
                        step.kind !== "tool" &&
                        step.full_detail &&
                        step.full_detail !== step.detail && (
                          <div className="space-y-1 pt-1">
                            <div className="text-foreground/90 leading-relaxed text-xs sm:text-sm">
                              <Markdown>{step.full_detail}</Markdown>
                            </div>
                          </div>
                        )}

                      {/* 4. Tool Execution: Name, Provenance, Parameters, Output */}
                      {step.kind === "tool" && (
                        <div className="space-y-2 pt-1 text-xs">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-1.5">
                              <Code2 className="text-muted-foreground size-3" />
                              <code className="text-foreground font-mono text-[11px] font-semibold">
                                {step.tool_name ||
                                  stripTrailingChevron(step.detail)}
                              </code>
                            </div>
                            {step.origin && (
                              <OriginBadge
                                origin={step.origin}
                                source={step.source}
                              />
                            )}
                          </div>

                          {/* Arguments / Parameters */}
                          {step.arguments &&
                            Object.keys(step.arguments).length > 0 && (
                              <div className="bg-muted/30 divide-y divide-border/40 rounded border border-border/50 font-mono text-[11px]">
                                {Object.entries(step.arguments).map(([k, v]) => (
                                  <div
                                    key={k}
                                    className="flex items-start justify-between gap-3 px-2.5 py-1"
                                  >
                                    <span className="text-muted-foreground shrink-0">
                                      {k}
                                    </span>
                                    <span className="text-foreground break-all text-right font-medium">
                                      {typeof v === "object" && v !== null
                                        ? JSON.stringify(v)
                                        : String(v)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}

                          {/* Error or Return Data */}
                          {step.error ? (
                            <pre className="bg-destructive/10 text-destructive border-destructive/20 overflow-x-auto rounded border p-2 font-mono text-[11px] whitespace-pre-wrap">
                              {step.error}
                            </pre>
                          ) : step.result !== undefined ? (
                            <div className="space-y-1">
                              <span className="text-muted-foreground/60 flex items-center gap-1 font-mono text-[10px] uppercase">
                                <Database className="size-2.5" />
                                Return Payload
                              </span>
                              <pre className="bg-muted/30 text-muted-foreground border-border/50 max-h-48 overflow-auto rounded border p-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
                                {typeof step.result === "string"
                                  ? step.result
                                  : JSON.stringify(step.result, null, 2)}
                              </pre>
                            </div>
                          ) : null}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}

              {/* End of Workflow / Thinking Completed Marker (inside the rail) */}
              {!isRunning && enrichedSteps.length > 0 && (
                <li className="relative pt-2 pb-1">
                  <span className="bg-background text-muted-foreground/70 ring-border/80 absolute -left-[31px] top-2 flex size-3.5 items-center justify-center rounded-full ring-1">
                    <Lightbulb className="size-2.5 stroke-[2]" />
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-foreground/80 font-medium text-xs sm:text-sm">
                      End
                    </span>
                    {duration !== undefined && (
                      <span className="text-muted-foreground/60 font-mono text-[11px]">
                        · {duration.toFixed(1)}s
                      </span>
                    )}
                  </div>
                </li>
              )}
            </ol>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}

