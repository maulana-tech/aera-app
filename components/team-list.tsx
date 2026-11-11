import { Crown, Lock, ShieldBan } from "lucide-react";

import type { TeamAgent, TeamDiff } from "@/app/lib";
import { AgentBadge } from "@/components/agent-card";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";

export const LOCKED_CAPS = new Set(["supervisor", "guardian", "treasury"]);

export function RoleMarks({ a }: { a: Pick<TeamAgent, "code" | "core" | "veto"> }) {
  return (
    <>
      {a.code === "supervisor" && <Crown className="size-3.5 shrink-0" aria-label="lead" />}
      {a.core && (
        <Badge variant="outline" className="h-5 gap-1 px-1.5 font-mono text-[9px]">
          <Lock className="size-2.5" />
          core
        </Badge>
      )}
      {a.veto && (
        <Badge variant="outline" className="h-5 gap-1 px-1.5 font-mono text-[9px]">
          <ShieldBan className="size-2.5" />
          veto
        </Badge>
      )}
    </>
  );
}

/** A capability chip. The three locked to a core role say so. */
export function CapChip({ name }: { name: string }) {
  const locked = LOCKED_CAPS.has(name);
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] ${
      locked ? "border-border bg-raised text-info " : ""}`}>
      {locked && <Lock className="size-2.5" />}
      {name}
    </span>
  );
}

/** A compact row per agent, for previews and diffs. */
export function TeamRows({ agents, action }: {
  agents: TeamAgent[]; action?: (a: TeamAgent) => React.ReactNode;
}) {
  return (
    <ul className="divide-y rounded-lg border">
      {agents.map((a) => (
        <li key={a.code} className="flex flex-wrap items-start gap-3 px-4 py-3">
          <AgentBadge nickname={a.nickname} title={a.title} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="text-sm font-medium">{a.nickname}</span>
              {a.title !== a.nickname && <span className="text-muted-foreground text-xs">{a.title}</span>}
              <RoleMarks a={a} />
              {a.status !== "active" && <StatusBadge status={a.status} />}
            </div>
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">{a.brief}</p>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {a.capabilities.map((c) => <CapChip key={c} name={c} />)}
            </div>
          </div>
          {action && <div className="shrink-0">{action(a)}</div>}
        </li>
      ))}
    </ul>
  );
}

/** What applying a proposal would change, before anyone applies it. */
export function DiffView({ diff }: { diff: TeamDiff }) {
  const none = !diff.add.length && !diff.remove.length && !diff.change.length;
  if (none) return <p className="text-muted-foreground text-sm">The proposal matches the team on record. Nothing would change.</p>;
  return (
    <div className="space-y-4">
      {diff.add.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-ok ">Joins the team ({diff.add.length})</p>
          <TeamRows agents={diff.add} />
        </div>
      )}
      {diff.remove.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-bad ">Would be disabled ({diff.remove.length})</p>
          <TeamRows agents={diff.remove} />
        </div>
      )}
      {diff.change.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-warn ">Changes ({diff.change.length})</p>
          <ul className="divide-y rounded-lg border">
            {diff.change.map((c) => (
              <li key={c.code} className="flex flex-wrap items-center gap-2 px-4 py-2 text-sm">
                <span className="font-mono text-xs">{c.code}</span>
                <span className="text-muted-foreground text-xs">{c.fields.join(", ")}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
