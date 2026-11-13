import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import {
  ArrowRight, BookOpenCheck, Cpu, FileSearch, GitBranch, Handshake, Lock, Megaphone, Radar, ReceiptText,
  ShieldCheck, ShoppingCart, Users,
} from "lucide-react";

import { publicApi, type Ledger, type PublicOfferings } from "@/app/lib";
import { AeraMark } from "@/components/aera-mark";
import { CanvasChip, Dot, Panel, type Tone } from "@/components/dort";
import { AppTour } from "@/components/landing/app-tour";
import { GuardianPlayground } from "@/components/landing/guardian-playground";
import { CopyHash, LandingNav } from "@/components/landing/landing-nav";
import { LiveRun } from "@/components/landing/live-run";
import { CountUp, Reveal } from "@/components/landing/motion";
import { TeamComposer } from "@/components/landing/team-composer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: { absolute: "AERA · Autonomous Enterprise, Run by Agents" },
  description: "Describe a business and a team of agents runs it: finds customers, sells, delivers and keeps the books, "
    + "on TEE-attested NEAR AI models, inside on-chain spending limits a person sets.",
};

const REPO = "https://github.com/maulana-tech/aera-app";

/* --------------------------------------------------------------- pieces */

function SectionHead({ eyebrow, title, lead }: { eyebrow: string; title: string; lead?: string }) {
  return (
    <Reveal className="max-w-2xl">
      <p className="text-on-canvas-dim font-mono text-[11.5px] tracking-[0.08em] uppercase">{eyebrow}</p>
      <h2 className="mt-3 text-[30px] leading-[1.1] tracking-[-0.02em] text-white md:text-[42px]">{title}</h2>
      {lead && <p className="text-on-canvas-dim mt-4 text-[15px] leading-relaxed md:text-[16.5px]">{lead}</p>}
    </Reveal>
  );
}

function Feature({ icon: Icon, title, children, delay = 0 }: {
  icon: React.ElementType; title: string; children: React.ReactNode; delay?: number;
}) {
  return (
    <Reveal delay={delay} className="h-full">
      <Panel className="group flex h-full flex-col p-5 transition-transform duration-300 hover:-translate-y-0.5">
        <span className="bg-raised text-brand group-hover:bg-brand inline-flex size-9 items-center justify-center rounded-lg transition-colors group-hover:text-white">
          <Icon className="size-[18px]" />
        </span>
        <h3 className="text-fg mt-4 text-[16px]">{title}</h3>
        <p className="text-body mt-1.5 text-[13.5px] leading-relaxed">{children}</p>
      </Panel>
    </Reveal>
  );
}

function Stat({ value, format, label, note }: { value: number | null; format: "usd" | "int"; label: string; note: string }) {
  return (
    <div className="min-w-0">
      <p className="font-mono text-[26px] tracking-[-0.02em] text-white tabular-nums md:text-[34px]"><CountUp value={value} format={format} /></p>
      <p className="mt-1 text-[13px] text-white/90">{label}</p>
      <p className="text-on-canvas-dim mt-0.5 text-[11.5px]">{note}</p>
    </div>
  );
}

const band = "border-y border-white/10 bg-white/[0.04]";

/* ----------------------------------------------------------------- page */

