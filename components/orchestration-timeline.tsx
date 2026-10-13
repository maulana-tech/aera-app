"use client";

import { useMemo, useState } from "react";
import {
  ChevronRight,
  Code2,
  Database,
  Loader2,
  Sparkles,
  Terminal,
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
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

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
  const activeStep =
    selectedIdx !== null && enrichedSteps[selectedIdx]
      ? enrichedSteps[selectedIdx]
      : null;

  return (
    <>
      {/* Compact Trigger Bar in Chat — clicking anywhere (or on `>`) pops open the Right Drawer Panel */}
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
              <span className="bg-primary/20 text-primary flex size-3.5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold">
                ✓
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
          className="flex w-full flex-col gap-0 p-0 data-[side=right]:sm:max-w-[560px]"
        >
          <SheetHeader className="bg-muted/20 shrink-0 border-b px-5 py-4 pr-12">
            <div className="flex items-center gap-2">
              {isRunning ? (
                <Loader2 className="text-primary size-3.5 shrink-0 animate-spin" />
              ) : (
                <span className="bg-primary/20 text-primary flex size-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold">
                  ✓
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
              <span className="text-muted-foreground/80">
                · Click any step&apos;s › badge to inspect details
              </span>
            </SheetDescription>
          </SheetHeader>

          {/* Drawer Body: Full Orchestration Timeline + Inline Step Inspector */}
          <div className="flex-1 overflow-y-auto px-5 py-4">
            <ol className="border-border/80 relative ml-2.5 space-y-4 border-l pl-5">
              {enrichedSteps.map((step, idx) => {
                const isLast = idx === enrichedSteps.length - 1;
                const isStepActive = isRunning && isLast;
                const isExpanded = selectedIdx === idx;

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
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex min-w-0 items-center gap-1.5">
                          {step.kind === "specialist_start" && step.target_name ? (
                            <span className="text-muted-foreground inline-flex shrink-0 items-center gap-1 text-[11px] font-medium">
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
                            <Loader2 className="text-primary size-3 shrink-0 animate-spin" />
                          )}
                        </div>

                        {step.at && (
                          <span className="text-muted-foreground/60 shrink-0 font-mono text-[10px]">
                            {formatStepTime(step.at)}
                          </span>
                        )}
                      </div>

                      {/* Bottom Line: Interactive Metadata Chip / Detail Trigger (`›`) */}
                      <div className="text-muted-foreground mt-1 flex flex-wrap items-center gap-1 text-[11px]">
                        <span className="text-muted-foreground/50 select-none">
                          └─
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            setSelectedIdx((cur) => (cur === idx ? null : idx))
                          }
                          className="group/chip inline-flex max-w-full cursor-pointer items-center gap-1.5 rounded text-left transition-colors focus-visible:outline-none"
                        >
                          <span
                            className={`inline-flex shrink-0 items-center gap-0.5 rounded border px-1.5 py-0.5 font-mono text-[10px] font-medium transition-colors ${
                              isExpanded
                                ? "border-primary/50 bg-primary/10 text-primary"
                                : "bg-background border-border/60 text-foreground/90 group-hover/chip:border-foreground/40 group-hover/chip:bg-muted"
                            }`}
                          >
                            {stripTrailingChevron(step.badge)}
                            <ChevronRight
                              className={`size-3 transition-transform duration-150 ${
                                isExpanded ? "rotate-90" : ""
                              }`}
                            />
                          </span>
                          {step.detail && (
                            <span className="text-muted-foreground/80 group-hover/chip:text-foreground truncate font-mono text-[10px] underline-offset-2 group-hover/chip:underline">
                              {step.detail}
                            </span>
                          )}
                        </button>
                      </div>

                      {/* Expanded Step Detail Card when `›` is clicked inside the Right Drawer */}
                      {isExpanded && activeStep && (
                        <div className="bg-muted/30 mt-2.5 space-y-3 rounded-lg border p-3.5 text-xs">
                          {/* Model Thinking / Reasoning */}
                          {activeStep.thinking && (
                            <div className="space-y-1.5">
                              <div className="text-muted-foreground flex items-center gap-1.5 text-[10px] font-semibold tracking-wider uppercase">
                                <Sparkles className="text-primary size-3" />
                                <span>Agent Thinking</span>
                              </div>
                              <div className="bg-background rounded-md border p-2.5 text-xs leading-relaxed">
                                <Markdown>{activeStep.thinking}</Markdown>
                              </div>
                            </div>
                          )}

                          {/* Init step overview */}
                          {activeStep.kind === "init" && (
                            <div className="space-y-2">
                              <p className="text-muted-foreground leading-relaxed">
                                <strong>Arya</strong> (Supervisor) analyzed the
                                request and coordinated{" "}
                                <strong>{specialistsCount}</strong> specialist
                                {specialistsCount === 1 ? "" : "s"} across{" "}
                                <strong>{checksCount}</strong> data check
                                {checksCount === 1 ? "" : "s"}.
                              </p>
                              {specialistsList.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 pt-1">
                                  {specialistsList.map((sp) => (
                                    <span
                                      key={sp}
                                      className="bg-background inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium"
                                    >
                                      <AgentBadge
                                        nickname={sp}
                                        size="xs"
                                        showTooltip={false}
                                      />
                                      {sp}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Specialist Delegation Task */}
                          {activeStep.kind === "specialist_start" && (
                            <div className="space-y-1.5">
                              <div className="text-muted-foreground flex items-center gap-1.5 text-[10px] font-semibold tracking-wider uppercase">
                                <Terminal className="size-3" />
                                <span>
                                  Task Delegated to{" "}
                                  {activeStep.target_name || "Specialist"}
                                </span>
                              </div>
                              <div className="bg-background rounded-md border p-3 leading-relaxed">
                                <Markdown>
                                  {activeStep.full_detail ||
                                    stripTrailingChevron(activeStep.detail)}
                                </Markdown>
                              </div>
                            </div>
                          )}

                          {/* Tool Execution Details */}
                          {activeStep.kind === "tool" && (
                            <div className="space-y-3">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="flex items-center gap-1.5">
                                  <Code2 className="text-muted-foreground size-3.5" />
                                  <code className="text-foreground font-mono text-[11px] font-semibold">
                                    {activeStep.tool_name ||
                                      stripTrailingChevron(activeStep.detail)}
                                  </code>
                                </div>
                                {activeStep.origin && (
                                  <OriginBadge
                                    origin={activeStep.origin}
                                    source={activeStep.source}
                                  />
                                )}
                              </div>

                              {activeStep.arguments &&
                                Object.keys(activeStep.arguments).length > 0 && (
                                  <div className="space-y-1">
                                    <p className="text-muted-foreground font-mono text-[10px] uppercase">
                                      Parameters
                                    </p>
                                    <div className="bg-background divide-y rounded-md border font-mono text-[11px]">
                                      {Object.entries(activeStep.arguments).map(
                                        ([k, v]) => (
                                          <div
                                            key={k}
                                            className="flex items-start justify-between gap-3 px-2.5 py-1.5"
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
                                        ),
                                      )}
                                    </div>
                                  </div>
                                )}

                              {activeStep.error ? (
                                <div className="space-y-1">
                                  <p className="text-destructive font-mono text-[10px] uppercase">
                                    Tool Error
                                  </p>
                                  <pre className="bg-destructive/10 text-destructive border-destructive/20 overflow-x-auto rounded-md border p-2.5 font-mono text-[11px] whitespace-pre-wrap">
                                    {activeStep.error}
                                  </pre>
                                </div>
                              ) : activeStep.result !== undefined ? (
                                <div className="space-y-1">
                                  <div className="text-muted-foreground flex items-center gap-1 font-mono text-[10px] uppercase">
                                    <Database className="size-3" />
                                    <span>Data Returned</span>
                                  </div>
                                  <pre className="bg-background text-foreground max-h-60 overflow-auto rounded-md border p-2.5 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
                                    {typeof activeStep.result === "string"
                                      ? activeStep.result
                                      : JSON.stringify(
                                          activeStep.result,
                                          null,
                                          2,
                                        )}
                                  </pre>
                                </div>
                              ) : null}
                            </div>
                          )}

                          {/* Specialist Finding / Final Summary */}
                          {(activeStep.kind === "specialist_done" ||
                            activeStep.kind === "summary" ||
                            (activeStep.kind !== "init" &&
                              activeStep.kind !== "specialist_start" &&
                              activeStep.kind !== "tool")) && (
                            <div className="space-y-1.5">
                              <div className="text-muted-foreground flex items-center gap-1.5 text-[10px] font-semibold tracking-wider uppercase">
                                <Sparkles className="size-3" />
                                <span>
                                  {activeStep.kind === "specialist_done"
                                    ? `${activeStep.agent_name} Finding`
                                    : "Synthesis"}
                                </span>
                              </div>
                              <div className="bg-background rounded-md border p-3 leading-relaxed">
                                <Markdown>
                                  {activeStep.full_detail ||
                                    stripTrailingChevron(activeStep.detail) ||
                                    activeStep.narrative}
                                </Markdown>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}

