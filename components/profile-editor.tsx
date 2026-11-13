"use client";

import { Check, Plus, Trash2 } from "lucide-react";

import {
  APPROVAL_INFO, APPROVAL_KINDS, CHANNEL_INFO, CHANNELS, DELIVERIES, DELIVERY_INFO, LANGUAGES, slugify,
  type Offering, type Profile,
} from "@/app/lib";
import { emptyOffering } from "@/lib/profile";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/* The business profile, as a person writes it. One set of fields serves the
 * onboarding wizard (a step at a time) and the Business page (all at once).
 * The service normalises whatever arrives (core/business.py) and says what
 * it had to change, so these fields only have to make the right thing easy. */

/* ------------------------------------------------------------------ fields */

export function Field({ label, hint, children, className, required, optional }: {
  label: string; hint?: string; children: React.ReactNode; className?: string;
  /** say it, so a person knows what they may skip */
  required?: boolean; optional?: boolean;
}) {
  return (
    <label className={cn("block min-w-0", className)}>
      <span className="text-text text-[12.5px]">
        {label}
        {required && <span className="text-bad ml-0.5" aria-hidden>*</span>}
        {optional && <span className="text-muted-foreground ml-1.5 text-[11px]">optional</span>}
      </span>
      <div className="mt-1.5">{children}</div>
      {hint && <span className="text-muted-foreground mt-1 block text-[11px] leading-relaxed">{hint}</span>}
    </label>
  );
}

export function TextArea(props: React.ComponentProps<"textarea">) {
  return (
    <textarea
      {...props}
      className={cn("border-input w-full rounded-lg border bg-white px-3 py-2 text-[13.5px] text-fg outline-none placeholder:text-muted-foreground/80 hover:border-[rgba(6,35,89,0.28)] focus-visible:border-[rgba(6,71,179,0.55)] focus-visible:ring-3 focus-visible:ring-[rgba(6,71,179,0.08)]", props.className)}
    />
  );
}

/** One item per line. Blank lines are dropped on the way out, not on the way in,
 *  so a person can type a new line without it vanishing under the cursor. */
export function Lines({ value, onChange, rows = 3, placeholder }: {
  value: string[]; onChange: (v: string[]) => void; rows?: number; placeholder?: string;
}) {
  return (
    <TextArea rows={rows} placeholder={placeholder} value={value.join("\n")}
      onChange={(e) => onChange(e.target.value.split("\n"))}
      onBlur={() => onChange(value.map((s) => s.trim()).filter(Boolean))} />
  );
}

export function Num({ value, onChange, step = "any", min = 0, prefix }: {
  value: number; onChange: (v: number) => void; step?: string; min?: number; prefix?: string;
}) {
  return (
    <div className="flex items-center gap-1.5">
      {prefix && <span className="text-muted-foreground font-mono text-xs">{prefix}</span>}
      <Input type="number" inputMode="decimal" step={step} min={min} value={Number.isFinite(value) ? value : 0}
        onChange={(e) => onChange(e.target.value === "" ? 0 : Number(e.target.value))} />
    </div>
  );
}

export const pill = (on: boolean) =>
  cn("rounded-sm px-2.5 py-1 font-mono text-[11px] transition-colors",
     on ? "bg-primary text-primary-foreground" : "bg-raised text-text hover:bg-hover");

const SELECT = "border-input h-9 w-full rounded-lg border bg-white px-3 text-[13.5px] text-fg outline-none focus-visible:border-[rgba(6,71,179,0.55)]";

function toggle(list: string[], v: string) {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
}

