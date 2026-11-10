"use client";

import { RefreshCw, RotateCcw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { errorText, post } from "@/lib/post";

/* Run a held or failed work item again: after the model key is added, or the
 * provider stops rate-limiting. Lands on the new run. */
export function RetryButton({ workItemId }: { workItemId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <div className="flex flex-col items-start gap-1">
      <Button size="sm" variant="outline" disabled={busy} onClick={async () => {
        setBusy(true);
        setError("");
        try {
          const r = await post<{ run: string }>(`work/${workItemId}/retry`);
          router.push(`/work/${r.run}`);
          router.refresh();
        } catch (e) {
          setError(errorText(e));
        } finally {
          setBusy(false);
        }
      }}>
        <RotateCcw className="size-3.5" /> {busy ? "Starting…" : "Run again"}
      </Button>
      {error && <p className="text-xs text-rose-600 dark:text-rose-400">{error}</p>}
    </div>
  );
}

/* Settle now: after an approver signed in their wallet, the record catches up
 * without waiting for the 30-second pass. */
export function SyncButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState("");
  return (
    <div className="flex items-center gap-2">
      <Button size="sm" variant="outline" disabled={busy} onClick={async () => {
        setBusy(true);
        try {
          const r = await post<{ done: string }>("treasury/sync");
          setSaid(r.done);
          router.refresh();
        } catch (e) {
          setSaid(errorText(e));
        } finally {
          setBusy(false);
        }
      }}>
        <RefreshCw className={`size-3.5 ${busy ? "animate-spin" : ""}`} /> Sync with the vault
      </Button>
      {said && <span className="text-muted-foreground text-xs">{said}</span>}
    </div>
  );
}
