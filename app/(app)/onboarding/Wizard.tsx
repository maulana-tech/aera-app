"use client";

import {
  ArrowLeft, ArrowRight, Check, Info, Loader2, Plus, RotateCcw, Sparkles, X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

import type { ComposeResult, ExtraRole, LibraryRole, Profile, TeamAgent } from "@/app/lib";
import { usd } from "@/app/lib";
import {
  BasicsFields, Field, LimitsFields, OfferingsFields, Problems, TextArea,
} from "@/components/profile-editor";
import { completeProfile } from "@/lib/profile";
import { TeamRows } from "@/components/team-list";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";
import { cn } from "@/lib/utils";

/* Each step says what it decides and who acts on it, so a person filling it in
 * knows why the question is asked. */
const STEPS = [
  {
    short: "Describe",
    hint: "Name, mission, customers",
    title: "Describe the business",
    why: "Every agent reads this before every task: it is the context for each decision the team makes.",
    who: "Read by the whole team.",
  },
  {
    short: "Offerings",
    hint: "What you sell, and for how much",
    title: "What customers can buy",
    why: "Each offering gets its own public checkout page (/buy/<id>). When a customer pays, the order becomes work for the team, delivered as you specify here.",
    who: "Used by Sales, Fulfilment and the checkout.",
  },
  {
    short: "Limits & rules",
    hint: "What the team may do without you",
    title: "What the team may do without you",
    why: "The Guardian checks every payment, refund and outgoing message against these rules in code, before anything happens. The spend limits are also written to the vault on chain, so even a compromised server cannot pay past them. Anything above a limit waits for your approval.",
    who: "Enforced by the Guardian, the Treasurer and the vault.",
  },
  {
    short: "Team",
    hint: "The agents that run it",
    title: "Who works for you",
    why: "AERA proposes a team from your offerings and channels. Supervisor, Guardian and Treasurer are always on it; leave out any specialist or add one.",
    who: "You can change the team any time on the Team page.",
  },
  {
    short: "Review",
    hint: "Check, then start",
    title: "Check it, then start",
    why: "This is exactly what will be saved. Nothing is stored until you press the button below.",
    who: "Every later change is saved as a new version you can look back at.",
  },
] as const;

const DRAFT_KEY = "aera.onboarding.draft";
const roleTitle = (r: ExtraRole) => (typeof r === "string" ? r : r.title);

/* An unsaved draft kept in this browser, so a refresh does not lose the form.
 * Read through useSyncExternalStore: the server renders "no draft", the
 * browser reads storage, and storage being blocked is just "no draft". */
function readDraft(): string | null {
  try { return window.localStorage.getItem(DRAFT_KEY); } catch { return null; }
}
function writeDraft(v: { p: Profile; step: number } | null) {
  try {
    if (v) window.localStorage.setItem(DRAFT_KEY, JSON.stringify(v));
    else window.localStorage.removeItem(DRAFT_KEY);
  } catch { /* private window or blocked storage: the form still works */ }
}
const subscribe = (cb: () => void) => {
  window.addEventListener("storage", cb);
  return () => window.removeEventListener("storage", cb);
};

export function Wizard({ initial, example, library, mayChange }: {
  initial: Profile; example: Profile; library: LibraryRole[]; mayChange: boolean;
}) {
  const router = useRouter();
  const [step, setStepRaw] = useState(0);
  const [reached, setReached] = useState(0);
  const [p, setPRaw] = useState<Profile>(initial);
  const [touched, setTouched] = useState(false);
  const [text, setText] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [drafted, setDrafted] = useState<string | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [team, setTeam] = useState<TeamAgent[] | null>(null);
  const stored = useSyncExternalStore(subscribe, readDraft, () => null);
  const [dismissed, setDismissed] = useState(false);

  const setP = (next: Profile) => { setPRaw(next); setTouched(true); writeDraft({ p: next, step }); };
  const setStep = (n: number) => {
    setStepRaw(n);
    setReached((r) => Math.max(r, n));
    if (touched) writeDraft({ p, step: n });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  function restore() {
    try {
      const d = JSON.parse(stored ?? "") as { p: Profile; step: number };
      setPRaw(completeProfile(d.p));
      const at = Math.min(Math.max(d.step ?? 0, 0), STEPS.length - 1);
      setStepRaw(at);
      setReached(at);
      setTouched(true);
    } catch { /* a draft that does not parse is no draft */ }
    setDismissed(true);
  }

  async function draft() {
    setDrafting(true);
    setError(null);
    setDrafted(null);
    try {
      const r = await post<{ profile: Partial<Profile>; problems: string[]; team: TeamAgent[] }>("business/draft", { text });
      const next = completeProfile(r.profile);
      setP(next);
      setProblems(r.problems);
      const c = next.constraints;
      setDrafted(
        `Drafted "${next.name || "your business"}": ${next.offerings.length} offering(s), autonomous spend up to ` +
        `${usd(c.autonomous_spend_usd.per_payment)} per payment and ${usd(c.autonomous_spend_usd.per_day)} a day, ` +
        `${c.forbidden.length} thing(s) it must never do. Check every step before you save: the draft is a suggestion.`,
      );
    } catch (e) {
      setError(`${errorText(e)}. You can fill in the steps by hand instead.`);
    } finally {
      setDrafting(false);
    }
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const r = await post<{ version: number; problems: string[]; team_applied: boolean }>(
        "business", { profile: p, apply_team: true, note: "onboarding" });
      setProblems(r.problems);
      writeDraft(null);
      router.push("/dashboard");
      router.refresh();
    } catch (e) {
      setError(errorText(e));
      setSaving(false);
    }
  }

  // What must be true to leave a step. Said, not just disabled.
  const blocker =
    step === 0 && !p.name.trim() ? "Give the business a name to continue."
      : step === 1 && p.offerings.some((o) => !o.title.trim()) ? "Every offering needs a title."
        : null;
  const meta = STEPS[step];
  // A step reads as done when what it asks for is there, not merely because it was passed.
  const done = [
    !!p.name.trim(),
    p.offerings.length > 0 && p.offerings.every((o) => o.title.trim()),
    reached > 2,
    reached > 3,
    false,
  ];
  const mayOpen = (i: number) => i <= reached || (i === step + 1 && !blocker);

  return (
    <div className="mt-6">
      {stored && !dismissed && !touched && (
        <div className="mb-6 flex flex-wrap items-center gap-3 rounded-lg border bg-raised px-4 py-3 text-sm">
          <RotateCcw className="size-4 shrink-0" />
          <span className="flex-1">You have an unsaved draft from earlier in this browser.</span>
          <Button size="sm" variant="outline" onClick={restore}>Restore it</Button>
          <Button size="sm" variant="ghost" onClick={() => { writeDraft(null); setDismissed(true); }}>Discard</Button>
        </div>
      )}

      {/* Phones: where you are, in one line, and how far there is to go. */}
      <div className="mb-5 lg:hidden">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-[13px]"><span className="text-muted-foreground">Step {step + 1} of {STEPS.length} · </span>{meta.short}</p>
          {step < STEPS.length - 1 && <p className="text-muted-foreground text-xs">Next: {STEPS[step + 1].short}</p>}
        </div>
        <div className="mt-2 grid grid-cols-5 gap-1">
          {STEPS.map((s, i) => (
            <button key={s.short} type="button" aria-label={`Step ${i + 1}: ${s.short}`} disabled={!mayOpen(i)}
              onClick={() => setStep(i)}
              className={cn("h-1.5 rounded-full transition-colors", i < step || (i <= reached && done[i]) ? "bg-brand" : i === step ? "bg-brand/60" : "bg-raised")} />
          ))}
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-[230px_minmax(0,1fr)]">
        {/* Desktop: the whole path, always in view. */}
        <nav aria-label="Onboarding steps" className="hidden lg:block">
          {/* The steps and the note travel together: sticking only the list let the note scroll under it. */}
          <div className="sticky top-6">
          <ol>
            {STEPS.map((s, i) => {
              const current = i === step;
              const complete = !current && i < reached + 1 && done[i] && i !== step;
              const open = mayOpen(i);
              return (
                <li key={s.short} className="relative pb-6 last:pb-0">
                  {i < STEPS.length - 1 && (
                    <span aria-hidden className={cn("absolute top-8 bottom-0 left-[15px] w-px", i < reached ? "bg-brand/40" : "bg-border")} />
                  )}
                  <button type="button" disabled={!open} onClick={() => setStep(i)} aria-current={current ? "step" : undefined}
                    className={cn("group flex w-full items-start gap-3 rounded-md text-left outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      open && !current && "cursor-pointer", !open && "cursor-not-allowed")}>
                    <span className={cn("relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full border text-[13px] transition-colors",
                      current ? "border-brand bg-brand text-white shadow-[0_0_0_4px_rgba(6,71,179,0.12)]"
                        : complete ? "border-brand/30 bg-raised text-brand"
                          : "border-border bg-white text-muted-foreground",
                      open && !current && "group-hover:border-brand/50")}>
                      {complete ? <Check className="size-4" /> : i + 1}
                    </span>
                    <span className="min-w-0 pt-1">
                      <span className={cn("block text-[14px] leading-tight", current ? "text-fg font-medium" : open ? "text-text" : "text-muted-foreground")}>{s.short}</span>
                      <span className="text-muted-foreground mt-0.5 block text-[12px] leading-snug">{s.hint}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
          <p className="text-muted-foreground mt-8 border-t pt-4 text-[11.5px] leading-relaxed">
            About three minutes. Nothing is saved until the last step; your answers are kept in this browser meanwhile.
          </p>
          </div>
        </nav>

        <div className="min-w-0">
          <header className="mb-6">
            <p className="text-muted-foreground hidden text-xs lg:block">Step {step + 1} of {STEPS.length}</p>
            <h2 className="mt-1 text-[22px] leading-tight">{meta.title}</h2>
            <p className="text-body mt-2 max-w-2xl text-[13.5px] leading-relaxed">{meta.why}</p>
            <p className="bg-raised text-text mt-3 inline-flex items-center gap-1.5 rounded-sm px-2 py-1 text-xs"><Info className="size-3.5" />{meta.who}</p>
          </header>

          <div className="space-y-6">
            {step === 0 && (
              <section className="space-y-6">
                <div className="bg-white rounded-lg border p-4">
                  <Field label="Fastest: describe the business in a few sentences and let AI fill in the steps. Say what you sell, to whom, at what price, what the team may spend on its own, and what it must never do.">
                    <TextArea rows={5} value={text} onChange={(e) => setText(e.target.value)}
                      placeholder="We write 5-page market briefs for founders in Southeast Asia, $15 each, delivered as a PDF within 2 hours. The team may spend up to $5 per payment on data, $20 a day. Never promise investment returns; refunds always need me." />
                  </Field>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Button type="button" onClick={draft} disabled={drafting || text.trim().length < 20}>
                      {drafting ? <Loader2 className="animate-spin" /> : <Sparkles />}
                      {drafting ? "Drafting…" : "Draft with AI"}
                    </Button>
                    <Button type="button" variant="ghost" onClick={() => {
                      setP(completeProfile(example)); setProblems([]);
                      setDrafted("Filled with the example business (a market-research shop). Change anything, or keep it to try AERA out.");
                    }}>
                      Use the example business
                    </Button>
                  </div>
                  <p className="text-muted-foreground mt-2 text-[11px]">
                    The draft is written by a TEE-attested model on NEAR AI and is not saved until you finish. Or skip this box and fill in the fields below.
                  </p>
                  {drafted && (
                    <p className="mt-3 rounded-md bg-raised px-3 py-2 text-sm text-ok ">{drafted}</p>
                  )}
                </div>
                <BasicsFields p={p} set={setP} />
              </section>
            )}
            {step === 1 && (
              <>
                {p.offerings.length === 0 && (
                  <p className="text-sm text-warn ">
                    No offering yet. You can continue without one (the team can still do work you ask for), but customers will have nothing to buy.
                  </p>
                )}
                <OfferingsFields p={p} set={setP} />
              </>
            )}
            {step === 2 && <LimitsFields p={p} set={setP} />}
            {step === 3 && <TeamStep p={p} set={setP} library={library} onTeam={setTeam} />}
            {step === 4 && <Review p={p} team={team} onEdit={setStep} />}

            <Problems problems={problems} />
            {error && <p className="text-sm text-bad ">{error}</p>}
          </div>

          {/* Always in reach, however long the step. */}
          <div className="bg-card-grad sticky bottom-0 z-10 -mx-4 mt-8 flex flex-wrap items-center gap-x-2 gap-y-2 border-t px-4 py-3 md:-mx-6 md:px-6">
            {/* On a phone the reason sits on its own line above, so Back and Next stay side by side. */}
            {(blocker || !mayChange) && (
              <p className="order-first w-full text-xs sm:order-none sm:w-auto">
                {blocker && <span className="text-warn">{blocker}</span>}
                {!mayChange && <span className="text-muted-foreground">Only an owner or admin can save a business.</span>}
              </p>
            )}
            <Button type="button" variant="outline" className="sm:order-first" onClick={() => setStep(step - 1)} disabled={step === 0}>
              <ArrowLeft /> Back
            </Button>
            <span className="ml-auto" />
            {step < STEPS.length - 1 ? (
              <Button type="button" onClick={() => setStep(step + 1)} disabled={!!blocker}>
                Next: {STEPS[step + 1].short} <ArrowRight />
              </Button>
            ) : (
              <Button type="button" onClick={save} disabled={saving || !mayChange || !p.name.trim()}>
                {saving && <Loader2 className="animate-spin" />}
                Save and start the business
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, step, onEdit, children }: {
  label: string; step: number; onEdit: (step: number) => void; children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1 border-b py-3 last:border-b-0 sm:grid-cols-[180px_1fr_auto] sm:gap-4">
      <p className="text-muted-foreground text-xs font-medium">{label}</p>
      <div className="text-sm leading-relaxed">{children}</div>
      <button type="button" onClick={() => onEdit(step)} className="justify-self-start text-xs underline underline-offset-2">Edit</button>
    </div>
  );
}

/** The profile in plain sentences, and what happens after saving. */
function Review({ p, team, onEdit }: { p: Profile; team: TeamAgent[] | null; onEdit: (step: number) => void }) {
  const c = p.constraints;
  const split = p.revenue_split.filter((s) => s.account);
  return (
    <section className="space-y-6">
      <div className="rounded-lg border px-4">
        <Row label="Business" step={0} onEdit={onEdit}>
          <p className="font-medium">{p.name || "(no name)"}</p>
          {p.mission && <p className="text-muted-foreground">{p.mission}</p>}
          {p.customers && <p className="text-muted-foreground">For: {p.customers}</p>}
        </Row>
        <Row label="Sells" step={1} onEdit={onEdit}>
          {p.offerings.length === 0 ? <p className="text-muted-foreground">Nothing yet.</p> : (
            <ul className="space-y-1">
              {p.offerings.map((o) => (
                <li key={o.id || o.title}>
                  <span className="font-medium">{o.title}</span> for {usd(o.price_usd)}, delivered as {o.delivery} within {o.sla_hours}h
                  {o.inputs.length > 0 && <span className="text-muted-foreground"> · asks the customer for {o.inputs.join(", ")}</span>}
                  <span className="text-muted-foreground font-mono text-xs"> · /buy/{o.id || "…"}</span>
                </li>
              ))}
            </ul>
          )}
        </Row>
        <Row label="Without you" step={2} onEdit={onEdit}>
          <p>
            The team may pay up to <b>{usd(c.autonomous_spend_usd.per_payment)}</b> per payment and{" "}
            <b>{usd(c.autonomous_spend_usd.per_day)}</b> a day on its own. Model spend stops at {usd(c.inference_max_usd_per_day)} a day.
          </p>
          <p className="text-muted-foreground">Always asks you first: {c.approval_required.join(", ") || "nothing extra"}.</p>
          {c.min_price_usd > 0 && <p className="text-muted-foreground">Never sells below {usd(c.min_price_usd)}.</p>}
        </Row>
        <Row label="Never" step={2} onEdit={onEdit}>
          {c.forbidden.length ? <ul className="list-inside list-disc">{c.forbidden.map((f) => <li key={f}>{f}</li>)}</ul>
            : <p className="text-muted-foreground">Nothing listed. The Guardian still blocks payments to unknown accounts and suspected manipulation.</p>}
        </Row>
        <Row label="Sensitive data" step={2} onEdit={onEdit}>
          {p.privacy.sensitive.length ? p.privacy.sensitive.join(", ")
            : <span className="text-muted-foreground">Nothing listed.</span>}
          <p className="text-muted-foreground text-xs">Every agent thinks on a TEE-attested model; prompts are not kept by the model provider.</p>
        </Row>
        {split.length > 0 && (
          <Row label="Revenue share" step={2} onEdit={onEdit}>
            {split.map((s) => `${(s.bps / 100).toFixed(2)}% to ${s.account}`).join(" · ")}, paid by the vault the moment an order is paid.
          </Row>
        )}
        <Row label="Team" step={3} onEdit={onEdit}>
          {team ? (
            <p>{team.filter((a) => a.status !== "draft").map((a) => a.nickname).join(", ")}
              {team.some((a) => a.status === "draft") && (
                <span className="text-muted-foreground"> · drafts to activate later: {team.filter((a) => a.status === "draft").map((a) => a.title).join(", ")}</span>
              )}
            </p>
          ) : <p className="text-muted-foreground">Open the Team step to see who is proposed.</p>}
        </Row>
      </div>

      <div className="rounded-lg border p-4">
        <h3 className="text-sm font-medium">What happens when you save</h3>
        <ol className="text-muted-foreground mt-2 list-inside list-decimal space-y-1 text-sm">
          <li>The profile is saved (version 1) and the team above is formed.</li>
          <li>The dashboard shows a short checklist: connect the models (NEAR AI key), connect the vault (NEAR), add an approver.</li>
          <li>Share a checkout link from Orders. A paid order becomes work: the Supervisor assigns it, the specialists do it, the Guardian checks what goes out.</li>
          <li>Anything above your limits waits for you under Work and Treasury. You can stop everything at any time with the kill switch.</li>
        </ol>
      </div>
    </section>
  );
}

/** The team the Composer proposes for this profile, before anything is saved:
 *  core roles are fixed, library roles can be left out or added, and any
 *  extra role becomes a draft that a person activates on the Team page. */
function TeamStep({ p, set, library, onTeam }: {
  p: Profile; set: (p: Profile) => void; library: LibraryRole[]; onTeam: (t: TeamAgent[]) => void;
}) {
  const [team, setTeam] = useState<TeamAgent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [extra, setExtra] = useState("");

  const key = JSON.stringify(p);
  useEffect(() => {
    let live = true;
    post<ComposeResult>("team/compose", { profile: JSON.parse(key) as Profile })
      .then((r) => { if (live) { setTeam(r.team); onTeam(r.team); setError(null); } })
      .catch((e) => live && setError(errorText(e)));
    return () => { live = false; };
  }, [key, onTeam]);

  const t = p.team;
  const proposed = new Set((team ?? []).map((a) => a.code));
  const addable = library.filter((r) => !proposed.has(r.key));

  const exclude = (code: string) => set({ ...p, team: { ...t, exclude: [...t.exclude, code], include: t.include.filter((x) => x !== code) } });
  const include = (code: string) => set({ ...p, team: { ...t, include: [...t.include, code], exclude: t.exclude.filter((x) => x !== code) } });
  const dropExtra = (title: string) => set({ ...p, team: { ...t, extra_roles: t.extra_roles.filter((r) => roleTitle(r) !== title) } });

  return (
    <section className="space-y-6">
      <div className="grid gap-2 sm:grid-cols-3">
        {[
          ["Supervisor", "Plans each piece of work and decides who does it."],
          ["Guardian", "Checks every payment and message against your rules. Its block is final."],
          ["Treasurer", "The only one who can move money, and only through the vault."],
        ].map(([n, d]) => (
          <div key={n} className="rounded-lg border px-3 py-2">
            <p className="text-sm font-medium">{n} <span className="text-muted-foreground font-mono text-[10px]">always on</span></p>
            <p className="text-muted-foreground text-xs">{d}</p>
          </div>
        ))}
      </div>

      {error && <p className="text-sm text-bad ">{error}</p>}
      {!team ? (
        <p className="text-muted-foreground inline-flex items-center gap-2 text-sm"><Loader2 className="size-4 animate-spin" /> Composing the team…</p>
      ) : (
        <>
          <p className="text-muted-foreground text-xs">Proposed for your business. Specialists were picked from your offerings, channels and limits.</p>
          <TeamRows agents={team} action={(a) =>
            a.core ? <span className="text-muted-foreground font-mono text-[10px]">always</span>
              : a.role === "custom" ? (
                <Button size="xs" variant="ghost" onClick={() => dropExtra(a.title)}><X /> Drop</Button>
              ) : (
                <Button size="xs" variant="ghost" onClick={() => exclude(a.code)}><X /> Leave out</Button>
              )} />
        </>
      )}

      {addable.length > 0 && (
        <div>
          <p className="text-muted-foreground mb-2 text-xs">Add a specialist from the role library</p>
          <div className="flex flex-wrap gap-2">
            {addable.map((r) => (
              <Button key={r.key} size="sm" variant="outline" onClick={() => include(r.key)} title={r.brief}>
                <Plus /> {r.title}
              </Button>
            ))}
          </div>
        </div>
      )}

      <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => {
        e.preventDefault();
        const title = extra.trim();
        if (!title) return;
        set({ ...p, team: { ...t, extra_roles: [...t.extra_roles, title] } });
        setExtra("");
      }}>
        <Field label="A role the library does not have, in your words" className="min-w-56 flex-1"
          hint="It joins as a draft with only basic capabilities (read files, write documents). It can never be given money or the veto. Activate it on the Team page.">
          <Input value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Copy editor" />
        </Field>
        <Button type="submit" variant="outline" disabled={!extra.trim()}><Plus /> Add role</Button>
      </form>
    </section>
  );
}
