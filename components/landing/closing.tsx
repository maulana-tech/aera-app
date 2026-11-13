import Link from "next/link";
import { Check, Minus } from "lucide-react";

import { AeraMark } from "@/components/aera-mark";
import { CityHorizon } from "./city-horizon";
import { GitHubMark, REPO } from "./nav";

/* ---------------------------------------------------------------- compare */

const ROWS: [string, boolean | "partly", boolean | "partly", boolean | "partly"][] = [
  ["Composes a team from a description of the business", true, "partly", false],
  ["Works on its own, on a schedule, with no one typing", true, "partly", false],
  ["Finds customers, sells, delivers and keeps the books", true, false, false],
  ["Moves money only through an on-chain vault with caps", true, false, false],
  ["Rules every action in code before it happens", true, false, false],
  ["Every model call attested in a TEE and verified", true, false, false],
  ["A person approves exactly what passes the limits", true, "partly", "partly"],
];

function Mark({ v, onBlue }: { v: boolean | "partly"; onBlue?: boolean }) {
  if (v === true) return <span className={`grid size-6 place-items-center rounded-full ${onBlue ? "bg-white text-brand" : "bg-white/15 text-white"}`}><Check className="size-3.5" /></span>;
  if (v === "partly") return <span className="text-on-canvas-dim text-[12px]">with your own code</span>;
  return <span className="grid size-6 place-items-center rounded-full border border-white/15 text-white/40"><Minus className="size-3.5" /></span>;
}