/** A titled group of fields, so a long step reads as a few short ones. */
export function Group({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-[14px] font-medium">{title}</h3>
      {note && <p className="text-muted-foreground mt-0.5 max-w-2xl text-xs leading-relaxed">{note}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** A choice that explains itself: a label, a line on what it means, and a tick. */
function ChoiceCard({ on, label, hint, onClick }: { on: boolean; label: string; hint: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={on}
      className={cn("flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-left transition-colors",
        on ? "border-brand/40 bg-raised" : "bg-white hover:border-[rgba(6,35,89,0.28)]")}>
      <span className={cn("mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-[5px] border",
        on ? "border-brand bg-brand text-white" : "border-[rgba(6,35,89,0.3)] bg-white")}>
        {on && <Check className="size-3" />}
      </span>
      <span className="min-w-0">
        <span className="text-fg block text-[13px] leading-tight">{label}</span>
        <span className="text-muted-foreground mt-0.5 block text-[11.5px] leading-snug">{hint}</span>
      </span>
    </button>
  );
}

type Edit = { p: Profile; set: (p: Profile) => void };

/* ------------------------------------------------------------------ basics */

export function BasicsFields({ p, set }: Edit) {
  const known = LANGUAGES.some((l) => l.code === p.language);
  return (
    <div className="space-y-8">
      <Group title="The business">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Business name" required>
            <Input value={p.name} onChange={(e) => set({ ...p, name: e.target.value })} placeholder="e.g. Lumen Research" required />
          </Field>
          <Field label="Customers are answered in" hint="The language the team writes to customers in.">
            <select className={SELECT} value={p.language} onChange={(e) => set({ ...p, language: e.target.value })}>
              {!known && p.language && <option value={p.language}>{p.language}</option>}
              {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
          </Field>
          <Field label="What the business does" className="sm:col-span-2" optional
            hint="One or two sentences. Every agent reads it before every task.">
            <TextArea rows={2} value={p.mission} onChange={(e) => set({ ...p, mission: e.target.value })}
              placeholder="e.g. Short, sourced market briefs for founders and small businesses in Southeast Asia." />
          </Field>
          <Field label="Who the customers are" className="sm:col-span-2" optional>
            <Input value={p.customers} onChange={(e) => set({ ...p, customers: e.target.value })} placeholder="e.g. Founders and SMEs in Southeast Asia" />
          </Field>
        </div>
      </Group>

      <Group title="Where customers reach you" note="Pick every way customers order or talk to the business. The team gets the agents each one needs.">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {CHANNELS.map((c) => (
            <ChoiceCard key={c} on={p.channels.includes(c)} label={CHANNEL_INFO[c].label} hint={CHANNEL_INFO[c].hint}
              onClick={() => set({ ...p, channels: toggle(p.channels, c) })} />
          ))}
        </div>
      </Group>

      <Group title="Standing goals" note="Recurring work the team takes on without being asked, one per line. Leave it empty if the team should only work on orders and your requests.">
        <Lines value={p.goals} onChange={(goals) => set({ ...p, goals })} rows={2}
          placeholder={"Publish one free sample brief each week\nFollow up with every customer a week after delivery"} />
      </Group>
    </div>
  );
}

/* --------------------------------------------------------------- offerings */

export function OfferingsFields({ p, set }: Edit) {
  const put = (i: number, o: Partial<Offering>) =>
    set({ ...p, offerings: p.offerings.map((x, j) => (j === i ? { ...x, ...o } : x)) });
  const minPrice = p.constraints.min_price_usd;
  return (
    <div className="space-y-4">
      {p.offerings.length === 0 && (
        <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
          Nothing on sale yet. You can continue without an offering: the team still works on your requests and goals,
          but customers will have nothing to buy.
        </p>
      )}
      {p.offerings.map((o, i) => {
        const autoId = !o.id || o.id === slugify(o.title);
        const cheap = minPrice > 0 && o.price_usd < minPrice;
        return (
          <fieldset key={i} className="bg-white rounded-lg border p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <legend className="text-muted-foreground text-xs">Offering {i + 1}</legend>
              <Button type="button" variant="ghost" size="xs" className="text-bad"
                onClick={() => set({ ...p, offerings: p.offerings.filter((_, j) => j !== i) })}>
                <Trash2 /> Remove
              </Button>
            </div>
            <div className="grid gap-4 sm:grid-cols-6">
              <Field label="Name" required className="sm:col-span-4">
                <Input value={o.title} placeholder="e.g. Market brief (5 pages)"
                  onChange={(e) => put(i, { title: e.target.value, ...(autoId ? { id: slugify(e.target.value) } : {}) })} />
              </Field>
              <Field label="Price" className="sm:col-span-2" hint={cheap ? `Below your minimum price of $${minPrice}: orders would be refused.` : "In USD, paid in USDC."}>
                <Num value={o.price_usd} onChange={(price_usd) => put(i, { price_usd })} prefix="$" />
              </Field>
              <Field label="What the customer gets" className="sm:col-span-6" optional>
                <TextArea rows={2} value={o.description ?? ""} onChange={(e) => put(i, { description: e.target.value })}
                  placeholder="e.g. Market size, competitors, recent news and three opportunities, every claim sourced." />
              </Field>
              <Field label="Delivered as" className="sm:col-span-3">
                <select value={o.delivery} onChange={(e) => put(i, { delivery: e.target.value })} className={SELECT}>
                  {DELIVERIES.map((d) => <option key={d} value={d}>{DELIVERY_INFO[d]}</option>)}
                </select>
              </Field>
              <Field label="Delivered within" className="sm:col-span-3" hint="Hours after payment. The team plans its work to this.">
                <div className="flex items-center gap-2">
                  <Num value={o.sla_hours} onChange={(sla_hours) => put(i, { sla_hours })} />
                  <span className="text-muted-foreground text-xs">hours</span>
                </div>
              </Field>
              <Field label="What the customer must tell you" className="sm:col-span-6" optional
                hint="Separated by commas. The checkout page asks for each one; the team cannot start without them.">
                <Input value={o.inputs.join(", ")} placeholder="e.g. industry, country"
                  onChange={(e) => put(i, { inputs: e.target.value.split(",").map((s) => s.trimStart()) })}
                  onBlur={() => put(i, { inputs: o.inputs.map((s) => s.trim()).filter(Boolean) })} />
              </Field>
              <Field label="Checkout link" className="sm:col-span-6"
                hint={autoId ? "Made from the name. Change it only if you want a different link." : "Set by hand."}>
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground shrink-0 font-mono text-xs">/buy/</span>
                  <Input value={o.id} className="font-mono" placeholder="market-brief"
                    onChange={(e) => put(i, { id: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "") })} />
                </div>
              </Field>
            </div>
          </fieldset>
        );
      })}
      <Button type="button" variant="outline" size="sm" onClick={() => set({ ...p, offerings: [...p.offerings, emptyOffering()] })}>
        <Plus /> {p.offerings.length ? "Add another offering" : "Add an offering"}
      </Button>
    </div>
  );
}

/* ---------------------------------------------------------- limits & rules */

export function LimitsFields({ p, set }: Edit) {
  const c = p.constraints;
  const setC = (x: Partial<Profile["constraints"]>) => set({ ...p, constraints: { ...c, ...x } });
  const splitTotal = p.revenue_split.reduce((s, r) => s + (Number(r.bps) || 0), 0);
  const perDayLow = c.autonomous_spend_usd.per_day < c.autonomous_spend_usd.per_payment;
  return (
    <div className="space-y-9">
      <Group title="Money the team may spend without you" note="Anything above these waits for your approval. They are also written to the vault on chain, so even a compromised server cannot pay past them.">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Per payment" hint="e.g. buying data or an API call.">
            <Num prefix="$" value={c.autonomous_spend_usd.per_payment}
              onChange={(v) => setC({ autonomous_spend_usd: { ...c.autonomous_spend_usd, per_payment: v } })} />
          </Field>
          <Field label="Per day, in total" hint={perDayLow ? "Lower than one payment: no payment could go through alone." : "All payments in one day together."}>
            <Num prefix="$" value={c.autonomous_spend_usd.per_day}
              onChange={(v) => setC({ autonomous_spend_usd: { ...c.autonomous_spend_usd, per_day: v } })} />
          </Field>
          <Field label="AI cost per day" hint="What the agents' thinking may cost. Past it, work is held until tomorrow.">
            <Num prefix="$" value={c.inference_max_usd_per_day} onChange={(v) => setC({ inference_max_usd_per_day: v })} />
          </Field>
          <Field label="Lowest price you sell at" hint="Orders below it are refused.">
            <Num prefix="$" value={c.min_price_usd} onChange={(v) => setC({ min_price_usd: v })} />
          </Field>
        </div>
      </Group>

      <Group title="Always ask me first" note="Whatever the amount, the team waits for you before doing these.">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {APPROVAL_KINDS.map((k) => (
            <ChoiceCard key={k} on={c.approval_required.includes(k)} label={APPROVAL_INFO[k].label} hint={APPROVAL_INFO[k].hint}
              onClick={() => setC({ approval_required: toggle(c.approval_required, k) })} />
          ))}
        </div>
      </Group>

      <Group title="Rules and private data" note="The Guardian checks every outgoing action against these, in code, and its block is final.">
        <div className="grid gap-4 lg:grid-cols-2">
          <Field label="The team must never…" hint="One per line. The Guardian blocks any action that does one of these.">
            <Lines value={c.forbidden} onChange={(forbidden) => setC({ forbidden })} rows={4}
              placeholder={"promise investment returns\nshare one customer's data with another"} />
          </Field>
          <Field label="Private data" hint="One per line. Never sent outside the business, never to another customer.">
            <Lines value={p.privacy.sensitive} onChange={(sensitive) => set({ ...p, privacy: { ...p.privacy, sensitive } })} rows={4}
              placeholder={"customer inputs\ncustomer contact details"} />
          </Field>
        </div>
        <label className="mt-4 flex items-start gap-2.5 text-[13px]">
          <input type="checkbox" className="accent-primary mt-0.5 size-4" checked={p.privacy.tee_only}
            onChange={(e) => set({ ...p, privacy: { ...p.privacy, tee_only: e.target.checked } })} />
          <span>
            Private AI only
            <span className="text-muted-foreground block text-xs">
              Every agent thinks inside an attested enclave (TEE) on NEAR AI Cloud, and each call is proven.
            </span>
            {!p.privacy.tee_only && (
              <span className="text-warn mt-1 block text-xs">Off: models outside a TEE may see the business&apos;s and customers&apos; data.</span>
            )}
          </span>
        </label>
      </Group>

      <Group title="Share revenue" note="Optional. The vault pays each account its share of every paid order, on chain, the moment the order is paid.">
        <div className="space-y-2">
          {p.revenue_split.map((s, i) => (
            <div key={i} className="grid grid-cols-[1fr_6.5rem_auto] items-center gap-2 sm:grid-cols-[1fr_1fr_7rem_auto]">
              <Input placeholder="partner.near" aria-label="NEAR account" value={s.account}
                onChange={(e) => set({ ...p, revenue_split: p.revenue_split.map((x, j) => j === i ? { ...x, account: e.target.value.trim() } : x) })} />
              <Input placeholder="Who it is (e.g. co-founder)" className="hidden sm:block" value={s.label ?? ""}
                onChange={(e) => set({ ...p, revenue_split: p.revenue_split.map((x, j) => j === i ? { ...x, label: e.target.value } : x) })} />
              <div className="flex items-center gap-1">
                <Input type="number" min={0} max={100} step="0.01" value={(Number(s.bps) || 0) / 100} aria-label="percent of revenue"
                  onChange={(e) => set({ ...p, revenue_split: p.revenue_split.map((x, j) => j === i ? { ...x, bps: Math.round(Number(e.target.value) * 100) } : x) })} />
                <span className="text-muted-foreground text-xs">%</span>
              </div>
              <Button type="button" size="icon-sm" variant="ghost" aria-label="Remove"
                onClick={() => set({ ...p, revenue_split: p.revenue_split.filter((_, j) => j !== i) })}>
                <Trash2 />
              </Button>
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" variant="outline" size="sm"
              onClick={() => set({ ...p, revenue_split: [...p.revenue_split, { account: "", bps: 1000, label: "" }] })}>
              <Plus /> Add a share
            </Button>
            {p.revenue_split.length > 0 && (
              <span className={cn("text-xs", splitTotal > 10_000 ? "text-bad" : "text-muted-foreground")}>
                {(splitTotal / 100).toFixed(2)}% of revenue shared{splitTotal > 10_000 ? ": more than 100%" : ""}
              </span>
            )}
          </div>
        </div>
      </Group>
    </div>
  );
}

const PROSPECTING_DEFAULT = { ideal_customer: "", per_day: 20, follow_ups: 2, follow_up_days: [3, 7] };

/** Who the team goes looking for, and how hard it may write. Empty: the business only sells to who comes to it. */
export function ProspectingFields({ p, set }: Edit) {
  const pr = p.prospecting ?? PROSPECTING_DEFAULT;
  const put = (v: Partial<typeof pr>) => set({ ...p, prospecting: { ...pr, ...v } });
  return (
    <div className="space-y-4">
      <Field label="Ideal customer to look for" optional
        hint="One or two sentences: who, where, what size, what tells you they need you. Filled in, the team gets a Lead Researcher and Sales.">
        <TextArea rows={2} value={pr.ideal_customer} maxLength={600}
          placeholder="Independent coffee roasters in Indonesia with an online shop and 5-50 staff"
          onChange={(e) => put({ ideal_customer: e.target.value })} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Cold messages a day" hint="first messages and unanswered follow-ups; at most 50">
          <Num value={pr.per_day} min={0} step="1" onChange={(v) => put({ per_day: Math.min(50, Math.round(v)) })} />
        </Field>
        <Field label="Follow-ups without an answer" hint="0 to 3">
          <Num value={pr.follow_ups} min={0} step="1" onChange={(v) => put({ follow_ups: Math.max(0, Math.min(3, Math.round(v))) })} />
        </Field>
        <Field label="Follow-up on day" hint="after the first message, comma separated">
          <Input value={pr.follow_up_days.join(", ")}
            onChange={(e) => put({ follow_up_days: e.target.value.split(/[ ,]+/).map(Number).filter((n) => n >= 1 && n <= 60) })} />
        </Field>
      </div>
      <p className="text-muted-foreground text-xs leading-relaxed">
        Always, whatever is set here: the first message to anyone waits for a person, every message says how to stop it,
        and an address that asked to stop is never written to again.
      </p>
    </div>
  );
}

/** What the service had to change or could not accept. */
export function Problems({ problems }: { problems: string[] }) {
  if (!problems.length) return null;
  return (
    <ul className="space-y-1 rounded-lg border border-border bg-raised px-4 py-3">
      {problems.map((x, i) => (
        <li key={i} className="text-xs text-warn ">{x}</li>
      ))}
    </ul>
  );
}
