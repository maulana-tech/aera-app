"use client";

import { Loader2, MessageCircle, Send } from "lucide-react";
import { useRef, useState } from "react";

import type { Offering } from "@/app/lib";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { Checkout } from "./Checkout";

/* A visitor asks before buying; Sales answers from the business's public profile only
 * (core/public_chat.py: no access to orders, customers or money, every reply screened).
 * When the visitor is ready, the order form below starts filled in. */

type Turn = { role: "user" | "assistant"; text: string };
type Reply = { reply: string; checkout?: { offering: string; inputs: Record<string, string>; complete: boolean }; held?: boolean };

const SESSION_KEY = "aera.visitor";
function session(): string {
  try {
    let s = window.localStorage.getItem(SESSION_KEY);
    if (!s) { s = crypto.randomUUID(); window.localStorage.setItem(SESSION_KEY, s); }
    return s;
  } catch { return "anon"; }
}

export function BuyArea({ offering, network, open, business }: {
  offering: Offering; network: string; open: boolean; business: string;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [prefill, setPrefill] = useState<{ inputs: Record<string, string>; v: number } | null>(null);
  const [shown, setShown] = useState(false);
  const form = useRef<HTMLDivElement>(null);
  const examples = [
    `What exactly do I get for ${offering.title}?`,
    offering.inputs.length ? `What do you need from me?` : `How fast is it delivered?`,
    `Can you do this for my industry?`,
  ];

  async function ask(q: string) {
    const question = q.trim();
    if (!question || busy) return;
    const history = turns;
    setTurns([...history, { role: "user", text: question }]);
    setText("");
    setBusy(true);
    try {
      const r = await fetch("/api/aera/public/ask", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ session: session(), offering: offering.id, message: question, history }),
      });
      const d = (await r.json()) as Reply;
      setTurns((t) => [...t, { role: "assistant", text: d.reply || "Sorry, I could not answer that." }]);
      if (d.checkout && d.checkout.offering === offering.id) {
        setPrefill((p) => ({ inputs: d.checkout!.inputs, v: (p?.v ?? 0) + 1 }));
        setTimeout(() => form.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 300);
      }
    } catch {
      setTurns((t) => [...t, { role: "assistant", text: "Sorry, I cannot answer right now; you can still order below." }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="mt-8">
        {!shown ? (
          <button type="button" onClick={() => setShown(true)}
            className="bg-raised hover:bg-hover flex w-full items-center gap-3 rounded-lg px-4 py-3 text-left transition-colors">
            <MessageCircle className="text-brand size-5 shrink-0" />
            <span className="min-w-0">
              <span className="block text-[14px] font-medium">Questions before you buy?</span>
              <span className="text-muted-foreground block text-xs">Ask {business}&apos;s team. It answers from what is on offer here and can fill in your order.</span>
            </span>
          </button>
        ) : (
          <div className="rounded-lg border">
            <div className="flex items-center gap-2 border-b px-4 py-2.5">
              <MessageCircle className="text-brand size-4" />
              <p className="text-[13px] font-medium">Ask {business}</p>
              <span className="text-muted-foreground ml-auto text-[11px]">answered by an AI agent in a TEE · it cannot see any order or customer</span>
            </div>
            <div className="max-h-80 space-y-3 overflow-y-auto px-4 py-3" aria-live="polite">
              {turns.length === 0 && (
                <div className="flex flex-wrap gap-2">
                  {examples.map((e) => (
                    <button key={e} type="button" onClick={() => ask(e)} className="bg-raised hover:bg-hover rounded-sm px-2.5 py-1 text-xs">{e}</button>
                  ))}
                </div>
              )}
              {turns.map((t, i) => (
                <div key={i} className={cn("flex", t.role === "user" ? "justify-end" : "justify-start")}>
                  <p className={cn("max-w-[85%] rounded-lg px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap",
                    t.role === "user" ? "bg-primary text-primary-foreground" : "bg-raised text-fg")}>{t.text}</p>
                </div>
              ))}
              {busy && <p className="text-muted-foreground inline-flex items-center gap-2 text-xs"><Loader2 className="size-3.5 animate-spin" />Thinking…</p>}
            </div>
            <form className="flex gap-2 border-t p-3" onSubmit={(e) => { e.preventDefault(); void ask(text); }}>
              <Input value={text} onChange={(e) => setText(e.target.value)} maxLength={800} placeholder="Ask about the price, delivery, what you need to give…" aria-label="Your question" />
              <Button type="submit" size="icon" disabled={busy || !text.trim()} aria-label="Send"><Send /></Button>
            </form>
          </div>
        )}
      </section>

      <section className="mt-8" ref={form}>
        <h2 className="text-sm font-medium">Your order</h2>
        {prefill && (
          <p className="bg-raised text-ok mt-2 rounded-md px-3 py-2 text-xs">Filled in from your conversation. Check it, then order.</p>
        )}
        <div className="mt-3">
          <Checkout key={prefill?.v ?? 0} offering={offering} network={network} open={open} prefill={prefill?.inputs} />
        </div>
      </section>
    </>
  );
}
