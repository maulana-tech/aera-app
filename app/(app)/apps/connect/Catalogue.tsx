"use client";

/* eslint-disable @next/next/no-img-element -- app logos come from Composio's CDN, any size */

import { Blocks, Check, ChevronDown, ExternalLink, Loader2, Plus, Search, Settings2, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ToolkitHit } from "@/app/lib";
import { Chip } from "@/components/dort";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";
import { cn } from "@/lib/utils";

type Hit = ToolkitHit & { connected?: boolean; added?: boolean };
type Page = { toolkits: Hit[]; next_cursor: string | null; total: number | null; error?: string };

/** How many categories show as chips; the rest are in a list. */
const MAIN_CATEGORIES = 10;
const pretty = (slug: string) => slug.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function Logo({ src, size = 40 }: { src: string | null; size?: number }) {
  return src
    ? <img src={src} alt="" width={size} height={size} className="shrink-0 rounded-lg border bg-white object-contain p-1" style={{ width: size, height: size }} />
    : <span className="bg-raised text-brand grid shrink-0 place-items-center rounded-lg border" style={{ width: size, height: size }}><Blocks className="size-5" /></span>;
}

/* The long tail of Composio's categories (hundreds): a button that opens a searchable list instead of a native
 * select nobody can scan. Typing filters; arrows and Enter pick; Escape or a click outside closes. */
function CategoryPicker({ options, value, active, onPick }: {
  options: { id: string; name: string }[]; value: string; active: boolean; onPick: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [term, setTerm] = useState("");
  const [cursor, setCursor] = useState(0);
  const box = useRef<HTMLDivElement | null>(null);
  const input = useRef<HTMLInputElement | null>(null);
  const sorted = useMemo(() => [...options].sort((x, y) => x.name.localeCompare(y.name)), [options]);
  const shown = useMemo(() => {
    const t = term.trim().toLowerCase();
    return t ? sorted.filter((c) => c.name.toLowerCase().includes(t)) : sorted;
  }, [sorted, term]);
  const current = sorted.find((c) => c.id === value);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", away);
    const t = setTimeout(() => input.current?.focus(), 0);
    return () => { document.removeEventListener("mousedown", away); clearTimeout(t); };
  }, [open]);

  const choose = (id: string) => { onPick(id); setOpen(false); setTerm(""); setCursor(0); };

  return (
    <div ref={box} className="relative">
      <div className={cn("inline-flex h-8 items-center rounded-full border text-[12.5px] transition-colors",
        active ? "border-brand bg-brand text-white" : "text-text hover:bg-raised")}>
        <button type="button" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen((o) => !o)}
          className="inline-flex h-full items-center gap-1.5 pr-2 pl-3">
          {active && current ? current.name : `More categories (${options.length})`}
          <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} />
        </button>
        {active && (
          <button type="button" aria-label="Clear the category" onClick={() => onPick("")}
            className="mr-1 grid size-6 place-items-center rounded-full hover:bg-white/20">
            <X className="size-3.5" />
          </button>
        )}
      </div>
      {open && (
        <div className="animate-in fade-in slide-in-from-top-1 absolute top-10 left-0 z-30 w-[300px] rounded-xl border bg-white p-2 shadow-float duration-150">
          <div className="relative">
            <Search className="text-muted-foreground absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2" />
            <Input ref={input} value={term} placeholder="Find a category"
              onChange={(e) => { setTerm(e.target.value); setCursor(0); }}
              onKeyDown={(e) => {
                if (e.key === "Escape") { e.preventDefault(); setOpen(false); }
                else if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, shown.length - 1)); }
                else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
                else if (e.key === "Enter") { e.preventDefault(); if (shown[cursor]) choose(shown[cursor].id); }
              }}
              className="h-8 pl-8 text-[12.5px]" />
          </div>
          <ul role="listbox" aria-label="Categories" className="mt-2 max-h-[300px] overflow-y-auto">
            {shown.length === 0 && <li className="text-muted-foreground px-2.5 py-2 text-[12.5px]">No category matches.</li>}
            {shown.map((c, i) => (
              <li key={c.id} role="option" aria-selected={c.id === value}>
                <button type="button" onMouseEnter={() => setCursor(i)} onClick={() => choose(c.id)}
                  ref={(el) => { if (i === cursor && el) el.scrollIntoView({ block: "nearest" }); }}
                  className={cn("flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-left text-[12.5px]",
                    i === cursor ? "bg-raised text-fg" : "text-text")}>
                  <span className="truncate">{c.name}</span>
                  {c.id === value && <Check className="text-brand size-3.5 shrink-0" />}
                </button>
              </li>
            ))}
          </ul>
          <p className="text-muted-foreground border-t px-2.5 pt-2 text-[11px]">{shown.length} of {options.length} · ↑ ↓ Enter · Esc</p>
        </div>
      )}
    </div>
  );
}

