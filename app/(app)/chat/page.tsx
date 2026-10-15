import { api, me, type Agent, type AgentSummary } from "@/app/lib";
import ChatSurface from "./ChatSurface";
import { AgentBadge } from "@/components/agent-card";

export const dynamic = "force-dynamic";

const EXAMPLES = [
  "Any disruption still unhandled?",
  "Which material is most critical this week?",
  "If Ningbo closes for another week, what happens?",
];

export default async function Chat(
  { searchParams }: { searchParams: Promise<{ c?: string }> },
) {
  const { c } = await searchParams;
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
    <main className="flex h-[calc(100dvh-3.5rem)] flex-col">
      <header className="flex shrink-0 items-center justify-between gap-x-4 border-b px-4 py-2.5 md:px-6 md:py-3">
        <div className="min-w-0">
          <h1 className="text-sm font-medium">Ask Arya</h1>
          <p className="text-muted-foreground hidden text-xs sm:block">
            She decides which specialists to pull in. You do not have to know who to ask.
          </p>
        </div>
        <div className="hidden items-center gap-1.5 sm:flex">
          {specialists.map((a) => (
            <AgentBadge
              key={a.code}
              nickname={a.nickname}
              title={a.title}
              href={`/agents/${a.code}`}
              align="end"
            />
          ))}
        </div>
        <span className="text-muted-foreground shrink-0 font-mono text-xs sm:hidden">
          {specialists.length} specialists
        </span>
      </header>

      {arya && (
        <ChatSurface
          code={arya.code}
          name={arya.nickname}
          work="Routing"
          examples={EXAMPLES}
          signedIn={!!user}
          threadId={c ?? null}
        />
      )}
    </main>
  );
}
