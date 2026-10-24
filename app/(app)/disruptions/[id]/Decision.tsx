"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";

type Verdict = "approved" | "rejected" | "escalated";

export default function Decision({ actionId, valueIdr, limitIdr, role, approvers }: {
  actionId: string; valueIdr: number; limitIdr: number;
  /** For a message that leaves the company: the roles that may approve it. */
  role?: string; approvers?: string[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<Verdict | null>(null);
  const [error, setError] = useState("");
  const notYours = !!approvers && !approvers.includes(role ?? "");
  const beyondAuthority = limitIdr <= 0 || valueIdr > limitIdr || notYours;

  async function send(decision: Verdict) {
    setBusy(decision);
    setError("");
    try {
      // Identity is NOT sent from here. The server takes it from the session token.
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
      {notYours ? (
        <p className="text-muted-foreground mt-2 text-[11px] leading-relaxed">
          This goes outside the company, so a {approvers![0].replace("_", " ")} approves it.
          Use Escalate.
        </p>
      ) : beyondAuthority && (
        <p className="text-muted-foreground mt-2 text-[11px] leading-relaxed">
          Beyond your authority{limitIdr > 0 && ` (limit Rp ${limitIdr.toLocaleString("en-US")})`}.
          Use Escalate.
        </p>
      )}
      {error && <p className="mt-2 font-mono text-xs text-rose-700 dark:text-rose-400">{error}</p>}
    </div>
  );
}
