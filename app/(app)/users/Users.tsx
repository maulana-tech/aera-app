"use client";

import { Loader2, UserMinus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Field } from "@/components/profile-editor";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";

/** What each role is for, in the words an owner picks one by. */
export const ROLE_HELP: Record<string, string> = {
  viewer: "Reads everything, decides nothing.",
  operator: "Day-to-day: approves small actions and runs work.",
  approver: "Signs off payments and refunds above the team's own limits.",
  owner: "Runs the business: profile, team, payout details, accounts.",
  admin: "Same powers as an owner, for whoever operates the service.",
};

export function AddUser({ roles }: { roles: string[] }) {
  const router = useRouter();
  const [f, setF] = useState({ name: "", email: "", role: "approver", password: "" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <form className="grid max-w-2xl gap-3 sm:grid-cols-2" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true);
      setMsg(null);
      try {
        await post("users", f);
        setF({ name: "", email: "", role: "approver", password: "" });
        setMsg({ ok: true, text: "Added. Share the password with them privately; they sign in at /login." });
        router.refresh();
      } catch (err) {
        setMsg({ ok: false, text: errorText(err) });
      } finally {
        setBusy(false);
      }
    }}>
      <Field label="Name">
        <Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required autoComplete="off" />
      </Field>
      <Field label="Email">
        <Input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required autoComplete="off" />
      </Field>
      <Field label="Role" hint={ROLE_HELP[f.role]}>
        <select className="border-input bg-background focus-visible:ring-ring/50 h-8 w-full rounded-lg border px-2 text-sm outline-none focus-visible:ring-3 " value={f.role}
                onChange={(e) => setF({ ...f, role: e.target.value })}>
          {roles.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </Field>
      <Field label="Temporary password" hint="At least 10 characters.">
        <Input type="password" minLength={10} value={f.password} autoComplete="new-password"
               onChange={(e) => setF({ ...f, password: e.target.value })} required />
      </Field>
      <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
        <Button type="submit" size="sm" disabled={busy}>{busy && <Loader2 className="animate-spin" />}{busy ? "Adding…" : "Add account"}</Button>
        {msg && <span className={msg.ok ? "text-muted-foreground text-xs" : "text-xs text-bad "}>{msg.text}</span>}
      </div>
    </form>
  );
}

export function RemoveUser({ id, name }: { id: string; name: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <span className="inline-flex flex-col items-end gap-1">
      <Button size="sm" variant="ghost" disabled={busy} aria-label={`Remove ${name}'s account`} onClick={async () => {
        if (!window.confirm(`Remove ${name}'s account? They will no longer be able to sign in or approve anything.`)) return;
        setBusy(true);
        setError("");
        try {
          await post(`users/${id}/delete`);
          router.refresh();
        } catch (e) {
          setError(errorText(e));
        } finally {
          setBusy(false);
        }
      }}>
        {busy ? <Loader2 className="animate-spin" /> : <UserMinus />} Remove
      </Button>
      {error && <span className="text-[11px] text-bad ">{error}</span>}
    </span>
  );
}
