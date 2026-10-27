import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { api, idr, type Summary, type View } from "@/app/lib";
import { Bars, Figure, type Datum } from "@/components/charts";
import { Metric, PageHeader, Section } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

/** Rupiah short enough to sit at the end of a bar. */
const short = (n: number) =>
  n >= 1e9
    ? `${(n / 1e9).toLocaleString("en-US", { maximumFractionDigits: 2 })}bn`
    : n >= 1e6
      ? `${(n / 1e6).toLocaleString("en-US", { maximumFractionDigits: 0 })}m`
      : n.toLocaleString("en-US");

const num = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 1 });

/* A bar per row stops being a chart somewhere around a dozen rows and becomes a
 * wall. The dashboard shows the sharp end and says how much it is not showing;
 * the agent's own page carries the full table, which handles sixty rows fine. */
const SHOWN = 8;

const andMore = (total: number, where: string) =>
  total > SHOWN
    ? `Showing the ${SHOWN} that matter most. ${total - SHOWN} more are on ${where}.`
    : undefined;

/* The periods on offer, the same three the operations report carries, so a
 * figure on this page and a figure in that report mean the same thing. */
const PERIODS: { label: string; query: Record<string, string> }[] = [
  { label: "Last 30 days", query: { days: "30" } },
  { label: "Last 90 days", query: { days: "90" } },
  { label: "All time", query: {} },
];

