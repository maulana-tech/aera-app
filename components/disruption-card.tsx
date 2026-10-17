import Link from "next/link";
import ReactMarkdown from "react-markdown";

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

export function DisruptionCard({ r }: { r: Run }) {
  const isHeld = r.status === "held";
  const isRunning = r.status === "running";
  const specialistsCount = Array.isArray(r.decision?.agents_called)
    ? r.decision.agents_called.length
    : 0;

  return (
    <Link
      href={`/disruptions/${r.id}`}
      className={cn(
        "group flex flex-col justify-between rounded-lg border border-border bg-card p-5 transition-colors hover:border-foreground/40",
        isHeld && "border-amber-500/40 hover:border-amber-500/70",
        isRunning && "border-sky-500/40 hover:border-sky-500/70"
      )}
    >
      <div>
        {/* Level 1: Machine metadata & Status */}
        <div className="flex items-center justify-between gap-3">
          <span className="font-mono text-xs text-muted-foreground">{r.kind}</span>
          <div className="flex shrink-0 items-center gap-2 font-mono text-[11px]">
            {r.mode === "guided" && <StatusBadge status="guided" />}
            <StatusBadge status={r.status} />
          </div>
        </div>

        {/* Level 2: Primary incident headline */}
        <h2 className="mt-2 text-base font-semibold leading-snug tracking-tight text-foreground transition-colors group-hover:text-primary">
          {r.title}
        </h2>

        {/* Level 2 Sub: External trigger signal */}
        {r.trigger && (
          <p className="mt-1 font-mono text-xs text-muted-foreground line-clamp-1">
            {r.trigger}
          </p>
        )}

        {/* Level 3: Finding / Reason / Recommendation (Direct prose, no card-in-card) */}
        {isHeld && r.decision?.reason ? (
          <p className="mt-3 text-sm leading-relaxed text-amber-700 dark:text-amber-400 line-clamp-2">
            <span className="font-medium text-amber-800 dark:text-amber-300">Held: </span>
            {r.decision.reason}
          </p>
        ) : r.decision?.recommendation ? (
          <div className="mt-3 text-sm leading-relaxed text-foreground/80 line-clamp-2 [&_p]:inline [&_p]:m-0 [&_strong]:font-semibold [&_strong]:text-foreground">
            <ReactMarkdown skipHtml>{r.decision.recommendation}</ReactMarkdown>
          </div>
        ) : r.error ? (
          <p className="mt-3 font-mono text-xs text-destructive line-clamp-2">
            {r.error}
          </p>
        ) : null}
      </div>

      {/* Level 4: Execution Facts (Separated by hairline, no box) */}
      <div className="mt-4 flex items-center justify-between border-t border-border/50 pt-3 font-mono text-[11px] text-muted-foreground">
        <span>{formatStartedAt(r.started_at)}</span>
        <div className="flex items-center gap-2">
          {r.token_cost_idr > 0 && <span>cost {idr(r.token_cost_idr)}</span>}
          {specialistsCount > 0 && (
            <span>
              {specialistsCount} {specialistsCount === 1 ? "specialist" : "specialists"}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
