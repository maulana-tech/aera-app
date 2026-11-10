"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";

export function AddUser({ roles }: { roles: string[] }) {
  const router = useRouter();
  const [f, setF] = useState({ name: "", email: "", role: "approver", password: "" });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form className="grid max-w-2xl gap-3 sm:grid-cols-2" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true);
      setMsg("");
      try {
        await post("users", f);
        setF({ name: "", email: "", role: "approver", password: "" });
        setMsg("Added. Share the password with them privately.");
        router.refresh();
      } catch (err) {
        setMsg(errorText(err));
      } finally {
        setBusy(false);
      }
    }}>
      <Input placeholder="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required />
      <Input type="email" placeholder="Email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required />
      <select className="border-input bg-background h-9 rounded-md border px-3 text-sm" value={f.role}
              onChange={(e) => setF({ ...f, role: e.target.value })}>
        {roles.map((r) => <option key={r} value={r}>{r}</option>)}
      </select>
      <Input type="password" placeholder="Temporary password (10+)" minLength={10} value={f.password}
             onChange={(e) => setF({ ...f, password: e.target.value })} required />
      <div className="flex items-center gap-3 sm:col-span-2">
        <Button type="submit" size="sm" disabled={busy}>{busy ? "Adding…" : "Add account"}</Button>
        {msg && <span className="text-muted-foreground text-xs">{msg}</span>}
      </div>
    </form>
  );
}

export function RemoveUser({ id }: { id: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <Button size="sm" variant="ghost" disabled={busy} onClick={async () => {
      if (!confirm("Remove this account? They will no longer be able to sign in.")) return;
      setBusy(true);
      try {
        await post(`users/${id}/delete`);
        router.refresh();
      } catch (e) {
        alert(errorText(e));
      } finally {
        setBusy(false);
      }
    }}>Remove</Button>
  );
}
