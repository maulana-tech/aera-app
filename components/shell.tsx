import { cn } from "@/lib/utils";

/* Page furniture for the operations console.
 *
 * Decisions encoded here so they cannot drift back:
 *   Radius   one scale. rounded-lg for containers, rounded-md inside them,
 *            rounded-full only for the agent badge and pills.
 *   Type     sans for prose, mono for anything a machine produced: ids,
 *            quantities, dates, money, tool names.
 *   Labels   no eyebrow above page titles. The breadcrumb already says where
 *            you are, and a second label on every page is the templated
 *            rhythm that makes generated interfaces look generated.
 *   Chrome   hairlines and spacing before boxes. A card has to earn its border
 *            by grouping things that genuinely belong together.
 */

export function PageHeader({
  title, lead, aside,
}: { title: string; lead?: string; aside?: React.ReactNode }) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3 border-b pb-4 md:gap-x-8 md:gap-y-4 md:pb-6">
      <div className="min-w-0 max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight md:text-2xl">{title}</h1>
        {lead && (
          <p className="text-muted-foreground mt-1.5 text-xs leading-relaxed md:mt-2 md:text-sm">{lead}</p>
        )}
      </div>
      {aside && <div className="flex shrink-0 flex-wrap items-center gap-2">{aside}</div>}
    </header>
  );
}

export function Section({
  title, note, action, className, children,
}: {
  title?: string;
  note?: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={cn("mt-10 first:mt-8", className)}>
      {(title || action) && (
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-medium">{title}</h2>}
            {note && (
              <p className="text-muted-foreground mt-1 max-w-3xl text-xs leading-relaxed">
                {note}
              </p>
            )}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

/** A right-hand rail of facts. Label left, value right, hairline between. */
export function Rail({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border">
      {title && (
        <p className="text-muted-foreground border-b px-4 py-2.5 text-xs font-medium">
          {title}
        </p>
      )}
      <dl className="divide-y">{children}</dl>
    </div>
  );
}

export function Fact({
  label, value, mono = true, tone,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
  tone?: "plain" | "quiet" | "warn";
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 px-4 py-2.5">
      <dt className="text-muted-foreground shrink-0 text-xs">{label}</dt>
      <dd
        className={cn(
          "min-w-0 truncate text-right text-xs",
          mono && "font-mono tabular-nums",
          tone === "quiet" && "text-muted-foreground",
          tone === "warn" && "text-amber-700 dark:text-amber-400",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

/** An empty state that says why it is empty and what would fill it.
 *  The product's whole claim is that it does not pretend, so neither does this. */
export function Empty({ what, why, fix }: { what: string; why: string; fix?: string }) {
  return (
    <div className="rounded-lg border border-dashed px-5 py-8">
      <p className="text-sm font-medium">{what}</p>
      <p className="text-muted-foreground mt-1.5 max-w-xl text-sm leading-relaxed">{why}</p>
      {fix && (
        <p className="text-muted-foreground mt-3 max-w-xl font-mono text-xs leading-relaxed">
          {fix}
        </p>
      )}
    </div>
  );
}

/** A number that carries weight. Named Metric, not Figure, because charts.tsx
 *  already owns Figure as the chart wrapper. */
export function Metric({
  value, label, note, className,
}: { value: string; label: string; note?: string; className?: string }) {
  return (
    <div className={className}>
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-1.5 font-mono text-xl font-semibold tabular-nums">{value}</p>
      {note && <p className="text-muted-foreground mt-1 text-xs leading-relaxed">{note}</p>}
    </div>
  );
}

/** Tool list for an agent's rail. Names are machine identifiers so they stay
 *  mono and wrap rather than truncate; a clipped tool name is useless. */
export function ToolList({
  tools,
}: { tools: { name: string; installed: boolean; description: string | null }[] }) {
  return (
    <ul className="divide-y">
      {tools.map((t) => (
        <li key={t.name} className="px-4 py-3">
          <p
            className={cn(
              "break-all font-mono text-[11px]",
              !t.installed && "text-muted-foreground/50",
            )}
          >
            {t.name}
            {!t.installed && <span className="ml-2 italic">not written</span>}
          </p>
          {t.description && (
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
              {t.description}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
