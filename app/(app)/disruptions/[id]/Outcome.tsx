"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { idr, wib } from "@/app/lib";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/status-badge";

/**
 * What actually happened, from store.OUTCOMES. Copied rather than fetched, the
 * same way the upload page copies its column lists; the server is still the
 * authority and rejects anything else.
 */
const OUTCOMES = ["delivered", "late", "short", "failed", "cancelled"] as const;

export default function Outcome({ actionId, predictedIdr, outcome, outcomeAt, detail }: {
  actionId: string;
  predictedIdr: number;
  /** Null until somebody has read reality. Recorded once; never edited. */
  outcome?: string | null;
  outcomeAt?: string | null;
  detail?: Record<string, unknown> | null;
}) {
  const router = useRouter();
  const [chosen, setChosen] = useState<string | null>(null);
  const [cost, setCost] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Already recorded: show it, and offer nothing to change.
  if (outcome) {
    const actual = typeof detail?.actual_idr === "number" ? detail.actual_idr : null;
    const delta = actual !== null && predictedIdr > 0 ? actual - predictedIdr : null;
    const by = typeof detail?.recorded_by === "string" ? detail.recorded_by : null;
    const said = typeof detail?.note === "string" ? detail.note : null;
    return (
      <div className="mt-3 border-t pt-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">What happened</span>
          <StatusBadge status={outcome} />
          {actual !== null ? (
            <span className="font-mono text-[11px]">
              actual {idr(actual)}
              {predictedIdr > 0 && ` · predicted ${idr(predictedIdr)}`}
              {delta !== null && (
                <span className={delta > 0 ? "text-amber-700 dark:text-amber-400" : "text-emerald-700 dark:text-emerald-400"}>
                  {" "}({delta > 0 ? "+" : ""}{idr(delta)})
                </span>
              )}
            </span>
          ) : (
            <span className="text-muted-foreground text-[11px]">
              realized cost not known
            </span>
          )}
        </div>
        {said && <p className="text-muted-foreground mt-1.5 text-[11px] leading-relaxed">{said}</p>}
        <p className="text-muted-foreground mt-1.5 text-[11px] leading-relaxed">
          Recorded once{outcomeAt && ` on ${wib(outcomeAt)}`}
          {by && ` by ${by}`}. A correction is a new reading of reality, not an edit of this one.
        </p>
      </div>
    );
  }

  const costGiven = cost.trim() !== "";
  const costBad = costGiven && !Number.isFinite(Number(cost));

  async function send() {
    setBusy(true);
    setError("");
    try {
      // Identity is NOT sent from here. The server takes it from the session token.
      const res = await fetch(`/api/aera/actions/${actionId}/outcome`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          outcome: chosen,
          ...(note.trim() ? { detail: { note: note.trim() } } : {}),
          // A number or nothing: the raw string is never sent, so no scale is
          // ever guessed for it on the way in.
          ...(costGiven ? { actual_cost_idr: Number(cost) } : {}),
        }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "failed");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 border-t pt-3">
      <p className="text-muted-foreground text-xs">
        This went out. What actually happened?
      </p>

      <div className="mt-2 flex flex-wrap gap-2">
        {OUTCOMES.map((o) => (
          <button
            key={o}
            type="button"
            onClick={() => setChosen(o)}
            className={`rounded-full border px-3 py-1 font-mono text-[11px] transition-colors ${
              chosen === o
                ? "bg-primary text-primary-foreground border-primary"
                : "hover:border-foreground/30"
            }`}
          >
            {o}
          </button>
        ))}
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <div>
          <label className="text-muted-foreground text-[11px]" htmlFor={`cost-${actionId}`}>
            Actual cost (Rp), if you have the figure
          </label>
          <Input
            id={`cost-${actionId}`}
            type="number"
            inputMode="numeric"
            value={cost}
            onChange={(e) => setCost(e.target.value)}
            placeholder={predictedIdr > 0 ? `predicted ${predictedIdr}` : ""}
            className="mt-1 font-mono text-xs"
          />
        </div>
        <div>
          <label className="text-muted-foreground text-[11px]" htmlFor={`note-${actionId}`}>
            What was seen (arrival date, quantity)
          </label>
          <Input
            id={`note-${actionId}`}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="arrived 3 Oct, 55 t"
            className="mt-1 text-xs"
          />
        </div>
      </div>

      <p className="text-muted-foreground mt-2 max-w-xl text-[11px] leading-relaxed">
        Leave the cost blank if you do not know it. The report will say the realized cost is
        not known rather than show a guess, and a figure written into the note stays a note:
        nothing reads money out of a sentence.
      </p>

      <div className="mt-2 flex items-center gap-3">
        <Button size="sm" disabled={busy || !chosen || costBad} onClick={send}>
          {busy ? "Recording…" : "Record what happened"}
        </Button>
        {costBad && (
          <span className="text-destructive text-[11px]">That is not a number.</span>
        )}
      </div>
      {error && <p className="mt-2 font-mono text-xs text-rose-700 dark:text-rose-400">{error}</p>}
    </div>
  );
}
