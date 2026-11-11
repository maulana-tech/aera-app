import { api, me, type Agent } from "@/app/lib";
import ChatSurface from "./ChatSurface";
import Link from "next/link";

import { AgentBadge } from "@/components/agent-card";
import { Empty } from "@/components/shell";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

const EXAMPLES = [
  "What is waiting for a person right now?",
  "How much did we earn and spend this week?",
  "Which paid orders are not delivered yet?",
  "Ask the specialists for a plan to win our next ten customers",
];

export default async function Chat(
  { searchParams }: { searchParams: Promise<{ c?: string }> },
) {
  const { c } = await searchParams;
  const [team, user] = await Promise.all([
    api<{ agents: Agent[] }>("agents"),
    me(),
  ]);
  const lead = team?.agents.find((a) => a.lead);
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
          <h1 className="text-sm font-medium">Ask the Supervisor</h1>
          <p className="text-muted-foreground hidden text-xs sm:block">
            It can delegate: it decides which specialists to ask and answers with what they found. You do not have to know who to ask.
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

      {!lead && (
        <div className="p-4 md:p-6">
          <Empty
            what={team ? "There is no Supervisor to talk to yet." : "The agent service is not responding."}
            why={team
              ? "The team is composed from the business profile. Describe the business, then apply the team the Composer proposes."
              : "The chat needs the agent service. Start it and reload this page."}
            action={team ? <Button asChild size="sm" variant="outline"><Link href="/agents">Open the Team</Link></Button> : undefined}
          />
        </div>
      )}
      {lead && (
        <ChatSurface
          code={lead.code}
          name={lead.nickname}
          work="Plans the work and delegates it to the specialists"
          examples={EXAMPLES}
          signedIn={!!user}
          threadId={c ?? null}
        />
      )}
    </main>
  );
}
