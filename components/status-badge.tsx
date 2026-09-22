import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const COLOURS: Record<string, string> = {
  done:     "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  sent:     "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  approved: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  running:  "border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-400",
  held:     "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  pending:  "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  guided:   "border-border bg-muted text-muted-foreground",
  failed:   "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-400",
  rejected: "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-400",
};

/** A status marker. The colour carries meaning, so the word is always written too. */
export function StatusBadge({ status, className, children }: {
  status: string; className?: string; children?: React.ReactNode;
}) {
  return (
    <Badge variant="outline" className={cn("font-mono text-[10px]", COLOURS[status], className)}>
      {children ?? status}
    </Badge>
  );
}

const ORIGINS: Record<string, { label: string; cls: string }> = {
  live:     { label: "live",     cls: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" },
  cached:   { label: "cached",   cls: "border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-400" },
  derived:  { label: "derived",  cls: "border-violet-500/40 bg-violet-500/10 text-violet-700 dark:text-violet-400" },
  modelled: { label: "modelled", cls: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400" },
  missing:  { label: "missing",  cls: "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-400" },
};

/** The data-origin label. This is what separates a figure you may trust from one you may not. */
export function OriginBadge({ origin, source }: { origin: string; source?: string | null }) {
  const o = ORIGINS[origin];
  if (!o) return null;
  return (
    <Badge variant="outline" className={cn("font-mono text-[10px] font-normal", o.cls)}>
      {o.label}
      {source ? ` · ${source}` : ""}
    </Badge>
  );
}
