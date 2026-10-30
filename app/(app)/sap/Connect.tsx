"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { SapSettings, SapTest } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

const FIELD =
  "h-9 w-full min-w-0 rounded-lg border border-input bg-transparent px-3 font-mono text-sm outline-none " +
  "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 " +
  "disabled:cursor-not-allowed disabled:opacity-60 dark:bg-input/30";

/* The key is write-only from here. The server never sends it back - the page
 * can show that one is set and its last four characters, nothing more - so the
 * field starts empty and an empty field means "leave it alone", not "clear it".
 * Clearing is a separate, named button, because a credential should never be
 * deleted by a stray keystroke. */
export function Connect({ data }: { data: SapSettings }) {
  const router = useRouter();
  const [key, setKey] = useState("");
  const [url, setUrl] = useState(data.base_url ?? "");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [test, setTest] = useState<SapTest | null>(null);

  async function post(body: Record<string, string>, what: string) {
    setBusy(what);
    setError("");
    setTest(null);
    try {
      const res = await fetch("/api/sigap/settings/sap", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "could not save");
      setKey("");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not save");
    } finally {
      setBusy("");
    }
  }

  async function probe() {
    setBusy("test");
    setError("");
    setTest(null);
    try {
      const res = await fetch("/api/sigap/settings/sap/test", { method: "POST" });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "could not test");
      setTest(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not test");
    } finally {
      setBusy("");
    }
  }

  const locked = !data.may_change || !!busy;

  return (
    <div className="mt-8 space-y-6">
      <section className="rounded-lg border">
        <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
          <p className="text-sm font-medium">Connection</p>
          <StatusBadge status={data.key_set ? "done" : "off"}>
            {data.key_set ? `key set ${data.key_hint}` : "no key"}
          </StatusBadge>
          {data.key_set && (
            <span className="text-muted-foreground font-mono text-[10px]">
              from {data.key_source === "settings" ? "this page" : "the server's .env"}
            </span>
          )}
          {data.data_mode === "demo" && (
            <span className="text-muted-foreground ml-auto text-xs">
              Demo mode is on, so nothing here is being called right now.
            </span>
          )}
        </div>

        <div className="grid gap-4 px-4 py-4 sm:grid-cols-2">
          <label className="space-y-1.5">
            <span className="text-sm font-medium">API key</span>
            <input
              className={FIELD}
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder={data.key_set ? `leave empty to keep ${data.key_hint}` : "paste the key"}
              value={key}
              onChange={(e) => setKey(e.target.value)}
              disabled={locked}
            />
            <span className="text-muted-foreground block text-xs leading-relaxed">
              Write-only. Once saved it is never sent back to a browser.
            </span>
          </label>

          <label className="space-y-1.5">
            <span className="text-sm font-medium">Base URL</span>
            <input
              className={FIELD}
              autoComplete="off"
              spellCheck={false}
              placeholder="https://sandbox.api.sap.com"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={locked}
            />
            <span className="text-muted-foreground block text-xs leading-relaxed">
              The sandbox, or your own tenant&apos;s API host. Nothing else changes.
            </span>
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t px-4 py-3">
          <Button
            size="sm"
            disabled={locked || (!key && url === (data.base_url ?? ""))}
            onClick={() => post(key ? { api_key: key, base_url: url } : { base_url: url }, "save")}
          >
            {busy === "save" ? "Saving…" : "Save"}
          </Button>
          <Button size="sm" variant="outline" disabled={locked || !data.key_set} onClick={probe}>
            {busy === "test" ? "Calling SAP…" : "Test connection"}
          </Button>
          {data.key_source === "settings" && (
            <Button
              size="sm"
              variant="ghost"
              disabled={locked}
              onClick={() => post({ api_key: "" }, "clear")}
            >
              {busy === "clear" ? "Clearing…" : "Clear key"}
            </Button>
          )}
          {!data.may_change && (
            <p className="text-muted-foreground text-xs">
              Only an admin or a procurement lead can change this.
            </p>
          )}
          {error && <p className="text-destructive text-xs">{error}</p>}
        </div>

        {test && (
          <div className="border-t px-4 py-3">
            <div className="flex items-center gap-2">
              <StatusBadge status={test.ok ? "done" : "held"}>{test.reason}</StatusBadge>
              {typeof test.ms === "number" && (
                <span className="text-muted-foreground font-mono text-[10px]">{test.ms} ms</span>
              )}
            </div>
            <p className="text-muted-foreground mt-1.5 text-xs leading-relaxed">
              {test.ok
                ? `SAP answered with ${test.rows} row from ${test.base_url}.`
                : test.detail}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
