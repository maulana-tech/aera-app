import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { api, me, type Agent, type GuardianCheck, type TeamPayload } from "@/app/lib";
import AskDrawer from "./AskDrawer";
import { AgentBadge } from "@/components/agent-card";
import { GuardianRulings } from "@/components/guardian-rulings";
import { Fact, Rail, Section, ToolList } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";
import { CapChip, RoleMarks } from "@/components/team-list";

export const dynamic = "force-dynamic";

/** What to ask each role, to start a conversation that is worth having. */
const EXAMPLES: Record<string, string[]> = {
  supervisor: ["What is the team working on right now?", "Summarise this week's orders and spend"],
  guardian: ["Which actions did you block this week, and why?", "Would a $12 payment to a new vendor pass?"],
  treasurer: ["What is in the vault and what did we pay today?", "Which payments are waiting for a person?"],
  researcher: ["What sources would you use for a market brief?", "Find three recent signals in our customers' market"],
  writer: ["Draft the outline of a deliverable", "Rewrite this paragraph in our voice"],
  analyst: ["Which offering earns the most per hour of model spend?"],
  sales: ["Draft a reply to a customer asking about pricing"],
  support: ["How would you answer a late-delivery complaint?"],
  marketing: ["Draft this week's free sample announcement"],
  ops: ["Which paid orders are not delivered yet?"],
  procurement: ["Which vendors are on record and allowlisted?"],
  qa: ["What do you check before a deliverable goes out?"],
};

export default async function AgentPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const [team, roster, user, guardian] = await Promise.all([
    api<TeamPayload>("team"),
    api<{ agents: Agent[] }>("agents"),
    me(),
    code === "guardian" ? api<{ checks: GuardianCheck[] }>("guardian") : Promise.resolve(null),
  ]);
  const a = team?.agents.find((x) => x.code === code);
  if (!a) notFound();
  const r = roster?.agents.find((x) => x.code === code);
  const tools = r?.tools ?? Object.values(a.tools ?? {}).flat().map((name) => ({ name, installed: true, description: null }));

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <Link href="/agents" className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs">
        <ArrowLeft className="size-3" />
        Team
      </Link>

      <header className="mt-3 border-b pb-4 md:mt-5 md:pb-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <AgentBadge nickname={a.nickname} large />
          <h1 className="text-xl font-semibold tracking-tight md:text-2xl">{a.nickname}</h1>
          <span className="text-muted-foreground text-sm">{a.title}</span>
          <RoleMarks a={a} />
          {a.status !== "active" && <StatusBadge status={a.status} />}
          <div className="ml-auto">
            {r ? (
              <AskDrawer code={a.code} name={a.nickname} title={a.title} work={a.title}
                examples={EXAMPLES[a.role] ?? EXAMPLES[a.code] ?? []} signedIn={!!user} />
            ) : (
              <span className="text-muted-foreground text-xs">not active, so not available to talk to</span>
            )}
          </div>
        </div>
        <p className="text-muted-foreground mt-3 max-w-2xl text-sm leading-relaxed">{a.brief}</p>
        <div className="mt-3 flex flex-wrap gap-1">{a.capabilities.map((c) => <CapChip key={c} name={c} />)}</div>
      </header>

      <div className="mt-8 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="rounded-lg border">
          <p className="text-muted-foreground border-b px-4 py-2.5 text-xs font-medium">Tools ({tools.length})</p>
          <ToolList tools={tools} />
        </div>
        <Rail>
          <Fact label="Status" value={a.status} tone={a.status === "active" ? "plain" : "warn"} />
          <Fact label="Model" value={a.model ?? r?.model ?? "-"} />
          <Fact label="Reasoning effort" value={a.effort ?? r?.effort ?? "-"} />
          <Fact label="Version" value={`v${a.version ?? 1}`} />
          <Fact label="Written by" value={a.origin} />
          <Fact label="Used in" value={`${r?.runs ?? 0} runs`} />
        </Rail>
      </div>

      <Section title="Prompt" note="What this agent is told before every piece of work. The business profile is filled in where it says {BUSINESS}.">
        <pre className="bg-muted/40 max-h-[28rem] overflow-auto rounded-lg border p-4 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">{a.prompt}</pre>
      </Section>

      {guardian && (
        <Section title="Recent rulings">
          <GuardianRulings checks={guardian.checks.slice(0, 20)} empty="Kira has not ruled on anything yet." />
        </Section>
      )}
    </main>
  );
}
