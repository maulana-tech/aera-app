import { cn } from "@/lib/utils";

/* The few primitives of the blue system (see app/globals.css).
 *
 * Colour is a tiny semantic dot and nothing else: green ok, yellow amount / waiting, red bad,
 * blue external or moving, grey neutral. A chip is a pale-blue pill; only its dot is coloured. */

export type Tone = "ok" | "warn" | "bad" | "info" | "neutral" | "solid";

const DOT: Record<Tone, string> = {
  ok: "bg-ok",
  warn: "bg-warn",
  bad: "bg-bad",
  info: "bg-info",
  neutral: "bg-muted-foreground/50",
  solid: "bg-fg",
};

export function Dot({ tone = "neutral", className }: { tone?: Tone; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-1.5 shrink-0 rounded-full", DOT[tone], className)} />;
}

export function Chip({ tone, className, children, title }: {
  tone?: Tone; className?: string; children: React.ReactNode; title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "bg-raised text-text inline-flex h-6 max-w-full shrink-0 items-center gap-1.5 rounded-sm px-2 text-[12px] whitespace-nowrap",
        className,
      )}
    >
      {tone && <Dot tone={tone} />}
      {children}
    </span>
  );
}

/** A chip that sits directly on the blue canvas. */
export function CanvasChip({ tone, className, children, title }: {
  tone?: Tone; className?: string; children: React.ReactNode; title?: string;
}) {
  const dot: Record<Tone, string> = {
    ok: "bg-emerald-300", warn: "bg-amber-300", bad: "bg-rose-300", info: "bg-sky-200",
    neutral: "bg-white/50", solid: "bg-white",
  };
  return (
    <span
      title={title}
      className={cn(
        "inline-flex h-8 shrink-0 items-center gap-2 rounded-md border border-white/15 bg-white/10 px-3 text-[13px] text-white whitespace-nowrap",
        className,
      )}
    >
      {tone && <span aria-hidden className={cn("size-1.5 rounded-full", dot[tone])} />}
      {children}
    </span>
  );
}

/** The white floating card: radius 18, card gradient, hairline, soft shadow. */
export function Panel({ className, children, glow }: { className?: string; children: React.ReactNode; glow?: boolean }) {
  return (
    <div className={cn("bg-card-grad rounded-xl border shadow-soft", glow && "glow-top", className)}>
      {children}
    </div>
  );
}
