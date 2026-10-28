import Link from "next/link";

import { idr, wib, type RunRow } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";
import { gist } from "@/lib/gist";
import { cn } from "@/lib/utils";

// Jakarta, like every other stamp SIGAP shows and writes.
const formatStartedAt = (iso: string) => wib(iso);

function formatTrigger(trigger?: string | null): string {
  if (!trigger) return "Direct trigger recorded";
  // Strip raw ISO timestamps like ", 2026-10-11T03:30:20+00:00"
  return trigger.replace(/,\s*\d{4}-\d{2}-\d{2}T[\d:+-]+/, "").trim();
}

/* The colour of a verdict. It carries no meaning on its own — every card
 * prints the verdict's own sentence beside it, which is where the figures are. */
const VERDICT_CLS: Record<string, string> = {
  needs_you_now: "border-rose-500/50 hover:border-rose-500/80",
  needs_you:     "border-amber-500/40 hover:border-amber-500/70",
  held:          "border-amber-500/40 hover:border-amber-500/70",
  failed:        "border-rose-500/40 hover:border-rose-500/70",
  owes_outcome:  "border-sky-500/30 hover:border-sky-500/60",
  running:       "border-sky-500/40 hover:border-sky-500/70",
};
const VERDICT_TEXT: Record<string, string> = {
  needs_you_now: "text-rose-700 dark:text-rose-400",
  needs_you:     "text-amber-700 dark:text-amber-400",
  held:          "text-amber-700 dark:text-amber-400",
  failed:        "text-rose-700 dark:text-rose-400",
  owes_outcome:  "text-sky-700 dark:text-sky-400",
  running:       "text-sky-700 dark:text-sky-400",
  handled:       "text-muted-foreground",
};

export function DisruptionCard({ r }: { r: RunRow }) {
  const v = r.verdict;
  const isHeld = r.status === "held";
  const isRunning = r.status === "running";
  const specialistsCount = Array.isArray(r.decision?.agents_called)
    ? r.decision.agents_called.length
    : 0;

  let bodyContent = "";
  let bodyCls = "text-foreground/85";

  if (isHeld && r.decision?.reason) {
    bodyContent = `Held: ${r.decision.reason}`;
    bodyCls = "text-amber-700 dark:text-amber-400 font-medium";
  } else if (r.error) {
    bodyContent = `Error: ${r.error}`;
    bodyCls = "text-destructive font-mono text-xs";
  } else if (r.decision?.recommendation) {
    bodyContent = gist(r.decision.recommendation);
    bodyCls = "text-foreground/80";
  } else if (isRunning) {
    bodyContent = "Specialists actively scanning SAP purchase orders, inventory buffers, and logistics exposure...";
    bodyCls = "text-muted-foreground/75 italic";
  } else {
    bodyContent = "Handling logged in decision queue. Awaiting agent assignment.";
    bodyCls = "text-muted-foreground/60 italic";
  }

  return (
    <Link
      href={`/disruptions/${r.id}`}
      className={cn(
        "group flex h-full w-full flex-col justify-between rounded-lg border border-border bg-card p-5 transition-colors hover:border-foreground/40",
        // The verdict decides the card's edge when there is one; the old
        // status colouring stays as the fallback so nothing goes unmarked.
        v ? VERDICT_CLS[v.state] : isHeld ? "border-amber-500/40 hover:border-amber-500/70"
          : isRunning ? "border-sky-500/40 hover:border-sky-500/70" : ""
      )}
    >
      <div>
        {/* Level 1: Category & Status (fixed h-5) */}
        <div className="flex h-5 items-center justify-between gap-3">
          <span className="truncate font-mono text-xs text-muted-foreground">
            {r.kind.replace(/_/g, " ")}
          </span>
          <div className="flex shrink-0 items-center gap-2 font-mono text-[11px]">
            {r.mode === "guided" && <StatusBadge status="guided" />}
            <StatusBadge status={r.status} />
          </div>
        </div>

        {/* Level 2: Headline (fixed h-6) */}
        <h2 className="mt-2.5 h-6 truncate text-base font-semibold leading-6 tracking-tight text-foreground transition-colors group-hover:text-primary">
          {r.title}
        </h2>

        {/* What this one still asks of a person, with the figures that earned
            it. Computed in engine/triage.py, never a model's opinion. */}
        {v && (
          <p className={cn("mt-1.5 h-4 truncate text-xs font-medium leading-4",
                           VERDICT_TEXT[v.state])}>
            {v.headline}
          </p>
        )}

        {/* Level 2 Sub: External trigger (fixed h-4) */}
        <p className="mt-1 h-4 truncate font-mono text-xs leading-4 text-muted-foreground">
          {formatTrigger(r.trigger)}
        </p>

        {/* Level 3: Finding / Summary (fixed h-11 line-clamp-2) */}
        <p className={cn("mt-3 h-11 text-sm leading-snug line-clamp-2", bodyCls)}>
          {bodyContent}
        </p>
      </div>

      {/* Level 4: Execution Facts Footer (pinned to bottom) */}
      <div className="mt-4 flex items-center justify-between border-t border-border/50 pt-3 font-mono text-[11px] text-muted-foreground">
        <span>{formatStartedAt(r.started_at)}</span>
        <div className="flex items-center gap-2">
          {r.token_cost_idr > 0 ? (
            <span>cost {idr(r.token_cost_idr)}</span>
          ) : isRunning ? (
            <span className="inline-flex items-center gap-1.5 text-sky-600 dark:text-sky-400">
              <span className="size-1.5 rounded-full bg-sky-500 animate-pulse" />
              in progress
            </span>
          ) : isHeld ? (
            <span className="text-amber-700 dark:text-amber-400">awaiting review</span>
          ) : (
            <span>no model cost</span>
          )}
          {specialistsCount > 0 && (
            <span>
              · {specialistsCount} {specialistsCount === 1 ? "specialist" : "specialists"}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
