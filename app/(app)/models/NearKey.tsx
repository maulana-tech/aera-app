"use client";

import { KeyRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Chip } from "@/components/dort";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText } from "@/lib/post";

/* For a business created on a shared install: whose NEAR AI key its agents run on. The key is written to the
 * business's own service by the hub and never comes back to the page. */
export function NearKey({ mode, cap, owner }: { mode: "own" | "shared"; cap: number | null; owner: boolean }) {
  const router = useRouter();
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState("");
  const save = async (value: string) => {
    setBusy(true);
    setSaid("");
    try {
      await fetch("/api/workspace/key", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ key: value }) })
        .then(async (r) => { if (!r.ok) throw new Error((await r.json()).error ?? `HTTP ${r.status}`); });
      setKey("");
      setSaid(value ? "Saved. Your agents now run on your key." : "Back on AERA's key, with its daily allowance.");
      router.refresh();
    } catch (e) {
      setSaid(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="bg-card-grad mt-6 rounded-xl border p-5 shadow-soft">
      <div className="flex flex-wrap items-center gap-2">
        <KeyRound className="text-brand size-4" />
        <h2 className="text-fg text-[15px]">NEAR AI key</h2>
        <Chip tone={mode === "own" ? "ok" : "warn"} className="ml-auto">
          {mode === "own" ? "your own key" : `AERA's key · up to $${(cap ?? 0.5).toFixed(2)} a day`}
        </Chip>
      </div>
      <p className="text-body mt-2 text-[13.5px] leading-relaxed">
        {mode === "own"
          ? "Your agents run on your own NEAR AI key. You pay NEAR AI for what they use; no daily allowance from AERA applies."
          : `Your agents run on AERA's shared key, which allows $${(cap ?? 0.5).toFixed(2)} of AI a day for this business. Add your own key to lift it.`}{" "}
        <Link href="/guide/near-ai-key" target="_blank" className="text-brand underline-offset-2 hover:underline">How to get a key</Link>
      </p>
      {owner ? (
        <form className="mt-4 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); if (key.trim()) void save(key.trim()); }}>
          <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder={mode === "own" ? "Replace with a new key" : "Paste your NEAR AI API key"}
                 autoComplete="off" className="min-w-[240px] flex-1" />
          <Button type="submit" disabled={busy || !key.trim()}>{busy ? "Saving…" : "Save key"}</Button>
          {mode === "own" && <Button type="button" variant="outline" disabled={busy} onClick={() => void save("")}>Use AERA&apos;s key</Button>}
        </form>
      ) : (
        <p className="text-muted-foreground mt-3 text-[12.5px]">Only the business&apos;s owner changes its key.</p>
      )}
      {said && <p className="text-muted-foreground mt-2 text-[12.5px]">{said}</p>}
    </section>
  );
}
