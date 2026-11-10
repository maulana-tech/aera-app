"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { McpPayload, McpServer } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

const FIELD =
  "h-9 w-full min-w-0 rounded-lg border border-input bg-transparent px-3 font-mono text-sm outline-none " +
  "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 " +
  "disabled:cursor-not-allowed disabled:opacity-60 dark:bg-input/30";

const AGENTS = [
  "supervisor", "impact", "demand", "inventory", "sourcing", "procurement",
  "logistics", "compliance", "simulation", "precedent", "execution", "exposure",
] as const;

export function Servers({ data }: { data: McpPayload }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [token, setToken] = useState("");
  const [agents, setAgents] = useState<string[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [tested, setTested] = useState<Record<string, string>>({});

  async function post(path: string, body: unknown, what: string) {
    setBusy(what);
    setError("");
    try {
      const res = await fetch(`/api/aera/${path}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body ?? {}),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "failed");
      return d;
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
      return null;
    } finally {
      setBusy("");
    }
  }

  async function add() {
    const d = await post("mcp/servers", { name, url, token: token || undefined, agents }, "add");
    if (d) {
      setName("");
      setUrl("");
      setToken("");
      setAgents([]);
      router.refresh();
    }
  }

  async function test(s: McpServer) {
    const d = await post(`mcp/servers/${s.id}/test`, {}, `test-${s.id}`);
    if (d) {
      setTested((t) => ({ ...t, [s.id]: d.ok ? d.note : `unreachable — ${d.note}` }));
      router.refresh();
    }
  }

  const locked = !data.may_change || !!busy;

  return (
    <div className="mt-8 space-y-6">
      <section className="rounded-lg border">
        <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
          <p className="text-sm font-medium">Servers AERA calls out to</p>
          <span className="text-muted-foreground text-xs">
            {data.servers.length === 0
              ? "none yet — the agents use their own tools only"
              : `${data.servers.length} configured`}
          </span>
        </div>

        {data.servers.length > 0 && (
          <ul className="divide-y">
            {data.servers.map((s) => {
              const writers = s.tools.filter((t) => !t.read_only).length;
              return (
                <li key={s.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium">{s.name}</p>
                    <StatusBadge status={s.enabled ? "done" : "off"}>
                      {s.enabled ? "enabled" : "off"}
                    </StatusBadge>
                    {s.last_error && <StatusBadge status="held">last call failed</StatusBadge>}
                    <span className="text-muted-foreground ml-auto font-mono text-[10px]">
                      {s.tools.length} tool{s.tools.length === 1 ? "" : "s"}
                      {writers > 0 && ` · ${writers} that write`}
                    </span>
                  </div>
                  <p className="text-muted-foreground mt-1 font-mono text-[10px] break-all">
                    {s.url}
                    {s.token_set && " · bearer token set"}
                  </p>
                  <p className="text-muted-foreground mt-1 text-xs">
                    {s.agents.length ? (
                      <>
                        {s.offered} of {s.tools.length} usable by{" "}
                        <span className="font-mono">{s.agents.join(", ")}</span>
                      </>
                    ) : (
                      "verified, but no agent may use it yet"
                    )}
                    {s.last_error && (
                      <span className="text-destructive"> · {s.last_error}</span>
                    )}
                  </p>
                  {tested[s.id] && (
                    <p className="text-muted-foreground mt-1 text-xs">{tested[s.id]}</p>
                  )}

                  {/* Its tools, so nothing arrives unseen. A remote tool that
                      says nothing about itself is shown as a writer, which is
                      the cautious reading and the one that matters. */}
                  {s.tools.length > 0 && (
                    <details className="mt-2">
                      <summary className="text-muted-foreground cursor-pointer text-xs">
                        What it offers
                      </summary>
                      <ul className="mt-1.5 space-y-1">
                        {s.tools.map((t) => (
                          <li key={t.name} className="flex items-baseline gap-2 text-xs">
                            <span className="font-mono">{t.name}</span>
                            <span
                              className={
                                t.read_only
                                  ? "text-muted-foreground font-mono text-[10px]"
                                  : "text-amber-700 font-mono text-[10px] dark:text-amber-400"
                              }
                            >
                              {t.read_only ? "reads" : "writes"}
                            </span>
                            <span className="text-muted-foreground truncate">
                              {t.description}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}

                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" disabled={locked} onClick={() => test(s)}>
                      {busy === `test-${s.id}` ? "Calling…" : "Test"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={locked}
                      onClick={async () => {
                        await post(`mcp/servers/${s.id}`, { enabled: !s.enabled }, `t-${s.id}`);
                        router.refresh();
                      }}
                    >
                      {s.enabled ? "Switch off" : "Switch on"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={locked}
                      onClick={async () => {
                        await post(`mcp/servers/${s.id}/delete`, {}, `d-${s.id}`);
                        router.refresh();
                      }}
                    >
                      Remove
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        <div className="border-t px-4 py-4">
          <p className="text-sm font-medium">Add a server</p>
          <p className="text-muted-foreground mt-1 max-w-3xl text-xs leading-relaxed">
            It is called once before it is saved. A server nobody could reach, sitting enabled
            in this list, is a tool an agent will try and a handling will wait on.
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <label className="space-y-1.5">
              <span className="text-xs font-medium">Name</span>
              <input className={FIELD} value={name} disabled={locked}
                     placeholder="carrier-track" onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="space-y-1.5 sm:col-span-2">
              <span className="text-xs font-medium">Endpoint</span>
              <input className={FIELD} value={url} disabled={locked} spellCheck={false}
                     placeholder="https://tools.example.com/mcp"
                     onChange={(e) => setUrl(e.target.value)} />
            </label>
            <label className="space-y-1.5">
              <span className="text-xs font-medium">Bearer token</span>
              <input className={FIELD} type="password" autoComplete="off" value={token}
                     disabled={locked} placeholder="optional"
                     onChange={(e) => setToken(e.target.value)} />
            </label>
            <div className="space-y-1.5 sm:col-span-2">
              <span className="text-xs font-medium">Which agents may use it</span>
              <div className="flex flex-wrap gap-1.5">
                {AGENTS.map((a) => {
                  const on = agents.includes(a);
                  return (
                    <button
                      key={a}
                      type="button"
                      disabled={locked}
                      onClick={() =>
                        setAgents((xs) => (on ? xs.filter((x) => x !== a) : [...xs, a]))
                      }
                      className={`rounded-full border px-2.5 py-1 font-mono text-[10px] transition-colors ${
                        on ? "border-foreground" : "border-input text-muted-foreground"
                      }`}
                    >
                      {a}
                    </button>
                  );
                })}
              </div>
              <span className="text-muted-foreground block text-xs">
                Pick nobody and the server is registered but reaches no
                handling. Verifying a server and giving an agent its tools are
                two separate acts, and the second one is the one that matters.
              </span>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button size="sm" disabled={locked || !name || !url} onClick={add}>
              {busy === "add" ? "Calling it…" : "Add"}
            </Button>
            {!data.may_change && (
              <p className="text-muted-foreground text-xs">
                Only an admin or a procurement lead can change this.
              </p>
            )}
            {error && <p className="text-destructive text-xs">{error}</p>}
          </div>
        </div>
      </section>
    </div>
  );
}
