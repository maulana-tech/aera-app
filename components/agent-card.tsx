import { Crown, ShieldBan } from "lucide-react";
import Link from "next/link";

import type { Agent } from "@/app/lib";
import { Badge } from "@/components/ui/badge";

/** Per-agent badge colour, derived from the first letter. Consistent across pages. */
const HUES = [
  "bg-sky-500/15 text-sky-700 dark:text-sky-400",
  "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  "bg-violet-500/15 text-violet-700 dark:text-violet-400",
  "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  "bg-rose-500/15 text-rose-700 dark:text-rose-400",
  "bg-teal-500/15 text-teal-700 dark:text-teal-400",
];
export const hue = (s: string) => HUES[s.charCodeAt(0) % HUES.length];

export function AgentBadge({ nickname, large }: { nickname: string; large?: boolean }) {
  return (
    <span
      className={`flex shrink-0 items-center justify-center rounded-full font-semibold ${hue(
        nickname,
      )} ${large ? "size-10 text-sm" : "size-8 text-xs"}`}
    >
      {nickname.slice(0, 2)}
    </span>
  );
}

export function AgentCard({ a }: { a: Agent }) {
  const complete = a.installed === a.tool_count;
  return (
    <Link
      href={`/agents/${a.code}`}
      className="hover:border-foreground/30 hover:bg-muted/30 group block rounded-xl border p-4 transition-colors"
    >
      <div className="flex items-start gap-3">
        <AgentBadge nickname={a.nickname} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <h3 className="font-medium leading-none">{a.nickname}</h3>
            <span className="text-muted-foreground text-xs">{a.title}</span>
            {a.lead && <Crown className="size-3.5 shrink-0" />}
            {a.veto && (
              <Badge variant="outline" className="h-5 gap-1 px-1.5 font-mono text-[9px]">
                <ShieldBan className="size-2.5" />
                veto
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground mt-1.5 line-clamp-2 text-xs leading-relaxed">
            {a.brief}
          </p>
          <p
            className={`mt-2 font-mono text-[10px] ${
              complete ? "text-muted-foreground" : "text-amber-700 dark:text-amber-400"
            }`}
          >
            {a.installed}/{a.tool_count} tools
            {!a.ready && " · no prompt"}
            {a.used_in > 0 && ` · ${a.used_in} disruptions`}
          </p>
        </div>
      </div>
    </Link>
  );
}
