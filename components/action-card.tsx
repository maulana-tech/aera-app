"use client";

import { Check, Lock, Loader2, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { usd, when, type Action, type Approval, type Me } from "@/app/lib";
import { ActionPayload } from "@/components/action-payload";
import { VerdictBadge } from "@/components/guardian-rulings";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";

const TONE: Record<string, string> = { blocked: "failed", sent: "sent", approved: "approved", pending: "pending", rejected: "rejected", failed: "failed" };

/** One action that leaves the business or moves money, and the decision on it.
 *  The approve button respects the signed-in person's limit; the service
 *  checks it again from the token, so the button is a courtesy, not the rule. */
export function ActionCard({
  action: a, user, approvals = [], killSwitch, showWork,
}: {
  action: Action; user: Me | null; approvals?: Approval[]; killSwitch?: boolean; showWork?: boolean;
}) {
  const router = useRouter();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const limit = user?.limit_usd ?? 0;
  const overLimit = a.value_usd > limit;
  const guardian = a.payload.guardian;

  async function decide(decision: "approved" | "rejected" | "escalated") {
    setBusy(decision);
    setError(null);
    try {
      const r = await post<{ action: Action; executed?: { ok?: boolean; summary?: string; error?: string } }>(
        `actions/${a.id}/decision`, { decision, note });
      setResult(r.executed?.summary ?? r.executed?.error ?? `${decision}`);
      router.refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <article className="rounded-lg border p-4">
      <header className="flex flex-wrap items-center gap-2">
        <StatusBadge status={TONE[a.status] ?? a.status}>{a.status}</StatusBadge>
        <span className="font-mono text-xs">{a.kind}</span>
        {a.value_usd > 0 && <span className="font-mono text-sm font-medium tabular-nums">{usd(a.value_usd)}</span>}
        <span className="text-muted-foreground text-[11px]">{a.autonomous ? "autonomous" : "needs a person"}</span>
        <span className="text-muted-foreground ml-auto font-mono text-[10px]">{when(a.created_at)}</span>
      </header>
      {showWork && a.work_title && (
        <Link href={`/work/${a.run_id}`} className="text-muted-foreground hover:text-foreground mt-1 block truncate text-xs underline-offset-2 hover:underline">
          {a.work_title}
        </Link>
      )}
      {a.reason && <p className="text-muted-foreground mt-2 text-xs leading-relaxed">{a.reason}</p>}

      <ActionPayload payload={a.payload} />

      {guardian?.verdict && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-muted-foreground text-xs">Guardian ruled</span>
          <VerdictBadge verdict={guardian.verdict} />
          {guardian.reasons?.filter((r) => r.verdict !== "allow").map((r, i) => (
            <span key={i} className="text-muted-foreground font-mono text-[10px]">{r.rule}</span>
          ))}
        </div>
      )}

      {approvals.length > 0 && (
        <ul className="text-muted-foreground mt-3 space-y-0.5 font-mono text-[10px]">
          {approvals.map((p) => (
            <li key={p.id}>{p.decision} by {p.decided_by} ({p.role}) · {when(p.at)}{p.note ? ` · “${p.note}”` : ""}</li>
          ))}
        </ul>
      )}

      {a.status === "blocked" && (
        <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-rose-700 dark:text-rose-400">
          <Lock className="size-3.5" />
          Blocked by the guardian. A block is final and cannot be approved.
        </p>
      )}

      {a.reference && (
        <p className="text-muted-foreground mt-2 font-mono text-[10px] break-all">reference {a.reference}</p>
      )}

      {a.status === "pending" && user && (
        <div className="mt-4 space-y-2 border-t pt-3">
          <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="A note for the record (optional)" maxLength={500} />
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={() => decide("approved")} disabled={!!busy || overLimit || limit <= 0 || killSwitch}>
              {busy === "approved" ? <Loader2 className="animate-spin" /> : <Check />}
              Approve
            </Button>
            <Button size="sm" variant="outline" onClick={() => decide("rejected")} disabled={!!busy || limit <= 0}>
              {busy === "rejected" ? <Loader2 className="animate-spin" /> : <X />}
              Reject
            </Button>
            {overLimit && limit > 0 && (
              <Button size="sm" variant="ghost" onClick={() => decide("escalated")} disabled={!!busy}>
                Escalate
              </Button>
            )}
            <span className="text-muted-foreground text-[11px]">
              {limit <= 0
                ? "a viewer approves nothing"
                : killSwitch
                  ? "the kill switch is on: resume the business before approving"
                  : overLimit
                    ? `above your limit of ${usd(limit)}: escalate to someone with a higher one`
                    : `you may approve up to ${usd(limit)}`}
            </span>
          </div>
        </div>
      )}
      {result && <p className="text-muted-foreground mt-2 text-xs">{result}</p>}
      {error && <p className="mt-2 text-xs text-rose-700 dark:text-rose-400">{error}</p>}
    </article>
  );
}