export default async function Dashboard({ searchParams }: {
  searchParams: Promise<{ days?: string; since?: string; until?: string }>;
}) {
  const sp = await searchParams;
  const period: Record<string, string> = {};
  for (const k of ["days", "since", "until"] as const) if (sp[k]) period[k] = String(sp[k]);
  const query = new URLSearchParams(period).toString();

  const [s, stock, sourcing, logistics, costing] = await Promise.all([
    api<Summary>(`summary${query ? `?${query}` : ""}`),
    api<View>("data/inventory"),
    api<View>("data/sourcing"),
    api<View>("data/logistics"),
    api<View>("data/simulation"),
  ]);

  if (!s) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">The agent service is not responding</h1>
      </main>
    );
  }

  const awaiting = s.actions.pending ?? 0;
  const running = s.runs.running ?? 0;
  const held = s.runs.held ?? 0;

  // ---- stock cover: how many days until each material runs out ----------
  const stockAll = (stock?.rows ?? []).filter((r) => r.days_left != null);
  const stockRows = stockAll.slice(0, SHOWN);
  const stockData: Datum[] = stockRows.map((r) => ({
    label: String(r.description || r.material),
    sub: `${r.material} · ${r.plant}`,
    value: Number(r.days_left),
    display: `${num(Number(r.days_left))}d`,
    hatched: Number(r.days_left) < 14,
    tag: r.depleted_on ? `out ${r.depleted_on}` : undefined,
    title: `${r.material} at ${r.plant}, ${num(Number(r.qty))} ${r.unit ?? ""} on hand, `
      + `${num(Number(r.daily_consumption))}/day`,
  }));

  // ---- supply options: extra cost of each ------------------------------
  const sourcingData: Datum[] = (sourcing?.rows ?? []).map((r) => ({
    label: String(r.label),
    sub: `${r.supplier ?? "-"} ${r.origin_country ?? ""}`,
    value: Number(r.cost_idr ?? 0),
    display: `Rp ${short(Number(r.cost_idr ?? 0))}`,
    hatched: r.allowed === false,
    tag: r.allowed === false ? "blocked by rules" : r.arrives ? `arrives ${r.arrives}` : undefined,
    title: String(r.reason || `Arrives ${r.arrives}, TKDN becomes ${r.tkdn ?? "-"}`),
  }));

  // ---- delayed shipments ------------------------------------------------
  const lateAll = (logistics?.rows ?? [])
    .filter((r) => r.status !== "planned" && Number(r.delay_days ?? 0) > 0)
    .sort((a, b) => Number(b.delay_days) - Number(a.delay_days));
  const lateRows = lateAll.slice(0, SHOWN);
  const lateData: Datum[] = lateRows.map((r) => ({
    label: String(r.reference),
    sub: `${r.material} ${r.port ?? ""}`,
    value: Number(r.delay_days),
    display: `${r.delay_days}d`,
    tag: `now ${r.arrival_revised}`,
    title: `Booked ${r.arrival_original}, now ${r.arrival_revised}, status ${r.status}`,
  }));

  // ---- costing: what each combination would cost ------------------------
  const costingData: Datum[] = (costing?.rows ?? []).map((r) => ({
    label: String(r.combination),
    value: Number(r.cost_idr ?? 0),
    display: `Rp ${short(Number(r.cost_idr ?? 0))}`,
    hatched: r.safe === false,
    tag: r.chosen ? "▸ chosen" : r.safe === false ? "leaves a gap" : undefined,
    title: `${r.safe ? "Bridges the supply gap" : "Still runs out of stock"}`
      + `${r.depleted_on ? `, out ${r.depleted_on}` : ""}`
      + `${r.tkdn != null ? ` · TKDN ${r.tkdn}` : ""}`,
  }));

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Overview"
        lead="What the agents have handled, what is waiting on a person, and where every
              figure on this page came from."
      />

      {/* The same line the decision queue leads with, computed the same way
          (engine/triage.py). Two screens that disagree about whether anything
          needs you are worse than one screen. It is deliberately NOT filtered
          by the period below: an approval that is late today is late whatever
          month the reader is looking at. */}
      {s.board && (
        <p className={`mt-4 text-sm ${
          s.board.clear ? "text-emerald-700 dark:text-emerald-400"
                        : s.board.needs_a_person ? "text-amber-700 dark:text-amber-400"
                        : "text-muted-foreground"}`}>
          {s.board.line}
        </p>
      )}

      {/* Right now. Three figures that a date range must not touch: what is
          owed today, and how much of what the rulings rest on anybody has
          actually checked. */}
      <section className="mt-6 grid gap-x-10 gap-y-6 border-b pb-8 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Needs a person"
          value={String(s.board?.needs_a_person ?? 0)}
          note={s.board?.needs_a_person
            ? `worth ${idr(s.board.value_idr)} · right now`
            : "nothing is waiting · right now"}
        />
        <Metric
          label="Outcomes owed"
          value={String(s.outcomes_owed ?? 0)}
          note={s.outcomes_owed
            ? `oldest ${s.oldest_owed_days ?? 0} day(s) — until these are recorded the realized side is incomplete`
            : "every action that went out has been closed"}
        />
        {/* The rulings rest on these. A page that shows a TKDN verdict without
            saying how much of the pack anybody has checked is half a figure. */}
        <Metric
          label="Rules verified"
          value={s.knowledge_base
            ? `${s.knowledge_base.verified} of ${s.knowledge_base.total}`
            : "-"}
          note={!s.knowledge_base ? "unknown"
            : !s.knowledge_base.pack ? "no rule pack installed; every rule is an assumption"
            : s.knowledge_base.unverified.length
              ? `${s.knowledge_base.unverified.length} still an assumption`
              : "every rule checked against its source"}
        />
        <Metric
          label="Being handled"
          value={String(running)}
          note={held ? `${held} held` : "none in flight"}
        />
      </section>

      {/* Over a period, so the figures can be compared month to month. The
          same three windows the operations report offers. */}
      <div className="mt-8 flex flex-wrap items-center gap-2">
        <h2 className="mr-1 text-sm font-medium">Over a period</h2>
        {PERIODS.map((x) => {
          const q = new URLSearchParams(x.query).toString();
          const active = q === query;
          return (
            <Link
              key={x.label}
              href={q ? `/dashboard?${q}` : "/dashboard"}
              className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                active ? "bg-primary text-primary-foreground border-primary"
                       : "hover:border-foreground/30"}`}
            >
              {x.label}
            </Link>
          );
        })}
        <span className="text-muted-foreground ml-1 font-mono text-[11px]">
          {s.period_label ?? "every handling on record"}
        </span>
      </div>

      <section className="mt-4 grid gap-x-10 gap-y-6 border-b pb-8 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Handled"
          value={String(Object.values(s.runs).reduce((a, n) => a + n, 0))}
          note={`disruptions worked in this period${held ? `, ${held} held` : ""}`}
        />
        <Metric
          label="Approved"
          value={idr(s.approved_value_idr)}
          note="value of actions that cleared approval"
        />
        <Metric
          label="Handled alone"
          value={String(s.autonomous_actions ?? 0)}
          note="carried out on the system's own authority, under the limit"
        />
        <Metric
          label="Model cost"
          value={idr(s.model_cost_idr)}
          note="what the agents spent thinking"
        />

        {/* What obeying the rules cost. engine/simulate.py prices every option
            including the ones Kira struck out, which is the only way to answer
            whether there was a cheaper way and what stopped us taking it. It
            used to live only inside a report somebody had to go and open. */}
        <Metric
          label="What the rules cost"
          value={s.rules_cost_cases ? idr(s.rules_cost_idr ?? 0) : "-"}
          note={s.rules_cost_cases
            ? `a rule struck out a cheaper plan on ${s.rules_cost_cases} disruption(s)`
            : "no cheaper plan has been struck out by a rule"}
        />
        <Metric
          label="Committed"
          value={idr(s.pending_value_idr + s.approved_value_idr)}
          note={awaiting ? `${awaiting} still awaiting a decision` : "nothing awaiting a decision"}
        />
      </section>

      {(!s.model_ready || !s.sap_ready) && (
        <div className="mt-8 rounded-lg border p-4">
          <p className="text-sm font-medium">Not fully connected</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {!s.model_ready && <StatusBadge status="held">AWS_REGION not set</StatusBadge>}
            {!s.sap_ready && <StatusBadge status="held">SAP_API_KEY not set</StatusBadge>}
          </div>
          <p className="text-muted-foreground mt-2 text-xs leading-relaxed">
            While both are empty the system makes no decisions at all, and does not
            pretend to. The charts below still label where every figure came from.
          </p>
        </div>
      )}

      <div className="mt-10 grid gap-4 xl:grid-cols-2">
        <Figure
          title="Remaining stock cover"
          blurb="Days until each material runs out at the current consumption rate. Hatched bars are already below the threshold."
          origin={stock?.origin}
          source={stock?.source}
          note={andMore(stockAll.length, "Iris's page")}
          empty={stockData.length ? undefined : "No stock data to work from yet."}
          table={{
            head: ["Material", "Plant", "Days left", "Depleted"],
            rows: stockRows.map((r) => [
              `${r.material} ${r.description}`, r.plant,
              num(Number(r.days_left)), r.depleted_on ?? "-",
            ].map(String)),
          }}
        >
          <Bars data={stockData} threshold={14} thresholdLabel="14-day safety threshold" />
        </Figure>

        <Figure
          title="Cost per supply option"
          blurb="Extra cost of each replacement option. Hatched bars were blocked by Kira for breaching TKDN or LARTAS. Price cannot overturn that."
          origin={sourcing?.origin}
          source={sourcing?.source}
          empty={sourcingData.length ? undefined : "No replacement options yet."}
          table={{
            head: ["Option", "Arrives", "Cost", "Clears rules"],
            rows: (sourcing?.rows ?? []).map((r) => [
              r.label, r.arrives ?? "-", idr(Number(r.cost_idr ?? 0)),
              r.allowed === false ? "no" : "yes",
            ].map(String)),
          }}
        >
          <Bars data={sourcingData} />
        </Figure>

        <Figure
          title="Delayed shipments"
          blurb="Days between the delivery date that was promised and the one that now applies."
          origin={logistics?.origin}
          source={logistics?.source}
          note={andMore(lateAll.length, "Milo's page")}
          empty={lateData.length ? undefined : "Nothing is running late."}
          table={{
            head: ["Reference", "Booked", "Now", "Delay"],
            rows: lateRows.map((r) => [
              r.reference, r.arrival_original, r.arrival_revised, `${r.delay_days}d`,
            ].map(String)),
          }}
        >
          <Bars data={lateData} />
        </Figure>

        <Figure
          title="Cost per handling combination"
          blurb="Straight from Tara's calculator. Hatched bars still run out of stock, so being cheap doesn't help."
          origin={costing?.origin}
          source={costing?.source}
          note={costing?.note}
          empty={
            costingData.length
              ? undefined
              : costing?.note || "The calculator refused to compute. Its inputs are not trustworthy."
          }
          table={{
            head: ["Combination", "Cost", "Bridges gap", "Depleted"],
            rows: (costing?.rows ?? []).map((r) => [
              r.combination, idr(Number(r.cost_idr ?? 0)),
              r.safe ? "yes" : "no", r.depleted_on ?? "-",
            ].map(String)),
          }}
        >
          <Bars data={costingData} />
        </Figure>
      </div>

      <div className="mt-2 grid gap-6 lg:grid-cols-2">
        <Section
          title="Most critical stock"
          action={
            <Link
              href="/agents/inventory"
              className="text-muted-foreground hover:text-foreground text-xs"
            >
              Iris has the full list
            </Link>
          }
        >
          {s.critical_stock.length === 0 ? (
            <p className="text-muted-foreground rounded-lg border border-dashed p-5 text-sm">
              Nothing is under 14 days of cover.
            </p>
          ) : (
            <ul className="divide-y rounded-lg border">
              {s.critical_stock.map((x) => (
                <li key={`${x.material}-${x.plant}`} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">
                      <span className="font-mono">{x.material}</span>
                      <span className="text-muted-foreground ml-2">{x.description}</span>
                    </p>
                    <p className="text-muted-foreground mt-0.5 font-mono text-[11px]">
                      {x.plant} · out {x.depleted_on}
                    </p>
                  </div>
                  <span className="font-mono text-sm tabular-nums">
                    {x.days_left}
                    <span className="text-muted-foreground ml-1 text-xs">days</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section
          title="Latest handlings"
          action={
            <Link href="/" className="text-muted-foreground hover:text-foreground text-xs">
              Decision queue
            </Link>
          }
        >
          {s.recent.length === 0 ? (
            <p className="text-muted-foreground rounded-lg border border-dashed p-5 text-sm">
              Nothing has been handled yet.
            </p>
          ) : (
            <ul className="divide-y rounded-lg border">
              {s.recent.map((r, i) => (
                <li key={i} className="flex items-center gap-3 px-4 py-3">
                  <StatusBadge status={r.status} />
                  <span className="min-w-0 flex-1 truncate text-sm">{r.title}</span>
                  <ArrowRight className="text-muted-foreground size-3.5 shrink-0" />
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
    </main>
  );
}
