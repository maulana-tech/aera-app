import { notFound } from "next/navigation";

import { api, me, type Agent, type AgentSummary, type View } from "@/app/lib";
import Conversation from "@/app/(app)/agents/[code]/Conversation";
import { AgentBadge } from "@/components/agent-card";
import { DataTable } from "@/components/data-table";

export const dynamic = "force-dynamic";

const PAGES: Record<string, { title: string; blurb: string; examples: string[] }> = {
  demand: {
    title: "Demand",
    blurb: "How fast material is consumed, and whether demand is moving.",
    examples: ["Is M-4471 consumption at KRW1 rising?", "Which material depletes soonest?"],
  },
  inventory: {
    title: "Stock",
    blurb: "What is on the books, what may actually be used, and when it runs out.",
    examples: ["Is any stock on quality hold?", "Which material is most critical?"],
  },
  sourcing: {
    title: "Supply options",
    blurb: "Replacement options, including the ones struck out on rules rather than price.",
    examples: ["Why was option E rejected?", "Which arrives soonest?"],
  },
  logistics: {
    title: "Logistics",
    blurb: "Arrival dates that survive contact with reality: port dwell, transhipment, customs.",
    examples: ["Which shipment slipped the most?", "Realistically, when does option B land?"],
  },
  simulation: {
    title: "Costing",
    blurb: "Cost of each option and combination. Deterministic — not a model's guess.",
    examples: ["Which combination is cheapest and still safe?", "How much does that save?"],
  },
  execution: {
    title: "Execution",
    blurb: "What has already run, and what is waiting on approval.",
    examples: ["Which actions are waiting?", "Has anything landed in SAP yet?"],
  },
};

export default async function DomainPage({ params }: { params: Promise<{ domain: string }> }) {
  const { domain } = await params;
  const meta = PAGES[domain];
  if (!meta) notFound();

  const [view, team, user] = await Promise.all([
    api<View>(`data/${domain}`),
    api<{ agents: Agent[]; summary: AgentSummary }>("agents"),
    me(),
  ]);
  if (!view) notFound();

  const agent = team?.agents.find((x) => x.code === view.agent);

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Data
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{meta.title}</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          {meta.blurb}
        </p>
      </header>

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <section>
          <DataTable
            columns={view.columns}
            rows={view.rows}
            origin={view.origin}
            source={view.source}
            note={view.note}
            highlight={(row) => row.chosen === true || row.allowed === false}
          />
        </section>

        <aside>
          {agent && (
            <>
              <div className="mb-3 flex items-center gap-2.5">
                <AgentBadge nickname={agent.nickname} />
                <div>
                  <p className="text-sm font-medium leading-none">{agent.nickname}</p>
                  <p className="text-muted-foreground mt-1 text-xs">
                    owns {meta.title.toLowerCase()}
                  </p>
                </div>
              </div>
              <Conversation
                code={agent.code}
                name={agent.nickname}
                examples={meta.examples}
                signedIn={!!user}
              />
            </>
          )}
        </aside>
      </div>
    </main>
  );
}
