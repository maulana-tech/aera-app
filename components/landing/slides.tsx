import { BadgeCheck, Lock, ShoppingCart } from "lucide-react";

import { Chip, Dot, type Tone } from "@/components/dort";

/*
 * The big words, after the Dort landing's 'Ask / Learn / Move' slides: one enormous light word per white
 * slide, its number, one line under it, and the product doing it beside the word. The slides stick a
 * little lower each, so scrolling piles them up like cards (CSS sticky; flat on phones and under
 * reduced motion). The widgets carry example data and say so.
 */

function Example() {
  return <span className="text-muted-foreground rounded-sm border px-1.5 text-[10px]">example data</span>;
}

function FindWidget() {
  const rows: [string, string, string, Tone][] = [
    ["Rina S.", "Studio Kopi Digital", "answered", "info"],
    ["Dewi P.", "Lumbung Creative", "written to", "info"],
    ["Andre W.", "Nusantara Retail Lab", "found", "neutral"],
    ["Maya L.", "Kedai Analytics", "won", "ok"],
  ];
  return (
    <div className="bg-card-grad w-full max-w-[460px] rounded-2xl border p-4 shadow-soft">
      <div className="flex items-center gap-2"><Dot tone="info" /><span className="text-fg text-[13px]">Leads</span><span className="ml-auto"><Example /></span></div>
      <div className="mt-3 grid grid-cols-4 gap-1.5 text-center">
        {[["24", "found"], ["11", "written"], ["4", "answered"], ["1", "won"]].map(([n, l]) => (
          <div key={l} className="bg-inner-grad rounded-lg border py-2"><p className="text-fg font-mono text-[17px]">{n}</p><p className="text-muted-foreground text-[10.5px]">{l}</p></div>
        ))}
      </div>
      <ul className="mt-3 divide-y rounded-lg border">
        {rows.map(([n, c, s, t]) => (
          <li key={n} className="flex items-center gap-2.5 px-3 py-2 text-[12.5px]">
            <Chip tone={t} className="w-[5.8rem]">{s}</Chip>
            <span className="text-fg truncate">{n} <span className="text-muted-foreground">· {c}</span></span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SellWidget() {
  return (
    <div className="bg-card-grad w-full max-w-[460px] rounded-2xl border p-4 shadow-soft">
      <div className="flex items-center gap-2"><ShoppingCart className="text-brand size-4" /><span className="text-fg text-[13px]">/buy/brief</span><span className="ml-auto"><Example /></span></div>
      <p className="text-fg mt-3 text-[16px]">Market brief (5 pages)</p>
      <p className="text-body mt-1 text-[12.5px]">Market size signals, competitors, recent news and three opportunities, every claim sourced.</p>
      <div className="bg-inner-grad mt-3 flex items-center justify-between rounded-lg border px-3 py-2.5">
        <span className="text-muted-foreground text-[12px]">Pay from your wallet</span>
        <span className="text-fg font-mono text-[15px]">15.00 USDC</span>
      </div>
      <ul className="mt-3 space-y-1.5 text-[12px]">
        <li className="flex items-center gap-2"><Dot tone="ok" /><span className="text-body flex-1">received by the vault</span><span className="text-muted-foreground font-mono">00:00</span></li>
        <li className="flex items-center gap-2"><Dot tone="ok" /><span className="text-body flex-1">revenue split on chain</span><span className="text-muted-foreground font-mono">00:00</span></li>
        <li className="flex items-center gap-2"><Dot tone="info" /><span className="text-body flex-1">order handed to the team</span><span className="text-muted-foreground font-mono">00:04</span></li>
      </ul>
    </div>
  );
}

function ProveWidget({ attested }: { attested: number | null }) {
  return (
    <div className="bg-card-grad w-full max-w-[460px] rounded-2xl border p-4 shadow-soft">
      <div className="flex items-center gap-2"><BadgeCheck className="text-brand size-4" /><span className="text-fg text-[13px]">Verified panel</span></div>
      <div className="mt-3 flex items-end gap-2">
        <p className="text-fg font-mono text-[30px] leading-none">{attested ?? "-"}</p>
        <p className="text-muted-foreground pb-0.5 text-[12px]">model calls attested in a TEE, live from the ledger</p>
      </div>
      <ul className="mt-4 space-y-1.5 text-[12px]">
        {[["nonce binding", "fresh per call"], ["compose hash", "matches the image"], ["signing key", "bound to the enclave"], ["response signature", "verified"]].map(([k, v]) => (
          <li key={k} className="bg-inner-grad flex items-center gap-2 rounded-md border px-2.5 py-1.5">
            <Dot tone="ok" /><span className="text-text font-mono text-[11px]">{k}</span><span className="text-body ml-auto">{v}</span>
          </li>
        ))}
      </ul>
      <p className="text-muted-foreground mt-3 flex items-center gap-1.5 text-[11.5px]"><Lock className="size-3" /> Prompts stay in memory; private mode refuses unattested models.</p>
    </div>
  );
}

export function Slides({ attested }: { attested: number | null }) {
  const slides = [
    { n: "01", word: "Find", line: "Customers, from public pages, with the page that shows who to write to.", widget: <FindWidget /> },
    { n: "02", word: "Sell", line: "A checkout per offering; USDC into the vault, the split on chain, the order to the team.", widget: <SellWidget /> },
    { n: "03", word: "Prove", line: "Every model call attested in a TEE, every payment a transaction anyone can check.", widget: <ProveWidget attested={attested} /> },
  ];
  return (
    <section id="product" aria-label="What the team does" className="relative mx-auto max-w-[1240px] scroll-mt-24 px-4 pb-24 md:px-6">
      <div className="space-y-6">
        {slides.map((s, i) => (
          <article key={s.n} className="ls-slide bg-card-grad shadow-float grid min-h-[520px] items-center gap-8 overflow-hidden rounded-[28px] border border-white/40 p-7 md:grid-cols-[1fr_minmax(0,1fr)] md:p-12"
            style={{ top: `${96 + i * 22}px` }}>
            <div>
              <p className="text-muted-foreground font-mono text-[12px]">{s.n} / 03</p>
              <h3 className="text-brand mt-3 text-[clamp(72px,11vw,150px)] leading-[0.9] font-light tracking-[-0.05em]">{s.word}</h3>
              <p className="text-body mt-5 max-w-[360px] text-[15.5px] leading-relaxed">{s.line}</p>
            </div>
            <div className="flex justify-center md:justify-end">{s.widget}</div>
          </article>
        ))}
      </div>
    </section>
  );
}
