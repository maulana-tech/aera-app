"use client";

import { AlertTriangle, Check, Copy, Mail, MessageCircle, Pencil, Phone, Trash2, Wallet } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { CONTACT_ROLES, explorer, when as stamp, type Contact, type Notification } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

const ROLES = CONTACT_ROLES;
// What a team member or approver can ask to be told about: work of each kind
// as it finishes, is held or fails (notify.py), and the morning digest.
const KINDS = ["order", "request", "goal", "payable", "digest"];
/** Only these roles are alerted; the rest are counterparties. */
const ALERTED = new Set(["team", "approver"]);
/** Where a vendor is paid. "near" pays the NEAR account straight from the vault;
 *  the others are USDC on another chain, quoted and routed through NEAR Intents
 *  (tools/money.py, quote_cross_chain_payment). */
const CHAINS: { v: string; l: string }[] = [
  { v: "near", l: "NEAR (USDC from the vault)" },
  { v: "base", l: "Base (USDC, via NEAR Intents)" },
  { v: "arb", l: "Arbitrum (USDC, via NEAR Intents)" },
  { v: "eth", l: "Ethereum (USDC, via NEAR Intents)" },
  { v: "sol", l: "Solana (USDC, via NEAR Intents)" },
];

const when = (t: string) => stamp(t);

/** The guardian asks a person about any payout changed in the last 14 days (core/guardian.py). */
const RECENT_DAYS = 14;
const changedRecently = (t?: string | null) =>
  !!t && Date.now() - Date.parse(t) < RECENT_DAYS * 86_400_000;

const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";

/** wa.me wants the number in international form, digits only. */
const whatsapp = (phone: string) => `https://wa.me/${phone.replace(/\D/g, "")}`;

const pill = (on: boolean) =>
  `rounded-full border px-3 py-1 font-mono text-[11px] transition-colors ${
    on ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30"
  }`;

type Draft = {
  name: string; email: string; role: string; notify: string[];
  phone: string; title: string; department: string; notes: string;
  near_account: string; payout_chain: string; payout_address: string;
};

const blank: Draft = {
  name: "", email: "", role: "team", notify: [], phone: "", title: "", department: "", notes: "",
  near_account: "", payout_chain: "near", payout_address: "",
};

const fromContact = (c: Contact): Draft => ({
  name: c.name, email: c.email, role: c.role,
  notify: c.notify_for === "*" ? [] : c.notify_for.split(",").filter(Boolean),
  phone: c.phone ?? "", title: c.title ?? "", department: c.department ?? "", notes: c.notes ?? "",
  near_account: c.near_account ?? "", payout_chain: c.payout_chain ?? "near", payout_address: c.payout_address ?? "",
});

const PAYOUT = ["near_account", "payout_chain", "payout_address"] as const;

/* One form for adding and for changing a contact. Name, email and role are
 * what an alert needs; the rest is how to reach a person when it cannot wait
 * for email, and none of it is sent anywhere by AERA. */
