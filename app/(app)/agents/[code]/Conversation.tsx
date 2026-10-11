"use client";

import {
  ArrowRight, CornerDownLeft, Loader2, Plus, Trash2,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { ToolActivity } from "@/components/agent-activity";
import { AgentBadge } from "@/components/agent-card";
import { Markdown } from "@/components/markdown";
import { OriginBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

type Reply = {
  answer: string;
  tools_used: string[];
  board: Record<string, { origin: string; source: string }>;
  untrusted: string[];
  cost_idr: number;
  conversation_id?: string;
};
type Message =
  | { from: "person"; text: string }
  | { from: "agent"; reply: Reply }
  | { from: "error"; text: string; hint?: string };

type Thread = { id: string; title: string; messages: number; updated_at: string };

/* One column, centred, in every host. The drawer is narrower than the cap so it
 * is a no-op there, and on the conversation page it keeps the transcript at a
 * readable measure instead of stretching a sentence across 1600px.
 */
const COLUMN = "mx-auto w-full max-w-3xl";

// store._now() writes an offset already, so this parses as-is.
const ago = (iso: string) => {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
};

/** Stored rows come back as records. The transcript wants them as messages. */
function fromRows(rows: { role: string; body: Record<string, unknown> }[]): Message[] {
  return rows.map((r) =>
    r.role === "person"
      ? { from: "person", text: String(r.body.text ?? "") }
      : r.role === "error"
        ? { from: "error", text: String(r.body.text ?? ""), hint: r.body.hint as string }
        : { from: "agent", reply: r.body as unknown as Reply },
  );
}

export default function Conversation({
  code, name, work, examples, signedIn, threadId = null, rail = false, onOpen,
}: {
  code: string;
  name: string;
  work: string;
  examples: string[];
  signedIn: boolean;
  /** Read from the URL. This is what makes a refresh keep the conversation. */
  threadId?: string | null;
  /** The conversation page gets a permanent history rail. The drawer does not. */
  rail?: boolean;
  onOpen?: (id: string | null) => void;
}) {
  const [id, setId] = useState<string | null>(threadId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(!!threadId);
  const bottom = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  const loadThreads = useCallback(async () => {
    if (!signedIn) return;
    try {
      const r = await fetch(`/api/sigap/agents/${code}/conversations`);
      if (r.ok) setThreads((await r.json()).conversations ?? []);
    } catch {
      // A history list that failed to load is not worth an error in the transcript.
    }
  }, [code, signedIn]);

  useEffect(() => {
    // The state update happens after the history fetch, not synchronously.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadThreads();
  }, [loadThreads]);

  // Restores whatever the URL named. Without this a refresh lands in an empty
  // conversation while the rows are still sitting in the database.
  useEffect(() => {
    if (!threadId) return;
    let alive = true;
    // Mark the external request as loading before restoring its result.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRestoring(true);
    fetch(`/api/sigap/conversations/${threadId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!alive) return;
        if (d) {
          setId(threadId);
          setMessages(fromRows(d.messages ?? []));
        } else {
          // Deleted, or never this user's to read. Start clean rather than
          // leave the page pointing at something that is not there.
          setId(null);
          onOpen?.(null);
        }
      })
      .finally(() => {
        if (alive) setRestoring(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId]);

  function startNew() {
    setId(null);
    setMessages([]);
    setText("");
    onOpen?.(null);
  }

  async function open(next: string) {
    if (next === id) return;
    setRestoring(true);
    try {
      const r = await fetch(`/api/sigap/conversations/${next}`);
      if (r.ok) {
        const d = await r.json();
        setId(next);
        setMessages(fromRows(d.messages ?? []));
        onOpen?.(next);
      }
    } finally {
      setRestoring(false);
    }
  }

  async function remove(target: string) {
    await fetch(`/api/sigap/conversations/${target}/delete`, { method: "POST" });
    setThreads((t) => t.filter((x) => x.id !== target));
    if (target === id) startNew();
  }

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
        body: JSON.stringify({ question: q, conversation_id: id }),
      });
      const d = await r.json();
      if (!r.ok) {
        setMessages((m) => [...m, { from: "error", text: d.error ?? "failed", hint: d.hint }]);
        return;
      }
      setMessages((m) => [...m, { from: "agent", reply: d as Reply }]);
      if (d.conversation_id && d.conversation_id !== id) {
        setId(d.conversation_id);
        onOpen?.(d.conversation_id);
      }
      loadThreads();
    } catch {
      setMessages((m) => [...m, { from: "error", text: "the agent service is not responding" }]);
    } finally {
      setBusy(false);
      field.current?.focus();
    }
  }

  const composer = !signedIn ? (
    <div className="flex items-center justify-between gap-3 rounded-lg border px-4 py-3">
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
      className="focus-within:border-foreground/30 bg-background flex items-end gap-2 rounded-lg border p-2 transition-colors"
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
        className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2.5 py-2 text-sm outline-none"
      />
      <Button type="submit" size="sm" disabled={busy || !text.trim()}>
        <CornerDownLeft className="size-3.5" />
        Send
      </Button>
    </form>
  );

  const threadList = (
    <ul className="space-y-0.5">
      {threads.map((t) => (
        <li key={t.id} className="group/row relative">
          <button
            onClick={() => open(t.id)}
            className={`hover:bg-muted/60 w-full rounded-md px-2.5 py-2 pr-8 text-left transition-colors ${
              t.id === id ? "bg-muted" : ""
            }`}
          >
            <span className="block truncate text-xs leading-snug">{t.title}</span>
            <span className="text-muted-foreground mt-0.5 block font-mono text-[10px]">
              {t.messages} messages · {ago(t.updated_at)}
            </span>
          </button>
          <button
            onClick={() => remove(t.id)}
            aria-label={`Delete conversation: ${t.title}`}
            className="text-muted-foreground hover:text-destructive absolute right-1.5 top-1.5 rounded-md p-1 opacity-0 transition-opacity group-hover/row:opacity-100 focus-visible:opacity-100"
          >
            <Trash2 className="size-3.5" />
          </button>
        </li>
      ))}
    </ul>
  );

  /* Nothing asked yet: the composer sits in the middle under the heading, where
   * the eye already is. Once there is a transcript it drops to the bottom and
   * stays there, which is the only place a reply box belongs.
   */
  const empty = (
    <div className="flex min-h-0 flex-1 flex-col justify-center overflow-y-auto px-5 py-8">
      <div className="mx-auto w-full max-w-xl space-y-6">
        <div className="text-center">
          {/* AgentBadge is display:flex, so text-align does not move it. */}
          <div className="flex justify-center">
            <AgentBadge nickname={name} large />
          </div>
          <h2 className="mt-3 text-lg font-semibold tracking-tight">Ask {name}</h2>
          <p className="text-muted-foreground mt-1.5 text-sm leading-relaxed">
            {work}. Same tools as inside the team, and every figure keeps the
            label of where it came from.
          </p>
        </div>

        {composer}

        {examples.length > 0 && (
          <ul className="space-y-2">
            {examples.map((ex) => (
              <li key={ex}>
                <button
                  onClick={() => send(ex)}
                  disabled={!signedIn}
                  className="hover:border-foreground/30 hover:bg-muted/50 focus-visible:ring-ring group flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left text-sm outline-none transition-colors focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <span className="flex-1">{ex}</span>
                  <ArrowRight className="text-muted-foreground group-hover:text-foreground size-3.5 shrink-0 transition-colors" />
                </button>
              </li>
            ))}
          </ul>
        )}

        {/* Without a rail this is the only way back to an earlier thread. */}
        {!rail && threads.length > 0 && (
          <div className="border-t pt-4">
            <p className="text-muted-foreground mb-1.5 px-2.5 text-xs font-medium">
              Earlier ({threads.length})
            </p>
            {threadList}
          </div>
        )}
      </div>
    </div>
  );

  const transcript = (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className={`${COLUMN} space-y-6 px-5 py-6`}>
          {messages.map((m, i) =>
            m.from === "person" ? (
              <div key={i} className="flex justify-end">
                <p className="bg-primary text-primary-foreground max-w-[85%] whitespace-pre-line rounded-lg rounded-br-sm px-4 py-2.5 text-sm leading-relaxed">
                  {m.text}
                </p>
              </div>
            ) : (
              <div key={i} className="flex gap-3">
                <AgentBadge nickname={name} />
                <div className="min-w-0 flex-1 space-y-2">
                  {m.from === "error" ? (
                    <div className="rounded-lg rounded-tl-sm border p-4">
                      <p className="text-destructive text-sm">{m.text}</p>
                      {m.hint && (
                        <p className="text-muted-foreground mt-2 text-xs leading-relaxed">
                          {m.hint}
                        </p>
                      )}
                    </div>
                  ) : (
                    <>
                      <div className="bg-muted/50 rounded-lg rounded-tl-sm border p-4">
                        <Markdown>{m.reply.answer}</Markdown>
                      </div>
                      <ToolActivity tools={m.reply.tools_used ?? []} />
                      {Object.keys(m.reply.board ?? {}).length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {Object.entries(m.reply.board).map(([k, v]) => (
                            <OriginBadge key={k} origin={v.origin} source={v.source} />
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ),
          )}

          {busy && (
            <div className="flex gap-3">
              <AgentBadge nickname={name} />
              <p className="text-muted-foreground flex items-center gap-2 pt-2 text-sm">
                <Loader2 className="size-3.5 animate-spin" />
                {name} is working…
              </p>
            </div>
          )}
          <div ref={bottom} />
        </div>
      </div>

      <div className="bg-background shrink-0 border-t">
        <div className={`${COLUMN} px-5 py-3`}>{composer}</div>
      </div>
    </div>
  );

  const body = restoring ? (
    <div className="text-muted-foreground flex min-h-0 flex-1 items-center justify-center gap-2 text-sm">
      <Loader2 className="size-3.5 animate-spin" />
      Opening the conversation…
    </div>
  ) : messages.length === 0 && !busy ? (
    empty
  ) : (
    transcript
  );

  if (!rail) return body;

  return (
    <div className="flex min-h-0 flex-1">
      <aside className="hidden w-64 shrink-0 flex-col border-r md:flex">
        <div className="shrink-0 p-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={startNew}
            disabled={!id && messages.length === 0}
          >
            <Plus className="size-3.5" />
            New conversation
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
          {threads.length === 0 ? (
            <p className="text-muted-foreground px-2.5 py-2 text-xs leading-relaxed">
              {signedIn
                ? "Nothing asked yet. What you ask is kept here, against your account."
                : "Sign in to keep a history."}
            </p>
          ) : (
            threadList
          )}
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">{body}</div>
    </div>
  );
}
