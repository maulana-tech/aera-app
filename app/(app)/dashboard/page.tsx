import { ArrowRight, Clock, TriangleAlert, Wallet } from "lucide-react";
import Link from "next/link";

import { api, idr, type Summary, type View } from "@/app/lib";
import { Bars, Figure, type Datum } from "@/components/charts";
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

function Stat({
  label, value, note, icon: Icon,
}: { label: string; value: string; note?: string; icon: React.ElementType }) {
  return (
    <div className="rounded-xl border p-4">
      <p className="text-muted-foreground flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider">
        <Icon className="size-3" />
        {label}
      </p>
      <p className="mt-2 font-mono text-xl font-semibold tabular-nums">{value}</p>
      {note && <p className="text-muted-foreground mt-1 text-xs leading-relaxed">{note}</p>}
    </div>
  );
}

export default async function Dashboard() {
  const [s, stock, sourcing, logistics, costing] = await Promise.all([
    api<Summary>("summary"),
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
  const stockRows = (stock?.rows ?? []).filter((r) => r.days_left != null);
  const stockData: Datum[] = stockRows.map((r) => ({
    label: r.description || r.material,
    sub: `${r.material} · ${r.plant}`,
    value: Number(r.days_left),
    display: `${num(Number(r.days_left))}d`,
    hatched: Number(r.days_left) < 14,
    tag: r.depleted_on ? `out ${r.depleted_on}` : undefined,
    title: `${r.material} at ${r.plant} — ${num(Number(r.qty))} ${r.unit ?? ""} on hand, `
      + `${num(Number(r.daily_consumption))}/day`,
  }));

  // ---- supply options: extra cost of each ------------------------------
  const sourcingData: Datum[] = (sourcing?.rows ?? []).map((r) => ({
    label: r.label,
    sub: `${r.supplier ?? "—"} · ${r.origin_country ?? "—"}`,
    value: Number(r.cost_idr ?? 0),
    display: `Rp ${short(Number(r.cost_idr ?? 0))}`,
    hatched: r.allowed === false,
    tag: r.allowed === false ? "blocked by rules" : r.arrives ? `arrives ${r.arrives}` : undefined,
    title: r.reason || `Arrives ${r.arrives}, TKDN becomes ${r.tkdn ?? "—"}`,
  }));

  // ---- delayed shipments ------------------------------------------------
  const lateRows = (logistics?.rows ?? []).filter(
    (r) => r.status !== "planned" && Number(r.delay_days ?? 0) > 0,
  );
  const lateData: Datum[] = lateRows.map((r) => ({
    label: r.reference,
    sub: `${r.material} · ${r.port ?? "—"}`,
    value: Number(r.delay_days),
    display: `${r.delay_days}d`,
    tag: `now ${r.arrival_revised}`,
    title: `Booked ${r.arrival_original}, now ${r.arrival_revised} — status ${r.status}`,
  }));

  // ---- costing: what each combination would cost ------------------------
  const costingData: Datum[] = (costing?.rows ?? []).map((r) => ({
    label: r.combination,
    value: Number(r.cost_idr ?? 0),
    display: `Rp ${short(Number(r.cost_idr ?? 0))}`,
    hatched: r.safe === false,
    tag: r.chosen ? "▸ chosen" : r.safe === false ? "leaves a gap" : undefined,
    title: `${r.safe ? "Bridges the supply gap" : "Still runs out of stock"}`
      + `${r.depleted_on ? ` — out ${r.depleted_on}` : ""}`
      + `${r.tkdn != null ? ` · TKDN ${r.tkdn}` : ""}`,
  }));

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Dashboard
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Overview</h1>
      </header>

      <section className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          icon={Clock}
          label="Awaiting decision"
          value={String(awaiting)}
          note={awaiting ? `worth ${idr(s.pending_value_idr)}` : "nothing is waiting"}
        />
        <Stat
          icon={Wallet}
          label="Approved"
          value={idr(s.approved_value_idr)}
          note="value of actions that cleared approval"
        />
        <Stat
          icon={TriangleAlert}
          label="Being handled"
          value={String(running)}
          note={held ? `${held} held` : undefined}
        />
        <Stat
          icon={Wallet}
          label="Model cost"
          value={idr(s.model_cost_idr)}
          note="since the beginning"
        />
      </section>

      {(!s.model_ready || !s.sap_ready) && (
        <div className="mt-6 rounded-xl border p-4">
          <p className="text-sm font-medium">Not fully connected</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {!s.model_ready && <StatusBadge status="held">AWS_REGION not set</StatusBadge>}
            {!s.sap_ready && <StatusBadge status="held">SAP_API_KEY not set</StatusBadge>}
          </div>
          <p className="text-muted-foreground mt-2 text-xs leading-relaxed">
            While both are empty the system makes no decisions at all — and does not
            pretend to. The charts below still label where every figure came from.
          </p>
        </div>
      )}

      <div className="mt-8 grid gap-4 xl:grid-cols-2">
        <Figure
          title="Remaining stock cover"
          blurb="Days until each material runs out at the current consumption rate. Hatched bars are already below the threshold."
          origin={stock?.origin}
          source={stock?.source}
          empty={stockData.length ? undefined : "No stock data to work from yet."}
          table={{
            head: ["Material", "Plant", "Days left", "Depleted"],
            rows: stockRows.map((r) => [
              `${r.material} — ${r.description}`, r.plant,
              num(Number(r.days_left)), r.depleted_on ?? "—",
            ]),
          }}
        >
          <Bars data={stockData} threshold={14} thresholdLabel="14-day safety threshold" />
        </Figure>

        <Figure
          title="Cost per supply option"
          blurb="Extra cost of each replacement option. Hatched bars were blocked by Kira for breaching TKDN or LARTAS — and price cannot overturn that."
          origin={sourcing?.origin}
          source={sourcing?.source}
          empty={sourcingData.length ? undefined : "No replacement options yet."}
          table={{
            head: ["Option", "Arrives", "Cost", "Clears rules"],
            rows: (sourcing?.rows ?? []).map((r) => [
              r.label, r.arrives ?? "—", idr(Number(r.cost_idr ?? 0)),
              r.allowed === false ? "no" : "yes",
            ]),
          }}
        >
          <Bars data={sourcingData} />
        </Figure>

        <Figure
          title="Delayed shipments"
          blurb="Days between the delivery date that was promised and the one that now applies."
          origin={logistics?.origin}
          source={logistics?.source}
          empty={lateData.length ? undefined : "Nothing is running late."}
          table={{
            head: ["Reference", "Booked", "Now", "Delay"],
            rows: lateRows.map((r) => [
              r.reference, r.arrival_original, r.arrival_revised, `${r.delay_days}d`,
            ]),
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
              : costing?.note || "The calculator refused to compute — its inputs aren't trustworthy."
          }
          table={{
            head: ["Combination", "Cost", "Bridges gap", "Depleted"],
            rows: (costing?.rows ?? []).map((r) => [
              r.combination, idr(Number(r.cost_idr ?? 0)),
              r.safe ? "yes" : "no", r.depleted_on ?? "—",
            ]),
          }}
        >
          <Bars data={costingData} />
        </Figure>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section>
          <div className="flex items-baseline justify-between">
            <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
              Most critical stock
            </h2>
            <Link href="/data/inventory" className="text-muted-foreground hover:text-foreground font-mono text-[11px]">
              all →
            </Link>
          </div>
          {s.critical_stock.length === 0 ? (
            <p className="text-muted-foreground mt-3 rounded-xl border border-dashed p-5 text-sm">
              Nothing is under 14 days of cover.
            </p>
          ) : (
            <ul className="mt-3 divide-y rounded-xl border">
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
        </section>

        <section>
          <div className="flex items-baseline justify-between">
            <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
              Latest handlings
            </h2>
            <Link href="/" className="text-muted-foreground hover:text-foreground font-mono text-[11px]">
              queue →
            </Link>
          </div>
          {s.recent.length === 0 ? (
            <p className="text-muted-foreground mt-3 rounded-xl border border-dashed p-5 text-sm">
              Nothing has been handled yet.
            </p>
          ) : (
            <ul className="mt-3 divide-y rounded-xl border">
              {s.recent.map((r, i) => (
                <li key={i} className="flex items-center gap-3 px-4 py-3">
                  <StatusBadge status={r.status} />
                  <span className="min-w-0 flex-1 truncate text-sm">{r.title}</span>
                  <ArrowRight className="text-muted-foreground size-3.5 shrink-0" />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
