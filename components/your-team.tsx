import { ArrowRight, MessagesSquare } from "lucide-react";
import Link from "next/link";

import type { TeamAgent } from "@/app/lib";
import { AgentBadge } from "@/components/agent-card";
import { Chip } from "@/components/dort";
import { CapChip } from "@/components/team-list";
import { Button } from "@/components/ui/button";

/* The team the business got, on the dashboard: who each agent is, what it may do, and why it is on THIS
 * business's team (core/team.py, reasons). First thing after onboarding, so a person meets the team that was
 * composed from what they described before anything else. */

const CORE_WHY: Record<string, string> = {
  supervisor: "on every AERA business: plans each piece of work and hands it to the right specialist",
  guardian: "on every AERA business: checks every payment and message against your rules; its block is final",
  treasurer: "on every AERA business: the only one who moves money, and only through the vault",
};

export function YourTeam({ agents, reasons, business, fresh }: {
  agents: TeamAgent[];
  reasons: Record<string, string>;
  business: string;
  /** no work yet: the team is new, so the next step is its first task */
  fresh: boolean;
}) {
  const active = agents.filter((a) => a.status === "active");
  const drafts = agents.filter((a) => a.status === "draft");
  const CORE_ORDER = ["supervisor", "guardian", "treasurer"];
  const core = active.filter((a) => a.core).sort((a, b) => CORE_ORDER.indexOf(a.code) - CORE_ORDER.indexOf(b.code));
  const ordered = [...core, ...active.filter((a) => !a.core)];
  return (
    <section className="mt-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-fg text-[18px] font-medium tracking-tight">Your AI team</h2>
          <p className="text-muted-foreground mt-1 text-[13px] leading-relaxed">
            {active.length} agents composed from {business}&apos;s profile. Each one says why it is here; change who is on the team any time.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {fresh && (
            <Button asChild size="sm"><Link href="/work">Give them their first task <ArrowRight className="size-3.5" /></Link></Button>
          )}
          <Button asChild size="sm" variant="outline"><Link href="/agents">Manage the team</Link></Button>
        </div>
      </div>

      <ul className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {ordered.map((a) => {
          const why = a.core ? CORE_WHY[a.code] : reasons[a.code] ?? (a.origin === "person" || a.origin === "model" ? "a role you described" : undefined);
          const caps = a.capabilities.filter((c) => c !== "shared");
          return (
            <li key={a.code} className="bg-card-grad flex flex-col rounded-xl border p-4 shadow-soft">
              <div className="flex items-start gap-3">
                <AgentBadge nickname={a.nickname} title={a.title} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <p className="text-fg text-[14.5px]">{a.nickname}</p>
                    {a.core && <Chip tone="solid" className="h-5 text-[10.5px]">always</Chip>}
                  </div>
                  {a.title !== a.nickname && <p className="text-muted-foreground text-[12px]">{a.title}</p>}
                </div>
              </div>
              <p className="text-body mt-3 line-clamp-2 text-[13px] leading-relaxed">{a.brief}</p>
              {why && (
                <p className="bg-raised text-text mt-3 rounded-md px-2.5 py-1.5 text-[12px] leading-relaxed">
                  <span className="text-brand">Why on your team:</span> {why}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-1">
                {caps.slice(0, 3).map((c) => <CapChip key={c} name={c} />)}
                {caps.length > 3 && <span className="text-muted-foreground self-center text-[11px]">+{caps.length - 3}</span>}
              </div>
              <div className="mt-auto pt-3">
                <Link href={`/agents/${a.code}`} className="text-brand inline-flex items-center gap-1.5 text-[12.5px] underline-offset-2 hover:underline">
                  <MessagesSquare className="size-3.5" /> Talk to {a.nickname}
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
      {drafts.length > 0 && (
        <p className="text-muted-foreground mt-3 text-[12.5px]">
          {drafts.length} role{drafts.length === 1 ? "" : "s"} you described {drafts.length === 1 ? "is a draft" : "are drafts"} ({drafts.map((d) => d.title).join(", ")}):
          switch {drafts.length === 1 ? "it" : "them"} on under <Link href="/agents" className="text-brand underline-offset-2 hover:underline">Team</Link>.
        </p>
      )}
    </section>
  );
}
