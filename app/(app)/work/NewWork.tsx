"use client";

import { Loader2, Plus, Send } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { WORK_KINDS, type WorkKind } from "@/app/lib";
import { Field, TextArea, pill } from "@/components/profile-editor";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";

const HINT: Record<WorkKind, string> = {
  request: "Something to do now: a question, a task, a message to answer.",
  goal: "A standing target the team works towards.",
  payable: "A bill or a cost the team should pay. It goes through Guardian and Treasurer.",
  order: "An order taken by hand. Paid orders normally arrive through checkout.",
};

/** Give the team something to do. Supervisor plans it the moment it is saved. */
export function NewWork({ disabled }: { disabled?: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<WorkKind>("request");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await post<{ work_item: string; run: string }>("work", { kind, title, text });
      router.push(`/work/${r.run}`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <Button size="sm" onClick={() => setOpen(true)} disabled={disabled}
        title={disabled ? "the kill switch is on" : undefined}>
        <Plus /> New request
      </Button>
    );
  }

  return (
    <form onSubmit={submit} className="w-full space-y-4 rounded-lg border p-4">
      <div className="flex flex-wrap gap-2">
        {WORK_KINDS.map((k) => (
          <button key={k} type="button" className={pill(kind === k)} onClick={() => setKind(k)} aria-pressed={kind === k}>{k}</button>
        ))}
      </div>
      <p className="text-muted-foreground text-xs">{HINT[kind]}</p>
      <Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required
        placeholder="Write this week's free sample brief" /></Field>
      <Field label="Details">
        <TextArea rows={4} value={text} onChange={(e) => setText(e.target.value)}
          placeholder="What you want, for whom, by when. The team reads this as instructions from you." />
      </Field>
      {error && <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy || !title.trim()}>
          {busy ? <Loader2 className="animate-spin" /> : <Send />}
          Give it to the team
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </form>
  );
}