export function Compare() {
  return (
    <section aria-label="How AERA compares" className="mx-auto max-w-[1240px] px-4 py-24 md:px-6 md:py-32">
      <div className="grid gap-6 md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] md:items-end">
        <h2 className="text-[clamp(34px,4.6vw,64px)] leading-[1.02] font-light tracking-[-0.035em] text-white">
          Agent frameworks print text.<br /><span className="text-white/55">AERA runs the business.</span>
        </h2>
        <p className="text-on-canvas-dim max-w-[420px] text-[15px] leading-relaxed md:justify-self-end">
          A framework gives you the parts; a chatbot gives you answers. AERA is the running business, with the brakes already on.
        </p>
      </div>
      <div className="mt-12 overflow-x-auto">
        <div className="relative min-w-[720px]">
          {/* the AERA column is one raised card behind its cells, not a stack of cells */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 grid grid-cols-[minmax(0,1.6fr)_repeat(3,minmax(0,1fr))] gap-x-3">
            <span className="lc-col col-start-2 rounded-2xl" />
          </div>
          <div className="relative grid grid-cols-[minmax(0,1.6fr)_repeat(3,minmax(0,1fr))] items-end gap-x-3 pb-3 text-[13px]">
            <span />
            <span className="flex items-center justify-center gap-2 px-3 pt-5 pb-3 text-white"><AeraMark className="size-4" /> AERA</span>
            <span className="text-on-canvas-dim px-3 text-center">Agent framework</span>
            <span className="text-on-canvas-dim px-3 text-center">Chatbot + spreadsheets</span>
          </div>
          {ROWS.map(([what, a, f, c], i) => (
            <div key={what} className="relative grid grid-cols-[minmax(0,1.6fr)_repeat(3,minmax(0,1fr))] items-center gap-x-3 text-[14px]">
              <span className="border-t border-white/10 py-4 pr-4 text-white/90">{what}</span>
              <span className={`flex h-full items-center justify-center border-t border-white/10 py-4 ${i === ROWS.length - 1 ? "pb-6" : ""}`}><Mark v={a} onBlue /></span>
              <span className="flex h-full items-center justify-center border-t border-white/10 py-4"><Mark v={f} /></span>
              <span className="flex h-full items-center justify-center border-t border-white/10 py-4"><Mark v={c} /></span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------- faq */

type Cat = "setup" | "money" | "safety" | "privacy";
const CATS: [string, string][] = [["all", "All questions"], ["setup", "Setup"], ["money", "Money"], ["safety", "Safety"], ["privacy", "Privacy"]];
const FAQ: [Cat, string, string][] = [
  ["setup", "What do I need to run AERA?", "Python 3.10+ and Node 20. The agent service is standard library only; the web app is Next.js. One docker compose up runs both, with the record in one SQLite file. A NEAR AI key runs the agents; a vault on NEAR testnet or mainnet moves the money."],
  ["setup", "Is it a chatbot?", "No. Chat is one way in. A scheduler hands work to the team every 20 seconds: paid orders, standing goals, replies from leads and due follow-ups become work items without anyone typing."],
  ["setup", "What kind of business can it run?", "One that sells work it can deliver as a document or a message: research, briefs, reports, data, outreach-led services. The profile says what it sells, to whom, and what it may never do; the Composer builds the team from that."],
  ["money", "Can an agent spend my money?", "Only the Treasurer, only to vendors on record, and only through the vault. The agent holds a function-call key: it can ask for a payment, never send one past the caps. Above them, an approver signs in their own wallet."],
  ["money", "How do customers pay?", "Each offering has a public checkout. The customer pays USDC from their wallet into the vault, the revenue split happens on chain, and the paid order becomes work for the team."],
  ["money", "Can two AERA businesses trade?", "Yes. One orders at the other's checkout and pays from its vault to the payout on record; the seller confirms the payment from the buyer's vault record before it works the order."],
  ["safety", "What stops a prompt injection?", "Three brakes. Tools take record ids, not addresses; the Guardian's rules run in code before any action; and the vault enforces its own caps on chain. A run that read outside text cannot pay without a person."],
  ["safety", "Can it spam people?", "No. A lead is saved only with the page that shows its address, the first message to anyone waits for a person, cold messages are capped per day, follow-ups never come early, and an opt-out is enforced forever."],
  ["safety", "What if something goes wrong?", "An approver or owner can hit the kill switch: nothing leaves and no money moves until an owner resumes. The Guardian can also freeze the vault on its own."],
  ["privacy", "Where do the models run?", "On NEAR AI Cloud inside trusted execution environments. Each call's attestation, with a fresh nonce, and its response signature are verified and shown on the run. Private mode refuses any model that cannot prove it."],
  ["privacy", "What happens to customer data?", "It stays in the business's own record. One customer's data never reaches another, personal data is redacted before alerts leave, and the personal data held is counted from the tables."],
];

export function Faq() {
  return (
    <section id="faq" className="lp-faq mx-auto max-w-[1240px] scroll-mt-24 px-4 pb-32 md:px-6">
      <div className="grid gap-5 md:grid-cols-2 md:items-end md:gap-10">
        <div>
          <p className="lp-eyebrow mb-5"><span className="size-1.5 rounded-full bg-white/60" />FAQ</p>
          <h2 className="max-w-[560px] text-[clamp(30px,3.4vw,46px)] leading-[1.12] font-normal tracking-[-0.025em] text-white">
            Answers to the questions owners ask most.
          </h2>
        </div>
        <p className="text-on-canvas-dim max-w-[400px] text-[15px] leading-relaxed md:justify-self-end">
          What AERA needs, how money moves, what stops it from being talked into things, and where your data goes.
        </p>
      </div>
      <div className="mt-10 grid gap-3 md:mt-14 md:grid-cols-[260px_minmax(0,1fr)] md:grid-rows-[auto_1fr] md:gap-4">
        <fieldset className="grid grid-cols-2 gap-1 rounded-[16px] border border-white/[.07] bg-[#0647b3] p-1.5 md:flex md:flex-col">
          <legend className="sr-only">Filter the questions</legend>
          {CATS.map(([id, label]) => (
            <label key={id}
              className="text-on-canvas-dim flex h-10 cursor-pointer items-center justify-center rounded-[11px] px-3 text-[13.5px] transition-colors hover:text-white has-[:checked]:bg-gradient-to-b has-[:checked]:from-white/[.22] has-[:checked]:to-white/[.12] has-[:checked]:text-white has-[:focus-visible]:ring-1 has-[:focus-visible]:ring-white/30">
              <input type="radio" name="faq-cat" value={id} defaultChecked={id === "all"} className="sr-only" />
              {label}
            </label>
          ))}
        </fieldset>
        <div className="space-y-2.5 md:col-start-2 md:row-span-2 md:row-start-1">
          {FAQ.map(([cat, q, a]) => (
            <details key={q} data-cat={cat}
              className="group rounded-[16px] border bg-gradient-to-b from-[#f3f7fe] to-white px-5 transition-colors md:px-6 [&_summary::-webkit-details-marker]:hidden">
              <summary className="text-fg flex min-h-[62px] cursor-pointer list-none items-center justify-between gap-6 py-3 text-[15px] md:text-[16px]">
                {q}
                <span className="bg-inset text-muted-foreground grid size-8 flex-none place-items-center rounded-full border transition-transform duration-300 group-open:rotate-180">
                  <svg aria-hidden="true" viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M4 6l4 4 4-4" /></svg>
                </span>
              </summary>
              <p className="text-body max-w-[640px] pb-5 text-[14px] leading-relaxed">{a}</p>
            </details>
          ))}
        </div>
        <div className="rounded-[16px] border border-white/[.07] bg-[#0647b3] p-5 md:col-start-1 md:row-start-2 md:self-end">
          <p className="text-[17px] text-white">Not answered here?</p>
          <p className="text-on-canvas-dim mt-2 text-[13.5px] leading-relaxed">Open the demo and read a run end to end, or open an issue on the repository.</p>
          <a href={`${REPO}/issues`} className="mt-4 inline-flex items-center gap-1.5 text-[13.5px] text-white hover:text-white/80">Open an issue <span aria-hidden="true">→</span></a>
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- finale */

export function Finale({ cta }: { cta: { href: string; label: string } }) {
  const cols: { title: string; links: [string, string][] }[] = [
    { title: "Product", links: [["Live demo", "/login"], ["Free samples", "/samples"], ["Public ledger", "/ledger-public"]] },
    { title: "The business", links: [["How it works", "/#how-it-works"], ["Guardian", "/#guardian"], ["The team", "/#team"]] },
    { title: "Project", links: [["GitHub", REPO], ["Issues", `${REPO}/issues`], ["FAQ", "/#faq"]] },
  ];
  return (
    <div className="relative overflow-hidden">
      <div className="relative mx-auto max-w-[1240px] px-4 pt-28 pb-[330px] md:px-6 md:pt-36 md:pb-[clamp(220px,26vw,360px)]">
        <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-[40%] hidden md:block">
          <span className="absolute left-0 h-px w-[18%] bg-gradient-to-r from-transparent to-white/20" />
          <span className="absolute left-[18%] -mt-[4px] -ml-[4px] text-[10px] leading-none text-white/50">+</span>
          <span className="absolute right-0 h-px w-[18%] bg-gradient-to-l from-transparent to-white/20" />
          <span className="absolute right-[18%] -mt-[4px] -mr-[4px] text-[10px] leading-none text-white/50">+</span>
        </div>
        <div className="relative text-center">
          <AeraMark className="lp-breathe mx-auto mb-8 size-14 text-white" />
          <h2 className="text-[clamp(38px,5.8vw,76px)] leading-[1.02] font-light tracking-[-0.035em] text-white">Open the demo business.</h2>
          <p className="text-on-canvas-dim mx-auto mt-5 max-w-[480px] text-[16px] leading-relaxed">
            Every run, ruling, proof and payment on this page comes from it. Then describe your own.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link href={cta.href} className="text-brand rounded-full bg-white px-5 py-2.5 text-[14px] font-medium hover:bg-white/90">{cta.label}</Link>
            {cta.href === "/login" && (
              <Link href="/login?mode=signup" className="rounded-full border border-white/[.28] bg-white/[.12] px-5 py-2.5 text-[14px] text-white hover:bg-white/20">Create an account</Link>
            )}
            <a href={REPO} className="inline-flex items-center gap-2 rounded-full border border-white/[.28] bg-white/[.12] px-5 py-2.5 text-[14px] text-white hover:bg-white/20">
              <GitHubMark className="size-4" /> View on GitHub
            </a>
          </div>
          <p className="text-on-canvas-dim mt-8 font-mono text-[12px]">docker compose up -d --build</p>
        </div>
      </div>
      <CityHorizon />
      <footer className="relative isolate before:absolute before:inset-0 before:-z-10 before:bg-[linear-gradient(to_bottom,transparent,rgba(6,71,179,.82)_38%,rgba(4,46,120,.94))]">
        <div className="mx-auto grid max-w-[1240px] gap-10 px-4 py-14 md:grid-cols-[2fr_1fr_1fr_1fr] md:px-6">
          <div>
            <span className="flex items-center gap-2.5 text-white"><AeraMark className="size-7" /><span className="text-[21px] tracking-[-0.02em]">aera</span></span>
            <p className="text-on-canvas-dim mt-4 max-w-[300px] text-[13px] leading-relaxed">Autonomous Enterprise, Run by Agents. Brakes on by design.</p>
          </div>
          {cols.map((c) => (
            <div key={c.title}>
              <p className="text-[13px] text-white">{c.title}</p>
              <ul className="text-on-canvas-dim mt-4 space-y-2.5 text-[13px]">
                {c.links.map(([label, href]) => <li key={label}><a href={href} className="transition-colors hover:text-white">{label}</a></li>)}
              </ul>
            </div>
          ))}
        </div>
        <div className="text-on-canvas-dim mx-auto flex max-w-[1240px] justify-between px-4 pb-8 text-[12px] md:px-6">
          <span>© 2026 AERA</span>
          <span>Built for NEAR Hackathon 2026.</span>
        </div>
      </footer>
    </div>
  );
}
