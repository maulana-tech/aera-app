"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { SkillsPayload } from "@/app/lib";
import { Button } from "@/components/ui/button";

const FIELD =
  "h-9 w-full min-w-0 rounded-lg border border-input bg-transparent px-3 font-mono text-sm outline-none " +
  "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 " +
  "disabled:cursor-not-allowed disabled:opacity-60 dark:bg-input/30";

const CHIP =
  "rounded-full border px-2 py-0.5 font-mono text-[10px] transition-colors disabled:opacity-60";

/**
 * Writing a procedure down. The server validates with the same checks
 * core/skills.py runs over the built-in catalogue, so everything refused here
 * is refused for a reason worth reading: a tool nobody wrote, an agent that
 * does not exist, or a procedure restricted to an agent that cannot reach its
 * own tools. The problems come back as a list and are shown as a list.
 */
export function Write({ data }: { data: SkillsPayload }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [agents, setAgents] = useState<string[]>([]);
  const [tools, setTools] = useState<string[]>([]);
  const [steps, setSteps] = useState("");
  const [busy, setBusy] = useState("");
  const [problems, setProblems] = useState<string[]>([]);

  async function post(path: string, body: unknown, what: string) {
    setBusy(what);
    setProblems([]);
    try {
      const res = await fetch(`/api/sigap/${path}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body ?? {}),
      });
      const d = await res.json();
      if (!res.ok) {
        setProblems(d.problems ?? [d.error ?? "failed"]);
        return null;
      }
      return d;
    } catch (err) {
      setProblems([err instanceof Error ? err.message : "failed"]);
      return null;
    } finally {
      setBusy("");
    }
  }

  async function add() {
    const lines = steps.split("\n").map((s) => s.trim()).filter(Boolean);
    const d = await post(
      "skills",
      { name, title, description, agents, tools, steps: lines },
      "add",
    );
    if (d) {
      setName("");
      setTitle("");
      setDescription("");
      setAgents([]);
      setTools([]);
      setSteps("");
      setOpen(false);
      router.refresh();
    }
  }

  function toggle(list: string[], set: (v: string[]) => void, v: string) {
    set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  }

  if (!data.may_change) return null;

  return (
    <section className="mt-6 rounded-lg border">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <p className="text-sm font-medium">Write a procedure</p>
        <p className="text-muted-foreground text-xs">
          An order you decided once, so it is not decided again differently next time.
        </p>
        <Button
          size="sm"
          variant={open ? "outline" : "default"}
          className="ml-auto"
          onClick={() => setOpen(!open)}
        >
          {open ? "Cancel" : "New skill"}
        </Button>
      </div>

      {open && (
        <div className="space-y-4 border-t px-4 py-4">
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
                Name
              </label>
              <input
                className={`${FIELD} mt-1`}
                placeholder="check_the_bonded_stock"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <p className="text-muted-foreground mt-1 text-[10px]">
                Lower case, underscores. This is what an agent calls.
              </p>
            </div>
            <div>
              <label className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
                Title
              </label>
              <input
                className={`${FIELD} mt-1`}
                placeholder="Check what is already in bond"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
              Why this order
            </label>
            <input
              className={`${FIELD} mt-1`}
              placeholder="Bonded goods clear faster than a new import, so look there before pricing freight."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div>
            <label className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
              Steps, one per line
            </label>
            <textarea
              className={`${FIELD} mt-1 h-28 py-2 leading-relaxed`}
              placeholder={
                "Find what is sitting in bond for this material.\n" +
                "Rule it before pricing it: bonded is not the same as cleared.\n" +
                "Say what could not be checked rather than treating it as checked."
              }
              value={steps}
              onChange={(e) => setSteps(e.target.value)}
            />
            <p className="text-muted-foreground mt-1 text-[10px]">
              A step is a sentence about what that step decides. Without steps it is a
              label, not a procedure, and it is refused.
            </p>
          </div>

          <div>
            <label className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
              Who may run it
            </label>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {data.agents.map((a) => (
                <button
                  key={a.code}
                  type="button"
                  disabled={!!busy}
                  className={`${CHIP} ${
                    agents.includes(a.code)
                      ? "border-primary bg-primary/10"
                      : "border-input text-muted-foreground"
                  }`}
                  onClick={() => toggle(agents, setAgents, a.code)}
                >
                  {a.code}
                </button>
              ))}
            </div>
            <p className="text-muted-foreground mt-1 text-[10px]">
              Nobody picked means any agent. Pick one and it is refused to everybody
              else, with the reason — and it must be made of tools that agent can
              actually reach, or nobody could run it.
            </p>
          </div>

          <div>
            <label className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
              Tools it composes ({tools.length})
            </label>
            <div className="mt-1 flex max-h-40 flex-wrap gap-1.5 overflow-y-auto rounded-lg border p-2">
              {data.tools.map((t) => (
                <button
                  key={t}
                  type="button"
                  disabled={!!busy}
                  className={`${CHIP} ${
                    tools.includes(t)
                      ? "border-primary bg-primary/10"
                      : "border-input text-muted-foreground"
                  }`}
                  onClick={() => toggle(tools, setTools, t)}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {problems.length > 0 && (
            <ul className="text-destructive space-y-1 text-xs">
              {problems.map((p) => (
                <li key={p}>· {p}</li>
              ))}
            </ul>
          )}

          <Button size="sm" disabled={!!busy || !name || !title || !steps.trim()} onClick={add}>
            {busy === "add" ? "Checking…" : "Save"}
          </Button>
        </div>
      )}
    </section>
  );
}

/** Removing one of the written ones. The catalogue itself is code. */
export function Remove({ name }: { name: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  return (
    <Button
      size="sm"
      variant="ghost"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        await fetch(`/api/sigap/skills/${name}/delete`, { method: "POST" });
        setBusy(false);
        router.refresh();
      }}
    >
      Remove
    </Button>
  );
}
