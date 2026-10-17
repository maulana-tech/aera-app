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

function formatTrigger(trigger?: string | null): string {
  if (!trigger) return "Direct trigger recorded";
  // Strip raw ISO timestamps like ", 2026-10-11T03:30:20+00:00"
  return trigger.replace(/,\s*\d{4}-\d{2}-\d{2}T[\d:+-]+/, "").trim();
}

function cleanExecutiveSummary(raw?: string): string {
  if (!raw) return "";

  const lines = raw
    .replace(/\r/g, "")
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("---") && !l.startsWith("==="));

  const candidates: string[] = [];

  for (const line of lines) {
    let clean = line
      .replace(/^#+\s*/, "") // headings
      .replace(/^[*_]{1,3}|[*_]{1,3}$/g, "") // bold/italic edges
      .replace(/^[*-]\s+/, "") // list markers
      .replace(/^\d+\.\s+/, "") // numbered list
      .trim();

    // Strip status banners or metadata lines with prefixes
    if (
      /^(status|event|issue|disruption|summary|overview|what happened|the evidence|what i need|critical data missing|options to proceed|recommendation):/i.test(
        clean
      )
    ) {
      const parts = clean.split(/:\s*/);
      if (parts.length > 1 && parts[1].length > 25) {
        clean = parts.slice(1).join(": ").trim();
      } else {
        continue;
      }
    }

    // Skip short labels, uppercase shouts, or metadata strings
    if (
      clean.length < 30 ||
      (/^[A-Z0-9\s—–_-]+$/.test(clean) && clean.length < 50) ||
      /^(disruption analysis|insufficient data|live, fetched|what happened|the problem|summary)/i.test(
        clean
      )
    ) {
      continue;
    }

    // Skip technical timestamp lines
    if (/^\d{4}-\d{2}-\d{2}|fetched \d{4}/i.test(clean)) {
      continue;
    }

    // Strip internal agent conversational meta-openers
    clean = clean
      .replace(/^(Elsa has made the right call\.?\s*)/i, "")
      .replace(/^(Understood\.?\s*Elsa is correct[—–-]?\s*)/i, "")
      .replace(/^(The data needed to route this disruption is missing\.?\s*)/i, "")
      .replace(/^(Let me escalate what we know and what needs to be provided\.?\s*)/i, "")
      .trim();

    if (clean.length >= 30) {
      clean = clean.replace(/\*\*/g, "").replace(/\s+/g, " ");
      candidates.push(clean);
    }
  }

  if (candidates.length > 0) {
    return candidates[0];
  }

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
  let bodyCls = "text-foreground/85";

  if (isHeld && r.decision?.reason) {
    bodyContent = `Held: ${r.decision.reason}`;
    bodyCls = "text-amber-700 dark:text-amber-400 font-medium";
  } else if (r.error) {
    bodyContent = `Error: ${r.error}`;
    bodyCls = "text-destructive font-mono text-xs";
  } else if (r.decision?.recommendation) {
    bodyContent = cleanExecutiveSummary(r.decision.recommendation);
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
        isHeld && "border-amber-500/40 hover:border-amber-500/70",
        isRunning && "border-sky-500/40 hover:border-sky-500/70"
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
