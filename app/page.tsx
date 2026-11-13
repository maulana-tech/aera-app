import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import {
  ArrowRight, BadgeCheck, BookOpenCheck, Cpu, FileSearch, GitBranch, Handshake, Landmark, Lock, Megaphone,
  Radar, ReceiptText, ScanEye, ShieldCheck, ShoppingCart, Users, Wallet,
} from "lucide-react";

import { publicApi, type Ledger, type PublicOfferings } from "@/app/lib";
import { AeraMark } from "@/components/aera-mark";
import { CanvasChip, Chip, Dot, Panel, type Tone } from "@/components/dort";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: { absolute: "AERA · Autonomous Enterprise, Run by Agents" },
  description: "Describe a business and a team of agents runs it: finds customers, sells, delivers and keeps the books, "
    + "on TEE-attested NEAR AI models, inside on-chain spending limits a person sets.",
};

const REPO = "https://github.com/maulana-tech/aera-app";
const TX = (h: string) => `https://testnet.nearblocks.io/txns/${h}`;
const usd = (n: number) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/* --------------------------------------------------------------- pieces */

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <p className="text-on-canvas-dim font-mono text-[11.5px] tracking-[0.08em] uppercase">{children}</p>;
}

function SectionHead({ eyebrow, title, lead }: { eyebrow: string; title: string; lead?: string }) {
  return (
    <div className="max-w-2xl">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h2 className="mt-3 text-[30px] leading-[1.1] tracking-[-0.02em] text-white md:text-[40px]">{title}</h2>
      {lead && <p className="text-on-canvas-dim mt-4 text-[15px] leading-relaxed md:text-[16px]">{lead}</p>}
    </div>
  );
}

function Step({ who, what, tone, at }: { who: string; what: string; tone: Tone; at: string }) {
  return (
    <li className="flex items-start gap-3 py-2.5">
      <Dot tone={tone} className="mt-[7px]" />
      <div className="min-w-0 flex-1">
        <p className="text-fg text-[13.5px]"><span className="text-text">{who}</span> · {what}</p>
      </div>
      <span className="text-muted-foreground shrink-0 font-mono text-[11px]">{at}</span>
    </li>
  );
}

/** What a run looks like inside AERA, drawn from a real one on testnet. */
function RunCard() {
  return (
    <Panel className="w-full p-5 md:p-6">
      <div className="flex items-center gap-2">
        <Chip tone="info">running</Chip>
        <span className="text-muted-foreground font-mono text-[11px]">order · market brief · $15.00</span>
      </div>
      <p className="text-fg mt-3 text-[16px]">Market brief: specialty coffee, Indonesia</p>
      <ul className="mt-2 divide-y">
        <Step who="Vault" what="15 USDC received, revenue split on chain" tone="ok" at="00:00" />
        <Step who="Supervisor" what="plans the brief, delegates research" tone="info" at="00:04" />
        <Step who="Researcher" what="6 sources read as untrusted text" tone="info" at="03:12" />
        <Step who="Writer" what="5-page brief, every claim sourced" tone="info" at="21:40" />
        <Step who="Guardian" what="recipient is the payer · no other client's data" tone="ok" at="22:05" />
        <Step who="Fulfilment" what="delivered · hash written to the vault" tone="ok" at="55:10" />
      </ul>
      <div className="bg-inner-grad mt-4 rounded-lg border px-3.5 py-3">
        <div className="flex items-center gap-2 text-[12.5px]">
          <BadgeCheck className="text-brand size-4" />
          <span className="text-text">Every model call ran in a TEE: attestation and signature verified</span>
        </div>
      </div>
    </Panel>
  );
}

