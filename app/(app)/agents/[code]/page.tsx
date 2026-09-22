import { Crown, ShieldBan, Wrench } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { api, me, type Agent, type AgentSummary } from "@/app/lib";
import Conversation from "./Conversation";
import { AgentBadge } from "@/components/agent-card";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

/** Example questions per agent — saves the blank-screen stare. */
const EXAMPLES: Record<string, string[]> = {
  supervisor: ["Any disruption still unhandled?", "Summarise today's supply position"],
  impact: ["Which orders route through Ningbo?", "When does M-4471 at KRW1 run out?"],
  demand: ["What's the daily consumption of M-4471 at KRW1?", "Any demand spike?"],
  inventory: ["Is any M-4471 stock at KRW1 on quality hold?", "What's the safety floor?"],
  sourcing: ["Any replacement source for M-4471?", "Which local supplier could we use?"],
  logistics: ["Realistically, when does option B land?", "How long is dwell at Priok?"],
  compliance: ["May we use the Vietnamese supplier for M-4471?", "Which option breaches TKDN?"],
  simulation: ["What does combination B+C cost?", "Which is cheapest and still safe?"],
  precedent: ["Has Ningbo disrupted us before?", "How was it handled then?"],
  execution: ["Which actions are awaiting approval?", "Has anything been sent to SAP?"],
  exposure: ["Which materials have only one supplier?", "Whose certificate expires soon?"],
};

export default async function AgentPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const [d, user] = await Promise.all([
    api<{ agents: Agent[]; summary: AgentSummary }>("agents"),
    me(),
  ]);
  const a = d?.agents.find((x) => x.code === code);
  if (!a) notFound();

  const missing = a.tools.filter((t) => !t.installed);

  return (
    <main className="w-full px-6 py-8">
      <Link href="/agents" className="text-muted-foreground hover:text-foreground font-mono text-xs">
        ← agent team
      </Link>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_340px]">
        <section>
          <div className="flex flex-wrap items-center gap-3">
            <AgentBadge nickname={a.nickname} large />
            <h1 className="text-2xl font-semibold tracking-tight">{a.nickname}</h1>
            <span className="text-muted-foreground text-sm">{a.title}</span>
            {a.lead && <Crown className="size-4" />}
            {a.veto && (
              <Badge variant="outline" className="gap-1 font-mono text-[10px]">
                <ShieldBan className="size-3" />
                veto
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground mt-1 max-w-2xl text-sm leading-relaxed">{a.brief}</p>

          <div className="mt-5">
            <Conversation
              code={a.code}
              name={a.nickname}
              examples={EXAMPLES[a.code] ?? []}
              signedIn={!!user}
            />
          </div>
        </section>

        <aside className="space-y-5">
          {!a.ready && (
            <div className="rounded-xl border p-4">
              <StatusBadge status="held">no instructions written</StatusBadge>
              <p className="text-muted-foreground mt-2 text-xs leading-relaxed">
                <code className="font-mono">prompts/{a.code}.txt</code> does not exist yet, so
                calling {a.nickname} raises an error rather than running on an empty prompt.
              </p>
            </div>
          )}

          {!d!.summary.model_ready && (
            <div className="rounded-xl border p-4">
              <StatusBadge status="held">reasoning engine not connected</StatusBadge>
              <p className="text-muted-foreground mt-2 text-xs leading-relaxed">
                Conversations are refused until <code className="font-mono">AWS_REGION</code> is
                set. The agent will not answer with a guess.
              </p>
            </div>
          )}

          <div className="rounded-xl border">
            <div className="flex items-center gap-2 border-b px-4 py-3">
              <Wrench className="size-3.5" />
              <p className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
                Tools · {a.installed}/{a.tool_count}
              </p>
            </div>
            <ul className="divide-y">
              {a.tools.map((t) => (
                <li key={t.name} className="px-4 py-3">
                  <p
                    className={`break-all font-mono text-xs ${
                      t.installed ? "" : "text-muted-foreground/50"
                    }`}
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
          </div>

          <div className="text-muted-foreground space-y-1.5 px-1 font-mono text-[11px]">
            <p>effort · {a.effort}</p>
            <p>used in · {a.used_in} disruptions</p>
            {missing.length > 0 && <p>{missing.length} tools not written</p>}
          </div>
        </aside>
      </div>
    </main>
  );
}
