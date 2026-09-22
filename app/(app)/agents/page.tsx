import { ArrowDown, ArrowLeftRight, Database } from "lucide-react";
import Link from "next/link";

import { api, type Agent, type AgentSummary } from "@/app/lib";
import { AgentBadge, AgentCard } from "@/components/agent-card";
import { StatusBadge } from "@/components/status-badge";
import { Progress } from "@/components/ui/progress";

export const dynamic = "force-dynamic";

export default async function AgentTeam() {
  const d = await api<{ agents: Agent[]; summary: AgentSummary }>("agents");

  if (!d) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">The agent service is not responding</h1>
        <pre className="bg-muted mt-4 rounded-lg border p-4 font-mono text-sm">
          cd sigap/agent{"\n"}python3 api.py
        </pre>
      </main>
    );
  }

  const { agents, summary } = d;
  const lead = agents.find((a) => a.lead)!;
  const responders = agents.filter((a) => !a.lead && a.code !== "exposure");
  const preventers = agents.filter((a) => a.code === "exposure");
  const pct = Math.round((summary.tools_installed / summary.tools_total) * 100);

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Agent team
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          One lead, ten specialists
        </h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Arya calls whichever specialist the last finding warrants — the order is decided
          in the moment, not written in advance. If moving stock between plants solves it,
          Clint never gets called at all.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-x-8 gap-y-3">
          <div className="min-w-40">
            <p className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">
              Tools installed
            </p>
            <p className="mt-1 font-mono text-lg font-semibold tabular-nums">
              {summary.tools_installed}
              <span className="text-muted-foreground text-sm">/{summary.tools_total}</span>
            </p>
            <Progress value={pct} className="mt-1.5 h-1" />
          </div>
          <div className="min-w-40">
            <p className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">
              Prompts written
            </p>
            <p className="mt-1 font-mono text-lg font-semibold tabular-nums">
              {summary.prompts_written}
              <span className="text-muted-foreground text-sm">/{summary.agent_count}</span>
            </p>
            <Progress
              value={Math.round((summary.prompts_written / summary.agent_count) * 100)}
              className="mt-1.5 h-1"
            />
          </div>
          <StatusBadge status={summary.model_ready ? "done" : "held"}>
            {summary.model_ready ? "Bedrock ready" : "AWS_REGION not set"}
          </StatusBadge>
          <StatusBadge status={summary.sap_ready ? "done" : "held"}>
            {summary.sap_ready ? "SAP connected" : "SAP_API_KEY not set"}
          </StatusBadge>
        </div>
      </header>

      {/* ---------------- the lead ---------------- */}
      <section className="mt-8">
        <div className="bg-muted/40 flex flex-wrap items-center gap-4 rounded-xl border p-5">
          <AgentBadge nickname={lead.nickname} large />
          <div className="min-w-60 flex-1">
            <h2 className="font-semibold">
              {lead.nickname}
              <span className="text-muted-foreground ml-2 text-sm font-normal">{lead.title}</span>
            </h2>
            <p className="text-muted-foreground mt-1 text-sm leading-relaxed">{lead.brief}</p>
          </div>
          <Link
            href={`/agents/${lead.code}`}
            className="text-muted-foreground hover:text-foreground font-mono text-xs"
          >
            open →
          </Link>
        </div>

        <p className="text-muted-foreground mt-3 flex flex-wrap items-center justify-center gap-x-6 gap-y-1 font-mono text-[11px] uppercase tracking-[0.12em]">
          <span className="flex items-center gap-1.5">
            <ArrowDown className="size-3" /> calls on what was found
          </span>
          <span className="flex items-center gap-1.5">
            <ArrowLeftRight className="size-3" /> specialists hand off to each other
          </span>
        </p>
      </section>

      {/* ---------------- responding specialists ---------------- */}
      <section className="mt-3">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {responders.map((a) => (
            <AgentCard key={a.code} a={a} />
          ))}
        </div>
      </section>

      {/* ---------------- the shared board ---------------- */}
      <section className="mt-3">
        <div className="text-muted-foreground flex flex-wrap items-start gap-3 rounded-xl border border-dashed p-4">
          <Database className="mt-0.5 size-4 shrink-0" />
          <div className="min-w-60 flex-1">
            <p className="text-foreground font-mono text-[11px] uppercase tracking-[0.12em]">
              Shared board
            </p>
            <p className="mt-1 text-xs leading-relaxed">
              Every specialist reads and writes here, and each finding carries its origin
              label. This is what lets Iris hand a quality hold straight to Elsa — the
              stockout date gets recomputed without going back through Arya.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------- prevent mode ---------------- */}
      <section className="mt-8">
        <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
          Prevent mode · not built yet
        </h2>
        <p className="text-muted-foreground mt-1 max-w-2xl text-xs leading-relaxed">
          Works without waiting for a disruption: hunts risk that has not happened,
          on a weekly schedule.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {preventers.map((a) => (
            <AgentCard key={a.code} a={a} />
          ))}
        </div>
      </section>
    </main>
  );
}
