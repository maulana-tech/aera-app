"use client";

import { Loader2, OctagonX, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { errorText, post } from "@/lib/post";
import { cn } from "@/lib/utils";

/** The kill switch: stop everything the team does, and freeze the vault when
 *  one is configured. Anyone who can approve may stop; only an owner resumes.
 *  Pressing stop asks once, because the cost of a second click is nothing
 *  next to the cost of a mis-click that halts a business. */
export function KillSwitch({
  on, mayStop, mayResume, compact,
}: { on: boolean; mayStop: boolean; mayResume: boolean; compact?: boolean }) {
  const router = useRouter();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function flip(next: boolean) {
    setBusy(true);
    setError(null);
    try {
      const r = await post<{ kill_switch: boolean; vault: unknown; note: string | null }>(
        "business/kill-switch", { on: next });
      setMsg(r.note ?? (next ? "Stopped. Nothing leaves the business and no payment moves." : "Resumed."));
      setConfirm(false);
      router.refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={cn("rounded-lg border p-4",
      on ? "border-rose-500/60 bg-rose-500/10" : "border-rose-500/30")}>
      <div className="flex flex-wrap items-center gap-3">
        <OctagonX className={cn("size-6 shrink-0", on ? "text-rose-600" : "text-rose-500/70")} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">{on ? "Stopped: the kill switch is on" : "Kill switch"}</p>
          {!compact && (
            <p className="text-muted-foreground text-xs leading-relaxed">
              {on
                ? "The team takes no new work, nothing is sent and no payment moves until an owner resumes."
                : "Stops the whole team at once and freezes the vault. Any approver may pull it; only an owner can resume."}
            </p>
          )}
        </div>
        {on ? (
          <Button size="sm" variant="outline" onClick={() => flip(false)} disabled={busy || !mayResume}
            title={mayResume ? undefined : "only an owner can resume"}>
            {busy ? <Loader2 className="animate-spin" /> : <Play />}
            Resume
          </Button>
        ) : confirm ? (
          <div className="flex gap-2">
            <Button size="sm" className="bg-rose-600 text-white hover:bg-rose-700" onClick={() => flip(true)} disabled={busy}>
              {busy ? <Loader2 className="animate-spin" /> : <OctagonX />}
              Yes, stop everything
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirm(false)} disabled={busy}>Cancel</Button>
          </div>
        ) : (
          <Button size="lg" className="bg-rose-600 font-semibold text-white hover:bg-rose-700"
            onClick={() => setConfirm(true)} disabled={!mayStop}
            title={mayStop ? undefined : "only an approver or an owner can pull the kill switch"}>
            <OctagonX />
            Stop
          </Button>
        )}
      </div>
      {on && !mayResume && <p className="text-muted-foreground mt-2 text-xs">Only an owner can resume the business.</p>}
      {!on && !mayStop && <p className="text-muted-foreground mt-2 text-xs">Only an approver or an owner can pull the kill switch.</p>}
      {msg && <p className="text-muted-foreground mt-2 text-xs">{msg}</p>}
      {error && <p className="mt-2 text-xs text-rose-700 dark:text-rose-400">{error}</p>}
    </div>
  );
}
