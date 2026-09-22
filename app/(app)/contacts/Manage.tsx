"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Contact } from "@/app/lib";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const ROLES = ["planner", "buyer", "procurement_lead", "qa", "oem"];
const KINDS = ["port_closure", "quality_hold", "customs_hold", "demand_spike", "supplier_failure"];

export function AddContact() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState(ROLES[0]);
  const [notifyFor, setNotifyFor] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/sigap/contacts", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name, email, role, notify_for: notifyFor.join(",") || "*" }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "failed");
      setName(""); setEmail(""); setNotifyFor([]);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border p-5">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">
            Name
          </span>
          <Input value={name} onChange={(e) => setName(e.target.value)} required className="mt-1.5" />
        </label>
        <label className="block">
          <span className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">
            Email
          </span>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="mt-1.5" />
        </label>
      </div>

      <div>
        <span className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">
          Role
        </span>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {ROLES.map((r) => (
            <button
              key={r} type="button" onClick={() => setRole(r)}
              className={`rounded-full border px-3 py-1 font-mono text-[11px] transition-colors ${
                role === r ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div>
        <span className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">
          Notified about
        </span>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {KINDS.map((k) => {
            const on = notifyFor.includes(k);
            return (
              <button
                key={k} type="button"
                onClick={() => setNotifyFor((f) => (on ? f.filter((x) => x !== k) : [...f, k]))}
                className={`rounded-full border px-3 py-1 font-mono text-[11px] transition-colors ${
                  on ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30"
                }`}
              >
                {k}
              </button>
            );
          })}
        </div>
        <p className="text-muted-foreground mt-1.5 text-xs">
          Selecting none means notified about every kind of disruption.
        </p>
      </div>

      {error && <p className="text-destructive text-xs">{error}</p>}
      <Button type="submit" size="sm" disabled={busy}>
        {busy ? "Saving…" : "Add contact"}
      </Button>
    </form>
  );
}

export function DeleteContact({ id }: { id: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <Button
      variant="ghost" size="icon" className="size-7 shrink-0" disabled={busy}
      aria-label="Delete contact"
      onClick={async () => {
        setBusy(true);
        await fetch(`/api/sigap/contacts/${id}/delete`, { method: "POST" });
        router.refresh();
        setBusy(false);
      }}
    >
      <Trash2 className="size-3.5" />
    </Button>
  );
}

export function ContactList({ contacts, canDelete }: { contacts: Contact[]; canDelete: boolean }) {
  if (!contacts.length) {
    return (
      <p className="text-muted-foreground mt-3 rounded-xl border border-dashed p-5 text-sm">
        No contacts yet. Without these, an agent's recommendation reaches nobody.
      </p>
    );
  }
  return (
    <ul className="mt-3 divide-y rounded-xl border">
      {contacts.map((c) => (
        <li key={c.id} className="flex items-start gap-3 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm">{c.name}</p>
            <p className="text-muted-foreground mt-0.5 truncate font-mono text-[11px]">
              {c.email} · {c.role}
            </p>
            <p className="text-muted-foreground mt-0.5 font-mono text-[10px]">
              {c.notify_for === "*" ? "every kind of disruption" : c.notify_for.split(",").join(" · ")}
            </p>
          </div>
          {canDelete && <DeleteContact id={c.id} />}
        </li>
      ))}
    </ul>
  );
}
