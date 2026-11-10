import { CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";

export type Step = { done: boolean; title: string; detail: string; href?: string; cta?: string };

/* What is left before this business runs on its own, in order. Hidden once
 * every step is done. */
export function GettingStarted({ steps }: { steps: Step[] }) {
  const left = steps.filter((s) => !s.done).length;
  if (!left) return null;
  return (
    <section className="mt-6 rounded-lg border p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">Getting started</h2>
        <span className="text-muted-foreground font-mono text-xs">{steps.length - left}/{steps.length} done</span>
      </div>
      <ol className="mt-3 space-y-2">
        {steps.map((s) => (
          <li key={s.title} className="flex items-start gap-2.5">
            {s.done
              ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
              : <Circle className="text-muted-foreground mt-0.5 size-4 shrink-0" />}
            <div className="min-w-0 flex-1">
              <p className={`text-sm ${s.done ? "text-muted-foreground line-through" : "font-medium"}`}>{s.title}</p>
              {!s.done && <p className="text-muted-foreground text-xs leading-relaxed">{s.detail}</p>}
            </div>
            {!s.done && s.href && (
              <Link href={s.href} className="shrink-0 text-xs underline underline-offset-2">{s.cta ?? "Open"}</Link>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
