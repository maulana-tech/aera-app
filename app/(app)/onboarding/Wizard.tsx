"use client";

import { ArrowLeft, ArrowRight, Loader2, Plus, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import type { ComposeResult, ExtraRole, LibraryRole, Profile, TeamAgent } from "@/app/lib";
import {
  BasicsFields, Field, LimitsFields, OfferingsFields, Problems, TextArea,
} from "@/components/profile-editor";
import { completeProfile } from "@/lib/profile";
import { TeamRows } from "@/components/team-list";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";
import { cn } from "@/lib/utils";

const STEPS = ["Describe", "Offerings", "Limits & rules", "Team"] as const;

const roleTitle = (r: ExtraRole) => (typeof r === "string" ? r : r.title);

export function Wizard({ initial, example, library, mayChange }: {
  initial: Profile; example: Profile; library: LibraryRole[]; mayChange: boolean;
}) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [p, setP] = useState<Profile>(initial);
  const [text, setText] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function draft() {
    setDrafting(true);
    setError(null);
    try {
      const r = await post<{ profile: Partial<Profile>; problems: string[]; team: TeamAgent[] }>("business/draft", { text });
      setP(completeProfile(r.profile));
      setProblems(r.problems);
    } catch (e) {
      setError(`${errorText(e)}. You can fill the profile in by hand below.`);
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
      router.push("/dashboard");
      router.refresh();
    } catch (e) {
      setError(errorText(e));
      setSaving(false);
    }
  }

  const canNext = step !== 0 || p.name.trim().length > 0;

  return (
    <div className="mt-6 space-y-6">
      <ol className="flex flex-wrap gap-2">
        {STEPS.map((s, i) => (
          <li key={s}>
            <button type="button" onClick={() => (i <= step || canNext) && setStep(i)}
              className={cn("rounded-full border px-3 py-1 text-xs transition-colors",
                i === step ? "bg-primary text-primary-foreground border-primary"
                  : i < step ? "border-foreground/30" : "text-muted-foreground")}>
              <span className="font-mono">{i + 1}</span> {s}
            </button>
          </li>
        ))}
      </ol>

      {step === 0 && (
        <section className="space-y-6">
          <div className="rounded-lg border p-4">
            <Field label="Describe the business in a few sentences: what you sell, to whom, at what price, what the team may spend on its own, and what it must never do.">
              <TextArea rows={5} value={text} onChange={(e) => setText(e.target.value)}
                placeholder="We write 5-page market briefs for founders in Southeast Asia, $15 each, delivered as a PDF within 2 hours. The team may spend up to $5 per payment on data, $20 a day. Never promise investment returns; refunds always need me." />
            </Field>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button type="button" onClick={draft} disabled={drafting || text.trim().length < 20}>
                {drafting ? <Loader2 className="animate-spin" /> : <Sparkles />}
                Draft with AI
              </Button>
              <Button type="button" variant="ghost" onClick={() => { setP(completeProfile(example)); setProblems([]); }}>
                Use the example business
              </Button>
              <span className="text-muted-foreground text-[11px]">
                The draft is written by a TEE-attested model and is not saved until you finish.
              </span>
            </div>
          </div>
          <BasicsFields p={p} set={setP} />
        </section>
      )}
      {step === 1 && <OfferingsFields p={p} set={setP} />}
      {step === 2 && <LimitsFields p={p} set={setP} />}
      {step === 3 && <TeamStep p={p} set={setP} library={library} />}

      <Problems problems={problems} />
      {error && <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>}

      <div className="flex flex-wrap items-center gap-2 border-t pt-4">
        <Button type="button" variant="outline" onClick={() => setStep(step - 1)} disabled={step === 0}>
          <ArrowLeft /> Back
        </Button>
        {step < STEPS.length - 1 ? (
          <Button type="button" onClick={() => setStep(step + 1)} disabled={!canNext}>
            Next <ArrowRight />
          </Button>
        ) : (
          <Button type="button" onClick={save} disabled={saving || !mayChange || !p.name.trim()}>
            {saving && <Loader2 className="animate-spin" />}
            Save the business and form the team
          </Button>
        )}
        {!mayChange && <span className="text-muted-foreground text-xs">Only an owner or admin can save a business.</span>}
      </div>
    </div>
  );
}

/** The team the Composer proposes for this profile, before anything is saved:
 *  core roles are fixed, library roles can be left out or added, and any
 *  extra role becomes a draft that a person activates on the Team page. */
function TeamStep({ p, set, library }: { p: Profile; set: (p: Profile) => void; library: LibraryRole[] }) {
  const [team, setTeam] = useState<TeamAgent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [extra, setExtra] = useState("");

  const key = JSON.stringify(p);
  useEffect(() => {
    let live = true;
    post<ComposeResult>("team/compose", { profile: JSON.parse(key) as Profile })
      .then((r) => { if (live) { setTeam(r.team); setError(null); } })
      .catch((e) => live && setError(errorText(e)));
    return () => { live = false; };
  }, [key]);

  const t = p.team;
  const proposed = new Set((team ?? []).map((a) => a.code));
  const addable = library.filter((r) => !proposed.has(r.key));

  const exclude = (code: string) => set({ ...p, team: { ...t, exclude: [...t.exclude, code], include: t.include.filter((x) => x !== code) } });
  const include = (code: string) => set({ ...p, team: { ...t, include: [...t.include, code], exclude: t.exclude.filter((x) => x !== code) } });
  const dropExtra = (title: string) => set({ ...p, team: { ...t, extra_roles: t.extra_roles.filter((r) => roleTitle(r) !== title) } });

  return (
    <section className="space-y-6">
      {error && <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>}
      {!team ? (
        <p className="text-muted-foreground inline-flex items-center gap-2 text-sm"><Loader2 className="size-4 animate-spin" /> Composing the team…</p>
      ) : (
        <TeamRows agents={team} action={(a) =>
          a.core ? <span className="text-muted-foreground font-mono text-[10px]">always</span>
            : a.role === "custom" ? (
              <Button size="xs" variant="ghost" onClick={() => dropExtra(a.title)}><X /> Drop</Button>
            ) : (
              <Button size="xs" variant="ghost" onClick={() => exclude(a.code)}><X /> Leave out</Button>
            )} />
      )}

      {addable.length > 0 && (
        <div>
          <p className="text-muted-foreground mb-2 text-xs">Add from the role library</p>
          <div className="flex flex-wrap gap-2">
            {addable.map((r) => (
              <Button key={r.key} size="sm" variant="outline" onClick={() => include(r.key)} title={r.brief}>
                <Plus /> {r.nickname} · {r.title}
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
        <Field label="An extra role, in your words" className="min-w-56 flex-1"
          hint="It joins as a draft with only generic capabilities; activate it on the Team page.">
          <Input value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Copy editor" />
        </Field>
        <Button type="submit" variant="outline" disabled={!extra.trim()}><Plus /> Add role</Button>
      </form>
    </section>
  );
}
