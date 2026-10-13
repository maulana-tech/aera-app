"use client";

import {
  ArrowRight,
  BarChart3,
  ChevronRight,
  CircleHelp,
  CornerDownLeft,
  FileText,
  ImagePlus,
  Loader2,
  Paperclip,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { Popover as PopoverPrimitive } from "radix-ui";
import { useCallback, useEffect, useRef, useState } from "react";

import { ToolActivity } from "@/components/agent-activity";
import { AgentBadge } from "@/components/agent-card";
import { Markdown } from "@/components/markdown";
import {
  OrchestrationTimeline,
  type OrchestrationStep,
  type OrchestrationTrailEntry,
} from "@/components/orchestration-timeline";
import { OriginBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

type Attachment = {
  name: string;
  mime_type: string;
  size: number;
  kind: "image" | "file";
  data?: string;
  text_content?: string;
  preview_url?: string;
};

type Reply = {
  answer: string;
  tools_used: string[];
  board: Record<string, { origin: string; source: string }>;
  untrusted: string[];
  cost_idr: number;
  conversation_id?: string;
  thinking_time?: number;
  steps?: OrchestrationStep[];
  trail?: OrchestrationTrailEntry[];
  usage?: UsageOverview;
  tokens?: {
    input: number;
    output: number;
    total: number;
  };
};
type Message =
  | { from: "person"; text: string; attachments?: Attachment[] }
  | { from: "agent"; reply: Reply }
  | { from: "error"; text: string; hint?: string };

type Thread = {
  id: string;
  title: string;
  messages: number;
  updated_at: string;
  total_tokens?: number;
  cost_idr?: number;
};

type UsageOverview = {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_idr: number;
  replies: number;
  runs_cost_idr: number;
  cost_cap_idr: number;
  max_output_tokens: number;
  context_turns: number;
  max_rounds: number;
  input_idr_per_million: number;
  output_idr_per_million: number;
  model: string;
};

const DEFAULT_COST_CAP_IDR = 500_000;
const DEFAULT_CONTEXT_TURNS = 12;
const DEFAULT_MAX_OUTPUT_TOKENS = 8_000;

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isTextLikeFile(file: File): boolean {
  const mime = (file.type || "").toLowerCase();
  if (
    mime.startsWith("text/") ||
    mime === "application/json" ||
    mime === "application/xml" ||
    mime === "application/csv"
  ) {
    return true;
  }
  return /\.(csv|tsv|txt|md|json|xml|yaml|yml|log|sql|py|ts|tsx|js)$/i.test(file.name);
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function fileToAttachment(file: File): Promise<Attachment> {
  const mime = file.type || (file.name.toLowerCase().endsWith(".csv") ? "text/csv" : "application/octet-stream");
  const isImage = mime.startsWith("image/");

  if (isImage) {
    const dataUrl = await readAsDataUrl(file);
    const commaIdx = dataUrl.indexOf(",");
    const base64 = commaIdx >= 0 ? dataUrl.slice(commaIdx + 1) : dataUrl;
    return {
      name: file.name,
      mime_type: mime,
      size: file.size,
      kind: "image",
      data: base64,
      preview_url: dataUrl,
    };
  }

  if (mime === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
    const dataUrl = await readAsDataUrl(file);
    const commaIdx = dataUrl.indexOf(",");
    const base64 = commaIdx >= 0 ? dataUrl.slice(commaIdx + 1) : dataUrl;
    return {
      name: file.name,
      mime_type: "application/pdf",
      size: file.size,
      kind: "file",
      data: base64,
    };
  }

  if (isTextLikeFile(file)) {
    const text = await file.text();
    return {
      name: file.name,
      mime_type: mime,
      size: file.size,
      kind: "file",
      text_content: text,
    };
  }

  const dataUrl = await readAsDataUrl(file);
  const commaIdx = dataUrl.indexOf(",");
  const base64 = commaIdx >= 0 ? dataUrl.slice(commaIdx + 1) : dataUrl;
  return {
    name: file.name,
    mime_type: mime,
    size: file.size,
    kind: "file",
    data: base64,
  };
}

function formatCompactTokens(n: number): string {
  if (n >= 1_000_000) {
    const m = n / 1_000_000;
    return `${m % 1 === 0 ? m.toFixed(0) : m.toFixed(1)}M`;
  }
  if (n >= 1_000) {
    const k = n / 1_000;
    return `${k % 1 === 0 ? k.toFixed(0) : k.toFixed(1)}k`;
  }
  return n.toLocaleString();
}

function formatPercent(ratio: number): string {
  const pct = ratio * 100;
  if (pct <= 0) return "0%";
  if (pct < 0.1) return `${pct.toFixed(2)}%`;
  if (pct < 10) return `${pct.toFixed(1)}%`;
  return `${Math.min(100, Math.round(pct))}%`;
}

function barWidthPct(ratio: number): number {
  if (ratio <= 0) return 0;
  return Math.min(100, Math.max(1.5, ratio * 100));
}

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
      ? {
          from: "person",
          text: String(r.body.text ?? ""),
          attachments: Array.isArray(r.body.attachments)
            ? (r.body.attachments as Attachment[])
            : undefined,
        }
      : r.role === "error"
        ? { from: "error", text: String(r.body.text ?? ""), hint: r.body.hint as string }
        : { from: "agent", reply: r.body as unknown as Reply },
  );
}

function ThinkingIndicator({
  seconds,
}: {
  seconds?: number;
}) {
  if (seconds === undefined) return null;

  return (
    <div className="mb-2 text-[11px] font-mono text-muted-foreground/80 select-none">
      <span>Thought for {seconds.toFixed(1)}s</span>
    </div>
  );
}

function UsageBarPopover({
  messages,
  threads,
  usage,
  modelId,
}: {
  messages: Message[];
  threads: Thread[];
  usage: UsageOverview | null;
  modelId: string | null;
}) {
  const [tokensExpanded, setTokensExpanded] = useState(false);
  const [showBreakdown, setShowBreakdown] = useState(false);

  const agentReplies = messages.filter(
    (m): m is { from: "agent"; reply: Reply } => m.from === "agent",
  );

  // Real token & cost figures from Bedrock responses in this conversation
  const sessionInput = agentReplies.reduce((s, m) => s + (m.reply.tokens?.input ?? 0), 0);
  const sessionOutput = agentReplies.reduce((s, m) => s + (m.reply.tokens?.output ?? 0), 0);
  const sessionTotal = agentReplies.reduce(
    (s, m) => s + (m.reply.tokens?.total ?? (m.reply.tokens ? m.reply.tokens.input + m.reply.tokens.output : 0)),
    0,
  );
  const sessionCostIdr = agentReplies.reduce((s, m) => s + (m.reply.cost_idr ?? 0), 0);
  const sessionThinkingSeconds = agentReplies.reduce((s, m) => s + (m.reply.thinking_time ?? 0), 0);

  const promptShare = sessionTotal > 0 ? sessionInput / sessionTotal : 0;
  const responseShare = sessionTotal > 0 ? sessionOutput / sessionTotal : 0;

  // Real backend configuration limits (api.py CONTEXT_TURNS, graph.py max_tokens, config.py SIGAP_COST_CAP_IDR)
  const costCapIdr = usage?.cost_cap_idr ?? DEFAULT_COST_CAP_IDR;
  const contextTurnsLimit = usage?.context_turns ?? DEFAULT_CONTEXT_TURNS;
  const maxOutputTokens = usage?.max_output_tokens ?? DEFAULT_MAX_OUTPUT_TOKENS;
  const activeModel = usage?.model || modelId || null;

  // Real context history turns sent to the model (_as_turns in api.py keeps last CONTEXT_TURNS messages)
  const nonErrorTurns = messages.filter((m) => m.from === "person" || m.from === "agent").length;
  const activeTurns = Math.min(nonErrorTurns, contextTurnsLimit);
  const remainingTurns = Math.max(0, contextTurnsLimit - activeTurns);
  const contextRemainingRatio = contextTurnsLimit > 0 ? remainingTurns / contextTurnsLimit : 0;

  // Real output tokens of latest turn vs max_tokens=8000 configured in graph.py
  const lastReplyOutput = agentReplies.at(-1)?.reply.tokens?.output ?? 0;
  const remainingOutputTokens = Math.max(0, maxOutputTokens - lastReplyOutput);
  const outputRemainingRatio = maxOutputTokens > 0 ? remainingOutputTokens / maxOutputTokens : 0;

  // Real cumulative usage across all stored conversations in SQLite
  const threadsTokensSum = threads.reduce((s, t) => s + (t.total_tokens ?? 0), 0);
  const threadsCostSum = threads.reduce((s, t) => s + (t.cost_idr ?? 0), 0);
  const allTokens = Math.max(usage?.total_tokens ?? 0, threadsTokensSum, sessionTotal);
  const allInputTokens = Math.max(usage?.input_tokens ?? 0, sessionInput);
  const allOutputTokens = Math.max(usage?.output_tokens ?? 0, sessionOutput);
  const allCostIdr = Math.max(
    (usage?.cost_idr ?? 0) + (usage?.runs_cost_idr ?? 0),
    threadsCostSum,
    sessionCostIdr,
  );

  // Real session cost vs SIGAP_COST_CAP_IDR (Rp 500,000)
  const sessionCostRatio = costCapIdr > 0 ? sessionCostIdr / costCapIdr : 0;
  const allCostRatio = costCapIdr > 0 ? allCostIdr / costCapIdr : 0;
  const remainingBudgetIdr = Math.max(0, costCapIdr - sessionCostIdr);
  const budgetRemainingRatio = costCapIdr > 0 ? remainingBudgetIdr / costCapIdr : 0;

  return (
    <PopoverPrimitive.Root>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          className="hover:bg-muted/80 text-muted-foreground hover:text-foreground inline-flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors"
          title="View usage"
        >
          <BarChart3 className="size-3.5" />
          <span>View usage</span>
        </button>
      </PopoverPrimitive.Trigger>

      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="end"
          side="top"
          sideOffset={8}
          className="bg-popover text-popover-foreground ring-foreground/10 z-50 w-80 rounded-xl p-4 shadow-xl ring-1 outline-none"
        >
          {/* 1. Real Session Tokens (Prompt vs Response from Bedrock usage) */}
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => setTokensExpanded((v) => !v)}
              className="flex w-full items-center justify-between text-left text-xs"
            >
              <span className="text-muted-foreground">Session tokens</span>
              <span className="text-muted-foreground inline-flex items-center gap-1 font-mono">
                {sessionTotal.toLocaleString()} tok ({formatPercent(promptShare)} in / {formatPercent(responseShare)} out)
                <ChevronRight
                  className={`size-3.5 transition-transform ${tokensExpanded ? "rotate-90" : ""}`}
                />
              </span>
            </button>

            {/* Real segmented bar: exact proportion of prompt (blue) vs response (orange) tokens */}
            <div className="bg-muted flex h-1.5 w-full items-center gap-[2px] overflow-hidden rounded-full">
              {sessionInput > 0 && (
                <div
                  className="h-full rounded-l-full bg-[#3b82f6] transition-all"
                  style={{ width: `${Math.max(4, promptShare * 100)}%` }}
                />
              )}
              {sessionOutput > 0 && (
                <div
                  className="h-full rounded-r-full bg-[#f97316] transition-all"
                  style={{ width: `${Math.max(4, responseShare * 100)}%` }}
                />
              )}
            </div>

            {tokensExpanded && (
              <div className="bg-muted/50 space-y-1 rounded-lg px-2.5 py-2 font-mono text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="size-2 rounded-full bg-[#3b82f6]" />
                    Prompt tokens
                  </span>
                  <span>
                    {sessionInput.toLocaleString()} ({formatPercent(promptShare)})
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="size-2 rounded-full bg-[#f97316]" />
                    Response tokens
                  </span>
                  <span>
                    {sessionOutput.toLocaleString()} ({formatPercent(responseShare)})
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Thinking time</span>
                  <span>{sessionThinkingSeconds.toFixed(2)}s</span>
                </div>
              </div>
            )}
          </div>

          <div className="bg-border my-3.5 h-px" />

          {/* 2. Real System & Session Limits enforced by SIGAP (Full = colored, Exhausted = grey) */}
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="text-muted-foreground truncate" title={activeModel ?? undefined}>
                Limits{activeModel ? ` · ${activeModel}` : ""}
              </span>
              <ArrowRight className="text-muted-foreground size-3.5 shrink-0" />
            </div>

            {/* Context history window (CONTEXT_TURNS = 12 in api.py) */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium">Context memory</span>
                <span className="text-muted-foreground font-mono text-[11px]">
                  {remainingTurns} / {contextTurnsLimit} left ({formatPercent(contextRemainingRatio)})
                </span>
              </div>
              <div className="bg-muted h-1.5 w-full overflow-hidden rounded-full">
                <div
                  className="h-full rounded-full bg-[#3b82f6] transition-all"
                  style={{ width: `${barWidthPct(contextRemainingRatio)}%` }}
                />
              </div>
            </div>

            {/* Last response output vs max_tokens=8000 in graph.py */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium">Response max_tokens</span>
                <span className="text-muted-foreground font-mono text-[11px]">
                  {remainingOutputTokens.toLocaleString()} / {maxOutputTokens.toLocaleString()} left ({formatPercent(outputRemainingRatio)})
                </span>
              </div>
              <div className="bg-muted h-1.5 w-full overflow-hidden rounded-full">
                <div
                  className="h-full rounded-full bg-[#3b82f6] transition-all"
                  style={{ width: `${barWidthPct(outputRemainingRatio)}%` }}
                />
              </div>
            </div>
          </div>

          <div className="bg-border my-3.5 h-px" />

          {/* 3. Real Session Cost Cap (SIGAP_COST_CAP_IDR in config.py / graph.py) */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="inline-flex items-center gap-1.5 font-medium">
                Session budget cap
                <span
                  title={`Enforced by SIGAP_COST_CAP_IDR (Rp ${costCapIdr.toLocaleString()} per session/event).`}
                  className="text-muted-foreground inline-flex cursor-help"
                >
                  <CircleHelp className="size-3.5" />
                </span>
              </span>
              <span className="text-muted-foreground font-mono text-[11px]">
                Rp {remainingBudgetIdr.toLocaleString()} left ({formatPercent(budgetRemainingRatio)})
              </span>
            </div>

            <div className="bg-muted h-1.5 w-full overflow-hidden rounded-full">
              <div
                className="h-full rounded-full bg-[#3b82f6] transition-all"
                style={{ width: `${barWidthPct(budgetRemainingRatio)}%` }}
              />
            </div>

            <div className="text-muted-foreground space-y-0.5 text-[11px]">
              <p>
                Session spend: <span className="text-foreground font-mono">Rp {sessionCostIdr.toLocaleString()}</span> / Rp {costCapIdr.toLocaleString()} ({formatPercent(sessionCostRatio)} used)
              </p>
              <p>
                All sessions ({threads.length || 1} conv):{" "}
                <span className="text-foreground font-mono">
                  {allTokens.toLocaleString()} tok · Rp {allCostIdr.toLocaleString()}
                </span>{" "}
                ({formatPercent(allCostRatio)})
              </p>
            </div>

            <button
              type="button"
              onClick={() => setShowBreakdown((v) => !v)}
              className="bg-secondary text-secondary-foreground hover:bg-secondary/80 mt-1 inline-flex items-center rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
            >
              {showBreakdown ? "Hide detailed breakdown" : "See detailed breakdown"}
            </button>

            {showBreakdown && (
              <div className="bg-muted/40 mt-2 max-h-44 space-y-1.5 overflow-y-auto rounded-lg border p-2.5 font-mono text-[11px]">
                <div className="text-muted-foreground flex justify-between border-b pb-1 text-[10px]">
                  <span>Turn</span>
                  <span>Prompt / Resp</span>
                  <span>Time · Cost</span>
                </div>
                {agentReplies.length === 0 ? (
                  <p className="text-muted-foreground py-1 text-center font-sans text-[11px]">
                    No replies in this session yet.
                  </p>
                ) : (
                  agentReplies.map((m, idx) => (
                    <div key={idx} className="flex items-center justify-between">
                      <span className="text-muted-foreground">#{idx + 1}</span>
                      <span>
                        {(m.reply.tokens?.input ?? 0).toLocaleString()} /{" "}
                        {(m.reply.tokens?.output ?? 0).toLocaleString()}
                      </span>
                      <span className="text-muted-foreground">
                        {m.reply.thinking_time !== undefined
                          ? `${m.reply.thinking_time.toFixed(1)}s · `
                          : ""}
                        Rp {(m.reply.cost_idr ?? 0).toLocaleString()}
                      </span>
                    </div>
                  ))
                )}
                {allTokens > 0 && (
                  <div className="text-muted-foreground flex justify-between border-t pt-1 text-[10px]">
                    <span>All-time DB total</span>
                    <span>
                      {allInputTokens.toLocaleString()} in / {allOutputTokens.toLocaleString()} out
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
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
  const [usage, setUsage] = useState<UsageOverview | null>(null);
  const [modelId, setModelId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [busy, setBusy] = useState(false);
  const [activeSteps, setActiveSteps] = useState<OrchestrationStep[]>([]);
  const [restoring, setRestoring] = useState(!!threadId);
  const bottom = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy, activeSteps]);

  useEffect(() => {
    if (field.current) {
      field.current.style.height = "auto";
      field.current.style.height = `${Math.min(field.current.scrollHeight, 220)}px`;
    }
  }, [text]);

  useEffect(() => {
    fetch("/api/sigap/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.model) setModelId(String(d.model));
      })
      .catch(() => {});
  }, []);

  const loadThreads = useCallback(async () => {
    if (!signedIn) return;
    try {
      const r = await fetch(`/api/sigap/agents/${code}/conversations`);
      if (r.ok) {
        const d = await r.json();
        setThreads(d.conversations ?? []);
        if (d.usage) setUsage(d.usage);
      }
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
          if (d.usage) setUsage(d.usage);
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
    setAttachments([]);
    onOpen?.(null);
  }

  async function addFiles(fileList: FileList | File[]) {
    const items = Array.from(fileList);
    if (!items.length) return;
    const converted = await Promise.all(items.map((f) => fileToAttachment(f)));
    setAttachments((prev) => [...prev, ...converted]);
  }

  function removeAttachment(index: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
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
        if (d.usage) setUsage(d.usage);
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
    loadThreads();
  }

  async function send(body: string, extraAttachments?: Attachment[]) {
    const q = body.trim();
    const currentAttachments = extraAttachments ?? attachments;
    if ((!q && currentAttachments.length === 0) || busy) return;
    setMessages((m) => [
      ...m,
      {
        from: "person",
        text: q,
        attachments: currentAttachments.length > 0 ? currentAttachments : undefined,
      },
    ]);
    setText("");
    setAttachments([]);
    setBusy(true);
    setActiveSteps([
      {
        seq: 0,
        kind: "init",
        agent: "supervisor",
        agent_name: name,
        narrative: "Analyzing question and coordinating specialist team...",
        badge: "Analysis ›",
        detail: "Preparing agent orchestration...",
        at: new Date().toISOString(),
      },
    ]);
    let activeCid = id;
    try {
      const r = await fetch(`/api/sigap/agents/${code}/ask`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          accept: "text/event-stream",
        },
        body: JSON.stringify({
          question: q,
          conversation_id: id,
          attachments: currentAttachments.length > 0 ? currentAttachments : undefined,
        }),
      });

      const contentType = r.headers.get("content-type") || "";
      if (r.ok && contentType.includes("text/event-stream") && r.body) {
        const reader = r.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finalReply: Reply | null = null;
        const liveSteps: OrchestrationStep[] = [];

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop() ?? "";

            for (const part of parts) {
              const trimmed = part.trim();
              if (!trimmed || trimmed.startsWith(":")) continue; // ignore keepalive comments
              let event = "message";
              let dataStr = "";
              for (const line of trimmed.split("\n")) {
                if (line.startsWith("event:")) {
                  event = line.slice(6).trim();
                } else if (line.startsWith("data:")) {
                  dataStr = line.slice(5).trim();
                }
              }

              if (!dataStr) continue;
              try {
                const data = JSON.parse(dataStr);
                if (data.conversation_id && !activeCid) {
                  activeCid = data.conversation_id;
                  setId(data.conversation_id);
                  onOpen?.(data.conversation_id);
                }
                if (event === "step") {
                  liveSteps.push(data as OrchestrationStep);
                  setActiveSteps([...liveSteps]);
                } else if (event === "done") {
                  finalReply = data as Reply;
                } else if (event === "error") {
                  throw new Error(data.error || "failed");
                }
              } catch (err) {
                if (event === "error") throw err;
              }
            }
          }
        } catch (streamErr) {
          console.warn("SSE stream interrupted, entering auto-recovery polling:", streamErr);
        }

        if (finalReply) {
          if (!finalReply.steps || finalReply.steps.length === 0) {
            finalReply.steps = liveSteps;
          }
          setMessages((m) => [...m, { from: "agent", reply: finalReply! }]);
          if (finalReply.usage) setUsage(finalReply.usage as unknown as UsageOverview);
          if (finalReply.conversation_id && finalReply.conversation_id !== id) {
            setId(finalReply.conversation_id);
            onOpen?.(finalReply.conversation_id);
          }
          loadThreads();
          return;
        }

        // Auto-recovery polling: if stream disconnected prematurely, poll conversation until finished
        if (activeCid) {
          const pollStart = Date.now();
          while (Date.now() - pollStart < 120000) {
            await new Promise((res) => setTimeout(res, 2000));
            try {
              const checkRes = await fetch(`/api/sigap/conversations/${activeCid}`);
              if (checkRes.ok) {
                const checkData = await checkRes.json();
                const msgs = checkData.messages ?? [];
                const lastMsg = msgs[msgs.length - 1];
                if (lastMsg && lastMsg.role === "agent") {
                  const replyData = lastMsg.body as Reply;
                  if (!replyData.steps || replyData.steps.length === 0) {
                    replyData.steps = liveSteps;
                  }
                  setMessages((m) => [...m, { from: "agent", reply: replyData }]);
                  if (checkData.usage) setUsage(checkData.usage as unknown as UsageOverview);
                  loadThreads();
                  return;
                }
              }
            } catch {
              // ignore transient error during polling check
            }
          }
        }
      } else {
        // Fallback JSON (only for non-streaming responses)
        const d = await r.json();
        if (!r.ok) {
          setMessages((m) => [...m, { from: "error", text: d.error ?? "failed", hint: d.hint }]);
          return;
        }
        setMessages((m) => [...m, { from: "agent", reply: d as Reply }]);
        if (d.usage) setUsage(d.usage);
        if (d.conversation_id && d.conversation_id !== id) {
          setId(d.conversation_id);
          onOpen?.(d.conversation_id);
        }
        loadThreads();
        return;
      }
    } catch {
      setMessages((m) => [...m, { from: "error", text: "the agent service is not responding" }]);
    } finally {
      setActiveSteps([]);
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
      onDragOver={(e) => {
        e.preventDefault();
      }}
      onDrop={(e) => {
        if (e.dataTransfer.files?.length) {
          e.preventDefault();
          addFiles(e.dataTransfer.files);
        }
      }}
      className="focus-within:border-foreground/30 focus-within:ring-1 focus-within:ring-ring/20 bg-background flex flex-col rounded-xl border p-3 shadow-xs transition-all"
    >
      {attachments.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2 px-0.5">
          {attachments.map((att, idx) => (
            <div
              key={`${att.name}-${idx}`}
              className="bg-muted/60 group relative flex items-center gap-2 rounded-md border px-2 py-1.5 pr-7 text-xs"
            >
              {att.kind === "image" && att.preview_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={att.preview_url}
                  alt={att.name}
                  className="size-9 shrink-0 rounded object-cover"
                />
              ) : (
                <div className="bg-background flex size-9 shrink-0 items-center justify-center rounded border">
                  <FileText className="text-muted-foreground size-4" />
                </div>
              )}
              <div className="min-w-0 max-w-40">
                <p className="truncate font-medium leading-tight">{att.name}</p>
                <p className="text-muted-foreground font-mono text-[10px]">
                  {formatFileSize(att.size)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => removeAttachment(idx)}
                aria-label={`Remove ${att.name}`}
                className="text-muted-foreground hover:text-foreground hover:bg-muted absolute right-1 top-1 rounded p-0.5 transition-colors"
              >
                <X className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Hidden file inputs */}
      <input
        ref={photoInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files) addFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.pdf,.txt,.json,.md,.log,.tsv,.xml,.yaml,.yml,image/*"
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files) addFiles(e.target.files);
          e.target.value = "";
        }}
      />

      {/* Full-width auto-expanding Textarea */}
      <textarea
        ref={field}
        rows={2}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onPaste={(e) => {
          if (e.clipboardData.files?.length) {
            e.preventDefault();
            addFiles(e.clipboardData.files);
          }
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send(text);
          }
        }}
        placeholder={`Ask ${name}…`}
        className="min-h-[48px] max-h-56 w-full resize-none bg-transparent px-1 py-1 text-sm leading-relaxed outline-none placeholder:text-muted-foreground/60"
      />

      {/* Bottom Action Bar */}
      <div className="mt-2 flex items-center justify-between border-t border-border/40 pt-2">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => photoInputRef.current?.click()}
            disabled={busy}
            title="Upload photo (PNG, JPG, WebP, GIF)"
            aria-label="Upload photo"
            className="text-muted-foreground hover:text-foreground hover:bg-muted inline-flex size-8 items-center justify-center rounded-md transition-colors disabled:opacity-40"
          >
            <ImagePlus className="size-4" />
          </button>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={busy}
            title="Upload file (CSV, PDF, TXT, JSON, MD)"
            aria-label="Upload file"
            className="text-muted-foreground hover:text-foreground hover:bg-muted inline-flex size-8 items-center justify-center rounded-md transition-colors disabled:opacity-40"
          >
            <Paperclip className="size-4" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <UsageBarPopover
            messages={messages}
            threads={threads}
            usage={usage}
            modelId={modelId}
          />
          <Button
            type="submit"
            size="sm"
            disabled={busy || (!text.trim() && attachments.length === 0)}
            className="gap-1.5"
          >
            <CornerDownLeft className="size-3.5" />
            Send
          </Button>
        </div>
      </div>
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
              {t.messages} messages
              {t.total_tokens ? ` · ${formatCompactTokens(t.total_tokens)} tok` : ""} · {ago(t.updated_at)}
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
                  onClick={() => send(ex, [])}
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
              <div key={i} className="flex flex-col items-end gap-2">
                {m.attachments && m.attachments.length > 0 && (
                  <div className="flex max-w-[85%] flex-wrap justify-end gap-2">
                    {m.attachments.map((att, idx) =>
                      att.kind === "image" && att.preview_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          key={`${att.name}-${idx}`}
                          src={att.preview_url}
                          alt={att.name}
                          className="max-h-56 max-w-xs rounded-lg border object-contain"
                        />
                      ) : (
                        <div
                          key={`${att.name}-${idx}`}
                          className="bg-muted flex items-center gap-2 rounded-lg border px-3 py-2 text-xs"
                        >
                          <FileText className="text-muted-foreground size-4 shrink-0" />
                          <div className="min-w-0">
                            <p className="max-w-48 truncate font-medium">{att.name}</p>
                            {att.size > 0 && (
                              <p className="text-muted-foreground font-mono text-[10px]">
                                {formatFileSize(att.size)}
                              </p>
                            )}
                          </div>
                        </div>
                      ),
                    )}
                  </div>
                )}
                {m.text && (
                  <p className="bg-primary text-primary-foreground max-w-[85%] whitespace-pre-line rounded-lg rounded-br-sm px-4 py-2.5 text-sm leading-relaxed">
                    {m.text}
                  </p>
                )}
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
                      <ThinkingIndicator seconds={m.reply.thinking_time} />
                      {m.reply.steps && m.reply.steps.length > 0 && (
                        <OrchestrationTimeline
                          steps={m.reply.steps}
                          duration={m.reply.thinking_time}
                          isRunning={false}
                          trail={m.reply.trail}
                          board={m.reply.board}
                          finalAnswer={m.reply.answer}
                        />
                      )}
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
              <div className="min-w-0 flex-1">
                {activeSteps.length > 0 ? (
                  <OrchestrationTimeline
                    steps={activeSteps}
                    isRunning={true}
                  />
                ) : (
                  <p className="text-muted-foreground flex items-center gap-2 pt-2 text-xs font-mono">
                    <Loader2 className="size-3.5 animate-spin" />
                    {name} is thinking…
                  </p>
                )}
              </div>
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
