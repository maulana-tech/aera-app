"use client";

import { CornerDownLeft, Loader2, Wrench } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { OriginBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

type Reply = {
  answer: string;
  tools_used: string[];
  board: Record<string, { origin: string; source: string }>;
  untrusted: string[];
  cost_idr: number;
};
type Message =
  | { from: "person"; text: string }
  | { from: "agent"; reply: Reply }
  | { from: "error"; text: string; hint?: string };

export default function Conversation({
  code, name, examples, signedIn,
}: { code: string; name: string; examples: string[]; signedIn: boolean }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  async function send(body: string) {
    const q = body.trim();
    if (!q || busy) return;
    setMessages((m) => [...m, { from: "person", text: q }]);
    setText("");
    setBusy(true);
    try {
      const r = await fetch(`/api/sigap/agents/${code}/ask`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const d = await r.json();
      setMessages((m) => [
        ...m,
        r.ok
          ? { from: "agent", reply: d as Reply }
          : { from: "error", text: d.error ?? "failed", hint: d.hint },
      ]);
    } catch {
      setMessages((m) => [...m, { from: "error", text: "the agent service is not responding" }]);
    } finally {
      setBusy(false);
      field.current?.focus();
    }
  }

  return (
    <div className="flex h-[calc(100vh-13rem)] flex-col rounded-xl border">
      <div className="flex-1 space-y-4 overflow-y-auto p-5">
        {messages.length === 0 && (
          <div className="text-muted-foreground space-y-3 text-sm">
            <p>Ask {name} directly. Same tools as when working inside the team.</p>
            <div className="flex flex-wrap gap-2">
              {examples.map((ex) => (
                <button
                  key={ex}
                  onClick={() => send(ex)}
                  disabled={!signedIn}
                  className="hover:border-foreground/30 hover:text-foreground rounded-full border px-3 py-1.5 text-left text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.from === "person" ? (
            <div key={i} className="flex justify-end">
              <p className="bg-primary text-primary-foreground max-w-[80%] rounded-2xl rounded-br-sm px-4 py-2 text-sm">
                {m.text}
              </p>
            </div>
          ) : m.from === "error" ? (
            <div key={i} className="max-w-[85%] rounded-2xl rounded-bl-sm border p-4">
              <p className="text-destructive text-sm">{m.text}</p>
              {m.hint && (
                <p className="text-muted-foreground mt-2 text-xs leading-relaxed">{m.hint}</p>
              )}
            </div>
          ) : (
            <div key={i} className="max-w-[85%] space-y-2">
              <div className="bg-muted/50 rounded-2xl rounded-bl-sm border p-4">
                <p className="whitespace-pre-line text-sm leading-relaxed">{m.reply.answer}</p>
              </div>
              {m.reply.tools_used.length > 0 && (
                <p className="text-muted-foreground flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
                  <Wrench className="size-3" />
                  {m.reply.tools_used.join(" · ")}
                </p>
              )}
              {Object.keys(m.reply.board).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(m.reply.board).map(([k, v]) => (
                    <OriginBadge key={k} origin={v.origin} source={v.source} />
                  ))}
                </div>
              )}
            </div>
          ),
        )}

        {busy && (
          <p className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="size-3.5 animate-spin" />
            {name} is working…
          </p>
        )}
        <div ref={bottom} />
      </div>

      {!signedIn ? (
        <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
          <p className="text-muted-foreground text-sm">
            Sign in to ask. Conversations are recorded against your account.
          </p>
          <Button asChild size="sm" variant="outline">
            <Link href="/login">Sign in</Link>
          </Button>
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(text);
          }}
          className="flex items-end gap-2 border-t p-3"
        >
          <textarea
            ref={field}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(text);
              }
            }}
            placeholder={`Ask ${name}…`}
            className="max-h-32 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
          />
          <Button type="submit" size="sm" disabled={busy || !text.trim()}>
            <CornerDownLeft className="size-3.5" />
            Send
          </Button>
        </form>
      )}
    </div>
  );
}
