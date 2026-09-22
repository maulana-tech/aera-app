import { api, me, type Agent, type AgentSummary } from "@/app/lib";
import Conversation from "@/app/(app)/agents/[code]/Conversation";
import { AgentBadge } from "@/components/agent-card";

export const dynamic = "force-dynamic";

const EXAMPLES = [
  "Any disruption still unhandled?",
  "Which material is most critical this week?",
  "If Ningbo closes for another week, what happens?",
];

export default async function Chat() {
  const [team, user] = await Promise.all([
    api<{ agents: Agent[]; summary: AgentSummary }>("agents"),
    me(),
  ]);
  const arya = team?.agents.find((a) => a.lead);
  const specialists = team?.agents.filter((a) => !a.lead) ?? [];

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Conversation
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Ask Arya</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Arya leads the team. She decides which specialists to pull in to answer —
          you don't have to know who to ask.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground mr-1 font-mono text-[10px] uppercase tracking-wider">
            can call
          </span>
          {specialists.map((a) => (
            <span key={a.code} title={`${a.nickname} · ${a.title}`}>
              <AgentBadge nickname={a.nickname} />
            </span>
          ))}
        </div>
      </header>

      <div className="mt-6 max-w-4xl">
        {arya && (
          <Conversation
            code={arya.code}
            name={arya.nickname}
            examples={EXAMPLES}
            signedIn={!!user}
          />
        )}
      </div>
    </main>
  );
}
