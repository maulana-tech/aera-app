"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ThemeToggle } from "@/components/theme";
import AuthSectionOne from "@/components/ui/auth-section-1";
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

  useEffect(() => {
    fetch("/api/setup", { cache: "no-store" })
      .then((r) => r.json())
      .then((d: { needs_owner?: boolean }) => setNeedsOwner(!!d.needs_owner))
      .catch(() => setNeedsOwner(false));
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

  if (needsOwner) {
    return (
      <main className="bg-background flex min-h-svh items-center justify-center px-4">
        <form
          className="w-full max-w-sm space-y-4 rounded-xl border p-6"
          onSubmit={(e) => {
            e.preventDefault();
            void send("/api/setup", { email, password, name }, "/onboarding");
          }}
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <h1 className="text-lg font-semibold">Set up AERA</h1>
              <p className="text-muted-foreground mt-1 text-sm">
                No account exists yet. Create the owner: the person who describes the business, sets its limits and
                approves the team.
              </p>
            </div>
            <ThemeToggle />
          </div>
          <Input placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} required />
          <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input type="password" placeholder="Password (10+ characters)" value={password} minLength={10}
                 onChange={(e) => setPassword(e.target.value)} required />
          {error && <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy}>{busy ? "Creating…" : "Create owner and continue"}</Button>
        </form>
      </main>
    );
  }

  return (
    <AuthSectionOne
      email={email}
      password={password}
      onEmailChange={setEmail}
      onPasswordChange={setPassword}
      onSubmit={(e) => {
        e.preventDefault();
        void send("/api/login", { email, password }, "/");
      }}
      busy={busy}
      error={error}
      header={<ThemeToggle />}
      note={<>No account? Ask the business owner to add you under Settings → Accounts.</>}
    />
  );
}
