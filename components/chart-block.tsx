import type { DomainChart } from "@/app/lib";
import { Figure } from "@/components/charts";
import { ArrivalChart } from "@/components/arrival-chart";
import { CoverChart } from "@/components/cover-chart";
import { ForecastChart } from "@/components/forecast-chart";
import { OffersChart } from "@/components/offers-chart";
import { PortfolioChart } from "@/components/portfolio-chart";
import { Section } from "@/components/shell";
import { num } from "@/lib/chart";

/* The one place that turns a view's chart payload into a section: its heading,
 * the note under it, the fallback table, and the drawing itself.
 *
 * The agent page stays generic because of this. Adding a chart to a domain
 * touches `tools/views.py` and this file, never `agents/[code]/page.tsx`, so a
 * new domain cannot arrive half-wired — the payload's `kind` either has a case
 * here or it does not compile.
 *
 * The table is never optional. The numbers have to be readable even when the
 * chart is not, whether that is a screen reader, a printed page, or a reader
 * who simply does not trust the picture.
 */

type Meta = {
  title: string;
  note?: string;
  table: { head: string[]; rows: (string | number)[][] };
};

function meta(chart: DomainChart): Meta {
  switch (chart.kind) {
    case "demand":
      return {
        title: `${chart.material} at ${chart.plant}, daily withdrawals`,
        note:
          `The dashed rule is the planned ${chart.planned_rate} ${chart.unit} a day ` +
          `that every cover date in the system is divided by. ` +
          (chart.mape_pct != null
            ? `The band is drawn from an in-sample error of ${chart.mape_pct}%, ` +
              `so treat anything past today as an estimate rather than a plan.`
            : `Anything past today is an estimate rather than a plan.`),
        table: {
          head: ["Date", `Forecast ${chart.unit}`, "Low", "High"],
          rows: chart.points.map((p) => [p.on, p.point, p.lower, p.upper]),
        },
      };

    case "cover":
      return {
        title: "Days of cover against the safety floor",
        note:
          `How long each material lasts at today's consumption rate. ` +
          `Bars left of the dashed rule are already under the ` +
          `${chart.threshold}-day floor that replenishment is measured against.`,
        table: {
          head: ["Material", "Plant", "Days", "Empty on"],
          rows: chart.items.map((i) => [
            i.material, i.plant, i.days, i.depleted_on ?? "—",
          ]),
        },
      };

    case "arrival":
      return {
        title: "Booked arrival against the arrival the system now expects",
        note:
          `The open circle is the date on the purchase order; the filled one is ` +
          `the date the system expects now, and the line between them is the slip.`,
        table: {
          head: ["Reference", "Material", "Booked", "Revised", "Slip (days)"],
          rows: chart.items.map((i) => [
            i.reference, i.material, i.booked, i.revised, i.slip,
          ]),
        },
      };

    case "portfolio":
      return {
        title: "Where the purchase-order volume goes",
        note:
          `Each bar is one supplier's share of the book and the curve is the ` +
          `running total. ${chart.cover_n} of the ${chart.active} suppliers that ` +
          `hold orders account for ${chart.rule_pct}% of it. The ` +
          `${chart.total - chart.active} on the approved list that hold no orders ` +
          `are in the table below.`,
        table: {
          head: ["Supplier", "Origin", "Share %", "Cumulative %", "Orders", "Late"],
          rows: chart.items.map((i) => [
            i.name, i.country, i.share, i.cumulative, i.orders, i.late,
          ]),
        },
      };

    case "offers":
      return {
        title: `${chart.material}, the bids on ${num(chart.qty)} ${chart.unit}`,
        note:
          `Every dot is one firm's offer, and the two axes are the whole ` +
          `decision: right is slower, higher is dearer, so the corner to be in ` +
          `is the bottom-left. The dashed line joins the ${chart.points.filter((p) => p.on_line).length} ` +
          `offers nothing else beats on both axes at once — everything drawn below ` +
          `and to the right of it is worse on paper. Offers past their last valid ` +
          `day are hollow and are listed without a rank. The vertical axis is ` +
          `measured against the cheapest offer on file, so read prices off the ` +
          `labels rather than off how high a dot sits.`,
        table: {
          head: ["Supplier", "Origin", `Rp per ${chart.unit}`, "Days", "Valid"],
          rows: chart.points.map((p) => [
            p.name, p.country, p.price, p.lead, p.live ? "live" : "lapsed",
          ]),
        },
      };
  }
}

export function ChartBlock({
  chart, origin, source,
}: {
  chart: DomainChart;
  origin: string;
  source: string;
}) {
  const m = meta(chart);

  return (
    <Section title={m.title} note={m.note}>
      <Figure title="" origin={origin} source={source} table={m.table}>
        {chart.kind === "demand" ? (
          <ForecastChart
            observed={chart.observed}
            points={chart.points}
            plannedRate={chart.planned_rate}
            unit={chart.unit}
            confidence={chart.confidence}
            windowDays={chart.window_days}
          />
        ) : chart.kind === "cover" ? (
          <CoverChart data={chart} />
        ) : chart.kind === "arrival" ? (
          <ArrivalChart data={chart} />
        ) : chart.kind === "offers" ? (
          <OffersChart data={chart} />
        ) : (
          <PortfolioChart data={chart} />
        )}
      </Figure>
    </Section>
  );
}
