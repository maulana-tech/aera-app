import type { Metadata } from "next";
import { cookies } from "next/headers";
import { ArrowUpRight, Cpu, Landmark, ShieldCheck, Users } from "lucide-react";

import { publicApi, type Ledger, type PublicOfferings } from "@/app/lib";
import { Dot, type Tone } from "@/components/dort";
import { Compare, Faq, Finale } from "@/components/landing/closing";
import { GuardianPlayground } from "@/components/landing/guardian-playground";
import { CopyHash } from "@/components/landing/copy-hash";
import { LiveRun } from "@/components/landing/live-run";
import { Reveal } from "@/components/landing/motion";
import { Nav } from "@/components/landing/nav";
import { Opening } from "@/components/landing/opening";
import { Slides } from "@/components/landing/slides";
import { Steps } from "@/components/landing/steps";
import { TeamComposer } from "@/components/landing/team-composer";
import "@/components/landing/landing.css";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: { absolute: "AERA · Autonomous Enterprise, Run by Agents" },
  description: "Describe a business and a team of agents runs it: finds customers, sells, delivers and keeps the books, "
    + "on TEE-attested NEAR AI models, inside on-chain spending limits a person sets.",
};

const usd = (n: number | null) => (n == null ? "-" : `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <p className="lp-eyebrow"><span className="size-1.5 rounded-full bg-white/60" />{children}</p>;
}

/** Light, two-tone: the claim in white, its continuation faded, as the Dort headings are set. */
function Heading({ a, b, className = "" }: { a: string; b: string; className?: string }) {
  return (
    <h2 className={`text-[clamp(32px,4.2vw,56px)] leading-[1.05] font-light tracking-[-0.03em] text-white ${className}`}>
      {a}<br /><span className="text-white/55">{b}</span>
    </h2>
  );
}

export default async function Landing() {
  const signedIn = !!(await cookies()).get("aera_session")?.value;
  const [led, info] = await Promise.all([publicApi<Ledger>("ledger"), publicApi<PublicOfferings>("offerings")]);
  const sum = (dir: string) => led?.money.filter((m) => m.direction === dir && m.status === "sent").reduce((a, m) => a + m.total, 0) ?? null;
  const cta = signedIn ? { href: "/dashboard", label: "Open the app" } : { href: "/login", label: "Launch demo" };
  const attested = led?.proofs?.attested ?? null;

  return (
    <main className="relative min-h-full overflow-x-clip">
      <Nav cta={cta} />

      {/* -------------------------------------------------------------- opening */}
      <Opening stats={[
        { value: usd(sum("in")), label: "paid in by customers" },
        { value: led ? String(led.blocked_by_guardian) : "-", label: "stopped by the Guardian", bad: true },
        { value: attested != null ? String(attested) : "-", label: "TEE-verified calls" },
        { value: usd(sum("out")), label: "paid out, within limits" },
      ]} />

      {/* ------------------------------------------------------------ statement */}
      <section className="mx-auto max-w-[1240px] px-4 py-24 md:px-6 md:py-32">
        <Reveal className="text-center">
          <h2 className="mx-auto max-w-[900px] text-[clamp(30px,3.8vw,52px)] leading-[1.08] font-light tracking-[-0.03em] text-white">
            A business needs a team.<br /><span className="text-white/55">Handing it to agents needs proof.</span>
          </h2>
        </Reveal>
        <div className="mt-14 grid gap-3 md:grid-cols-3">
          <Reveal className="md:col-span-2 h-full">
            <div className="lp-blue-card h-full rounded-[20px] p-6">
              <p className="text-[17px] text-white">Two bad answers, and nothing in between</p>
              <p className="text-on-canvas-dim mt-2 max-w-[640px] text-[14px] leading-relaxed">
                Hire people and every order waits on someone&apos;s calendar. Let an agent loose and it can be talked into paying anyone
                by one line on a web page. AERA is the part in between: a team that works on its own, inside rules it cannot argue with.
              </p>
            </div>
          </Reveal>
          <Reveal delay={80} className="h-full">
            <div className="lp-blue-card h-full rounded-[20px] p-6">
              <p className="text-[17px] text-white">One paragraph, one team</p>
              <p className="text-on-canvas-dim mt-2 text-[14px] leading-relaxed">Describe what you sell. The Composer builds the roles, and the same profile always yields the same team.</p>
            </div>
          </Reveal>
          <Reveal className="h-full">
            <div className="lp-blue-card h-full rounded-[20px] p-6">
              <Cpu className="size-5 text-white" />
              <p className="mt-4 text-[17px] text-white">Evidence, not promises</p>
              <p className="text-on-canvas-dim mt-2 text-[14px] leading-relaxed">Every model call attested in a TEE; every payment a transaction on NEAR anyone can open.</p>
            </div>
          </Reveal>
          <Reveal delay={80} className="md:col-span-2 h-full">
            <div className="lp-blue-card h-full rounded-[20px] p-6">
              <Landmark className="size-5 text-white" />
              <p className="mt-4 text-[17px] text-white">A person where it matters, and only there</p>
              <p className="text-on-canvas-dim mt-2 max-w-[640px] text-[14px] leading-relaxed">
                Small payments and follow-ups run on the team&apos;s authority. A refund, a new vendor, a first message to a stranger, anything past the caps:
                those wait for you, and the vault holds the money until you sign.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ------------------------------------------------------------- watch it */}
      <section className="mx-auto max-w-[1240px] px-4 pb-24 md:px-6 md:pb-32">
        <div className="lp-blue-card grid items-center gap-8 rounded-[28px] p-5 md:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)] md:p-10">
          <Reveal><LiveRun /></Reveal>
          <Reveal delay={80}>
            <div className="bg-card-grad shadow-float rounded-2xl border p-6">
              <p className="text-fg text-[20px]">Watch an order run</p>
              <p className="text-body mt-2 text-[14px] leading-relaxed">From the payment landing in the vault to the brief in the customer&apos;s inbox, every step is on the record.</p>
              <ul className="mt-5 space-y-3 text-[13.5px]">
                {["The Supervisor delegates one step at a time, to the role whose brief fits",
                  "Outside text is read as data: web pages and replies never give orders",
                  "The Guardian checks the recipient is the one who paid",
                  "The deliverable's hash is written to the vault as proof of delivery"].map((t) => (
                  <li key={t} className="flex gap-2.5"><Dot tone="ok" className="mt-[7px]" /><span className="text-body leading-relaxed">{t}</span></li>
                ))}
              </ul>
            </div>
          </Reveal>
        </div>
      </section>

      {/* --------------------------------------------------------------- slides */}
      <Slides attested={attested} />

      {/* ---------------------------------------------------------------- steps */}
      <Steps />

      {/* ------------------------------------------------------------- guardian */}
      <section id="guardian" className="mx-auto max-w-[1240px] scroll-mt-24 px-4 py-24 md:px-6 md:py-32">
        <div className="grid gap-6 md:grid-cols-2 md:items-end">
          <div>
            <Eyebrow>Try it</Eyebrow>
            <Heading className="mt-5" a="Agents get told things." b="The Guardian decides." />
          </div>
          <p className="text-on-canvas-dim max-w-[420px] text-[15px] leading-relaxed md:justify-self-end">
            An agent that reads the open web can be told to do anything. Pick a request and watch which rule, and which of the three brakes, catches it.
          </p>
        </div>
        <Reveal className="mt-12"><GuardianPlayground /></Reveal>
      </section>

      {/* ----------------------------------------------------------------- team */}
      <section id="team" className="mx-auto max-w-[1240px] scroll-mt-24 px-4 pb-24 md:px-6 md:pb-32">
        <div className="grid gap-6 md:grid-cols-2 md:items-end">
          <div>
            <Eyebrow>Compose one</Eyebrow>
            <Heading className="mt-5" a="Roles, not prompts." b="Capabilities, not tools." />
          </div>
          <p className="text-on-canvas-dim max-w-[420px] text-[15px] leading-relaxed md:justify-self-end">
            Say what the business does and the Composer picks the roles. Supervisor, Guardian and Treasurer are always there, locked in code.
          </p>
        </div>
        <Reveal className="mt-12"><TeamComposer /></Reveal>
      </section>

      {/* ---------------------------------------------------------------- proof */}
      <section id="proof" className="mx-auto max-w-[1240px] scroll-mt-24 px-4 pb-24 md:px-6 md:pb-32">
        <div className="grid gap-6 md:grid-cols-2 md:items-end">
          <Heading a="Not a mock-up." b="Check it on chain." />
          <p className="text-on-canvas-dim max-w-[420px] text-[15px] leading-relaxed md:justify-self-end">
            The demo business runs on NEAR testnet with a real vault{info?.vault ? ` (${info.vault})` : ""}. These are three of its transactions.
          </p>
        </div>
        <div className="mt-12 grid gap-3 md:grid-cols-3">
          {([
            [ShieldCheck, "A customer paid", "15 USDC into the vault for a market brief; the team researched, wrote and delivered it.", "Dj6GRKMAmCSjGdiwgoREoWKkpzcL7YRu9VdW4c3VytHa", "ok", [["amount", "15.00 USDC"], ["split", "on chain, at once"], ["delivered", "hash in the vault"]]],
            [Users, "The team bought alone", "A $3 dataset from a vendor on record, under the autonomous cap. No person involved.", "E7B2f1UBpSSiArEyLvDZnm8jEa7L7bvs82q4TVEtTFKk", "info", [["amount", "3.00 USDC"], ["cap", "$5.00 a payment"], ["approved by", "nobody needed"]]],
            [Landmark, "Over the cap, a person signed", "An $8 purchase: approved in AERA, held by the vault, paid only after the owner signed approve.", "31BQURupVH6h8NVuxw5ThpLhi7wQn5t57uVQvX7pwsPg", "warn", [["amount", "8.00 USDC"], ["held by", "the vault"], ["released by", "approve(), 1 yocto"]]],
          ] as [React.ElementType, string, string, string, Tone, [string, string][]][]).map(([Icon, t, d, h, tone, kv], i) => (
            <Reveal key={h} delay={i * 80} className="h-full">
              <article className="bg-card-grad shadow-soft flex h-full flex-col rounded-[18px] border p-5">
                <div className="flex items-center gap-2">
                  <Icon className="text-brand size-4" /><p className="text-fg text-[15px]">{t}</p>
                  <ArrowUpRight className="text-muted-foreground ml-auto size-4" />
                </div>
                <p className="text-body mt-2 text-[13.5px] leading-relaxed">{d}</p>
                <dl className="mt-4 flex-1 space-y-1 border-t pt-3 text-[12px]">
                  {kv.map(([k, v]) => (
                    <div key={k} className="flex gap-3"><dt className="text-muted-foreground w-24">{k}</dt><dd className="text-fg font-mono text-[11.5px]">{v}</dd></div>
                  ))}
                </dl>
                <div className="flex items-center gap-2"><Dot tone={tone} /><CopyHash hash={h} /></div>
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      <Compare />
      <Faq />
      <Finale cta={cta} />
    </main>
  );
}