export default async function Landing() {
  const signedIn = !!(await cookies()).get("aera_session")?.value;
  const [led, info] = await Promise.all([publicApi<Ledger>("ledger"), publicApi<PublicOfferings>("offerings")]);
  const sum = (dir: string) => led?.money.filter((m) => m.direction === dir && m.status === "sent").reduce((a, m) => a + m.total, 0) ?? null;
  const primary = signedIn ? { href: "/dashboard", label: "Open the dashboard" } : { href: "/login", label: "Try the live demo" };

  return (
    <div className="flex min-h-dvh flex-col">
      <LandingNav primary={primary} signedIn={signedIn} />

      <main className="flex-1">
        {/* -------------------------------------------------------------- hero */}
        <section className="relative mx-auto grid w-full max-w-6xl items-center gap-10 px-4 pt-12 pb-16 md:px-6 md:pt-20 md:pb-24 lg:grid-cols-[1.05fr_minmax(0,0.95fr)]">
          <div aria-hidden className="pointer-events-none absolute -top-24 right-0 -z-10 h-[420px] w-[620px] max-w-full rounded-full bg-[radial-gradient(closest-side,rgba(255,255,255,0.16),transparent)] blur-2xl" />
          <div className="animate-in fade-in slide-in-from-bottom-3 duration-700">
            <div className="flex flex-wrap gap-2">
              <CanvasChip tone="ok">Live on NEAR testnet</CanvasChip>
              <CanvasChip tone="info">NEAR Hackathon 2026</CanvasChip>
            </div>
            <h1 className="mt-6 text-[42px] leading-[1.02] tracking-[-0.035em] text-white md:text-[66px]">
              A business, run by a team of agents.
            </h1>
            <p className="text-on-canvas-dim mt-6 max-w-xl text-[16px] leading-relaxed md:text-[18px]">
              Describe what you sell. AERA composes the team: it finds customers, sells, delivers and keeps the books,
              on TEE-attested NEAR AI models, and moves money only through an on-chain vault with limits you set.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href={primary.href}
                className="text-brand group inline-flex h-11 items-center gap-2 rounded-lg bg-white px-5 text-[15px] shadow-float hover:bg-white/90">
                {primary.label} <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <a href="#playground" className="inline-flex h-11 items-center rounded-lg border border-white/25 px-5 text-[15px] text-white hover:bg-white/10">
                Try to fool the Guardian
              </a>
            </div>
            {!signedIn && (
              <p className="text-on-canvas-dim mt-4 text-[12.5px]">The demo is a read-only account: open every run, proof and payment; it changes nothing.</p>
            )}
          </div>
          <div className="animate-in fade-in slide-in-from-bottom-4 delay-150 duration-700">
            <LiveRun />
          </div>
        </section>

        {/* ------------------------------------------------------------ numbers */}
        <section className={band}>
          <div className="mx-auto grid w-full max-w-6xl grid-cols-2 gap-8 px-4 py-10 md:grid-cols-4 md:px-6">
            <Stat value={sum("in")} format="usd" label="Paid in by customers" note="USDC into the vault, last 30 days" />
            <Stat value={sum("out")} format="usd" label="Paid out by the team" note="to vendors on record, within limits" />
            <Stat value={led?.blocked_by_guardian ?? null} format="int" label="Actions the Guardian stopped" note="before anything left" />
            <Stat value={led?.proofs?.attested ?? null} format="int" label="Model calls verified in a TEE" note="attestation + signature, per call" />
          </div>
          <p className="text-on-canvas-dim mx-auto w-full max-w-6xl px-4 pb-6 text-[11.5px] md:px-6">
            <span className="mr-1.5 inline-block size-1.5 rounded-full bg-emerald-300 align-middle" />
            Live from the public ledger of {info?.business ?? "the demo business"}. <Link href="/ledger-public" className="underline underline-offset-2">Check every entry</Link>.
          </p>
        </section>

        {/* -------------------------------------------------------- how it works */}
        <section id="how" className="mx-auto w-full max-w-6xl scroll-mt-20 px-4 py-20 md:px-6 md:py-28">
          <SectionHead eyebrow="How it works" title="You write the rules. The team does the work."
            lead="Four steps from a paragraph to a business that runs while you sleep, and stops where you told it to." />
          <ol className="relative mt-12 grid gap-4 md:grid-cols-4">
            <li aria-hidden className="pointer-events-none absolute top-[36px] right-[12%] left-[12%] hidden h-px bg-gradient-to-r from-white/0 via-white/30 to-white/0 md:block" />
            {[
              ["01", "Describe the business", "What you sell, to whom, at what price. Or write a paragraph and a TEE model drafts the profile."],
              ["02", "Get a team", "The Composer turns the profile into roles. The same profile always yields the same team."],
              ["03", "Work arrives", "Paid orders, standing goals, replies from leads. Each becomes a work item the Supervisor delegates."],
              ["04", "Approve what passes the limits", "Small things run alone. Above the caps, a person decides, and the vault holds the money until they sign."],
            ].map(([n, t, d], i) => (
              <li key={n}>
                <Reveal delay={i * 90} className="h-full">
                  <div className="bg-card-grad relative h-full rounded-xl border p-5 shadow-soft">
                    <span className="bg-brand inline-flex size-8 items-center justify-center rounded-full font-mono text-[12px] text-white">{n}</span>
                    <h3 className="text-fg mt-4 text-[16px]">{t}</h3>
                    <p className="text-body mt-1.5 text-[13.5px] leading-relaxed">{d}</p>
                  </div>
                </Reveal>
              </li>
            ))}
          </ol>
        </section>

        {/* ------------------------------------------------------ inside the app */}
        <section id="app" className={`${band} scroll-mt-20`}>
          <div className="mx-auto w-full max-w-6xl px-4 py-20 md:px-6 md:py-28">
            <SectionHead eyebrow="Inside the app" title="What you look at while the team works."
              lead="Not a chat window. A scheduler hands work to the team every 20 seconds; you see the pipeline, decide what waits for you, and read how much ran alone." />
            <Reveal className="mt-12"><AppTour /></Reveal>
          </div>
        </section>

        {/* ---------------------------------------------------- runs on its own */}
        <section className="mx-auto w-full max-w-6xl px-4 py-20 md:px-6 md:py-28">
          <SectionHead eyebrow="Runs on its own" title="Everything a small business does, end to end." />
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Feature icon={Radar} title="Finds its own customers">
              A Lead Researcher saves prospects from public pages, only with an address the page shows. Sales writes, follows up on schedule and reads the replies.
            </Feature>
            <Feature icon={ShoppingCart} title="Sells at a checkout" delay={80}>
              Every offering has a public checkout. A customer pays USDC to the vault, the revenue split happens on chain, and the order becomes work.
            </Feature>
            <Feature icon={FileSearch} title="Delivers the work" delay={160}>
              Research, writing and quality review produce the deliverable; Fulfilment sends it only to the customer who paid, and writes its hash to the vault.
            </Feature>
            <Feature icon={Megaphone} title="Publishes free samples">
              Marketing puts a finished sample on a public page after code checks it; its checkout link counts the orders it brings.
            </Feature>
            <Feature icon={Handshake} title="Buys from other agent businesses" delay={80}>
              One AERA orders from another at its checkout and pays from its vault. The seller confirms from the buyer&apos;s vault record.
            </Feature>
            <Feature icon={ReceiptText} title="Keeps the books" delay={160}>
              Receipts, the monthly report, reconciliation with the vault and an autonomy report: every figure computed in code, never by a model.
            </Feature>
          </div>
        </section>

        {/* -------------------------------------------------------- playground */}
        <section id="playground" className={`${band} scroll-mt-20`}>
          <div className="mx-auto w-full max-w-6xl px-4 py-20 md:px-6 md:py-28">
            <SectionHead eyebrow="Safety · try it" title="Try to fool the Guardian."
              lead="An agent that reads the open web can be told to do anything. AERA assumes it will be. Pick a request and watch which rule, and which of the three brakes, catches it." />
            <Reveal className="mt-12"><GuardianPlayground /></Reveal>
          </div>
        </section>

        {/* ------------------------------------------------------------- team */}
        <section id="team" className="mx-auto w-full max-w-6xl scroll-mt-20 px-4 py-20 md:px-6 md:py-28">
          <SectionHead eyebrow="The team · compose one" title="Roles, not prompts. Capabilities, not tools."
            lead="Tell it what the business does. The Composer picks the roles; the three core roles are always there and locked in code." />
          <Reveal className="mt-12"><TeamComposer /></Reveal>
        </section>

        {/* ---------------------------------------------------------- privacy */}
        <section className={band}>
          <div className="mx-auto w-full max-w-6xl px-4 py-20 md:px-6 md:py-24">
            <SectionHead eyebrow="Private by default" title="Your business data stays sealed." />
            <div className="mt-12 grid gap-4 md:grid-cols-3">
              <Feature icon={Cpu} title="TEE-only models">
                Every agent runs on a NEAR AI Cloud model inside a trusted execution environment. Private mode refuses any model that cannot prove it.
              </Feature>
              <Feature icon={Lock} title="Verified per call" delay={80}>
                Each call&apos;s attestation (with a fresh nonce) and response signature are checked and shown in the run, re-checkable live.
              </Feature>
              <Feature icon={Users} title="Nobody else's data" delay={160}>
                Personal data is redacted before alerts leave; one customer&apos;s data never reaches another; the personal data held is counted from the tables.
              </Feature>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------ proof */}
        <section id="proof" className="mx-auto w-full max-w-6xl scroll-mt-20 px-4 py-20 md:px-6 md:py-28">
          <SectionHead eyebrow="Proof" title="Not a mock-up. Check it on chain."
            lead="The demo business runs on NEAR testnet with a real vault. These are its transactions." />
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {[
              ["A customer paid", "15 USDC into the vault for a market brief; the team researched, wrote and delivered it.", "Dj6GRKMAmCSjGdiwgoREoWKkpzcL7YRu9VdW4c3VytHa", "ok"],
              ["The team bought on its own", "A $3 dataset from a vendor on record, under the autonomous cap. No person involved.", "E7B2f1UBpSSiArEyLvDZnm8jEa7L7bvs82q4TVEtTFKk", "info"],
              ["Over the cap, a person signed", "An $8 purchase: approved in AERA, held by the vault, paid only after the owner signed approve.", "31BQURupVH6h8NVuxw5ThpLhi7wQn5t57uVQvX7pwsPg", "warn"],
            ].map(([t, d, h, tone], i) => (
              <Reveal key={h} delay={i * 90} className="h-full">
                <Panel className="flex h-full flex-col p-5">
                  <div className="flex items-center gap-2"><Dot tone={tone as Tone} /><p className="text-fg text-[15px]">{t}</p></div>
                  <p className="text-body mt-2 flex-1 text-[13.5px] leading-relaxed">{d}</p>
                  <CopyHash hash={h} />
                </Panel>
              </Reveal>
            ))}
          </div>
          <div className="mt-6 flex flex-wrap gap-2">
            {info?.vault && <CanvasChip tone="ok">vault · {info.vault}</CanvasChip>}
            <Link href="/ledger-public"><CanvasChip tone="info">Public ledger</CanvasChip></Link>
            <Link href="/samples"><CanvasChip tone="neutral">Free samples</CanvasChip></Link>
          </div>
        </section>

        {/* ----------------------------------------------------------- tracks */}
        <section className={band}>
          <div className="mx-auto w-full max-w-6xl px-4 py-20 md:px-6 md:py-24">
            <SectionHead eyebrow="Built for NEAR Hackathon 2026" title="Three tracks, one running business." />
            <div className="mt-12 grid gap-4 md:grid-cols-3">
              <Feature icon={BookOpenCheck} title="Autonomous Business">
                A profile becomes a team; orders in, payments out, customers found, books kept, autonomy counted in code.
              </Feature>
              <Feature icon={Cpu} title="Privacy & Private AI" delay={80}>
                TEE-only models, per-call attestation and signatures, personal data redacted before anything leaves.
              </Feature>
              <Feature icon={ShieldCheck} title="AI Security & Defense" delay={160}>
                Guardian rules in code, injection-aware runs, an on-chain vault the agent cannot overrule.
              </Feature>
            </div>
          </div>
        </section>

        {/* -------------------------------------------------------------- cta */}
        <section className="mx-auto w-full max-w-6xl px-4 py-20 md:px-6 md:py-28">
          <Reveal>
            <Panel className="relative flex flex-col items-start gap-6 overflow-hidden p-8 md:flex-row md:items-center md:p-12">
              <AeraMark className="text-brand/[0.06] pointer-events-none absolute -right-10 -bottom-16 size-72" />
              <div className="relative flex-1">
                <h2 className="text-fg text-[28px] leading-tight tracking-[-0.02em] md:text-[36px]">Watch a business run itself.</h2>
                <p className="text-body mt-2 max-w-xl text-[15px] leading-relaxed">
                  Open the demo: every run, every Guardian ruling, every TEE proof and every payment is there to read.
                </p>
              </div>
              <div className="relative flex flex-wrap gap-3">
                <Link href={primary.href}
                  className="bg-brand group inline-flex h-11 items-center gap-2 rounded-lg px-5 text-[15px] text-white shadow-soft hover:bg-[var(--brand-lit)]">
                  {primary.label} <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                </Link>
                <a href={REPO} target="_blank" rel="noopener noreferrer"
                  className="text-text hover:bg-raised inline-flex h-11 items-center gap-2 rounded-lg border bg-white px-5 text-[15px]">
                  <GitBranch className="size-4" /> Source
                </a>
              </div>
            </Panel>
          </Reveal>
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
