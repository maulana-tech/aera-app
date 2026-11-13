import { Dot, type Tone } from "@/components/dort";
import { cn } from "@/lib/utils";

/* A status is a pale-blue chip with one semantic dot; the word is always written too, so the
 * colour is never the only carrier. green done / ok · yellow waiting or money · red refused or
 * failed · blue moving · grey neutral. */
const TONES: Record<string, Tone> = {
  // done
  done: "ok", sent: "ok", ok: "ok", approved: "ok", delivered: "ok", attested: "ok", paid: "ok",
  active: "ok", vault: "ok",
  // moving
  running: "info", working: "info", submitted: "info", new: "info", contacted: "info", replied: "info",
  interested: "ok", won: "ok",
  // waiting on a person or on money
  held: "warn", pending: "warn", late: "warn", short: "warn", partial: "warn", awaiting_payment: "warn",
  pending_onchain: "warn", draft: "warn", simulated: "warn",
  // refused or broken
  failed: "bad", rejected: "bad", blocked: "bad", opted_out: "bad",
  // neutral
  guided: "neutral", skipped: "neutral", off: "neutral", cancelled: "neutral", refunded: "neutral",
  disabled: "neutral", lost: "neutral", no_reply: "neutral",
};

export function toneOf(status: string): Tone {
  return TONES[status] ?? "neutral";
}

/** A status marker. */
export function StatusBadge({ status, className, children }: {
  status: string; className?: string; children?: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "bg-raised text-text inline-flex h-6 w-fit shrink-0 items-center gap-1.5 rounded-sm px-2 text-[12px] whitespace-nowrap",
        className,
      )}
    >
      <Dot tone={toneOf(status)} />
      {children ?? status.replace(/_/g, " ")}
    </span>
  );
}

const ORIGINS: Record<string, { label: string; tone: Tone }> = {
  live:     { label: "live",     tone: "ok" },
  cached:   { label: "cached",   tone: "info" },
  derived:  { label: "derived",  tone: "neutral" },
  modelled: { label: "modelled", tone: "warn" },
  missing:  { label: "missing",  tone: "bad" },
};

/** The data-origin label. This is what separates a figure you may trust from one you may not. */
export function OriginBadge({ origin, source }: { origin: string; source?: string | null }) {
  const o = ORIGINS[origin];
  if (!o) return null;
  return (
    <span className="bg-raised text-text inline-flex h-6 w-fit shrink-0 items-center gap-1.5 rounded-sm px-2 font-mono text-[11px] whitespace-nowrap">
      <Dot tone={o.tone} />
      {o.label}
      {source ? ` · ${source}` : ""}
    </span>
  );
}
