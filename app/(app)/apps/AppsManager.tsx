"use client";

/* eslint-disable @next/next/no-img-element -- app logos come from Composio's CDN, any size */

import { Blocks, ExternalLink, Loader2, RefreshCw, Search, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import type { AppTool, AppsPayload, ConnectedApp, ToolkitHit } from "@/app/lib";
import { Chip } from "@/components/dort";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";
import { cn } from "@/lib/utils";

type AgentRef = { code: string; nickname: string };

function Logo({ src, size = 32 }: { src: string | null; size?: number }) {
  return src
    ? <img src={src} alt="" width={size} height={size} className="shrink-0 rounded-md border bg-white object-contain p-0.5" style={{ width: size, height: size }} />
    : <span className="bg-raised text-brand grid shrink-0 place-items-center rounded-md border" style={{ width: size, height: size }}><Blocks className="size-4" /></span>;
}

/* ----------------------------------------------------------- one connected app */
function AppCard({ app, agents, connected, mayChange }: { app: ConnectedApp; agents: AgentRef[]; connected: boolean; mayChange: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [granted, setGranted] = useState<string[]>(app.agents);
  const [tools, setTools] = useState<AppTool[]>(app.tools);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState("");
  const [said, setSaid] = useState("");
  const dirty = JSON.stringify(granted) !== JSON.stringify(app.agents) || JSON.stringify(tools) !== JSON.stringify(app.tools);
  const used = tools.filter((t) => t.enabled);
  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const list = q ? tools.filter((t) => `${t.name} ${t.slug} ${t.description}`.toLowerCase().includes(q)) : tools;
    return [...list].sort((a, b) => Number(b.enabled) - Number(a.enabled) || Number(b.important) - Number(a.important) || a.name.localeCompare(b.name));
  }, [tools, filter]);

  const act = async (what: string, run: () => Promise<unknown>, done: string) => {
    setBusy(what);
    setSaid("");
    try { await run(); setSaid(done); router.refresh(); } catch (e) { setSaid(errorText(e)); } finally { setBusy(""); }
  };
  const save = () => act("save", () => post(`apps/${app.toolkit}`, {
    agents: granted,
    tools: Object.fromEntries(tools.map((t) => [t.slug, { enabled: t.enabled, write_allowed: t.write_allowed }])),
  }), "Saved. Agents see the change on their next step.");
  const set = (slug: string, patch: Partial<AppTool>) => setTools((ts) => ts.map((t) => (t.slug === slug ? { ...t, ...patch } : t)));

  return (
    <li className="bg-card-grad rounded-xl border shadow-soft">
      <div className="flex flex-wrap items-center gap-3 p-4">
        <Logo src={app.logo} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-fg text-[15px]">{app.name}</p>
            <Chip tone={connected ? "ok" : "warn"}>{connected ? "connected" : "connection missing"}</Chip>
            {!app.enabled && <Chip tone="neutral">switched off</Chip>}
          </div>
          <p className="text-muted-foreground mt-0.5 text-[12px]">
            {used.length} of {tools.length} tools in use · {app.agents.length ? `given to ${app.agents.map((c) => agents.find((a) => a.code === c)?.nickname ?? c).join(", ")}` : "given to no agent yet"}
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={() => setOpen((o) => !o)}>{open ? "Close" : "Manage"}</Button>
      </div>

      {open && (
        <div className="space-y-5 border-t p-4">
          <div>
            <p className="text-text text-[13px]">Which agents may use it</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {agents.map((a) => {
                const on = granted.includes(a.code);
                return (
                  <button key={a.code} type="button" disabled={!mayChange}
                    onClick={() => setGranted((g) => (on ? g.filter((x) => x !== a.code) : [...g, a.code]))}
                    className={cn("h-7 rounded-md border px-2.5 text-[12.5px] transition-colors disabled:opacity-60",
                      on ? "border-brand bg-brand text-white" : "text-text hover:bg-raised")}>
                    {a.nickname}
                  </button>
                );
              })}
            </div>
            <p className="text-muted-foreground mt-1.5 text-[11.5px]">The Guardian and the Treasurer never take outside tools.</p>
          </div>

          <div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-text text-[13px]">Tools ({used.length} in use)</p>
              <div className="relative">
                <Search className="text-muted-foreground absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2" />
                <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter tools" className="h-8 w-56 pl-8 text-[12.5px]" />
              </div>
            </div>
            <ul className="mt-2 max-h-[420px] divide-y overflow-y-auto rounded-lg border">
              {shown.map((t) => (
                <li key={t.slug} className="flex flex-wrap items-start gap-3 px-3 py-2.5">
                  <input type="checkbox" checked={t.enabled} disabled={!mayChange} onChange={(e) => set(t.slug, { enabled: e.target.checked })}
                    className="mt-1 size-4 accent-[var(--brand)]" aria-label={`Use ${t.name}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-fg text-[13px]">{t.name}</span>
                      <Chip tone={t.read_only ? "ok" : "warn"} className="h-5 text-[10.5px]">{t.read_only ? "reads" : "changes things"}</Chip>
                      {t.important && <span className="text-muted-foreground text-[10.5px]">main</span>}
                    </div>
                    <p className="text-muted-foreground mt-0.5 line-clamp-2 text-[11.5px] leading-relaxed">{t.description}</p>
                  </div>
                  {!t.read_only && t.enabled && (
                    <label className="text-text flex items-center gap-1.5 text-[11.5px]">
                      <input type="checkbox" checked={t.write_allowed} disabled={!mayChange} onChange={(e) => set(t.slug, { write_allowed: e.target.checked })}
                        className="size-3.5 accent-[var(--brand)]" />
                      allow (each call waits for you)
                    </label>
                  )}
                </li>
              ))}
              {shown.length === 0 && <li className="text-muted-foreground px-3 py-4 text-[12.5px]">No tool matches.</li>}
            </ul>
          </div>

          {mayChange ? (
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" onClick={save} disabled={!dirty || !!busy}>{busy === "save" ? <Loader2 className="animate-spin" /> : null} Save</Button>
              <Button size="sm" variant="outline" disabled={!!busy}
                onClick={() => act("enable", () => post(`apps/${app.toolkit}`, { enabled: !app.enabled }), app.enabled ? "Switched off: no agent sees its tools." : "Switched on.")}>
                {app.enabled ? "Switch off" : "Switch on"}
              </Button>
              <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => act("refresh", () => post(`apps/${app.toolkit}/refresh`), "Tools read again from Composio; your choices kept.")}>
                <RefreshCw className={cn("size-3.5", busy === "refresh" && "animate-spin")} /> Refresh tools
              </Button>
              <Button size="sm" variant="ghost" className="text-bad ml-auto" disabled={!!busy}
                onClick={() => { if (window.confirm(`Stop using ${app.name}? The connection stays in Composio until you revoke it there.`)) void act("delete", () => post(`apps/${app.toolkit}/delete`), "Removed."); }}>
                <Trash2 className="size-3.5" /> Remove
              </Button>
            </div>
          ) : (
            <p className="text-muted-foreground text-[12px]">Only an owner or admin changes apps.</p>
          )}
          {said && <p className="text-muted-foreground text-[12.5px]">{said}</p>}
        </div>
      )}
    </li>
  );
}

/* ------------------------------------------------------------- the catalogue */
function AddApp({ added, connected, mayChange }: { added: Set<string>; connected: Set<string>; mayChange: boolean }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<ToolkitHit[] | null>(null);
  const [busy, setBusy] = useState("");
  const [said, setSaid] = useState<Record<string, string>>({});
  const [opened, setOpened] = useState<Set<string>>(new Set());

  const search = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setBusy("search");
    try {
      const r = await fetch(`/api/aera/apps/search?q=${encodeURIComponent(q)}`).then((x) => x.json());
      if (r.error) throw new Error(r.error);
      setHits(r.toolkits);
    } catch (err) {
      setSaid({ _: errorText(err) });
    } finally { setBusy(""); }
  };
  const connect = async (t: ToolkitHit) => {
    setBusy(t.slug);
    setSaid((s) => ({ ...s, [t.slug]: "" }));
    try {
      const r = await post<{ connected?: boolean; url?: string }>("apps/connect", { toolkit: t.slug });
      if (r.url) {
        window.open(r.url, "_blank", "noopener,noreferrer");
        setOpened((o) => new Set(o).add(t.slug));
        setSaid((s) => ({ ...s, [t.slug]: "Sign in on the Composio page that opened, then come back and press Add to AERA." }));
      } else {
        await add(t);
      }
    } catch (err) {
      setSaid((s) => ({ ...s, [t.slug]: errorText(err) }));
    } finally { setBusy(""); }
  };
  const add = async (t: ToolkitHit) => {
    setBusy(t.slug);
    try {
      await post("apps/add", { toolkit: t.slug });
      setSaid((s) => ({ ...s, [t.slug]: "Added. Open it above to give agents its tools." }));
      router.refresh();
    } catch (err) {
      setSaid((s) => ({ ...s, [t.slug]: errorText(err) }));
    } finally { setBusy(""); }
  };

  return (
    <section className="mt-10">
      <h2 className="text-fg text-[16px] font-medium">Connect an app</h2>
      <form onSubmit={search} className="mt-3 flex max-w-xl gap-2">
        <div className="relative flex-1">
          <Search className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Slack, Google Sheets, Notion, HubSpot…" className="pl-9" />
        </div>
        <Button type="submit" disabled={busy === "search"}>{busy === "search" ? <Loader2 className="animate-spin" /> : "Search"}</Button>
      </form>
      {said._ && <p className="text-bad mt-2 text-[12.5px]">{said._}</p>}
      {hits && (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {hits.length === 0 && <li className="text-muted-foreground text-sm">Nothing matches.</li>}
          {hits.map((t) => {
            const isAdded = added.has(t.slug);
            const isConnected = connected.has(t.slug) || t.no_auth;
            return (
              <li key={t.slug} className="bg-card-grad flex flex-col rounded-xl border p-4">
                <div className="flex items-start gap-3">
                  <Logo src={t.logo} size={36} />
                  <div className="min-w-0 flex-1">
                    <p className="text-fg text-[14px]">{t.name}</p>
                    <p className="text-muted-foreground text-[11.5px]">{t.tools_count ?? "?"} tools{t.categories.length ? ` · ${t.categories.join(", ")}` : ""}</p>
                  </div>
                  {isAdded ? <Chip tone="ok">added</Chip> : isConnected ? <Chip tone="info">connected</Chip> : null}
                </div>
                <p className="text-body mt-2 line-clamp-3 flex-1 text-[12.5px] leading-relaxed">{t.description}</p>
                {mayChange && !isAdded && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {!isConnected && (
                      <Button size="sm" variant="outline" disabled={busy === t.slug} onClick={() => void connect(t)}>
                        {busy === t.slug ? <Loader2 className="animate-spin" /> : <ExternalLink className="size-3.5" />} Connect
                      </Button>
                    )}
                    <Button size="sm" disabled={busy === t.slug || (!isConnected && !opened.has(t.slug))} onClick={() => void add(t)}>Add to AERA</Button>
                  </div>
                )}
                {said[t.slug] && <p className="text-muted-foreground mt-2 text-[11.5px] leading-relaxed">{said[t.slug]}</p>}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export function AppsManager({ data, agents }: { data: AppsPayload; agents: AgentRef[] }) {
  const connected = new Set(data.connections.map((c) => c.toolkit));
  const added = new Set(data.apps.map((a) => a.toolkit));
  return (
    <>
      <div className="text-muted-foreground mt-6 flex flex-wrap items-center gap-2 text-[12.5px]">
        <Chip tone="ok">Composio connected</Chip>
        <span>as user <span className="font-mono">{data.user_id}</span> · {data.connections.length} active connection(s)</span>
        {data.error && <span className="text-bad">· {data.error}</span>}
      </div>
      <section className="mt-6">
        <h2 className="text-fg text-[16px] font-medium">Your apps</h2>
        {data.apps.length === 0 ? (
          <p className="text-muted-foreground mt-2 text-sm">No app added yet. Search below, connect one, then add it.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {data.apps.map((a) => <AppCard key={a.toolkit} app={a} agents={agents} connected={connected.has(a.toolkit) || !a.account_id} mayChange={data.may_change} />)}
          </ul>
        )}
      </section>
      <AddApp added={added} connected={connected} mayChange={data.may_change} />
    </>
  );
}
