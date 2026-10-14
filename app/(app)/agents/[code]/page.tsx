import { ArrowLeft, Crown, ShieldBan } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Fragment } from "react";

import { api, me, type Agent, type AgentSummary, type View, type ViewSection } from "@/app/lib";
import AskDrawer from "./AskDrawer";
import { AgentBadge } from "@/components/agent-card";
import { DataTable } from "@/components/data-table";
import { ChartBlock } from "@/components/chart-block";
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
  procurement: {
    work: "Vendor offers, and the supplier book behind them",
    note: "What the firms are quoting, and who carries the book.",
    examples: [
      "Who quotes M-4471 cheapest and who can deliver fastest?",
      "How concentrated is our supply base?",
      "Which suppliers deliver late?",
      "Which suppliers hold no orders?",
    ],
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

  // A desk with one question returns its view flat. One with two returns
  // `sections`, each with its own heading. Both are drawn the same way below,
  // so a new domain cannot arrive half-wired: it either publishes a section or
  // it publishes nothing.
  const sections: ViewSection[] =
    view?.sections ??
    (view
      ? [{
          title: desk.work,
          note: view.note,
          columns: view.columns ?? [],
          rows: view.rows ?? [],
          origin: view.origin ?? "modelled",
          source: view.source ?? "",
          chart: view.chart,
        }]
      : []);

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <Link
        href="/agents"
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs"
      >
        <ArrowLeft className="size-3" />
        Agent team
      </Link>

      <header className="mt-3 border-b pb-4 md:mt-5 md:pb-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <AgentBadge nickname={a.nickname} large />
          <h1 className="text-xl font-semibold tracking-tight md:text-2xl">{a.nickname}</h1>
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
              work={desk.work}
              examples={desk.examples}
              signedIn={!!user}
            />
          </div>
        </div>
        <p className="text-muted-foreground mt-3 max-w-2xl text-sm leading-relaxed">
          {a.brief}
        </p>
      </header>

      {/* Her tools and her settings explain the table, so they come before it. */}
      <div className="mt-8 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="rounded-lg border">
          <p className="text-muted-foreground border-b px-4 py-2.5 text-xs font-medium">
            Tools {a.installed} of {a.tool_count}
          </p>
          <ToolList tools={a.tools} />
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

      {/* Each section publishes its chart, then its table underneath: the shape
          of the finding is the finding, and the numbers are there for anyone
          who would rather check. */}
      {sections.length === 0 ? (
        <Section title={desk.work} note={desk.note}>
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
        </Section>
      ) : (
        sections.map((sec, i) => (
          <Fragment key={sec.title}>
            {/* The chart comes first and outside the section below it: its own
                heading is the one that says what the picture is, and the
                section's heading then frames the table of numbers underneath.
                That is how every other domain on the site is laid out, so a
                two-section desk reads exactly like two single-section ones. */}
            {sec.chart && (
              <ChartBlock chart={sec.chart} origin={sec.origin} source={sec.source} />
            )}

            <Section
              title={sec.title}
              note={sec.note ?? (sections.length === 1 ? desk.note : undefined)}
            >
              {sec.rows.length === 0 ? (
                <Empty
                  what="Nothing to show, and that is the correct answer."
                  why={sec.note || "The inputs were not trustworthy enough to produce a result."}
                  fix={`source: ${sec.source}`}
                />
              ) : code === "compliance" && i === 0 ? (
                <RulingList rulings={sec.rows as unknown as Ruling[]} />
              ) : (
                <DataTable
                  columns={sec.columns}
                  rows={sec.rows}
                  origin={sec.origin}
                  source={sec.source}
                  highlight={(r) =>
                    r.chosen === true ||
                    r.allowed === false ||
                    r.flagged === true ||
                    r.live === false
                  }
                />
              )}
            </Section>
          </Fragment>
        ))
      )}

    </main>
  );
}