function GuardianCard() {
  const rows: [Tone, string, string][] = [
    ["ok", "on record", "payout account is on the vendor's record"],
    ["ok", "allowlist", "allowlisted in the vault"],
    ["warn", "autonomous cap", "$8.00 is over the $5.00 per payment"],
    ["bad", "injection", "\"ignore previous instructions\" in the invoice"],
  ];
  return (
    <Panel className="p-5 md:p-6">
      <div className="flex items-center gap-2">
        <ShieldCheck className="text-brand size-4" />
        <p className="text-fg text-[14px]">Guardian ruling, rule by rule</p>
      </div>
      <ul className="mt-3 space-y-2">
        {rows.map(([t, rule, detail]) => (
          <li key={rule} className="flex items-start gap-2.5 text-[13px]">
            <Dot tone={t} className="mt-[7px]" />
            <span className="text-text w-28 shrink-0 font-mono text-[11.5px] leading-6">{rule}</span>
            <span className="text-body leading-6">{detail}</span>
          </li>
        ))}
      </ul>
      <p className="text-muted-foreground mt-4 border-t pt-3 text-[12px] leading-relaxed">
        Computed in code from the record, before any action. A warn waits for a person; a block is final.
      </p>
    </Panel>
  );
}

function Feature({ icon: Icon, title, children }: { icon: React.ElementType; title: string; children: React.ReactNode }) {
  return (
    <Panel className="flex flex-col p-5">
      <span className="bg-raised text-brand inline-flex size-9 items-center justify-center rounded-lg"><Icon className="size-[18px]" /></span>
      <h3 className="text-fg mt-4 text-[16px]">{title}</h3>
      <p className="text-body mt-1.5 text-[13.5px] leading-relaxed">{children}</p>
    </Panel>
  );
}

function Role({ name, may, core }: { name: string; may: string; core?: boolean }) {
  return (
    <div className="bg-card-grad rounded-lg border p-4">
      <div className="flex items-center gap-2">
        <Dot tone={core ? "solid" : "info"} />
        <p className="text-fg text-[14px]">{name}</p>
        {core && <span className="text-muted-foreground ml-auto font-mono text-[10.5px]">always</span>}
      </div>
      <p className="text-body mt-1.5 text-[12.5px] leading-relaxed">{may}</p>
    </div>
  );
}

function Stat({ value, label, note }: { value: string; label: string; note?: string }) {
  return (
    <div className="min-w-0">
      <p className="font-mono text-[26px] tracking-[-0.02em] text-white tabular-nums md:text-[32px]">{value}</p>
      <p className="mt-1 text-[13px] text-white/90">{label}</p>
      {note && <p className="text-on-canvas-dim mt-0.5 text-[11.5px]">{note}</p>}
    </div>
  );
}

/* ----------------------------------------------------------------- page */

