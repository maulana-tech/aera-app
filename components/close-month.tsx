"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { errorText, post } from "@/lib/post";

/** Hand the month to the Finance agent: reconcile, then file the report with its notes. */
export function CloseMonth({ month, label }: { month: string; label: string }) {
  // A month that has not ended is not closed: Finance rightly refuses to file it as a monthly report.
  // For the running month it is asked for a month-to-date report, labelled as provisional.
  const running = month === new Date().toISOString().slice(0, 7);
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function go() {
    setBusy(true);
    setError(null);
    try {
      const r = await post<{ run: string }>("work", running ? {
        kind: "request", title: `Month-to-date report for ${label}`,
        text: `Finance: ${label} has not ended. Reconcile with the vault, then file a MONTH-TO-DATE report for ${month} with save_monthly_report. Begin your notes with "Provisional, month to date as of today: not a closed month" and say what a person should check.`,
      } : {
        kind: "request", title: `Close the books for ${label}`,
        text: `Finance: run the monthly_close procedure for ${month}. Reconcile with the vault first, then file the report with save_monthly_report and your notes.`,
      });
      router.push(`/work/${r.run}`);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  }
  return (
    <>
      <Button size="sm" onClick={go} disabled={busy}>{busy ? <Loader2 className="animate-spin" /> : <Sparkles />}{running ? "Ask Finance for a month-to-date report" : `Ask Finance to close ${label}`}</Button>
      {error && <p className="text-xs text-bad">{error}</p>}
    </>
  );
}
