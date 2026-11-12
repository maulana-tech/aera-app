"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Field } from "@/components/profile-editor";
import { AeraMark } from "@/components/aera-mark";
import { Dot } from "@/components/dort";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/* The session lives in an httpOnly cookie set by /api/login (or /api/setup on
 * a fresh install). On first run, when no account exists yet, this page offers
 * to create the owner instead of a sign-in nobody could complete. */
export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [needsOwner, setNeedsOwner] = useState(false);
  const [demo, setDemo] = useState<{ email: string; password: string } | null>(null);

  useEffect(() => {
    fetch("/api/setup", { cache: "no-store" })
      .then((r) => r.json())
      .then((d: { needs_owner?: boolean }) => setNeedsOwner(!!d.needs_owner))
      .catch(() => setNeedsOwner(false));
    fetch("/api/demo", { cache: "no-store" })
      .then((r) => r.json())
      .then((d: { enabled?: boolean; email?: string; password?: string }) => {
        if (d.enabled && d.email && d.password) setDemo({ email: d.email, password: d.password });
      })
      .catch(() => setDemo(null));
  }, []);

  async function send(path: string, body: Record<string, string>, next: string) {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(path, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error((await res.json()).error ?? "could not sign in");
      router.push(next);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not sign in");
    } finally {
      setBusy(false);
    }
  }

  const setup = needsOwner;
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-8 px-4 py-10">
      <div className="flex items-center gap-2.5 text-white">
        <AeraMark className="size-8" />
        <span className="text-[26px] tracking-[-0.02em]">aera</span>
      </div>
      <form
        className="bg-card-grad shadow-float w-full max-w-[420px] space-y-5 rounded-xl border border-white/40 p-6 md:p-8"
        onSubmit={(e) => {
          e.preventDefault();
          if (setup) void send("/api/setup", { email, password, name }, "/onboarding");
          else void send("/api/login", { email, password }, "/");
        }}
      >
        <div>
          <h1 className="text-[22px]">{setup ? "Set up AERA" : "Sign in"}</h1>
          <p className="text-muted-foreground mt-1.5 text-[13px] leading-relaxed">
            {setup
              ? "No account exists yet. Create the owner: the person who describes the business, sets its limits and approves the team."
              : "A team of agents runs the business; you set the limits and approve what goes past them."}
          </p>
        </div>
        {setup && (
          <Field label="Your name"><Input value={name} autoComplete="name" onChange={(e) => setName(e.target.value)} required /></Field>
        )}
        <Field label="Email"><Input type="email" value={email} autoComplete="email" onChange={(e) => setEmail(e.target.value)} required /></Field>
        <Field label="Password" hint={setup ? "At least 10 characters. You sign in with it from now on." : undefined}>
          <Input type="password" value={password} minLength={setup ? 10 : undefined}
                 autoComplete={setup ? "new-password" : "current-password"}
                 onChange={(e) => setPassword(e.target.value)} required />
        </Field>
        {error && (
          <p className="text-bad flex items-center gap-2 text-[13px]"><Dot tone="bad" />{error}</p>
        )}
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          {busy ? (setup ? "Creating…" : "Signing in…") : setup ? "Create owner and continue" : "Sign in"}
        </Button>
        {!setup && demo && (
          <div className="space-y-2">
            <Button type="button" variant="outline" size="lg" className="w-full" disabled={busy}
                    onClick={() => { setEmail(demo.email); setPassword(demo.password); setError(""); }}>
              Use the demo account
            </Button>
            <p className="text-muted-foreground text-center text-[12px] leading-relaxed">
              Fills in a read-only account: every page, run and proof is open to read; it starts no work, approves no payment and changes no settings.
            </p>
          </div>
        )}
        {!setup && (
          <p className="text-muted-foreground text-center text-[12.5px]">
            No account? Ask the business owner to add you under Settings → Accounts.
          </p>
        )}
      </form>
      <p className="text-on-canvas-dim max-w-sm text-center text-[12.5px]">
        Agents on TEE-attested NEAR AI models · money only through an on-chain vault with limits a person sets.
      </p>
    </main>
  );
}
