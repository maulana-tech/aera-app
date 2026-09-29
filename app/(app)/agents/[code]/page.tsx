import { ArrowLeft, Crown, ShieldBan } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { api, me, type Agent, type AgentSummary, type View } from "@/app/lib";
import AskDrawer from "./AskDrawer";
import { AgentBadge } from "@/components/agent-card";
import { DataTable } from "@/components/data-table";
import { Figure } from "@/components/charts";
import { ForecastChart } from "@/components/forecast-chart";
import { RulingList, type Ruling } from "@/components/rulings";
import { Empty, Fact, Rail, Section, ToolList } from "@/components/shell";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

/** What each agent's own page is showing, and what to ask them. */
const DESK: Record<string, { work: string; note?: string; examples: string[] }> = {
  supervisor: {
    work: "Routing",
    note: "Which specialists Arya pulled in, in what order, and where she stopped.",
    examples: ["Any disruption still unhandled?", "Summarise today's supply position"],
  },
  impact: {
    work: "Disruption trace",
    examples: ["Which orders route through Ningbo?", "When does M-4471 at KRW1 run out?"],
  },
  demand: {
    work: "Planned rate against what actually happened",
    examples: ["What is daily consumption of M-4471 at KRW1?", "Any demand spike?"],
  },
  inventory: {
    work: "Stock, and how much of it is usable",
    examples: ["Is any M-4471 stock on quality hold?", "What is the safety floor?"],
  },
  sourcing: {
    work: "Replacement supply options",
    examples: ["Any replacement source for M-4471?", "Which local supplier could we use?"],
  },
  logistics: {
    work: "Arrival dates that survive contact with reality",
    examples: ["When does option B really land?", "How long is dwell at Priok?"],
  },
  compliance: {
    work: "Rulings",
    examples: ["May we use the Vietnamese supplier?", "Which option breaches TKDN?"],
  },
  simulation: {
    work: "Costed combinations",
    examples: ["What does combination B+C cost?", "Which is cheapest and still safe?"],
  },
  precedent: {
    work: "Comparable past incidents",
    examples: ["Has Ningbo disrupted us before?", "How was it handled then?"],
  },
  execution: {
    work: "Actions raised, and what became of them",
    examples: ["Which actions await approval?", "Has anything been sent to SAP?"],
  },
  exposure: {
    work: "Latent risk",
    examples: ["Which materials have one supplier?", "Whose certificate expires soon?"],
  },
};

export default async function AgentPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const [team, user] = await Promise.all([
    api<{ agents: Agent[]; summary: AgentSummary }>("agents"),
    me(),
  ]);
  const a = team?.agents.find((x) => x.code === code);
  if (!a) notFound();

  const desk = DESK[code] ?? { work: "Work", examples: [] };
  const view = await api<View>(`data/${code}`);
  const missingTools = a.tools.filter((t) => !t.installed);

  return (
    <main className="w-full px-6 py-8">
      <Link
        href="/agents"
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs"
      >
        <ArrowLeft className="size-3" />
        Agent team
      </Link>

      <header className="mt-5 border-b pb-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <AgentBadge nickname={a.nickname} large />
          <h1 className="text-2xl font-semibold tracking-tight">{a.nickname}</h1>
          <span className="text-muted-foreground text-sm">{a.title}</span>
          {a.lead && (
            <Badge variant="outline" className="gap-1 font-mono text-[10px]">
              <Crown className="size-3" />
              lead
            </Badge>
          )}
          {a.veto && (
            <Badge variant="outline" className="gap-1 font-mono text-[10px]">
              <ShieldBan className="size-3" />
              veto
            </Badge>
          )}
          <div className="ml-auto">
            <AskDrawer
              code={a.code}
              name={a.nickname}
              title={a.title}
              examples={desk.examples}
              signedIn={!!user}
            />
          </div>
        </div>
        <p className="text-muted-foreground mt-3 max-w-2xl text-sm leading-relaxed">
          {a.brief}
        </p>
      </header>

      {/* A forecast is a range, so it gets a chart before it gets a table. */}
      {view?.chart && (
        <Section
          title={`${view.chart.material} at ${view.chart.plant}, daily withdrawals`}
          note={
            view.chart.planned_rate
              ? `The dashed rule is the planned ${view.chart.planned_rate} ${view.chart.unit} a day that every cover date in the system is divided by. In-sample error ${view.chart.mape_pct}%.`
              : undefined
          }
        >
          <Figure
            title=""
            origin={view.origin}
            source={view.source}
            table={{
              head: ["Date", `Forecast ${view.chart.unit}`, "Low", "High"],
              rows: view.chart.points.map((p) => [p.on, p.point, p.lower, p.upper]),
            }}
          >
            <ForecastChart
              observed={view.chart.observed}
              points={view.chart.points}
              plannedRate={view.chart.planned_rate}
              unit={view.chart.unit}
              confidence={view.chart.confidence}
              windowDays={view.chart.window_days}
            />
          </Figure>
        </Section>
      )}

      <Section title={desk.work} note={view?.note ?? desk.note}>
        {!view ? (
          <Empty
            what={`${a.nickname} has nothing on her desk yet.`}
            why={
              missingTools.length === a.tools.length
                ? `None of her tools are written, so there is nothing for her to read.`
                : `This agent does not publish a table of her own. Her findings show up inside a run.`
            }
            fix={
              missingTools.length
                ? `not written yet: ${missingTools.map((t) => t.name).join(", ")}`
                : undefined
            }
          />
        ) : view.rows.length === 0 ? (
          <Empty
            what="Nothing to show, and that is the correct answer."
            why={view.note || "The inputs were not trustworthy enough to produce a result."}
            fix={`source: ${view.source}`}
          />
        ) : code === "compliance" ? (
          <RulingList rulings={view.rows as unknown as Ruling[]} />
        ) : (
          <DataTable
            columns={view.columns}
            rows={view.rows}
            origin={view.origin}
            source={view.source}
            highlight={(r) => r.chosen === true || r.allowed === false}
          />
        )}
      </Section>

      <div className="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <div className="rounded-lg border">
            <p className="text-muted-foreground border-b px-4 py-2.5 text-xs font-medium">
              Tools {a.installed} of {a.tool_count}
            </p>
            <ToolList tools={a.tools} />
          </div>
        </div>

        <div className="space-y-4">
          <Rail>
            <Fact label="Reasoning effort" value={a.effort} />
            <Fact
              label="Instructions"
              value={a.ready ? "written" : "not written"}
              tone={a.ready ? "plain" : "warn"}
            />
            <Fact label="Used in" value={`${a.used_in} runs`} />
          </Rail>

          {!a.ready && (
            <p className="text-muted-foreground px-1 text-xs leading-relaxed">
              Calling {a.nickname} raises an error rather than sending the model an
              empty prompt. Write{" "}
              <code className="font-mono">prompts/{a.code}.txt</code> first.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
