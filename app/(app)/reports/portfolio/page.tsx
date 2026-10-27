import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { api, idr, wib } from "@/app/lib";
import { Markdown } from "@/components/markdown";
import { ReportFiles } from "@/components/report-files";
import { ReportSend } from "@/components/report-send";
import { Empty, PageHeader, Section } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

/* What obeying the rules cost on one disruption: the plan that was taken set
 * against the cheaper one a rule struck out. engine/simulate.py computes it;
 * engine/report.py reads it back off the record. */
type ComplianceCost = {
  run_id: string; title: string; idr: number;
  chosen: string[]; chosen_cost_idr: number;
  cheaper_but_blocked: string[]; cheaper_cost_idr: number;
  blocked_by: { id: string; label: string; reason: string }[];
  started_at: string;
};

type Portfolio = {
  title: string;
  markdown: string;
  summary_by: string | null;
  summary?: string | null;
  sheets?: { name: string; rows: number }[];
  compliance_costs?: ComplianceCost[];
  handlings?: {
    id: string; title: string; kind: string; status: string; mode: string;
    started_at: string; finished_at: string | null; steps: number; tools: number;
    actions: number; token_cost_idr: number | null;
  }[];
  actions?: {
    id: string; run_id: string; title: string; kind: string; status: string;
    autonomous: boolean; what: string; cost_idr: number | null; created_at: string;
    outcome: string | null; outcome_at: string | null; actual_idr: number | null;
    awaiting_outcome: boolean;
  }[];
  metrics: {
    period_label: string;
    runs_total: number;
    by_status: Record<string, number>;
    actions_total: number;
    actions_sent: number;
    actions_pending: number;
    predicted_idr_total: number;
    /** every recorded outcome */
    settled_actions: number;
    /** the ones with BOTH a prediction and a realized figure: the only ones a
     *  delta may be drawn from */
    settled_with_cost: number;
    settled_without_cost: number;
    by_outcome: Record<string, number>;
    awaiting_outcome: number;
    settled_predicted_idr?: number;
    settled_actual_idr?: number;
    settled_delta_idr: number;
    rules_cost_idr: number;
    rules_cost_cases: number;
    knowledge_base: {
      pack: string | null; total: number; verified: number;
      unverified: string[]; problems: string[];
    };
    decided_on_trusted: number;
    decided_with_untrusted: number;
  };
};

/* The periods on offer. A rollup with no period mixes this month's delta with
 * last year's and neither can be read out of the total again, so the period is
 * always on screen — "all" is a choice here, not the absence of one. */
const PERIODS: { label: string; query: Record<string, string> }[] = [
  { label: "Last 30 days", query: { days: "30" } },
  { label: "Last 90 days", query: { days: "90" } },
  { label: "All time", query: {} },
];

/* One tile. The number leads; the label and any note sit under it. */
function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-1 font-mono text-xl font-semibold tracking-tight tabular-nums">{value}</p>
      {note && <p className="text-muted-foreground mt-0.5 text-[11px]">{note}</p>}
    </div>
  );
}

const th = "text-muted-foreground px-4 py-2.5 text-left text-xs font-normal whitespace-nowrap";
const td = "px-4 py-2.5 align-top";

