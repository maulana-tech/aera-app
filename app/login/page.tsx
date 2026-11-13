"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Field } from "@/components/profile-editor";
import { AeraMark } from "@/components/aera-mark";
import { Dot } from "@/components/dort";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/* The session lives in an httpOnly cookie set by /api/login (or /api/setup on a fresh install, /api/signup for a
 * tester, /api/business for a new business). On first run, when no account exists yet, this page offers to create
 * the owner instead of a sign-in nobody could complete.
 *
 *   signin    any account, in any business on this install (the server finds which)
 *   business  create your own business: its own team and record, on your NEAR AI key or the shared one
 *   tester    join the demo business: give its team work and talk to its agents, approve nothing */
type Mode = "signin" | "business" | "tester";
type HubInfo = { open: boolean; shared_daily_usd?: number; shared_key?: boolean; why_closed?: string | null };

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [business, setBusiness] = useState("");
  const [keyMode, setKeyMode] = useState<"shared" | "own">("shared");
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [needsOwner, setNeedsOwner] = useState(false);
  const [demo, setDemo] = useState<{ email: string; password: string } | null>(null);
  const [tester, setTester] = useState<{ work_per_day: number; asks_per_day: number } | null>(null);
  const [hubInfo, setHubInfo] = useState<HubInfo | null>(null);
  const [mode, setMode] = useState<Mode>("signin");

  useEffect(() => {
    const want = new URLSearchParams(window.location.search).get("mode");
    fetch("/api/setup", { cache: "no-store" }).then((r) => r.json())
      .then((d: { needs_owner?: boolean }) => setNeedsOwner(!!d.needs_owner)).catch(() => setNeedsOwner(false));
    fetch("/api/demo", { cache: "no-store" }).then((r) => r.json())
      .then((d: { enabled?: boolean; email?: string; password?: string }) => {
        if (d.enabled && d.email && d.password) setDemo({ email: d.email, password: d.password });
      }).catch(() => setDemo(null));
    fetch("/api/signup", { cache: "no-store" }).then((r) => r.json())
      .then((d: { enabled?: boolean; work_per_day?: number; asks_per_day?: number }) => {
        if (!d.enabled) return;
        setTester({ work_per_day: d.work_per_day ?? 5, asks_per_day: d.asks_per_day ?? 20 });
        if (want === "tester" || want === "signup") setMode("tester");
      }).catch(() => setTester(null));
    fetch("/api/business", { cache: "no-store" }).then((r) => r.json())
      .then((d: HubInfo) => {
        setHubInfo(d);
        if (!d.shared_key) setKeyMode("own");
        if (want === "business" && d.open) setMode("business");
      }).catch(() => setHubInfo(null));
  }, []);

  async function send(path: string, body: Record<string, string>, next: string) {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
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
  const canBusiness = !!hubInfo?.open;
  const m: Mode | "setup" = setup ? "setup" : mode === "business" && !canBusiness ? "signin" : mode === "tester" && !tester ? "signin" : mode;
  const creating = m !== "signin";
  const cap = hubInfo?.shared_daily_usd ?? 0.5;

  const title = { setup: "Set up AERA", signin: "Sign in", business: "Create your business", tester: "Join the demo as a tester" }[m];
  const lead = {
    setup: "No account exists yet. Create the owner: the person who describes the business, sets its limits and approves the team.",
    signin: "A team of agents runs the business; you set the limits and approve what goes past them.",
    business: "Your own business with its own team of agents, its own record and its own limits. You describe it next. Payments run simulated until you connect a NEAR vault.",
    tester: `Give the demo business's team work (${tester?.work_per_day} a day) and talk to any agent (${tester?.asks_per_day} questions a day). It approves nothing and changes no settings; anything the work would pay or send waits for its owner.`,
  }[m];

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-8 px-4 py-10">
      <Link href="/" className="flex items-center gap-2.5 text-white">
        <AeraMark className="size-8" />
        <span className="text-[26px] tracking-[-0.02em]">aera</span>
      </Link>

      {!setup && (canBusiness || tester) && (
        <div role="tablist" aria-label="What do you want to do" className="flex rounded-full border border-white/20 bg-white/10 p-1 text-[13px]">
          {([["signin", "Sign in", true], ["business", "Create your business", canBusiness], ["tester", "Try the demo", !!tester]] as [Mode, string, boolean][])
            .filter(([, , on]) => on).map(([id, label]) => (
              <button key={id} type="button" role="tab" aria-selected={m === id} onClick={() => { setMode(id); setError(""); }}
                className={cn("rounded-full px-3.5 py-1.5 transition-colors", m === id ? "text-brand bg-white" : "text-white/85 hover:text-white")}>
                {label}
              </button>
            ))}
        </div>
      )}

      <form
        className="bg-card-grad shadow-float w-full max-w-[440px] space-y-5 rounded-xl border border-white/40 p-6 md:p-8"
        onSubmit={(e) => {
          e.preventDefault();
          if (m === "setup") void send("/api/setup", { email, password, name }, "/onboarding");
          else if (m === "business") void send("/api/business", { business, name, email, password, key: keyMode === "own" ? key : "" }, "/onboarding");
          else if (m === "tester") void send("/api/signup", { email, password, name }, "/dashboard");
          else void send("/api/login", { email, password }, "/dashboard");
        }}
      >
        <div>
          <h1 className="text-[22px]">{title}</h1>
          <p className="text-muted-foreground mt-1.5 text-[13px] leading-relaxed">{lead}</p>
        </div>
        {m === "business" && (
          <Field label="Business name"><Input value={business} onChange={(e) => setBusiness(e.target.value)} placeholder="Kopi Analytics" maxLength={80} required /></Field>
        )}
        {creating && (
          <Field label="Your name"><Input value={name} autoComplete="name" onChange={(e) => setName(e.target.value)} required /></Field>
        )}
        <Field label="Email"><Input type="email" value={email} autoComplete="email" onChange={(e) => setEmail(e.target.value)} required /></Field>
        <Field label="Password" hint={creating ? "At least 10 characters. You sign in with it from now on." : undefined}>
          <Input type="password" value={password} minLength={creating ? 10 : undefined}
                 autoComplete={creating ? "new-password" : "current-password"} onChange={(e) => setPassword(e.target.value)} required />
        </Field>

        {m === "business" && (
          <fieldset className="space-y-2">
            <legend className="text-text mb-1.5 text-[12.5px]">The AI your agents run on</legend>
            {hubInfo?.shared_key && (
              <label className={cn("flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors", keyMode === "shared" ? "border-brand bg-raised" : "hover:bg-raised")}>
                <input type="radio" name="key" checked={keyMode === "shared"} onChange={() => setKeyMode("shared")} className="mt-1 accent-[var(--brand)]" />
                <span>
                  <span className="text-fg block text-[13.5px]">Start on AERA&apos;s key</span>
                  <span className="text-muted-foreground block text-[12px] leading-relaxed">Free to try, up to ${cap.toFixed(2)} of AI a day. Add your own key any time under Models.</span>
                </span>
              </label>
            )}
            <label className={cn("flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors", keyMode === "own" ? "border-brand bg-raised" : "hover:bg-raised")}>
              <input type="radio" name="key" checked={keyMode === "own"} onChange={() => setKeyMode("own")} className="mt-1 accent-[var(--brand)]" />
              <span className="min-w-0 flex-1">
                <span className="text-fg block text-[13.5px]">Use my own NEAR AI key</span>
                <span className="text-muted-foreground block text-[12px] leading-relaxed">
                  No daily cap from us; you pay NEAR AI for what your agents use.{" "}
                  <Link href="/guide/near-ai-key" target="_blank" className="text-brand underline-offset-2 hover:underline">How to get a key</Link>
                </span>
                {keyMode === "own" && (
                  <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="Paste your NEAR AI API key" autoComplete="off" className="mt-2" required />
                )}
              </span>
            </label>
          </fieldset>
        )}

        {error && <p className="text-bad flex items-center gap-2 text-[13px]"><Dot tone="bad" />{error}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          {busy ? (creating ? (m === "business" ? "Starting your business…" : "Creating…") : "Signing in…")
            : { setup: "Create owner and continue", signin: "Sign in", business: "Create my business", tester: "Create tester account" }[m]}
        </Button>

        {m === "signin" && demo && (
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
        {m === "signin" && !canBusiness && !tester && (
          <p className="text-muted-foreground text-center text-[12.5px]">No account? Ask the business owner to add you under Settings → Accounts.</p>
        )}
        {m === "business" && hubInfo && !hubInfo.open && hubInfo.why_closed && (
          <p className="text-muted-foreground text-center text-[12.5px]">{hubInfo.why_closed}</p>
        )}
      </form>
      <p className="text-on-canvas-dim max-w-sm text-center text-[12.5px]">
        Agents on TEE-attested NEAR AI models · money only through an on-chain vault with limits a person sets.
      </p>
    </main>
  );
}
