import { api, idr, type AuditReport } from "@/app/lib";
import { AuditActions } from "./Actions";
import { Empty, Metric } from "@/components/shell";
import { OriginBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

const SEVERITY: Record<string, { label: string; rank: string }> = {
  critical: { label: "Critical", rank: "text-rose-700 dark:text-rose-400" },
  serious: { label: "Serious", rank: "text-amber-700 dark:text-amber-400" },
  warning: { label: "Warning", rank: "text-muted-foreground" },
  note: { label: "Note", rank: "text-muted-foreground" },
};

const num = (n: number) => n.toLocaleString("en-US");

export default async function AuditPage() {
  const a = await api<AuditReport>("audit");

  if (!a) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">The agent service is not responding</h1>
      </main>
    );
  }

  const c = a.coverage;
  const entities = Object.entries(a.origins ?? {});
  const bySeverity = ["critical", "serious", "warning", "note"]
    .map((s) => [s, a.findings.filter((f) => f.severity === s)] as const)
    .filter(([, list]) => list.length > 0);

  return (
    <main className="w-full px-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <h1 className="text-2xl font-semibold tracking-tight">Supply data audit</h1>
          <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
            Read across {num(c.rows ?? 0)} rows of master and transactional data. Every
            finding below names the rows it rests on, and none of it came from a model,
            so all of it can be recomputed from the same file.
          </p>
        </div>
        <AuditActions report={a} />
      </div>

      {a.findings.length === 0 ? (
        <div className="mt-8 max-w-3xl">
          <Empty
            what="Nothing to audit."
            why={a.note || "No readable data reached the audit."}
          />
        </div>
      ) : (
        <article className="mt-8 space-y-10">
          <section className="grid gap-x-10 gap-y-6 border-y py-6 sm:grid-cols-2 lg:grid-cols-4">
            {bySeverity.map(([sev, list]) => (
              <Metric
                key={sev}
                label={SEVERITY[sev].label}
                value={String(list.length)}
                note={
                  sev === "critical"
                    ? "act before the next planning cycle"
                    : sev === "serious"
                      ? "schedule this quarter"
                      : sev === "warning"
                        ? "fix when the record is next touched"
                        : "no action forced"
                }
              />
            ))}
          </section>

          <section>
            <h2 className="text-sm font-medium">What was read</h2>
            <dl className="mt-3 grid gap-x-10 gap-y-3 sm:grid-cols-3 lg:grid-cols-4">
              {[
                ["Materials", num(c.materials ?? 0)],
                ["Plants", num(c.plants ?? 0)],
                ["Suppliers", num(c.suppliers ?? 0)],
                ["Finished goods", num(c.finished_goods ?? 0)],
                ["Purchase orders", num(c.purchase_orders ?? 0)],
                ["Customer orders", num(c.customer_orders ?? 0)],
                ["Committed value", idr(c.committed_idr ?? 0)],
                ["Rows in total", num(c.rows ?? 0)],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-muted-foreground text-xs">{label}</dt>
                  <dd className="mt-0.5 font-mono text-sm tabular-nums">{value}</dd>
                </div>
              ))}
            </dl>
          </section>

          {bySeverity.map(([sev, list]) => (
            <section key={sev}>
              <h2 className={cn("text-sm font-medium", SEVERITY[sev].rank)}>
                {SEVERITY[sev].label} ({list.length})
              </h2>
              <ul className="mt-3 space-y-3">
                {list.map((f, i) => (
                  <li key={`${sev}-${i}`} className="rounded-lg border p-5">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
                      <h3 className="text-sm font-medium">{f.title}</h3>
                      {f.value_idr !== null && (
                        <span className="shrink-0 font-mono text-sm tabular-nums">
                          {idr(f.value_idr)}
                        </span>
                      )}
                    </div>
                    <p className="text-muted-foreground mt-1 font-mono text-[11px]">
                      {f.category}
                    </p>
                    <p className="text-muted-foreground mt-2.5 max-w-2xl text-sm leading-relaxed">
                      {f.detail}
                    </p>

                    {f.evidence.length > 0 && (
                      <div className="mt-3">
                        <p className="text-muted-foreground text-xs">
                          Evidence ({f.evidence.length})
                        </p>
                        <ul className="mt-1.5 flex flex-wrap gap-1.5">
                          {f.evidence.slice(0, 14).map((e) => (
                            <li
                              key={e}
                              className="text-muted-foreground rounded-md border px-1.5 py-0.5 font-mono text-[11px]"
                            >
                              {e}
                            </li>
                          ))}
                          {f.evidence.length > 14 && (
                            <li className="text-muted-foreground px-1.5 py-0.5 text-[11px]">
                              and {f.evidence.length - 14} more
                            </li>
                          )}
                        </ul>
                      </div>
                    )}

                    <p className="mt-4 border-t pt-3 text-sm leading-relaxed">
                      <span className="text-muted-foreground">Recommended. </span>
                      {f.action}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          ))}

          <section className="border-t pt-6">
            <h2 className="text-sm font-medium">Where the data came from</h2>
            <p className="text-muted-foreground mt-1.5 max-w-2xl text-sm leading-relaxed">
              An audit that does not say which of its inputs were modelled is an audit of
              nothing. The weakest input here is{" "}
              <span className="font-mono">{a.weakest_origin}</span>, and every conclusion
              above inherits that.
            </p>
            <ul className="mt-4 divide-y rounded-lg border">
              {entities.map(([entity, o]) => (
                <li
                  key={entity}
                  className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3"
                >
                  <span className="font-mono text-xs">{entity}</span>
                  <OriginBadge origin={o.origin} source={o.source} />
                </li>
              ))}
            </ul>
            <p className="text-muted-foreground mt-4 max-w-2xl text-xs leading-relaxed">
              {a.note}
            </p>
          </section>
        </article>
      )}
    </main>
  );
}
