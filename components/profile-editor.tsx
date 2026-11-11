"use client";

import { Plus, Trash2 } from "lucide-react";

import {
  APPROVAL_KINDS, CHANNELS, DELIVERIES, type Offering, type Profile,
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

export function Field({ label, hint, children, className }: {
  label: string; hint?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <label className={cn("block min-w-0", className)}>
      <span className="text-muted-foreground text-xs">{label}</span>
      <div className="mt-1.5">{children}</div>
      {hint && <span className="text-muted-foreground mt-1 block text-[11px] leading-relaxed">{hint}</span>}
    </label>
  );
}

export function TextArea(props: React.ComponentProps<"textarea">) {
  return (
    <textarea
      {...props}
      className={cn("border-input bg-background focus-visible:border-ring focus-visible:ring-ring/50 w-full rounded-lg border px-2.5 py-2 text-sm outline-none focus-visible:ring-3 ", props.className)}
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
  cn("rounded-full border px-3 py-1 font-mono text-[11px] transition-colors",
     on ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30");

function toggle(list: string[], v: string) {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
}

type Edit = { p: Profile; set: (p: Profile) => void };

/* ------------------------------------------------------------------ basics */

export function BasicsFields({ p, set }: Edit) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Business name"><Input value={p.name} onChange={(e) => set({ ...p, name: e.target.value })} required /></Field>
      <Field label="Language customers are answered in" hint="ISO code: en, id, es…">
        <Input value={p.language} maxLength={8} onChange={(e) => set({ ...p, language: e.target.value })} />
      </Field>
      <Field label="Mission" className="sm:col-span-2">
        <TextArea rows={2} value={p.mission} onChange={(e) => set({ ...p, mission: e.target.value })} />
      </Field>
      <Field label="Customers" className="sm:col-span-2">
        <Input value={p.customers} onChange={(e) => set({ ...p, customers: e.target.value })} placeholder="Founders and SMEs in Southeast Asia" />
      </Field>
      <div className="sm:col-span-2">
        <span className="text-muted-foreground text-xs">Channels</span>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {CHANNELS.map((c) => (
            <button key={c} type="button" className={pill(p.channels.includes(c))}
              onClick={() => set({ ...p, channels: toggle(p.channels, c) })} aria-pressed={p.channels.includes(c)}>
              {c}
            </button>
          ))}
        </div>
      </div>
      <Field label="Standing goals (one per line)" className="sm:col-span-2" hint="Recurring work the team takes on without being asked.">
        <Lines value={p.goals} onChange={(goals) => set({ ...p, goals })} rows={2} />
      </Field>
    </div>
  );
}

/* --------------------------------------------------------------- offerings */

export function OfferingsFields({ p, set }: Edit) {
  const put = (i: number, o: Partial<Offering>) =>
    set({ ...p, offerings: p.offerings.map((x, j) => (j === i ? { ...x, ...o } : x)) });
  return (
    <div className="space-y-4">
      {p.offerings.length === 0 && (
        <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
          Nothing on sale yet. A business without an offering can still work requests and goals, but takes no orders.
        </p>
      )}
      {p.offerings.map((o, i) => (
        <fieldset key={i} className="rounded-lg border p-4">
          <div className="grid gap-3 sm:grid-cols-6">
            <Field label="Id" className="sm:col-span-2" hint="Short, used in checkout links">
              <Input value={o.id} onChange={(e) => put(i, { id: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "") })} placeholder="brief" />
            </Field>
            <Field label="Title" className="sm:col-span-4">
              <Input value={o.title} onChange={(e) => put(i, { title: e.target.value })} />
            </Field>
            <Field label="Description" className="sm:col-span-6">
              <TextArea rows={2} value={o.description ?? ""} onChange={(e) => put(i, { description: e.target.value })} />
            </Field>
            <Field label="Price (USD)" className="sm:col-span-2">
              <Num value={o.price_usd} onChange={(price_usd) => put(i, { price_usd })} prefix="$" />
            </Field>
            <Field label="Delivered as" className="sm:col-span-2">
              <select value={o.delivery} onChange={(e) => put(i, { delivery: e.target.value })}
                className="border-input bg-background h-8 w-full rounded-lg border px-2 text-sm ">
                {DELIVERIES.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </Field>
            <Field label="SLA (hours)" className="sm:col-span-2">
              <Num value={o.sla_hours} onChange={(sla_hours) => put(i, { sla_hours })} />
            </Field>
            <Field label="Inputs the customer gives (comma separated)" className="sm:col-span-5">
              <Input value={o.inputs.join(", ")} placeholder="industry, country"
                onChange={(e) => put(i, { inputs: e.target.value.split(",").map((s) => s.trimStart()) })}
                onBlur={() => put(i, { inputs: o.inputs.map((s) => s.trim()).filter(Boolean) })} />
            </Field>
            <div className="flex items-end sm:col-span-1">
              <Button type="button" variant="ghost" size="sm" className="text-destructive"
                onClick={() => set({ ...p, offerings: p.offerings.filter((_, j) => j !== i) })}>
                <Trash2 /> Remove
              </Button>
            </div>
          </div>
        </fieldset>
      ))}
      <Button type="button" variant="outline" size="sm" onClick={() => set({ ...p, offerings: [...p.offerings, emptyOffering()] })}>
        <Plus /> Add an offering
      </Button>
    </div>
  );
}

/* ---------------------------------------------------------- limits & rules */

export function LimitsFields({ p, set }: Edit) {
  const c = p.constraints;
  const setC = (x: Partial<Profile["constraints"]>) => set({ ...p, constraints: { ...c, ...x } });
  const splitTotal = p.revenue_split.reduce((s, r) => s + (Number(r.bps) || 0), 0);
  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Autonomous spend, per payment" hint="Above this, a person approves.">
          <Num prefix="$" value={c.autonomous_spend_usd.per_payment}
            onChange={(v) => setC({ autonomous_spend_usd: { ...c.autonomous_spend_usd, per_payment: v } })} />
        </Field>
        <Field label="Autonomous spend, per day">
          <Num prefix="$" value={c.autonomous_spend_usd.per_day}
            onChange={(v) => setC({ autonomous_spend_usd: { ...c.autonomous_spend_usd, per_day: v } })} />
        </Field>
        <Field label="Model spend cap, per day" hint="The team stops reasoning past it.">
          <Num prefix="$" value={c.inference_max_usd_per_day} onChange={(v) => setC({ inference_max_usd_per_day: v })} />
        </Field>
        <Field label="Minimum price">
          <Num prefix="$" value={c.min_price_usd} onChange={(v) => setC({ min_price_usd: v })} />
        </Field>
      </div>

      <div>
        <span className="text-muted-foreground text-xs">Always needs a person, whatever the amount</span>
        <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {APPROVAL_KINDS.map((k) => (
            <label key={k} className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="accent-primary size-4" checked={c.approval_required.includes(k)}
                onChange={() => setC({ approval_required: toggle(c.approval_required, k) })} />
              <span className="font-mono text-xs">{k}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Field label="Never (one per line)" hint="The guardian blocks any action that does one of these.">
          <Lines value={c.forbidden} onChange={(forbidden) => setC({ forbidden })} rows={4}
            placeholder={"promise investment returns\nshare one customer's data with another"} />
        </Field>
        <Field label="Sensitive data (one per line)" hint="Never sent outside the business, never to another customer.">
          <Lines value={p.privacy.sensitive} onChange={(sensitive) => set({ ...p, privacy: { ...p.privacy, sensitive } })} rows={4}
            placeholder={"customer inputs\ncustomer contact details"} />
        </Field>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="accent-primary mt-0.5 size-4" checked={p.privacy.tee_only}
          onChange={(e) => set({ ...p, privacy: { ...p.privacy, tee_only: e.target.checked } })} />
        <span>
          Only TEE-attested models
          <span className="text-muted-foreground block text-xs">Every agent thinks inside an attested enclave on NEAR AI Cloud; proxied models are refused.</span>
        </span>
      </label>

      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="text-muted-foreground text-xs">Revenue split, paid on chain as each order settles</span>
          <span className={cn("font-mono text-[11px]", splitTotal > 10_000 ? "text-bad " : "text-muted-foreground")}>
            {(splitTotal / 100).toFixed(2)}% of revenue
          </span>
        </div>
        <div className="mt-2 space-y-2">
          {p.revenue_split.map((s, i) => (
            <div key={i} className="grid grid-cols-[1fr_6rem_auto] gap-2 sm:grid-cols-[1fr_1fr_7rem_auto]">
              <Input placeholder="contributor.testnet" value={s.account}
                onChange={(e) => set({ ...p, revenue_split: p.revenue_split.map((x, j) => j === i ? { ...x, account: e.target.value.trim() } : x) })} />
              <Input placeholder="label" className="hidden sm:block" value={s.label ?? ""}
                onChange={(e) => set({ ...p, revenue_split: p.revenue_split.map((x, j) => j === i ? { ...x, label: e.target.value } : x) })} />
              <div className="flex items-center gap-1">
                <Input type="number" min={0} max={10000} value={s.bps} aria-label="basis points"
                  onChange={(e) => set({ ...p, revenue_split: p.revenue_split.map((x, j) => j === i ? { ...x, bps: Number(e.target.value) } : x) })} />
                <span className="text-muted-foreground font-mono text-[10px]">bps</span>
              </div>
              <Button type="button" size="icon-sm" variant="ghost" aria-label="Remove"
                onClick={() => set({ ...p, revenue_split: p.revenue_split.filter((_, j) => j !== i) })}>
                <Trash2 />
              </Button>
            </div>
          ))}
          <Button type="button" variant="outline" size="sm"
            onClick={() => set({ ...p, revenue_split: [...p.revenue_split, { account: "", bps: 1000, label: "" }] })}>
            <Plus /> Add a split
          </Button>
          <p className="text-muted-foreground text-[11px]">100 bps = 1%. The vault pays each account its share of every paid order.</p>
        </div>
      </div>
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
