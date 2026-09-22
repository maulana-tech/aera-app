"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";

type Verdict = "approved" | "rejected" | "escalated";

export default function Decision({ actionId, valueIdr, limitIdr }: {
  actionId: string; valueIdr: number; limitIdr: number;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<Verdict | null>(null);
  const [error, setError] = useState("");
  const beyondAuthority = limitIdr <= 0 || valueIdr > limitIdr;

  async function send(decision: Verdict) {
    setBusy(decision);
    setError("");
    try {
      // Identity is NOT sent from here — the server takes it from the session token.
      const res = await fetch(`/api/sigap/actions/${actionId}/decision`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ decision }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "failed");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-3">
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={!!busy || beyondAuthority}
          onClick={() => send("approved")}
        >
          {busy === "approved" ? "Sending…" : "Approve"}
        </Button>
        <Button
          variant="outline" size="sm" disabled={!!busy}
          onClick={() => send("escalated")}
        >
          Escalate
        </Button>
        <Button
          variant="ghost" size="sm" className="text-destructive" disabled={!!busy}
          onClick={() => send("rejected")}
        >
          Reject
        </Button>
      </div>
      {beyondAuthority && (
        <p className="text-muted-foreground mt-2 text-[11px] leading-relaxed">
          Beyond your authority{limitIdr > 0 && ` (limit Rp ${limitIdr.toLocaleString("en-US")})`}.
          Use Escalate.
        </p>
      )}
      {error && <p className="mt-2 font-mono text-xs text-rose-700 dark:text-rose-400">{error}</p>}
    </div>
  );
}
