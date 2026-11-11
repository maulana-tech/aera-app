"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { ModelListing, ModelsPayload, ModelTest } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

const ROLES = [
  { key: "lead", label: "Lead and veto", hint: "Supervisor decides what to do. Guardian decides what may be done." },
  { key: "specialists", label: "Specialists", hint: "Every specialist on the team: research, writing, review, fulfilment and the rest." },
  { key: "fallback", label: "Fallback", hint: "Answers when an agent's own model fails, for the rest of that run." },
  { key: "aux", label: "Summaries", hint: "The one-paragraph report summaries. No tools." },
] as const;

const SELECT =
  "h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2 text-sm outline-none " +
  "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 " +
  "disabled:cursor-not-allowed disabled:opacity-60 ";

function rate(m: ModelListing): string {
  const [i, o] = m.usd_per_mtok;
  return `$${i} / $${o} per MTok`;
}

function groups(catalog: ModelListing[]): [string, ModelListing[]][] {
  const out = new Map<string, ModelListing[]>();
  for (const m of catalog) {
    const k = m.vendor ?? "From .env";
    out.set(k, [...(out.get(k) ?? []), m]);
  }
  return [...out.entries()];
}

function source(s: string): string {
  return s.startsWith("page:") ? "chosen here" : s;
}

