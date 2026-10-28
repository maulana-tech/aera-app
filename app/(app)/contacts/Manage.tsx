"use client";

import { Check, Copy, Mail, MessageCircle, Pencil, Phone, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import type { Contact, Notification } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

const ROLES = ["planner", "buyer", "procurement_lead", "qa", "oem"];
// What a person can ask to be told about. The first five are raised by people;
// the rest by the watchers (jobs.py), and "digest" is the morning summary.
const KINDS = [
  "port_closure", "quality_hold", "customs_hold", "demand_spike", "supplier_failure",
  "seismic", "earthquake", "tropical_cyclone", "flood", "volcano", "wildfire", "drought",
  "port_weather", "plant_weather", "exposure", "certificate_lapse", "digest",
];

const when = (t: string) =>
  new Date(t).toLocaleString("en-GB", {
    timeZone: "Asia/Jakarta", day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });

const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";

/** wa.me wants the number in international form without the plus: an
 * Indonesian 08… becomes 628…. */
const whatsapp = (phone: string) => {
  const digits = phone.replace(/\D/g, "");
  return `https://wa.me/${digits.startsWith("0") ? "62" + digits.slice(1) : digits}`;
};

const pill = (on: boolean) =>
  `rounded-full border px-3 py-1 font-mono text-[11px] transition-colors ${
    on ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30"
  }`;

type Draft = {
  name: string; email: string; role: string; notify: string[];
  phone: string; title: string; department: string; notes: string;
};

const blank: Draft = {
  name: "", email: "", role: ROLES[0], notify: [], phone: "", title: "", department: "", notes: "",
};

const fromContact = (c: Contact): Draft => ({
  name: c.name, email: c.email, role: c.role,
  notify: c.notify_for === "*" ? [] : c.notify_for.split(",").filter(Boolean),
  phone: c.phone ?? "", title: c.title ?? "", department: c.department ?? "", notes: c.notes ?? "",
});

/* One form for adding and for changing a contact. Name, email and role are
 * what an alert needs; the rest is how to reach a person when it cannot wait
 * for email, and none of it is sent anywhere by SIGAP. */
function ContactForm({ initial, submitLabel, onSave, onCancel }: {
  initial: Draft; submitLabel: string;
  onSave: (d: Draft) => Promise<void>; onCancel?: () => void;
}) {
  const [d, setD] = useState<Draft>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k: keyof Draft) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setD({ ...d, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSave(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  const field = (k: keyof Draft, label: string, props: React.ComponentProps<typeof Input> = {}) => (
    <label className="block">
      <span className="text-muted-foreground text-xs">{label}</span>
      <Input value={d[k] as string} onChange={set(k)} className="mt-1.5" {...props} />
    </label>
  );

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2">
        {field("name", "Name", { required: true })}
        {field("email", "Email", { type: "email", required: true })}
        {field("phone", "Phone", { type: "tel", placeholder: "+62 812 3456 7890" })}
        {field("title", "Job title", { placeholder: "Buyer, steel and coil" })}
        {field("department", "Department", { placeholder: "Procurement" })}
      </div>

      <div>
        <span className="text-muted-foreground text-xs">Role</span>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {ROLES.map((r) => (
            <button key={r} type="button" onClick={() => setD({ ...d, role: r })} className={pill(d.role === r)}>
              {r}
            </button>
          ))}
        </div>
      </div>

      <div>
        <span className="text-muted-foreground text-xs">Notified about</span>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {KINDS.map((k) => {
            const on = d.notify.includes(k);
            return (
              <button key={k} type="button" className={pill(on)}
                onClick={() => setD({ ...d, notify: on ? d.notify.filter((x) => x !== k) : [...d.notify, k] })}>
                {k}
              </button>
            );
          })}
        </div>
        <p className="text-muted-foreground mt-1.5 text-xs">
          Selecting none means every kind, and the morning digest.
        </p>
      </div>

      <label className="block">
        <span className="text-muted-foreground text-xs">Notes</span>
        <textarea value={d.notes} onChange={set("notes")} rows={3} maxLength={1000}
          placeholder="When to call rather than email, who covers for them…"
          className="border-input bg-background mt-1.5 w-full rounded-md border px-3 py-2 text-sm" />
      </label>

      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy}>{busy ? "Saving…" : submitLabel}</Button>
        {onCancel && <Button type="button" size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>}
      </div>
    </form>
  );
}

async function save(path: string, d: Draft) {
  const res = await fetch(`/api/sigap/${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name: d.name, email: d.email, role: d.role, notify_for: d.notify.join(",") || "*",
      phone: d.phone, title: d.title, department: d.department, notes: d.notes,
    }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error ?? "failed");
  return body;
}

export function AddContact() {
  const router = useRouter();
  const [key, setKey] = useState(0);
  return (
    <div className="rounded-lg border p-5">
      <h2 className="mb-4 text-sm font-medium">Add a contact</h2>
      <ContactForm key={key} initial={blank} submitLabel="Add contact"
        onSave={async (d) => {
          await save("contacts", d);
          setKey(key + 1);              // a fresh, empty form
          router.refresh();
        }} />
    </div>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button variant="ghost" size="icon-sm" aria-label={`Copy ${label}`}
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1500);
      }}>
      {done ? <Check /> : <Copy />}
    </Button>
  );
}

function Reach({ icon, label, value, href, extra }: {
  icon: React.ReactNode; label: string; value: string | null | undefined;
  href?: string; extra?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="text-muted-foreground">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-muted-foreground text-[11px]">{label}</p>
        {value ? (
          <a href={href} className="block truncate font-mono text-sm hover:underline">{value}</a>
        ) : (
          <p className="text-muted-foreground text-sm">not on file</p>
        )}
      </div>
      {value && extra}
      {value && <CopyButton text={value} label={label.toLowerCase()} />}
    </div>
  );
}

/* A contact opened: how to reach them, what they are told, and what SIGAP
 * has actually sent them, read fresh each time it opens. */
function ContactDetail({ contact, open, onOpenChange, canChange }: {
  contact: Contact; open: boolean; onOpenChange: (v: boolean) => void; canChange: boolean;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [sent, setSent] = useState<Notification[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    let live = true;
    fetch(`/api/sigap/contacts/${contact.id}`)
      .then((r) => r.json())
      .then((d) => live && setSent(d.sent ?? []))
      .catch(() => live && setSent([]));
    return () => { live = false; };
  }, [open, contact.id]);

  async function remove() {
    setBusy(true);
    setError("");
    const res = await fetch(`/api/sigap/contacts/${contact.id}/delete`, { method: "POST" });
    setBusy(false);
    if (!res.ok) {
      setError((await res.json()).error ?? "failed");
      return;
    }
    onOpenChange(false);
    router.refresh();
  }

  const kinds = contact.notify_for === "*" ? null : contact.notify_for.split(",").filter(Boolean);
  return (
    <Dialog open={open} onOpenChange={(v) => { onOpenChange(v); if (!v) setEditing(false); }}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader className="border-b">
          <div className="flex items-center gap-3">
            <span className="bg-muted flex size-11 shrink-0 items-center justify-center rounded-full text-sm font-medium">
              {initials(contact.name)}
            </span>
            <div className="min-w-0">
              <DialogTitle className="truncate">{contact.name}</DialogTitle>
              <DialogDescription className="truncate text-xs">
                {[contact.title, contact.department].filter(Boolean).join(" · ") || "No job title on file"}
              </DialogDescription>
            </div>
            <span className="ml-auto rounded-full border px-2.5 py-0.5 font-mono text-[10px]">{contact.role}</span>
          </div>
        </DialogHeader>

        <div className="overflow-y-auto px-5 py-4">
          {editing ? (
            <ContactForm initial={fromContact(contact)} submitLabel="Save changes"
              onCancel={() => setEditing(false)}
              onSave={async (d) => {
                await save(`contacts/${contact.id}`, d);
                setEditing(false);
                router.refresh();
              }} />
          ) : (
            <div className="space-y-5">
              <div className="divide-y rounded-lg border px-3">
                <Reach icon={<Mail className="size-4" />} label="Email" value={contact.email}
                  href={`mailto:${contact.email}`} />
                <Reach icon={<Phone className="size-4" />} label="Phone" value={contact.phone}
                  href={contact.phone ? `tel:${contact.phone.replace(/[^\d+]/g, "")}` : undefined}
                  extra={contact.phone && (
                    <Button asChild variant="ghost" size="icon-sm" aria-label="WhatsApp">
                      <a href={whatsapp(contact.phone)} target="_blank" rel="noopener noreferrer">
                        <MessageCircle />
                      </a>
                    </Button>
                  )} />
              </div>

              <div>
                <p className="text-muted-foreground text-xs">Notified about</p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {kinds ? kinds.map((k) => (
                    <span key={k} className="rounded-full border px-2.5 py-0.5 font-mono text-[10px]">{k}</span>
                  )) : <span className="text-sm">every kind of disruption, and the morning digest</span>}
                </div>
              </div>

              {contact.notes && (
                <div>
                  <p className="text-muted-foreground text-xs">Notes</p>
                  <p className="mt-1 text-sm leading-relaxed whitespace-pre-wrap">{contact.notes}</p>
                </div>
              )}

              <div>
                <p className="text-muted-foreground text-xs">Sent to {contact.name.split(" ")[0]}</p>
                {sent === null ? (
                  <p className="text-muted-foreground mt-1.5 text-xs">Reading…</p>
                ) : sent.length === 0 ? (
                  <p className="text-muted-foreground mt-1.5 text-sm">Nothing yet.</p>
                ) : (
                  <ul className="mt-1.5 divide-y rounded-lg border">
                    {sent.map((n) => (
                      <li key={n.id} className="px-3 py-2">
                        <div className="flex min-w-0 items-center gap-2">
                          <StatusBadge status={n.status} />
                          <p className="min-w-0 flex-1 truncate text-sm">{n.subject}</p>
                        </div>
                        <p className="text-muted-foreground mt-0.5 font-mono text-[10px]">
                          {n.kind} · {when(n.created_at)} WIB
                          {n.attachments && n.attachments.length > 0 &&
                            ` · ${n.attachments.map((a) => a.format.toUpperCase()).join(" + ")}`}
                        </p>
                        {n.error && n.status !== "sent" && (
                          <p className="text-muted-foreground mt-0.5 text-[11px] break-words">{n.error}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <p className="text-muted-foreground font-mono text-[10px]">
                {contact.created_at && `added ${when(contact.created_at)} WIB`}
                {contact.updated_at && ` · changed ${when(contact.updated_at)} WIB`}
              </p>
            </div>
          )}
        </div>

        {canChange && !editing && (
          <div className="flex items-center gap-2 border-t px-5 py-3">
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="size-3.5" />
              Edit
            </Button>
            <Button size="sm" variant="ghost" className="text-destructive" disabled={busy} onClick={remove}>
              <Trash2 className="size-3.5" />
              Remove
            </Button>
            {error && <p className="text-destructive text-xs">{error}</p>}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function ContactList({ contacts, canDelete }: { contacts: Contact[]; canDelete: boolean }) {
  const [openId, setOpenId] = useState<string | null>(null);
  if (!contacts.length) {
    return (
      <p className="text-muted-foreground mt-3 rounded-lg border border-dashed p-5 text-sm">
        No contacts yet. Without these, an agent&apos;s recommendation reaches nobody.
      </p>
    );
  }
  return (
    <ul className="mt-3 grid gap-2 sm:grid-cols-2">
      {contacts.map((c) => (
        <li key={c.id}>
          <button type="button" onClick={() => setOpenId(c.id)}
            className="hover:border-foreground/30 flex w-full items-start gap-3 rounded-lg border px-4 py-3 text-left transition-colors">
            <span className="bg-muted flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-medium">
              {initials(c.name)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm">{c.name}</span>
              <span className="text-muted-foreground block truncate text-xs">
                {[c.title, c.department].filter(Boolean).join(" · ") || c.role}
              </span>
              <span className="text-muted-foreground mt-1 block truncate font-mono text-[10px]">
                {c.email}{c.phone && ` · ${c.phone}`}
              </span>
              <span className="text-muted-foreground mt-0.5 block truncate font-mono text-[10px]">
                {c.notify_for === "*" ? "every kind" : c.notify_for.split(",").join(" · ")}
              </span>
            </span>
          </button>
          <ContactDetail contact={c} open={openId === c.id}
            onOpenChange={(v) => setOpenId(v ? c.id : null)} canChange={canDelete} />
        </li>
      ))}
    </ul>
  );
}
