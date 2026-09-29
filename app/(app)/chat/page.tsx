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

  /* A conversation is not a document on a page, it is the page. It takes the
   * viewport minus the app bar, so the transcript scrolls against a composer
   * that stays put, instead of a 32rem box floating in the middle of a page
   * that scrolls behind it.
   */
  return (
    <main className="flex h-[calc(100svh-3.5rem)] flex-col">
      <header className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-b px-6 py-3">
        <h1 className="text-sm font-medium">Ask Arya</h1>
        <p className="text-muted-foreground text-xs">
          She decides which specialists to pull in. You do not have to know who to ask.
        </p>
        <div className="ml-auto flex items-center gap-1">
          {specialists.map((a) => (
            <span key={a.code} title={`${a.nickname} · ${a.title}`}>
              <AgentBadge nickname={a.nickname} />
            </span>
          ))}
        </div>
      </header>

      {arya && (
        <Conversation
          code={arya.code}
          name={arya.nickname}
          work="Routing"
          examples={EXAMPLES}
          signedIn={!!user}
        />
      )}
    </main>
  );
}