export function ModelChoice({ data }: { data: ModelsPayload }) {
  const router = useRouter();
  const byModel = new Map(data.catalog.map((m) => [m.model, m]));
  const name = (model: string | null) => {
    if (!model) return "none";
    const m = byModel.get(model);
    return m ? `${m.label} · ${m.via}` : model;
  };
  const saved = (key: string) => data.chosen[key]?.value ?? "";
  const keys = [...ROLES.map((r) => r.key as string), ...data.team.map((t) => t.agent)];

  const [picks, setPicks] = useState<Record<string, string>>(
    () => Object.fromEntries(keys.map((k) => [k, saved(k)])),
  );
  const [tests, setTests] = useState<Record<string, ModelTest>>(data.tested);
  const [testing, setTesting] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const changed = keys.filter((k) => picks[k] !== saved(k));
  const pick = (k: string, v: string) => setPicks((p) => ({ ...p, [k]: v }));

  // What a role falls back to when nothing is chosen here.
  const fromEnv: Record<string, string> = {
    lead: name(data.env.lead),
    specialists: data.env.specialists ? name(data.env.specialists) : "same as the lead",
    fallback: data.env.fallback ? name(data.env.fallback) : "no fallback",
    aux: name(data.env.aux),
  };
  // The model a role would run on with the picks as they stand, for Test.
  const inForce = (k: string): string | null =>
    picks[k] === "none" ? null : picks[k] || data.roles[k as keyof ModelsPayload["roles"]] || null;

  async function save() {
    setBusy(true);
    setError("");
    const body: Record<string, unknown> = {};
    const agents: Record<string, string | null> = {};
    for (const k of changed) {
      const v = picks[k] || null;
      if (ROLES.some((r) => r.key === k)) body[k] = v;
      else agents[k] = v;
    }
    if (Object.keys(agents).length) body.agents = agents;
    try {
      const res = await fetch("/api/aera/models", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "failed");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  async function test(model: string) {
    setTesting(model);
    try {
      const res = await fetch("/api/aera/models/test", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ model }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "failed");
      setTests((t) => ({ ...t, [model]: d }));
    } catch (err) {
      setTests((t) => ({
        ...t,
        [model]: { ok: false, said: err instanceof Error ? err.message : "failed", seconds: 0, at: "", by: "" },
      }));
    } finally {
      setTesting("");
    }
  }

  const options = groups(data.catalog).map(([vendor, items]) => (
    <optgroup key={vendor} label={vendor}>
      {items.map((m) => (
        <option key={m.model} value={m.model} disabled={!m.ready}>
          {m.label} · {m.via} · {rate(m)}
          {m.ready ? "" : " · not configured here"}
        </option>
      ))}
    </optgroup>
  ));

  const testResult = (model: string | null) => {
    const t = model ? tests[model] : undefined;
    if (!t) return null;
    return (
      <span className="flex min-w-0 items-center gap-2">
        <StatusBadge status={t.ok ? "done" : "failed"}>
          {t.ok ? `answered in ${t.seconds}s` : "failed"}
        </StatusBadge>
        {!t.ok && <span className="text-destructive truncate text-[11px]">{t.said}</span>}
      </span>
    );
  };

  return (
    <div className="mt-8 space-y-10">
      {!data.may_change && (
        <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
          Only an owner or admin can change the models. This is what the team runs on now.
        </p>
      )}

      <section className="space-y-5 rounded-lg border p-5">
        {ROLES.map((r) => {
          const model = inForce(r.key);
          return (
            <div key={r.key} className="grid gap-2 md:grid-cols-[11rem_1fr] md:gap-4">
              <div>
                <p className="text-sm font-medium">{r.label}</p>
                <p className="text-muted-foreground mt-0.5 text-xs leading-snug">{r.hint}</p>
              </div>
              <div className="min-w-0 space-y-1.5">
                <select
                  className={SELECT} value={picks[r.key]} disabled={!data.may_change}
                  onChange={(e) => pick(r.key, e.target.value)} aria-label={r.label}
                >
                  <option value="">From .env: {fromEnv[r.key]}</option>
                  {r.key === "fallback" && <option value="none">No fallback</option>}
                  {options}
                </select>
                <div className="flex flex-wrap items-center gap-2">
                  {data.may_change && model && (
                    <Button
                      type="button" variant="outline" size="sm" className="h-6 px-2 text-[11px]"
                      disabled={testing !== ""} onClick={() => test(model)}
                    >
                      {testing === model ? "Testing…" : "Test"}
                    </Button>
                  )}
                  {testResult(model)}
                  {data.chosen[r.key] && (
                    <span className="text-muted-foreground font-mono text-[10px]">
                      chosen by {data.chosen[r.key].updated_by}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </section>

      <section>
        <h2 className="text-sm font-medium">Per agent</h2>
        <p className="text-muted-foreground mt-1 max-w-2xl text-xs leading-relaxed">
          An agent set here, or by its own AERA_MODEL_&lt;CODE&gt; variable, leaves its role&apos;s model.
        </p>
        <ul className="mt-3 divide-y rounded-lg border">
          {data.team.map((t) => (
            <li key={t.agent} className="grid gap-2 px-4 py-3 md:grid-cols-[11rem_1fr] md:gap-4">
              <div className="min-w-0">
                <p className="text-sm">
                  {t.name} <span className="text-muted-foreground font-mono text-[11px]">{t.agent}</span>
                </p>
                <p className="text-muted-foreground mt-0.5 truncate font-mono text-[10px]">
                  {name(t.model)} · {source(t.source)}
                </p>
              </div>
              <select
                className={SELECT} value={picks[t.agent]} disabled={!data.may_change}
                onChange={(e) => pick(t.agent, e.target.value)} aria-label={`Model for ${t.name}`}
              >
                <option value="">
                  {t.source === `AERA_MODEL_${t.agent.toUpperCase()}`
                    ? `From .env: ${name(t.model)}`
                    : "Follows its role"}
                </option>
                {options}
              </select>
            </li>
          ))}
        </ul>
      </section>

      {data.may_change && (
        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" size="sm" disabled={busy || changed.length === 0} onClick={save}>
            {busy ? "Saving…" : changed.length ? `Save ${changed.length} change${changed.length > 1 ? "s" : ""}` : "Saved"}
          </Button>
          {changed.length > 0 && (
            <Button type="button" variant="ghost" size="sm" disabled={busy}
              onClick={() => setPicks(Object.fromEntries(keys.map((k) => [k, saved(k)])))}>
              Discard
            </Button>
          )}
          {error && <p className="text-destructive text-xs">{error}</p>}
        </div>
      )}
    </div>
  );
}
