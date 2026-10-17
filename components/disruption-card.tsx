import Link from "next/link";

import { idr, type Run } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";

function formatStartedAt(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-GB", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function extractCardSummary(raw: string): string {
  if (!raw) return "";

  // Split lines and drop empty / divider lines
  const lines = raw
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("---") && !l.startsWith("==="));

  for (const line of lines) {
    const clean = line
      .replace(/^#+\s*/, "") // remove markdown header marks
      .replace(/^\*\*|\*\*$/g, "") // remove enclosing bold marks
      .replace(/^Status:\s*/i, "")
      .replace(/^[*-]\s*/, "")
      .trim();

    // Skip generic headings like "DISRUPTION ANALYSIS" or "SUMMARY"
    if (/^(disruption analysis|summary|overview|what happened)/i.test(clean) && clean.length < 65) {
      continue;
    }

    if (clean.length > 25) {
      return clean.replace(/\*\*/g, "").replace(/\s+/g, " ");
    }
  }

  // Fallback: strip markdown formatting
  return raw
    .replace(/[#*_-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function DisruptionCard({ r }: { r: Run }) {
  const isHeld = r.status === "held";
  const isRunning = r.status === "running";
  const specialistsCount = Array.isArray(r.decision?.agents_called)
    ? r.decision.agents_called.length
    : 0;

  let bodyContent = "";
  let bodyCls = "text-muted-foreground";

  if (isHeld && r.decision?.reason) {
    bodyContent = `Held: ${r.decision.reason}`;
    bodyCls = "text-amber-700 dark:text-amber-400/90";
  } else if (r.error) {
    bodyContent = `Error: ${r.error}`;
    bodyCls = "text-destructive font-mono text-xs";
  } else if (r.decision?.recommendation) {
    bodyContent = extractCardSummary(r.decision.recommendation);
    bodyCls = "text-foreground/80";
  } else if (isRunning) {
    bodyContent = "Specialists actively analyzing SAP exposure and commitments...";
    bodyCls = "text-muted-foreground/70 italic";
  } else {
    bodyContent = "Handling logged. Awaiting agent assignment.";
    bodyCls = "text-muted-foreground/60 italic";
  }

  return (
    <Link
      href={`/disruptions/${r.id}`}
      className={cn(
        "group flex h-full w-full flex-col justify-between rounded-lg border border-border bg-card p-5 transition-colors hover:border-foreground/40",
        isHeld && "border-amber-500/40 hover:border-amber-500/70",
        isRunning && "border-sky-500/40 hover:border-sky-500/70"
      )}
    >
      <div>
        {/* Level 1: Category & Status (fixed h-5) */}
        <div className="flex h-5 items-center justify-between gap-3">
          <span className="truncate font-mono text-xs text-muted-foreground">{r.kind}</span>
          <div className="flex shrink-0 items-center gap-2 font-mono text-[11px]">
            {r.mode === "guided" && <StatusBadge status="guided" />}
            <StatusBadge status={r.status} />
          </div>
        </div>

        {/* Level 2: Headline (1 line truncate so triggers align horizontally) */}
        <h2 className="mt-2.5 truncate text-base font-semibold leading-snug tracking-tight text-foreground transition-colors group-hover:text-primary">
          {r.title}
        </h2>

        {/* Level 2 Sub: External trigger (1 line truncate) */}
        <p className="mt-1 truncate font-mono text-xs text-muted-foreground">
          {r.trigger || "-"}
        </p>

        {/* Level 3: Finding / Summary (Strictly 2 lines with consistent h-10) */}
        <p className={cn("mt-3 h-10 text-sm leading-relaxed line-clamp-2", bodyCls)}>
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
            <span className="text-sky-600 dark:text-sky-400">in progress</span>
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
