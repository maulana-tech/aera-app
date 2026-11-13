"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { LeadStage } from "@/app/lib";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";

/* A person closes a lead, marks it interested, or records that it asked to stop (final). */
export function LeadActions({ id, stage }: { id: string; stage: LeadStage }) {
  const router = useRouter();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  if (stage === "opted_out") {
    return <p className="text-muted-foreground text-xs">This person asked not to be contacted. Nobody writes to them again.</p>;
  }
  const set = async (to: "interested" | "lost" | "opted_out") => {
    if (to === "opted_out" && !window.confirm("Record that this person asked not to be contacted? This cannot be undone here.")) return;
    setBusy(to);
    setError("");
    try {
      await post(`leads/${id}`, { stage: to });
      router.refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy("");
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      {stage !== "interested" && stage !== "won" && (
        <Button size="sm" variant="outline" disabled={!!busy} onClick={() => set("interested")}>Mark interested</Button>
      )}
      {stage !== "lost" && stage !== "won" && (
        <Button size="sm" variant="outline" disabled={!!busy} onClick={() => set("lost")}>Close as lost</Button>
      )}
      <Button size="sm" variant="outline" disabled={!!busy} onClick={() => set("opted_out")}>They asked to stop</Button>
      {error && <p className="w-full text-xs text-bad">{error}</p>}
    </div>
  );
}

/* Paste an e-mail that came in, when no inbox is connected. */
export function PasteReply() {
  const router = useRouter();
  const [from, setFrom] = useState("");
  const [subject, setSubject] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState("");
  return (
    <form className="space-y-2" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true);
      setSaid("");
      try {
        const r = await post<{ stored: boolean; kind?: string; why?: string; opted_out?: boolean; work_item_id?: string }>(
          "inbound", { from, subject, text });
        setSaid(!r.stored ? (r.why ?? "not stored")
          : r.opted_out ? "Opted out: nobody writes to this address again."
          : r.work_item_id ? "Handed to the team as work." : `Stored (${r.kind?.replace("_", " ")}).`);
        if (r.stored) { setFrom(""); setSubject(""); setText(""); }
        router.refresh();
      } catch (err) {
        setSaid(errorText(err));
      } finally {
        setBusy(false);
      }
    }}>
      <Input placeholder="From (name <address>)" value={from} onChange={(e) => setFrom(e.target.value)} required />
      <Input placeholder="Subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
      <textarea placeholder="What they wrote" value={text} onChange={(e) => setText(e.target.value)} required rows={4}
        className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm" />
      <Button size="sm" type="submit" disabled={busy}>{busy ? "Saving…" : "Add the reply"}</Button>
      {said && <p className="text-muted-foreground text-xs">{said}</p>}
    </form>
  );
}
