"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Delivery } from "@/app/lib";
import { Button } from "@/components/ui/button";

/** Who may approve a message that leaves the company. Mirrors outreach.py:
 * the server refuses anyone else, this only says so before the click. */
export const OUTWARD: Record<string, string[]> = {
  supplier_request: ["buyer", "procurement_lead", "admin"],
  customer_notice: ["procurement_lead", "admin"],
};

const when = (t: string) =>
  new Date(t).toLocaleString("en-GB", {
    timeZone: "Asia/Jakarta", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });

/* Where an approved supplier request or customer notice went, or why it did
 * not. Before approval it says where it would go, so the approver sees the
 * address, and outside production, that it goes to the test address instead. */
export function Outbound({ actionId, status, delivery, mayResend }: {
  actionId: string; status: string; delivery: Delivery; mayResend: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function resend() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/api/sigap/actions/${actionId}/resend`, { method: "POST" });
      const d = await res.json();
      if (!res.ok) throw new Error(d.why ?? d.error ?? "failed");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  let line: string;
  if (delivery.status === "sent") {
    line = `Emailed to ${delivery.to}${delivery.sent_at ? ` on ${when(delivery.sent_at)} WIB` : ""}.`;
  } else if (delivery.status === "pending") {
    line = `Queued for ${delivery.to}.`;
  } else if (delivery.status === "failed" || delivery.status === "skipped") {
    line = `Not delivered to ${delivery.to}: ${delivery.error ?? delivery.status}.`;
  } else if (delivery.to) {
    line = status === "pending"
      ? `Once approved, SIGAP emails it to ${delivery.to}${delivery.why ? ` (${delivery.why})` : ""}.`
      : `Will be emailed to ${delivery.to}.`;
  } else {
    line = status === "pending"
      ? `Once approved it will not be sent by SIGAP: ${delivery.why}.`
      : `Not sent: ${delivery.why}.`;
  }

  return (
    <div className="mt-3 rounded-md border border-dashed px-3 py-2">
      <p className="text-muted-foreground text-xs leading-relaxed">{line}</p>
      {status === "approved" && mayResend && (delivery.status === "failed" || delivery.status === "skipped") && (
        <Button size="sm" variant="outline" className="mt-2" disabled={busy} onClick={resend}>
          {busy ? "Sending…" : "Send again"}
        </Button>
      )}
      {error && <p className="mt-2 font-mono text-xs text-rose-700 dark:text-rose-400">{error}</p>}
    </div>
  );
}
