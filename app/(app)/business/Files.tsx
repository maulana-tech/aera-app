"use client";

import { FileText, Loader2, Trash2, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { when, type BusinessFile } from "@/app/lib";
import { Field, TextArea } from "@/components/profile-editor";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";

const TEXTLIKE = /\.(txt|md|csv|json|tsv|html?|xml|ya?ml)$/i;

/** What the business knows that no API does: price lists, style guides, past
 *  briefs. Text only; agents with the knowledge capability read these. */
export function Files({ files, mayChange }: { files: BusinessFile[]; mayChange: boolean }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy("add");
    setError(null);
    try {
      await post("files", { name, text, mime: name.endsWith(".md") ? "text/markdown" : "text/plain" });
      setName(""); setText("");
      router.refresh();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function remove(id: string, name: string) {
    if (!window.confirm(`Remove ${name}? The agents can no longer read it.`)) return;
    setBusy(id);
    setError(null);
    try {
      await post(`files/${id}/delete`);
      router.refresh();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      {files.length === 0 ? (
        <p className="text-muted-foreground text-sm">No files yet. Add what the team should know that is not in the profile: a price list, a style guide, a sample of past work.</p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {files.map((f) => (
            <li key={f.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              <FileText className="text-muted-foreground size-4" />
              <span className="min-w-0 flex-1 truncate text-sm">{f.name}</span>
              <span className="text-muted-foreground font-mono text-[10px]">{f.size.toLocaleString("en-US")} chars · {f.uploaded_by} · {when(f.uploaded_at)}</span>
              {mayChange && !f.name.startsWith("doc:") && (
                <Button size="icon-xs" variant="ghost" aria-label={`Remove ${f.name}`} disabled={busy === f.id} onClick={() => remove(f.id, f.name)}>
                  {busy === f.id ? <Loader2 className="animate-spin" /> : <Trash2 />}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {mayChange && <form onSubmit={add} className="space-y-3 rounded-lg border p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="price-list.md" required /></Field>
          <Field label="Or read a text file">
            <Input type="file" accept=".txt,.md,.csv,.json,.tsv,.html,.xml,.yaml,.yml,text/*"
              onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                if (!TEXTLIKE.test(f.name) && !f.type.startsWith("text/")) { setError("only text files can be read"); return; }
                setName(f.name);
                setText((await f.text()).slice(0, 200_000));
              }} />
          </Field>
        </div>
        <Field label="Text"><TextArea rows={5} value={text} onChange={(e) => setText(e.target.value)} placeholder="Our tone of voice: plain, specific, no hype…" /></Field>
        {error && <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>}
        <Button type="submit" size="sm" disabled={!!busy || !name.trim() || !text.trim()}>
          {busy === "add" ? <Loader2 className="animate-spin" /> : <Upload />}
          Add file
        </Button>
      </form>}
    </div>
  );
}