export default async function Landing() {
  const signedIn = !!(await cookies()).get("aera_session")?.value;
  const [led, info] = await Promise.all([publicApi<Ledger>("ledger"), publicApi<PublicOfferings>("offerings")]);
  const moneyIn = led?.money.filter((m) => m.direction === "in" && m.status === "sent").reduce((a, m) => a + m.total, 0) ?? null;
  const moneyOut = led?.money.filter((m) => m.direction === "out" && m.status === "sent").reduce((a, m) => a + m.total, 0) ?? null;
  const attested = led?.proofs?.attested ?? null;
  const primary = signedIn
    ? { href: "/dashboard", label: "Open the dashboard" }
    : { href: "/login", label: "Try the live demo" };

  return (
    <div className="flex min-h-dvh flex-col">
      {/* ------------------------------------------------------------ header */}
      <header className="sticky top-0 z-20 border-b border-white/10 bg-[color-mix(in_oklab,var(--canvas)_88%,transparent)] backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-3 px-4 md:px-6">
          <Link href="/" className="flex items-center gap-2.5 text-white">
            <AeraMark className="size-6" />
            <span className="text-[19px] tracking-[-0.02em]">aera</span>
          </Link>
          <nav className="ml-6 hidden items-center gap-1 text-[13.5px] md:flex">
            {[["#how", "How it works"], ["#team", "The team"], ["#safety", "Safety"], ["#proof", "Proof"]].map(([h, l]) => (
              <a key={h} href={h} className="rounded-md px-3 py-1.5 text-white/85 hover:bg-white/10 hover:text-white">{l}</a>
            ))}
            <Link href="/samples" className="rounded-md px-3 py-1.5 text-white/85 hover:bg-white/10 hover:text-white">Samples</Link>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {!signedIn && (
              <Link href="/login" className="hidden rounded-md px-3 py-1.5 text-[13.5px] text-white/90 hover:bg-white/10 sm:inline-flex">Sign in</Link>
            )}
            <Link href={primary.href}
              className="text-brand inline-flex h-9 items-center gap-1.5 rounded-md bg-white px-3.5 text-[13.5px] shadow-soft hover:bg-white/90">
              {primary.label} <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* -------------------------------------------------------------- hero */}
        <section className="mx-auto grid w-full max-w-6xl items-center gap-10 px-4 pt-14 pb-16 md:px-6 md:pt-20 md:pb-24 lg:grid-cols-[1.05fr_minmax(0,0.95fr)]">
          <div>
            <div className="flex flex-wrap gap-2">
              <CanvasChip tone="ok">Live on NEAR testnet</CanvasChip>
              <CanvasChip tone="info">NEAR Hackathon 2026</CanvasChip>
            </div>
            <h1 className="mt-6 text-[42px] leading-[1.02] tracking-[-0.035em] text-white md:text-[64px]">
              A business, run by a team of agents.
            </h1>
            <p className="text-on-canvas-dim mt-6 max-w-xl text-[16px] leading-relaxed md:text-[18px]">
              Describe what you sell. AERA composes the team: it finds customers, sells, delivers and keeps the books,
              on TEE-attested NEAR AI models, and moves money only through an on-chain vault with limits you set.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href={primary.href}
                className="text-brand inline-flex h-11 items-center gap-2 rounded-lg bg-white px-5 text-[15px] shadow-float hover:bg-white/90">
                {primary.label} <ArrowRight className="size-4" />
              </Link>
              <a href="#how" className="inline-flex h-11 items-center rounded-lg border border-white/25 px-5 text-[15px] text-white hover:bg-white/10">
                See how it works
              </a>
            </div>
            {!signedIn && (
              <p className="text-on-canvas-dim mt-4 text-[12.5px]">
                The demo is a read-only account: open every run, proof and payment; it changes nothing.
              </p>
            )}
          </div>
          <RunCard />
        </section>

        {/* ------------------------------------------------------------ numbers */}
        <section className="border-y border-white/10 bg-white/[0.04]">
          <div className="mx-auto grid w-full max-w-6xl grid-cols-2 gap-8 px-4 py-10 md:grid-cols-4 md:px-6">
            <Stat value={moneyIn != null ? usd(moneyIn) : "-"} label="Paid in by customers" note="USDC into the vault, last 30 days" />
            <Stat value={moneyOut != null ? usd(moneyOut) : "-"} label="Paid out by the team" note="to vendors on record, within limits" />
            <Stat value={led ? String(led.blocked_by_guardian) : "-"} label="Actions the Guardian stopped" note="before anything left" />
            <Stat value={attested != null ? String(attested) : "-"} label="Model calls verified in a TEE" note="attestation + signature, per call" />
          </div>
          <p className="text-on-canvas-dim mx-auto w-full max-w-6xl px-4 pb-6 text-[11.5px] md:px-6">
            Live from the public ledger of {info?.business ?? "the demo business"}. <Link href="/ledger-public" className="underline underline-offset-2">Check every entry</Link>.
          </p>
        </section>

        {/* -------------------------------------------------------- how it works */}
        <section id="how" className="mx-auto w-full max-w-6xl scroll-mt-20 px-4 py-20 md:px-6 md:py-28">
          <SectionHead eyebrow="How it works" title="You write the rules. The team does the work."
            lead="Four steps from a paragraph to a business that runs while you sleep, and stops where you told it to." />
          <ol className="mt-12 grid gap-4 md:grid-cols-4">
            {[
              ["01", "Describe the business", "What you sell, to whom, at what price. Or write a paragraph and a TEE model drafts the profile."],
              ["02", "Get a team", "The Composer turns the profile into roles. The same profile always yields the same team."],
              ["03", "Work arrives", "Paid orders, standing goals, replies from leads. Each becomes a work item the Supervisor delegates."],
              ["04", "Approve what passes the limits", "Small things run alone. Above the caps, a person decides, and the vault holds the money until they sign."],
            ].map(([n, t, d]) => (
              <li key={n} className="bg-card-grad rounded-xl border p-5 shadow-soft">
                <span className="text-brand font-mono text-[12px]">{n}</span>
                <h3 className="text-fg mt-3 text-[16px]">{t}</h3>
                <p className="text-body mt-1.5 text-[13.5px] leading-relaxed">{d}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* ---------------------------------------------------- runs on its own */}
        <section className="mx-auto w-full max-w-6xl px-4 pb-20 md:px-6 md:pb-28">
          <SectionHead eyebrow="Runs on its own" title="Everything a small business does, end to end."
            lead="Not a chat window. A scheduler hands work to the team every 20 seconds; the team reaches outside to find customers, sell, buy and report." />
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Feature icon={Radar} title="Finds its own customers">
              A Lead Researcher saves prospects from public pages, only with an address the page shows. Sales writes, follows up on schedule and reads the replies.
            </Feature>
            <Feature icon={ShoppingCart} title="Sells at a checkout">
              Every offering has a public checkout. A customer pays USDC to the vault, the revenue split happens on chain, and the order becomes work.
            </Feature>
            <Feature icon={FileSearch} title="Delivers the work">
              Research, writing and quality review produce the deliverable; Fulfilment sends it only to the customer who paid, and writes its hash to the vault.
            </Feature>
            <Feature icon={Megaphone} title="Publishes free samples">
              Marketing puts a finished sample on a public page after code checks it; its checkout link counts the orders it brings.
            </Feature>
            <Feature icon={Handshake} title="Buys from other agent businesses">
              One AERA orders from another at its checkout and pays from its vault. The seller confirms from the buyer&apos;s vault record.
            </Feature>
            <Feature icon={ReceiptText} title="Keeps the books">
              Receipts, the monthly report, reconciliation with the vault and an autonomy report: every figure computed in code, never by a model.
            </Feature>
          </div>
        </section>

        {/* ------------------------------------------------------------- team */}
        <section id="team" className="scroll-mt-20 border-y border-white/10 bg-white/[0.04]">
          <div className="mx-auto w-full max-w-6xl px-4 py-20 md:px-6 md:py-28">
            <SectionHead eyebrow="The team" title="Roles, not prompts. Capabilities, not tools."
              lead="Three core roles are always there and locked in code. The rest are composed from what the business sells and how it reaches customers." />
            <div className="mt-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Role core name="Supervisor" may="Reads the work, delegates one step at a time, writes the outcome. Cannot move money." />
              <Role core name="Guardian" may="Rules on every payment, message and counterparty. Its block is final; it can freeze the vault." />
              <Role core name="Treasurer" may="The only role that pays: vendors on record, through the vault, inside the caps." />
              <Role name="Lead Researcher" may="Finds businesses that fit the ideal customer and saves them as leads, with their source." />
              <Role name="Sales" may="Writes to leads, follows up, answers replies, links the checkout." />
              <Role name="Researcher · Writer · QA" may="Sources, writes and reviews the deliverable a customer paid for." />
              <Role name="Finance" may="Books, receipts, reconciliation, the autonomy and unit economics report." />
              <Role name="Legal & Compliance" may="Checks what goes out, keeps the policy pages and the register of personal data." />
            </div>
          </div>
        </section>

        {/* ----------------------------------------------------------- safety */}
        <section id="safety" className="mx-auto w-full max-w-6xl scroll-mt-20 px-4 py-20 md:px-6 md:py-28">
          <div className="grid items-start gap-10 lg:grid-cols-[1fr_minmax(0,0.9fr)]">
            <div>
              <SectionHead eyebrow="Safety" title="Three brakes on every payment."
                lead="An agent that reads the open web can be told to do anything. AERA assumes it will be, and puts the decision where a prompt cannot reach it." />
              <ul className="mt-10 space-y-4">
                {[
                  [Wallet, "Tools take ids, not addresses", "A payment names a contact on record. The payout address comes from the record, never from a model or a message."],
                  [ShieldCheck, "Rules in code before any action", "Injection phrases, blocklist, address-change cooldown, caps, privacy, opt-outs: computed from evidence a model did not write."],
                  [Landmark, "A vault on chain", "The agent holds a function-call key: it can ask for a payment, never send one past the caps. Above them, an approver signs."],
                ].map(([Icon, t, d]) => {
                  const I = Icon as React.ElementType;
                  return (
                    <li key={t as string} className="flex gap-4">
                      <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg border border-white/15 bg-white/10 text-white"><I className="size-[18px]" /></span>
                      <div>
                        <p className="text-[16px] text-white">{t as string}</p>
                        <p className="text-on-canvas-dim mt-1 text-[14px] leading-relaxed">{d as string}</p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
            <div className="space-y-4">
              <GuardianCard />
              <Panel className="p-5 md:p-6">
                <div className="flex items-center gap-2">
                  <ScanEye className="text-brand size-4" />
                  <p className="text-fg text-[14px]">Outside text is data, never instructions</p>
                </div>
                <p className="text-body mt-2 text-[13px] leading-relaxed">
                  A run that read a web page, a reply or a remote tool cannot pay, refund or write elsewhere without a person.
                  <span className="text-text"> manage.py attack-demo</span> sends one injected payout through all three brakes; each stops it.
                </p>
              </Panel>
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------- privacy */}
        <section className="mx-auto w-full max-w-6xl px-4 pb-20 md:px-6 md:pb-28">
          <div className="grid gap-4 md:grid-cols-3">
            <Feature icon={Cpu} title="Private by default">
              Every agent runs on a NEAR AI Cloud model inside a TEE. Private mode refuses any model that cannot prove it.
            </Feature>
            <Feature icon={Lock} title="Verified per call">
              Each call&apos;s attestation (with a fresh nonce) and response signature are checked and shown in the run, re-checkable live.
            </Feature>
            <Feature icon={Users} title="Nobody else's data">
              Personal data is redacted before alerts leave; one customer&apos;s data never reaches another; the personal data held is counted from the tables.
            </Feature>
          </div>
        </section>

        {/* ------------------------------------------------------------ proof */}
        <section id="proof" className="scroll-mt-20 border-y border-white/10 bg-white/[0.04]">
          <div className="mx-auto w-full max-w-6xl px-4 py-20 md:px-6 md:py-28">
            <SectionHead eyebrow="Proof" title="Not a mock-up. Check it on chain."
              lead="The demo business runs on NEAR testnet with a real vault. These are its transactions." />
            <div className="mt-12 grid gap-4 md:grid-cols-3">
              {[
                ["A customer paid", "15 USDC into the vault for a market brief; the team researched, wrote and delivered it.", "Dj6GRKMAmCSjGdiwgoREoWKkpzcL7YRu9VdW4c3VytHa", "ok"],
                ["The team bought on its own", "A $3 dataset from a vendor on record, under the autonomous cap. No person involved.", "E7B2f1UBpSSiArEyLvDZnm8jEa7L7bvs82q4TVEtTFKk", "info"],
                ["Over the cap, a person signed", "An $8 purchase: approved in AERA, held by the vault, paid only after the owner signed approve.", "31BQURupVH6h8NVuxw5ThpLhi7wQn5t57uVQvX7pwsPg", "warn"],
              ].map(([t, d, h, tone]) => (
                <Panel key={h} className="flex flex-col p-5">
                  <div className="flex items-center gap-2"><Dot tone={tone as Tone} /><p className="text-fg text-[15px]">{t}</p></div>
                  <p className="text-body mt-2 flex-1 text-[13.5px] leading-relaxed">{d}</p>
                  <a href={TX(h)} target="_blank" rel="noopener noreferrer"
                    className="text-brand mt-4 inline-flex items-center gap-1.5 font-mono text-[12px] underline-offset-2 hover:underline">
                    {h.slice(0, 10)}… on NearBlocks <ArrowRight className="size-3" />
                  </a>
                </Panel>
              ))}
            </div>
            <div className="mt-6 flex flex-wrap gap-2">
              {info?.vault && <CanvasChip tone="ok">vault · {info.vault}</CanvasChip>}
              <Link href="/ledger-public"><CanvasChip tone="info">Public ledger</CanvasChip></Link>
              <Link href="/samples"><CanvasChip tone="neutral">Free samples</CanvasChip></Link>
            </div>
          </div>
        </section>

        {/* ----------------------------------------------------------- tracks */}
        <section className="mx-auto w-full max-w-6xl px-4 py-20 md:px-6 md:py-28">
          <SectionHead eyebrow="Built for NEAR Hackathon 2026" title="Three tracks, one running business." />
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {[
              [BookOpenCheck, "Autonomous Business", "A profile becomes a team; orders in, payments out, customers found, books kept, autonomy counted in code."],
              [Cpu, "Privacy & Private AI", "TEE-only models, per-call attestation and signatures, PII redacted before anything leaves."],
              [ShieldCheck, "AI Security & Defense", "Guardian rules in code, injection-aware runs, an on-chain vault the agent cannot overrule."],
            ].map(([Icon, t, d]) => {
              const I = Icon as React.ElementType;
              return (
                <Panel key={t as string} className="p-5">
                  <I className="text-brand size-5" />
                  <h3 className="text-fg mt-3 text-[16px]">{t as string}</h3>
                  <p className="text-body mt-1.5 text-[13.5px] leading-relaxed">{d as string}</p>
                </Panel>
              );
            })}
          </div>
        </section>

        {/* -------------------------------------------------------------- cta */}
        <section className="mx-auto w-full max-w-6xl px-4 pb-20 md:px-6 md:pb-28">
          <Panel className="flex flex-col items-start gap-6 p-8 md:flex-row md:items-center md:p-12">
            <div className="flex-1">
              <h2 className="text-fg text-[28px] leading-tight tracking-[-0.02em] md:text-[34px]">Watch a business run itself.</h2>
              <p className="text-body mt-2 max-w-xl text-[15px] leading-relaxed">
                Open the demo: every run, every Guardian ruling, every TEE proof and every payment is there to read.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link href={primary.href}
                className="bg-brand inline-flex h-11 items-center gap-2 rounded-lg px-5 text-[15px] text-white shadow-soft hover:bg-[var(--brand-lit)]">
                {primary.label} <ArrowRight className="size-4" />
              </Link>
              <a href={REPO} target="_blank" rel="noopener noreferrer"
                className="text-text inline-flex h-11 items-center gap-2 rounded-lg border bg-white px-5 text-[15px] hover:bg-raised">
                <GitBranch className="size-4" /> Source
              </a>
            </div>
          </Panel>
        </section>
      </main>

      {/* ------------------------------------------------------------ footer */}
      <footer className="border-t border-white/10">
        <div className="text-on-canvas-dim mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-8 text-[12.5px] md:px-6">
          <span className="flex items-center gap-2 text-white"><AeraMark className="size-4" /> aera</span>
          <span>Autonomous Enterprise, Run by Agents</span>
          <span className="ml-auto flex flex-wrap gap-4">
            <Link href="/samples" className="hover:text-white">Samples</Link>
            <Link href="/ledger-public" className="hover:text-white">Public ledger</Link>
            <a href={REPO} target="_blank" rel="noopener noreferrer" className="hover:text-white">GitHub</a>
            <Link href="/login" className="hover:text-white">Sign in</Link>
          </span>
        </div>
      </footer>
    </div>
  );
}
