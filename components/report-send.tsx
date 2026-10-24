"use client";

import { Mail } from "lucide-react";
import { useEffect, useState } from "react";

import type { Contact } from "@/app/lib";
import { Button } from "@/components/ui/button";
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger,
} from "@/components/ui/sheet";

/* A report by email, with its files attached. Only to people on the Contacts
 * page, or to yourself: a report carries what was decided and what it is
 * worth, and the contact list is where an admin or a procurement lead chose
 * who may read that. The agent service renders the files when it sends, from
 * the record as it then stands. `base` is the API path, as for ReportFiles:
 * "reports/run_x" or "portfolio". */
export function ReportSend({ base, title, excel = true }: { base: string; title: string; excel?: boolean }) {
  const [open, setOpen] = useState(false);
  const [contacts, setContacts] = useState<Contact[] | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [me, setMe] = useState(false);
  const [formats, setFormats] = useState<string[]>(["pdf"]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || contacts) return;
    fetch("/api/sigap/contacts")
      .then((r) => r.json())
      .then((d) => setContacts(d.contacts ?? []))
      .catch(() => setError("The contact list could not be read."));
  }, [open, contacts]);

  const flip = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  async function send() {
    setBusy(true);
    setError("");
    setResult("");
    try {
      const res = await fetch(`/api/sigap/${base}/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contacts: chosen, me, formats, note }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "failed");
      setResult(`Queued to ${d.to.join(", ")} · ${d.delivery}`);
      setChosen([]);
      setMe(false);
      setNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  const nobody = chosen.length === 0 && !me;
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm">
          <Mail className="size-3.5" />
          Send by email
        </Button>
      </SheetTrigger>
      <SheetContent
        side="right"
        className="flex w-full data-[side=right]:w-full flex-col gap-0 p-0 sm:data-[side=right]:max-w-[480px]"
      >
        <SheetHeader className="border-b px-5 py-3.5">
          <SheetTitle className="text-sm font-medium">Send by email</SheetTitle>
          <SheetDescription className="text-xs">{title}</SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-4">
          <fieldset>
            <legend className="text-sm font-medium">To</legend>
            <p className="text-muted-foreground mt-1 text-xs">
              People on the Contacts page. To add someone, ask an admin or a procurement lead.
            </p>
            <ul className="mt-2 divide-y rounded-lg border">
              <li>
                <label className="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm">
                  <input type="checkbox" checked={me} onChange={() => setMe(!me)} />
                  Me
                </label>
              </li>
              {contacts === null ? (
                <li className="text-muted-foreground px-3 py-2 text-xs">Reading contacts…</li>
              ) : contacts.length === 0 ? (
                <li className="text-muted-foreground px-3 py-2 text-xs">No contacts yet.</li>
              ) : (
                contacts.map((c) => (
                  <li key={c.id}>
                    <label className="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm">
                      <input type="checkbox" checked={chosen.includes(c.id)}
                        onChange={() => setChosen(flip(chosen, c.id))} />
                      <span className="min-w-0 flex-1 truncate">{c.name}</span>
                      <span className="text-muted-foreground truncate font-mono text-[10px]">
                        {c.role} · {c.email}
                      </span>
                    </label>
                  </li>
                ))
              )}
            </ul>
          </fieldset>

          <fieldset>
            <legend className="text-sm font-medium">Attach</legend>
            <div className="mt-2 flex gap-4 text-sm">
              {[["pdf", "PDF"], ...(excel ? [["xlsx", "Excel workbook"]] : [])].map(([v, l]) => (
                <label key={v} className="flex cursor-pointer items-center gap-2">
                  <input type="checkbox" checked={formats.includes(v)} onChange={() => setFormats(flip(formats, v))} />
                  {l}
                </label>
              ))}
            </div>
          </fieldset>

          <label className="block">
            <span className="text-sm font-medium">Note</span>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={4} maxLength={2000}
              placeholder="Optional, above the report's link in the email."
              className="border-input bg-background mt-2 w-full rounded-md border px-3 py-2 text-sm" />
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t px-5 py-3">
          <Button type="button" size="sm" disabled={busy || nobody || formats.length === 0} onClick={send}>
            {busy ? "Sending…" : "Send"}
          </Button>
          {result && <p className="text-muted-foreground min-w-0 flex-1 text-xs">{result}</p>}
          {error && <p className="text-destructive min-w-0 flex-1 text-xs">{error}</p>}
        </div>
      </SheetContent>
    </Sheet>
  );
}