function ContactForm({ initial, submitLabel, onSave, onCancel, payoutEditable, changedAt }: {
  initial: Draft; submitLabel: string;
  onSave: (d: Draft) => Promise<void>; onCancel?: () => void;
  /** Where money goes: only an owner changes it. */
  payoutEditable: boolean;
  changedAt?: string | null;
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
        {field("phone", "Phone", { type: "tel", placeholder: "+1 555 010 0100" })}
        {field("title", "Job title", { placeholder: "Data vendor, account manager" })}
        {field("department", "Department", { placeholder: "Operations" })}
      </div>

      <fieldset className="rounded-lg border p-3">
        <legend className="text-muted-foreground px-1 text-xs">Payout details · where money to this contact goes</legend>
        {changedRecently(changedAt) && (
          <p className="mb-2 inline-flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400">
            <AlertTriangle className="size-3.5" />
            Changed recently ({when(changedAt!)}): the guardian sends any payment here to a person.
          </p>
        )}
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block">
            <span className="text-muted-foreground text-xs">Paid on</span>
            <select value={d.payout_chain} disabled={!payoutEditable} onChange={(e) => setD({ ...d, payout_chain: e.target.value })}
              className="border-input bg-background focus-visible:ring-ring/50 mt-1.5 h-8 w-full rounded-lg border px-2 text-sm outline-none focus-visible:ring-3 disabled:opacity-50 dark:bg-input/30">
              {CHAINS.map((c) => <option key={c.v} value={c.v}>{c.l}</option>)}
              {!CHAINS.some((c) => c.v === d.payout_chain) && <option value={d.payout_chain}>{d.payout_chain}</option>}
            </select>
          </label>
          {field("near_account", "NEAR account", { placeholder: "vendor.testnet", disabled: !payoutEditable })}
          {field("payout_address", d.payout_chain === "near" ? "Address on another chain (not used for NEAR)" : `Payout address on ${d.payout_chain}`, {
            placeholder: d.payout_chain === "sol" ? "Solana address" : "0x…",
            disabled: !payoutEditable || d.payout_chain === "near",
          })}
        </div>
        <p className="text-muted-foreground mt-2 text-[11px] leading-relaxed">
          {payoutEditable
            ? "A payment tool reads the address from here, never from a message or a model. Changing it is stamped, and the guardian treats a recent change as a reason to ask a person."
            : "Only an owner can change where money goes."}
        </p>
      </fieldset>

      <div>
        <span className="text-muted-foreground text-xs">Role</span>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {ROLES.map((r) => (
            <button key={r} type="button" onClick={() => setD({ ...d, role: r })} className={pill(d.role === r)} aria-pressed={d.role === r}>
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
              <button key={k} type="button" className={pill(on)} aria-pressed={on}
                onClick={() => setD({ ...d, notify: on ? d.notify.filter((x) => x !== k) : [...d.notify, k] })}>
                {k}
              </button>
            );
          })}
        </div>
        <p className="text-muted-foreground mt-1.5 text-xs">
          Selecting none means every kind, and the morning digest. Only team members and approvers are alerted.
        </p>
      </div>

      <label className="block">
        <span className="text-muted-foreground text-xs">Notes</span>
        <textarea value={d.notes} onChange={set("notes")} rows={3} maxLength={1000}
          placeholder="What they do for the business, when to call rather than email…"
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

/** Payout fields go only when they changed (and only from an owner), so an
 *  edit to a phone number never restamps address_changed_at. */
async function save(path: string, d: Draft, before?: Draft, payoutEditable = false) {
  const payout = payoutEditable
    ? Object.fromEntries(PAYOUT.filter((k) => !before || d[k] !== before[k]).map((k) => [k, d[k]]))
    : {};
  const res = await fetch(`/api/aera/${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name: d.name, email: d.email, role: d.role, notify_for: d.notify.join(",") || "*",
      phone: d.phone, title: d.title, department: d.department, notes: d.notes, ...payout,
    }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error ?? "failed");
  return body;
}

export function AddContact({ payoutEditable }: { payoutEditable: boolean }) {
  const router = useRouter();
  const [key, setKey] = useState(0);
  return (
    <div className="rounded-lg border p-5">
      <h2 className="mb-4 text-sm font-medium">Add a contact</h2>
      <ContactForm key={key} initial={blank} submitLabel="Add contact" payoutEditable={payoutEditable}
        onSave={async (d) => {
          await save("contacts", d, undefined, payoutEditable);
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

/* A contact opened: how to reach them, what they are told, and what AERA
 * has actually sent them, read fresh each time it opens. */
function ContactDetail({ contact, open, onOpenChange, canChange, payoutEditable }: {
  contact: Contact; open: boolean; onOpenChange: (v: boolean) => void; canChange: boolean;
  payoutEditable: boolean;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [sent, setSent] = useState<Notification[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    let live = true;
    fetch(`/api/aera/contacts/${contact.id}`)
      .then((r) => r.json())
      .then((d) => live && setSent(d.sent ?? []))
      .catch(() => live && setSent([]));
    return () => { live = false; };
  }, [open, contact.id]);

  async function remove() {
    if (!window.confirm(`Remove ${contact.name}? The team can no longer pay or alert them, and their payout details are deleted.`)) return;
    setBusy(true);
    setError("");
    const res = await fetch(`/api/aera/contacts/${contact.id}/delete`, { method: "POST" });
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
              payoutEditable={payoutEditable} changedAt={contact.address_changed_at}
              onCancel={() => setEditing(false)}
              onSave={async (d) => {
                await save(`contacts/${contact.id}`, d, fromContact(contact), payoutEditable);
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
                <Reach icon={<Wallet className="size-4" />} label="NEAR account" value={contact.near_account}
                  href={contact.near_account ? explorer(contact.near_account.endsWith(".near") ? "mainnet" : "testnet", "address", contact.near_account) : undefined} />
                {contact.payout_address && (
                  <Reach icon={<Wallet className="size-4" />} label={`Payout on ${contact.payout_chain ?? "?"}`} value={contact.payout_address} />
                )}
              </div>
              {changedRecently(contact.address_changed_at) && (
                <p className="inline-flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="size-3.5" />
                  Payout details changed {when(contact.address_changed_at!)}. Payments here wait for a person for {RECENT_DAYS} days.
                </p>
              )}

              <div>
                <p className="text-muted-foreground text-xs">Notified about</p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {kinds ? kinds.map((k) => (
                    <span key={k} className="rounded-full border px-2.5 py-0.5 font-mono text-[10px]">{k}</span>
                  )) : <span className="text-sm">{ALERTED.has(contact.role) ? "every kind of work, and the morning digest" : "nothing: only team members and approvers are alerted"}</span>}
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
                          {n.kind} · {when(n.created_at)}
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
                {contact.created_at && `added ${when(contact.created_at)}`}
                {contact.updated_at && ` · changed ${when(contact.updated_at)}`}
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

export function ContactList({ contacts, canDelete, payoutEditable }: {
  contacts: Contact[]; canDelete: boolean; payoutEditable: boolean;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  if (!contacts.length) {
    return (
      <p className="text-muted-foreground mt-3 rounded-lg border border-dashed p-5 text-sm">
        No contacts yet. Vendors need a payout account on record before the team can pay them, and team members here are who gets alerted.
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
                {c.payout_chain && c.payout_chain !== "near" && c.payout_address
                  ? `payout on ${c.payout_chain} ${c.payout_address.slice(0, 10)}…`
                  : c.near_account ? `payout ${c.near_account}` : ALERTED.has(c.role) ? (c.notify_for === "*" ? "every kind" : c.notify_for.split(",").join(" · ")) : "no payout account"}
              </span>
              {changedRecently(c.address_changed_at) && (
                <span className="mt-0.5 block text-[10px] text-amber-700 dark:text-amber-400">payout changed recently</span>
              )}
            </span>
          </button>
          <ContactDetail contact={c} open={openId === c.id}
            onOpenChange={(v) => setOpenId(v ? c.id : null)} canChange={canDelete} payoutEditable={payoutEditable} />
        </li>
      ))}
    </ul>
  );
}