export default async function PortfolioReport({ searchParams }: {
  searchParams: Promise<{ days?: string; since?: string; until?: string }>;
}) {
  const sp = await searchParams;
  // Only what the service understands, and only when it is there: a stray
  // parameter must not become part of the period.
  const period: Record<string, string> = {};
  for (const k of ["days", "since", "until"] as const) if (sp[k]) period[k] = String(sp[k]);
  const query = new URLSearchParams(period).toString();

  const p = await api<Portfolio>(`portfolio${query ? `?${query}` : ""}`);
  const m = p?.metrics;
  const handlings = p?.handlings ?? [];
  const actions = p?.actions ?? [];
  const costs = p?.compliance_costs ?? [];

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <Link
        href="/reports"
        className="text-muted-foreground hover:text-foreground mb-3 inline-flex items-center gap-1.5 text-xs md:mb-5"
      >
        <ArrowLeft className="size-3" />
        Reports
      </Link>

      <PageHeader
        title="Operations report"
        lead="The handlings in the period rolled up: how much was handled, what it was predicted
              to cost, what obeying the rules cost, and — once outcomes are recorded — what it
              actually cost. The figures are computed from the record; a written summary is added
              only when the auxiliary model is available."
        aside={p && (
          <>
            <ReportFiles base="portfolio" sheets={p.sheets?.length} primary period={period} />
            <ReportSend base="portfolio" title="Operations report" period={period}
                        periodLabel={m?.period_label} />
          </>
        )}
      />

      <div className="mt-5 flex flex-wrap items-center gap-2">
        {PERIODS.map((x) => {
          const q = new URLSearchParams(x.query).toString();
          const active = q === query;
          return (
            <Link
              key={x.label}
              href={q ? `/reports/portfolio?${q}` : "/reports/portfolio"}
              className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                active ? "bg-primary text-primary-foreground border-primary"
                       : "hover:border-foreground/30"
              }`}
            >
              {x.label}
            </Link>
          );
        })}
        {m && (
          <span className="text-muted-foreground ml-1 font-mono text-[11px]">
            {m.period_label}
          </span>
        )}
      </div>

      {!p || !m ? (
        <p className="text-muted-foreground mt-6 rounded-lg border border-dashed p-6 text-sm">
          The report could not be assembled. The agent service may be unavailable, or the period
          may not be a date it can read.
        </p>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile
              label="Handlings"
              value={String(m.runs_total)}
              note={Object.entries(m.by_status).map(([k, v]) => `${v} ${k}`).join(" · ") || "none"}
            />
            <Tile
              label="Actions raised"
              value={String(m.actions_total)}
              note={`${m.actions_sent} sent · ${m.actions_pending} awaiting approval`}
            />
            <Tile
              label="Committed (predicted)"
              value={idr(m.predicted_idr_total)}
              note={`${m.decided_on_trusted} decided on trusted evidence · ${m.decided_with_untrusted} with a caveat`}
            />
            {/* The delta is drawn from the comparable actions alone, and the
                count beside it says so. It used to count every recorded
                outcome, which made a delta of nothing — no figures at all —
                read as a book that came in exactly on prediction. */}
            <Tile
              label="Realized vs predicted"
              value={m.settled_with_cost ? (m.settled_delta_idr <= 0 ? "" : "+") + idr(m.settled_delta_idr) : "-"}
              note={m.settled_with_cost
                ? `${m.settled_with_cost} comparable action(s)`
                : m.settled_actions
                  ? `${m.settled_actions} outcome(s) recorded, none with a figure`
                  : "no outcomes recorded yet"}
            />
          </div>

          {p.summary && (
            <Section title="Summary" note="Phrased by the auxiliary model from the figures above. It was given no number to invent.">
              <div className="rounded-lg border p-5">
                <Markdown>{p.summary}</Markdown>
              </div>
            </Section>
          )}

          {/* What the rules cost comes high up: it is the figure that turns a
              veto from an assertion into a priced decision. */}
          <Section
            title="What the rules cost"
            note="Where a rule struck out a cheaper plan, the difference between the plan that was taken and that one. The price of the rule, not an overrun."
          >
            {costs.length === 0 ? (
              <Empty
                what="Nothing in this period."
                why="No disruption had a cheaper plan struck out by a rule, so obeying them cost nothing that can be measured."
              />
            ) : (
              <>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <Tile label="Cost of compliance" value={idr(m.rules_cost_idr)}
                        note={`across ${m.rules_cost_cases} disruption(s)`} />
                  <Tile label="Chosen plans"
                        value={idr(costs.reduce((a, c) => a + (c.chosen_cost_idr ?? 0), 0))}
                        note="what the compliant plans were predicted to cost" />
                  <Tile label="Cheaper, struck out"
                        value={idr(costs.reduce((a, c) => a + (c.cheaper_cost_idr ?? 0), 0))}
                        note="what they would have cost if no rule applied" />
                </div>
                <div className="mt-3 overflow-x-auto rounded-lg border">
                  <table className="w-full min-w-[820px] text-sm">
                    <thead className="bg-muted/40 border-b">
                      <tr>
                        <th className={th}>Handling</th>
                        <th className={th}>Chosen</th>
                        <th className={th}>Cheaper, struck out</th>
                        <th className={`${th} text-right`}>Cost of the rule</th>
                        <th className={th}>Struck out by</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {costs.map((c) => (
                        <tr key={c.run_id} className="hover:bg-muted/30">
                          <td className={td}>
                            <Link href={`/reports/${c.run_id}`} className="font-medium hover:underline">
                              {c.title}
                            </Link>
                            <span className="text-muted-foreground block font-mono text-[11px]">
                              {wib(c.started_at, { time: false })}
                            </span>
                          </td>
                          <td className={`${td} font-mono text-xs`}>
                            {(c.chosen ?? []).join(", ") || "-"}
                            <span className="text-muted-foreground block tabular-nums">
                              {idr(c.chosen_cost_idr ?? 0)}
                            </span>
                          </td>
                          <td className={`${td} font-mono text-xs`}>
                            {(c.cheaper_but_blocked ?? []).join(", ") || "-"}
                            <span className="text-muted-foreground block tabular-nums">
                              {idr(c.cheaper_cost_idr ?? 0)}
                            </span>
                          </td>
                          <td className={`${td} text-right font-mono tabular-nums whitespace-nowrap`}>
                            {idr(c.idr)}
                          </td>
                          <td className={`${td} text-xs leading-relaxed`}>
                            {(c.blocked_by ?? []).map((b) => (
                              <span key={b.id} className="block">
                                <span className="font-mono">{b.id}</span> {b.reason}
                              </span>
                            ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </Section>

          <Section title={`Handlings (${handlings.length})`}>
            {handlings.length === 0 ? (
              <Empty what="No handling in this period." why="Nothing was handled between these dates, so there is nothing to roll up." />
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full min-w-[720px] text-sm">
                  <thead className="bg-muted/40 border-b">
                    <tr>
                      <th className={th}>Handling</th>
                      <th className={th}>Kind</th>
                      <th className={th}>Status</th>
                      <th className={th}>Started</th>
                      <th className={`${th} text-right`}>Steps</th>
                      <th className={`${th} text-right`}>Actions</th>
                      <th className={`${th} text-right`}>Model time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {handlings.map((h) => (
                      <tr key={h.id} className="hover:bg-muted/30">
                        <td className={td}>
                          <Link href={`/reports/${h.id}`} className="font-medium hover:underline">{h.title}</Link>
                        </td>
                        <td className={`${td} text-muted-foreground font-mono text-xs`}>{h.kind}</td>
                        <td className={td}><StatusBadge status={h.status} /></td>
                        <td className={`${td} text-muted-foreground font-mono text-xs whitespace-nowrap`}>{wib(h.started_at)}</td>
                        <td className={`${td} text-right font-mono tabular-nums`}>{h.steps}</td>
                        <td className={`${td} text-right font-mono tabular-nums`}>{h.actions}</td>
                        <td className={`${td} text-right font-mono tabular-nums whitespace-nowrap`}>
                          {h.token_cost_idr ? idr(h.token_cost_idr) : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          <Section
            title={`Actions (${actions.length})`}
            note={m.awaiting_outcome
              ? `${m.awaiting_outcome} of these went out and still owe an outcome. Until those are recorded the realized side below is incomplete.`
              : undefined}
          >
            {actions.length === 0 ? (
              <Empty what="No action has been raised." why="No handling has reached the point of proposing a change." />
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full min-w-[920px] text-sm">
                  <thead className="bg-muted/40 border-b">
                    <tr>
                      <th className={th}>Action</th>
                      <th className={th}>What it does</th>
                      <th className={th}>Handling</th>
                      <th className={`${th} text-right`}>Value</th>
                      <th className={th}>Status</th>
                      <th className={th}>What happened</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {actions.map((a) => (
                      <tr key={a.id} className="hover:bg-muted/30">
                        <td className={`${td} font-mono text-xs whitespace-nowrap`}>
                          {a.kind}
                          {a.autonomous && <span className="text-muted-foreground block font-sans text-[11px]">own authority</span>}
                        </td>
                        <td className={`${td} text-xs leading-relaxed`}>
                          <span className="line-clamp-3">{a.what || "-"}</span>
                        </td>
                        <td className={`${td} text-xs`}>
                          <Link href={`/reports/${a.run_id}`} className="text-muted-foreground hover:text-foreground hover:underline">{a.title}</Link>
                        </td>
                        <td className={`${td} text-right font-mono tabular-nums whitespace-nowrap`}>
                          {typeof a.cost_idr === "number" ? idr(a.cost_idr) : "-"}
                        </td>
                        <td className={td}><StatusBadge status={a.status} /></td>
                        <td className={`${td} whitespace-nowrap`}>
                          {a.outcome ? (
                            <>
                              <StatusBadge status={a.outcome} />
                              <span className="text-muted-foreground mt-0.5 block font-mono text-[11px] tabular-nums">
                                {typeof a.actual_idr === "number" ? idr(a.actual_idr) : "no figure"}
                              </span>
                            </>
                          ) : a.awaiting_outcome ? (
                            <Link href={`/disruptions/${a.run_id}`}
                                  className="text-amber-700 text-xs hover:underline dark:text-amber-400">
                              owes an outcome
                            </Link>
                          ) : (
                            <span className="text-muted-foreground text-xs">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          <Section title="Realized vs predicted">
            {m.settled_with_cost ? (
              <>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <Tile label="Predicted" value={idr(m.settled_predicted_idr ?? 0)} note={`${m.settled_with_cost} comparable action(s)`} />
                  <Tile label="Actual" value={idr(m.settled_actual_idr ?? 0)} />
                  <Tile label="Delta" value={(m.settled_delta_idr > 0 ? "+" : "") + idr(m.settled_delta_idr)}
                        note={m.settled_delta_idr < 0 ? "came in under prediction" : m.settled_delta_idr > 0 ? "came in over prediction" : "exactly at prediction"} />
                </div>
                {(m.settled_without_cost > 0 || m.awaiting_outcome > 0) && (
                  <p className="text-muted-foreground mt-3 max-w-2xl rounded-lg border border-dashed p-4 text-xs leading-relaxed">
                    Drawn from {m.settled_with_cost} action(s) that have both a prediction and a
                    realized figure.
                    {m.settled_without_cost > 0 && ` A further ${m.settled_without_cost} recorded outcome(s) carry no figure and are not in this comparison.`}
                    {m.awaiting_outcome > 0 && ` ${m.awaiting_outcome} action(s) that went out still owe an outcome.`}
                  </p>
                )}
              </>
            ) : (
              <p className="text-muted-foreground rounded-lg border border-dashed p-5 text-sm leading-relaxed">
                {m.settled_actions
                  ? `${m.settled_actions} outcome(s) are recorded, but none carries a realized figure, so
                     no comparison with the prediction can be made. A blank figure is "not known",
                     never zero.`
                  : "No action has a recorded outcome in this period, so realized cost cannot be stated. The predicted figures stand alone."}
                {m.awaiting_outcome > 0 && ` ${m.awaiting_outcome} action(s) that went out still owe an outcome.`}
              </p>
            )}
          </Section>

          {/* The rules the decisions rested on, and how much of that is still
              assumption. Every figure on this page carries its origin; the
              knowledge base behind the rulings deserves the same. */}
          <Section
            title="The rules behind these decisions"
            note="A rule counts as verified only where the pack states it, cites the document it was read from, and a person has checked it there."
          >
            <div className="max-w-3xl rounded-lg border p-5">
              <p className="font-mono text-sm tabular-nums">
                {m.knowledge_base.verified} of {m.knowledge_base.total} rules verified
              </p>
              {m.knowledge_base.unverified.length > 0 && (
                <p className="text-muted-foreground mt-2 text-xs leading-relaxed">
                  Assumptions, applied and labelled as such:{" "}
                  <span className="font-mono">{m.knowledge_base.unverified.join(", ")}</span>
                </p>
              )}
              <p className="text-muted-foreground mt-2 text-xs leading-relaxed">
                {m.knowledge_base.pack
                  ? `Rule pack: ${m.knowledge_base.pack}`
                  : "No rule pack is installed, so every rule is a built-in assumption or the company's own profile figure."}
              </p>
              {m.knowledge_base.problems.length > 0 && (
                <ul className="mt-3 space-y-1.5 border-t pt-3">
                  {m.knowledge_base.problems.map((x) => (
                    <li key={x} className="text-xs leading-relaxed text-amber-700 dark:text-amber-400">{x}</li>
                  ))}
                </ul>
              )}
            </div>
          </Section>
        </>
      )}
    </main>
  );
}