/* The catalogue of tools to connect: Composio's toolkits, most used first, by category or search. Connecting goes to
 * the app's own sign-in on Composio and comes back here with ?connected=<slug>, which adds it to AERA at once. */
export function Catalogue({ mayChange, ready, added: addedAtLoad }: { mayChange: boolean; ready: string[]; added: string[] }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [cats, setCats] = useState<{ id: string; name: string }[]>([]);
  const [items, setItems] = useState<Hit[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [note, setNote] = useState<Record<string, string>>({});
  const [added, setAdded] = useState<Set<string>>(new Set(addedAtLoad));
  const [banner, setBanner] = useState<{ ok: boolean; text: string; slug?: string } | null>(null);
  const first = useRef(true);

  const load = useCallback(async (opts: { q: string; category: string; cursor?: string | null; append?: boolean }) => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (opts.q) params.set("q", opts.q);
      if (opts.category) params.set("category", opts.category);
      if (opts.cursor) params.set("cursor", opts.cursor);
      const page: Page = await fetch(`/api/aera/apps/catalogue?${params.toString()}`).then((r) => r.json());
      if (page.error) throw new Error(page.error);
      setItems((xs) => (opts.append ? [...xs, ...page.toolkits] : page.toolkits));
      setCursor(page.next_cursor);
      setTotal(page.total);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const add = useCallback(async (slug: string, quiet = false) => {
    setBusy(slug);
    try {
      await post("apps/add", { toolkit: slug });
      setAdded((s) => new Set(s).add(slug));
      if (!quiet) setNote((n) => ({ ...n, [slug]: "Added to AERA." }));
      setBanner({ ok: true, text: `${pretty(slug)} is connected and added to AERA. Choose which agents may use which of its tools.`, slug });
      router.refresh();
    } catch (e) {
      if (quiet) setBanner({ ok: false, text: `${pretty(slug)}: ${errorText(e)}` });
      else setNote((n) => ({ ...n, [slug]: errorText(e) }));
    } finally {
      setBusy("");
    }
  }, [router]);

  // first load: categories, the most used apps, and an app just connected on Composio (?connected=<slug>)
  useEffect(() => {
    if (!first.current) return;
    first.current = false;
    fetch("/api/aera/apps/categories").then((r) => r.json()).then((d) => setCats(d.categories ?? [])).catch(() => setCats([]));
    void load({ q: "", category: "" });
    const just = new URLSearchParams(window.location.search).get("connected");
    if (just && /^[a-z0-9_-]{2,60}$/.test(just)) {
      window.history.replaceState(null, "", "/apps/connect");
      if (mayChange) void add(just, true);
    }
  }, [add, load, mayChange]);

  const connect = async (t: Hit) => {
    setBusy(t.slug);
    setNote((n) => ({ ...n, [t.slug]: "" }));
    try {
      const r = await post<{ connected?: boolean; url?: string }>("apps/connect", { toolkit: t.slug });
      if (r.url) {
        setNote((n) => ({ ...n, [t.slug]: "Opening the sign-in…" }));
        window.location.href = r.url;            // comes back to /apps/connect?connected=<slug>
        return;
      }
      await add(t.slug);
    } catch (e) {
      setNote((n) => ({ ...n, [t.slug]: errorText(e) }));
      setBusy("");
    }
  };

  // a search looks across every tool; a category browses one, from the top
  const pick = (id: string) => {
    setCategory(id);
    setQ("");
    void load({ q: "", category: id });
  };

  return (
    <div className="mt-6">
      {banner && (
        <div className={cn("mb-6 flex flex-wrap items-center gap-3 rounded-xl border px-4 py-3 text-[13.5px]", banner.ok ? "bg-raised" : "bg-raised text-bad")}>
          {banner.ok ? <Check className="text-ok size-4" /> : null}
          <span className="flex-1">{banner.text}</span>
          {banner.ok && <Button asChild size="sm"><Link href="/apps"><Settings2 className="size-3.5" /> Choose agents and tools</Link></Button>}
        </div>
      )}

      {mayChange && ready.filter((s) => !added.has(s)).length > 0 && (
        <section className="mb-8">
          <p className="text-text text-[13px]">Already connected in Composio, not used by AERA yet</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {ready.filter((s) => !added.has(s)).map((s) => (
              <Button key={s} size="sm" variant="outline" disabled={busy === s} onClick={() => void add(s)}>
                {busy === s ? <Loader2 className="animate-spin" /> : <Plus className="size-3.5" />} {pretty(s)}
              </Button>
            ))}
          </div>
        </section>
      )}

      <form className="flex max-w-2xl gap-2" onSubmit={(e) => { e.preventDefault(); setCategory(""); void load({ q, category: "" }); }}>
        <div className="relative flex-1">
          <Search className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search 1,700+ tools: Slack, Google Sheets, Notion, HubSpot…" className="pl-9" />
        </div>
        <Button type="submit" disabled={loading}>Search</Button>
      </form>

      {/* Composio has hundreds of fine-grained categories: the main ones as chips, every one in the list */}
      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        {[{ id: "", name: "Most used" }, ...cats.slice(0, MAIN_CATEGORIES)].map((c) => (
          <button key={c.id || "all"} type="button" onClick={() => pick(c.id)}
            className={cn("h-8 rounded-full border px-3 text-[12.5px] transition-colors",
              category === c.id ? "border-brand bg-brand text-white" : "text-text hover:bg-raised")}>
            {c.name}
          </button>
        ))}
        {cats.length > MAIN_CATEGORIES && (
          <CategoryPicker options={cats.slice(MAIN_CATEGORIES)} value={category}
            active={!!category && !cats.slice(0, MAIN_CATEGORIES).some((c) => c.id === category)} onPick={pick} />
        )}
      </div>

      <p className="text-muted-foreground mt-5 text-[12px]">
        {loading && items.length === 0 ? "Loading…" : `${items.length}${total ? ` of ${total.toLocaleString()}` : ""} tools`}
        {q && ` matching “${q}”`}{category && ` in ${cats.find((c) => c.id === category)?.name ?? category}`}
      </p>
      {error && <p className="text-bad mt-2 text-[13px]">{error}</p>}

      <ul className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((t) => {
          const isAdded = added.has(t.slug) || t.added;
          return (
            <li key={t.slug} className="bg-card-grad flex flex-col rounded-xl border p-4 shadow-soft">
              <div className="flex items-start gap-3">
                <Logo src={t.logo} />
                <div className="min-w-0 flex-1">
                  <p className="text-fg truncate text-[14.5px]">{t.name}</p>
                  <p className="text-muted-foreground truncate text-[11.5px]">{t.tools_count ?? "?"} tools{t.categories.length ? ` · ${t.categories.join(", ")}` : ""}</p>
                </div>
                {isAdded ? <Chip tone="ok">in AERA</Chip> : t.connected ? <Chip tone="info">connected</Chip> : null}
              </div>
              <p className="text-body mt-3 line-clamp-3 flex-1 text-[12.5px] leading-relaxed">{t.description || "No description from Composio."}</p>
              {mayChange && (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {isAdded ? (
                    <Button asChild size="sm" variant="outline"><Link href="/apps"><Settings2 className="size-3.5" /> Manage</Link></Button>
                  ) : t.connected ? (
                    <Button size="sm" disabled={busy === t.slug} onClick={() => void add(t.slug)}>
                      {busy === t.slug ? <Loader2 className="animate-spin" /> : <Plus className="size-3.5" />} Add to AERA
                    </Button>
                  ) : (
                    <Button size="sm" disabled={busy === t.slug} onClick={() => void connect(t)}>
                      {busy === t.slug ? <Loader2 className="animate-spin" /> : <ExternalLink className="size-3.5" />} Connect
                    </Button>
                  )}
                  {!t.connected && !isAdded && !t.managed && !t.no_auth && (
                    <span className="text-muted-foreground text-[11px]">needs its own auth config in Composio</span>
                  )}
                </div>
              )}
              {note[t.slug] && <p className="text-muted-foreground mt-2 text-[11.5px] leading-relaxed">{note[t.slug]}</p>}
            </li>
          );
        })}
      </ul>

      {cursor && (
        <div className="mt-6 flex justify-center">
          <Button variant="outline" disabled={loading} onClick={() => void load({ q, category, cursor, append: true })}>
            {loading ? <Loader2 className="animate-spin" /> : null} Load more
          </Button>
        </div>
      )}
      {!mayChange && <p className="text-muted-foreground mt-6 text-[12.5px]">Only an owner or admin connects tools.</p>}
    </div>
  );
}
