import { ShieldAlert, ShieldBan, ShieldCheck } from "lucide-react";

import { when, type GuardianCheck, type GuardianReason, type Verdict } from "@/app/lib";
import { OriginBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const TONE: Record<Verdict, { cls: string; icon: typeof ShieldCheck; word: string }> = {
  allow: { cls: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400", icon: ShieldCheck, word: "allow" },
  warn: { cls: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400", icon: ShieldAlert, word: "warn · a person decides" },
  block: { cls: "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-400", icon: ShieldBan, word: "block · final" },
};

export function VerdictBadge({ verdict, short }: { verdict: Verdict | string; short?: boolean }) {
  const t = TONE[verdict as Verdict] ?? TONE.warn;
  const Icon = t.icon;
  return (
    <Badge variant="outline" className={cn("gap-1 font-mono text-[10px]", t.cls)}>
      <Icon className="size-3" />
      {short ? verdict : t.word}
    </Badge>
  );
}

function Reason({ r }: { r: GuardianReason }) {
  return (
    <li className="flex items-start gap-2 py-1.5">
      <VerdictBadge verdict={r.verdict} short />
      <div className="min-w-0 flex-1">
        <p className="font-mono text-[11px]">{r.rule}</p>
        <p className="text-muted-foreground text-xs leading-relaxed break-words">{r.detail}</p>
      </div>
      {r.origin && <OriginBadge origin={r.origin} />}
    </li>
  );
}

/** Guardian's rulings: every check it made, its verdict, and each rule behind it.
 *  A block is final; a warn always goes to a person. */
export function GuardianRulings({ checks, empty }: { checks: GuardianCheck[]; empty?: string }) {
  if (!checks.length) {
    return (
      <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-xs leading-relaxed">
        {empty ?? "No rulings: nothing in this run tried to leave the business or move money."}
      </p>
    );
  }
  return (
    <ul className="divide-y rounded-lg border">
      {checks.map((c) => (
        <li key={c.id} className="px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <VerdictBadge verdict={c.verdict} />
            <span className="text-muted-foreground font-mono text-[10px]">{c.kind}</span>
            <span className="min-w-0 truncate text-sm">{c.subject}</span>
            <span className="text-muted-foreground ml-auto font-mono text-[10px]">{when(c.at, { seconds: true })}</span>
          </div>
          {c.reasons.length > 0 && <ul className="mt-1.5 divide-y">{c.reasons.map((r, i) => <Reason key={i} r={r} />)}</ul>}
        </li>
      ))}
    </ul>
  );
}
