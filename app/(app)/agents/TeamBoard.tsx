"use client";

import { Loader2, Lock, MessageSquare, Pencil, Plus, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { AgentStatus, Capability, ComposeResult, TeamAgent, TeamPayload } from "@/app/lib";
import { AgentBadge } from "@/components/agent-card";
import { Field, TextArea } from "@/components/profile-editor";
import { StatusBadge } from "@/components/status-badge";
import { CapChip, DiffView, RoleMarks } from "@/components/team-list";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";
import { cn } from "@/lib/utils";

/** A capability is locked when it belongs to another role, or is this core role's own. */
function lockState(c: Capability, a: TeamAgent): "own" | "other" | null {
  if (!c.locked_to) return null;
  return c.locked_to === a.code ? "own" : "other";
}

function AgentCardEditable({ a, mayChange, onEdit }: {
  a: TeamAgent; mayChange: boolean; onEdit: () => void;
}) {
  const tools = Object.values(a.tools ?? {}).flat();
  return (
    <article className={cn("flex flex-col rounded-lg border p-4", a.status === "disabled" && "opacity-60")}>
      <div className="flex items-start gap-3">
        <AgentBadge nickname={a.nickname} large />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <h3 className="font-medium leading-none">{a.nickname}</h3>
            <span className="text-muted-foreground text-xs">{a.title}</span>
            <RoleMarks a={a} />
            {a.status !== "active" && <StatusBadge status={a.status} />}
          </div>
          <p className="text-muted-foreground mt-1.5 text-xs leading-relaxed">{a.brief}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1">
        {a.capabilities.map((c) => <CapChip key={c} name={c} />)}
      </div>
      <p className="text-muted-foreground mt-2 font-mono text-[10px]">
        {tools.length} tools · {a.model ?? "model?"} · v{a.version ?? 1} · {a.origin}
      </p>
      <div className="mt-auto flex flex-wrap gap-2 pt-3">
        <Button asChild size="xs" variant="outline">
          <Link href={`/agents/${a.code}`}><MessageSquare /> Open</Link>
        </Button>
        {mayChange && (
          <Button size="xs" variant="ghost" onClick={onEdit}><Pencil /> Edit</Button>
        )}
      </div>
    </article>
  );
}

function EditDialog({ a, caps, open, onOpenChange }: {
  a: TeamAgent; caps: Capability[]; open: boolean; onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const [title, setTitle] = useState(a.title);
  const [brief, setBrief] = useState(a.brief);
  const [prompt, setPrompt] = useState(a.prompt);
  const [chosen, setChosen] = useState<string[]>(a.capabilities);
  const [status, setStatus] = useState<AgentStatus>(a.status);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await post(`team/${a.code}`, {
        title, brief, prompt, capabilities: chosen,
        ...(status !== a.status ? { status } : {}),
      });
      onOpenChange(false);
      router.refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader className="border-b">
          <DialogTitle>{a.nickname} · {a.title}</DialogTitle>
          <DialogDescription className="text-xs">
            {a.core ? "A core role: it cannot be disabled, and its locked capability cannot be removed." : "A specialist. Tools come only from the capability catalogue."}
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[70vh] space-y-5 overflow-y-auto px-5 py-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
            <Field label="Status">
              <select value={status} disabled={a.core} onChange={(e) => setStatus(e.target.value as AgentStatus)}
                className="border-input bg-background h-8 w-full rounded-lg border px-2 text-sm disabled:opacity-50 dark:bg-input/30">
                <option value="active">active</option>
                <option value="draft">draft</option>
                <option value="disabled">disabled</option>
              </select>
            </Field>
            <Field label="Brief" className="sm:col-span-2"><TextArea rows={2} value={brief} onChange={(e) => setBrief(e.target.value)} /></Field>
          </div>

          <div>
            <p className="text-muted-foreground text-xs">Capabilities</p>
            <ul className="mt-2 space-y-2">
              {caps.map((c) => {
                const lock = lockState(c, a);
                const on = chosen.includes(c.name);
                return (
                  <li key={c.name}>
                    <label className={cn("flex items-start gap-2", lock && "cursor-not-allowed")}>
                      <input type="checkbox" className="accent-primary mt-0.5 size-4" checked={on || (lock === "own" && a.core)}
                        disabled={lock === "other" || (lock === "own" && a.core)}
                        onChange={() => setChosen(on ? chosen.filter((x) => x !== c.name) : [...chosen, c.name])} />
                      <span className="min-w-0">
                        <span className="inline-flex items-center gap-1 font-mono text-xs">
                          {lock && <Lock className="size-3" />}{c.name}
                          {lock === "other" && <span className="text-muted-foreground">· locked to {c.locked_to}</span>}
                        </span>
                        <span className="text-muted-foreground block text-[11px] leading-relaxed">{c.description}</span>
                        {c.tools.length > 0 && <span className="text-muted-foreground block font-mono text-[10px]">{c.tools.join(" · ")}</span>}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>

          <Field label="Prompt" hint="{NAME} and {BUSINESS} are filled with the profile when the agent runs.">
            <TextArea rows={12} className="font-mono text-xs" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          </Field>
          {error && <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>}
        </div>
        <div className="flex gap-2 border-t px-5 py-3">
          <Button size="sm" onClick={save} disabled={busy}>{busy && <Loader2 className="animate-spin" />}Save</Button>
          <Button size="sm" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function NewRole({ caps }: { caps: Capability[] }) {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [chosen, setChosen] = useState<string[]>(["knowledge", "documents"]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const open = caps.filter((c) => !c.locked_to);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post("team/new", { title, brief, capabilities: chosen });
      setTitle(""); setBrief("");
      router.refresh();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={add} className="space-y-3 rounded-lg border p-4">
      <h3 className="text-sm font-medium">Add a custom role</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Copy editor" required /></Field>
        <Field label="Brief"><Input value={brief} onChange={(e) => setBrief(e.target.value)} placeholder="Tightens every deliverable before QA" /></Field>
      </div>
      <div className="flex flex-wrap gap-2">
        {open.map((c) => {
          const on = chosen.includes(c.name);
          return (
            <button key={c.name} type="button" title={c.description} aria-pressed={on}
              onClick={() => setChosen(on ? chosen.filter((x) => x !== c.name) : [...chosen, c.name])}
              className={cn("rounded-full border px-3 py-1 font-mono text-[11px]", on ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30")}>
              {c.name}
            </button>
          );
        })}
      </div>
      <p className="text-muted-foreground text-[11px]">Money, veto and delegation stay locked to Treasurer, Guardian and Supervisor.</p>
      {error && <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>}
      <Button type="submit" size="sm" disabled={busy || !title.trim()}>{busy ? <Loader2 className="animate-spin" /> : <Plus />}Add role</Button>
    </form>
  );
}

function Recompose() {
  const router = useRouter();
  const [proposal, setProposal] = useState<ComposeResult | null>(null);
  const [busy, setBusy] = useState<"compose" | "apply" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function compose() {
    setBusy("compose");
    setError(null);
    try {
      setProposal(await post<ComposeResult>("team/compose", {}));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }
  async function apply() {
    setBusy("apply");
    setError(null);
    try {
      await post("team/apply", {});
      setProposal(null);
      router.refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }
  const changes = proposal ? proposal.diff.add.length + proposal.diff.remove.length + proposal.diff.change.length : 0;

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium">Recompose from the profile</h3>
          <p className="text-muted-foreground text-xs">See what the Composer would change before anything changes.</p>
        </div>
        <Button size="sm" variant="outline" onClick={compose} disabled={!!busy}>
          {busy === "compose" ? <Loader2 className="animate-spin" /> : <RefreshCw />}Propose
        </Button>
      </div>
      {proposal && <DiffView diff={proposal.diff} />}
      {proposal && changes > 0 && (
        <Button size="sm" onClick={apply} disabled={!!busy}>{busy === "apply" && <Loader2 className="animate-spin" />}Apply {changes} change{changes === 1 ? "" : "s"}</Button>
      )}
      {error && <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>}
    </div>
  );
}

export function TeamBoard({ data }: { data: TeamPayload }) {
  const [editing, setEditing] = useState<string | null>(null);
  const core = data.agents.filter((a) => a.core);
  const rest = data.agents.filter((a) => !a.core);
  const editingAgent = data.agents.find((a) => a.code === editing);

  const grid = (agents: TeamAgent[]) => (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {agents.map((a) => (
        <AgentCardEditable key={a.code} a={a} mayChange={data.may_change} onEdit={() => setEditing(a.code)} />
      ))}
    </div>
  );

  return (
    <>
      <section className="mt-8">
        <h2 className="mb-3 text-sm font-medium">Core roles <span className="text-muted-foreground font-normal">· always present</span></h2>
        {grid(core)}
      </section>
      <section className="mt-8">
        <h2 className="mb-3 text-sm font-medium">Specialists <span className="text-muted-foreground font-normal">· composed from the profile</span></h2>
        {rest.length ? grid(rest) : <p className="text-muted-foreground text-sm">No specialists yet.</p>}
      </section>
      {data.may_change && (
        <section className="mt-8 grid gap-4 lg:grid-cols-2">
          <Recompose />
          <NewRole caps={data.capabilities} />
        </section>
      )}
      {editingAgent && (
        <EditDialog key={editingAgent.code} a={editingAgent} caps={data.capabilities}
          open onOpenChange={(v) => !v && setEditing(null)} />
      )}
    </>
  );
}
