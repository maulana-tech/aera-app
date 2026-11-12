import { Download } from "lucide-react";
import Link from "next/link";

import { usd, when, type FinancePayload } from "@/app/lib";
import { Dot, type Tone } from "@/components/dort";
import { Section } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { CloseMonth } from "./close-month";

/* The month's books as the Finance agent sees them: figures computed in code (core/finance.py),
 * the reconciliation with the vault read live, and the reports the agent has filed. */

const RECON_TONE: Record<string, Tone> = { balanced: "ok", differences: "bad", "in flight": "warn", "not applicable": "neutral", unknown: "warn" };

function shift(month: string, by: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + by, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function Books({ data, mayAsk }: { data: FinancePayload; mayAsk: boolean }) {
  const r = data.report;
  const rec = data.reconcile;
  const lines: [string, number, boolean?][] = [
    ["Revenue", r.revenue_usd], ["Refunds", -r.refunds_usd], ["Revenue shares paid", -r.revenue_shares_usd],
    ["Vendors", -r.vendor_spend_usd], ["AI (model) cost", -r.ai_cost_usd], ["Net", r.net_usd, true],
  ];
  const thisMonth = new Date().toISOString().slice(0, 7);
  return (
    <Section title={`Books · ${r.label}`} className="mt-8"
      note="Computed by AERA's books from the payment record and the vault; no figure here is written by a model. The Finance agent explains them and files the monthly report."
      action={
        <nav className="flex items-center gap-1 text-xs">
          <Link href={`/ledger?month=${shift(r.month, -1)}`} className="bg-raised hover:bg-hover rounded-sm px-2.5 py-1">← {shift(r.month, -1)}</Link>
          {r.month !== thisMonth && <Link href="/ledger" className="bg-raised hover:bg-hover rounded-sm px-2.5 py-1">this month</Link>}
          {r.month < thisMonth && <Link href={`/ledger?month=${shift(r.month, 1)}`} className="bg-raised hover:bg-hover rounded-sm px-2.5 py-1">{shift(r.month, 1)} →</Link>}
        </nav>
      }>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="bg-white rounded-lg border">
          <table className="w-full text-[13px]">
            <tbody className="divide-y">
              {lines.map(([label, v, strong]) => (
                <tr key={label} className={strong ? "bg-raised" : ""}>
                  <td className={`px-4 py-2 ${strong ? "font-medium" : ""}`}>{label}</td>
                  <td className={`px-4 py-2 text-right font-mono ${strong ? "font-medium" : ""} ${v < 0 ? "text-muted-foreground" : ""}`}>
                    {v < 0 ? `−${usd(-v)}` : usd(v)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-muted-foreground border-t px-4 py-2.5 text-xs">
            {r.orders_paid} paid order{r.orders_paid === 1 ? "" : "s"} · {r.runs} team runs · AI cost per paid order {usd(r.ai_cost_per_order_usd)}
            {r.margin_pct != null && <> · margin <span className="text-fg">{r.margin_pct}%</span></>}
            {r.waiting_out_usd > 0 && <> · {usd(r.waiting_out_usd)} waiting to go out</>}
            {r.includes_simulated && <> · includes SIMULATED entries</>}
          </p>
          {(r.by_offering.length > 0 || r.by_vendor.length > 0) && (
            <div className="grid gap-4 border-t px-4 py-3 text-xs sm:grid-cols-2">
              {r.by_offering.length > 0 && (
                <div>
                  <p className="text-muted-foreground mb-1">By offering</p>
                  {r.by_offering.map((b) => <p key={b.offering} className="flex justify-between gap-2"><span>{b.offering} · {b.orders}</span><span className="font-mono">{usd(b.revenue_usd)}</span></p>)}
                </div>
              )}
              {r.by_vendor.length > 0 && (
                <div>
                  <p className="text-muted-foreground mb-1">Vendors paid</p>
                  {r.by_vendor.map((v) => <p key={v.vendor} className="flex justify-between gap-2"><span className="truncate">{v.vendor}</span><span className="font-mono">{usd(v.paid_usd)}</span></p>)}
                </div>
              )}
            </div>
          )}
        </div>
        <aside className="space-y-4">
          <div className="bg-white rounded-lg border p-4">
            <p className="flex items-center gap-2 text-[13px] font-medium"><Dot tone={RECON_TONE[rec.status] ?? "neutral"} />Reconciliation: {rec.status}</p>
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">{rec.summary}</p>
            {rec.differences.length > 0 && (
              <ul className="mt-2 space-y-1">{rec.differences.map((d) => <li key={d} className="text-xs text-bad">· {d}</li>)}</ul>
            )}
            {(rec.notes ?? []).length > 0 && (
              <ul className="mt-2 space-y-1">{rec.notes!.map((d) => <li key={d} className="text-xs text-warn">· {d}</li>)}</ul>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Button asChild variant="outline" size="sm"><a href={`/api/aera/finance/report.pdf?month=${r.month}`} download><Download /> Report PDF</a></Button>
            {mayAsk && <CloseMonth month={r.month} label={r.label} />}
          </div>
          {data.filed.length > 0 && (
            <div>
              <p className="text-muted-foreground mb-1 text-xs">Filed by Finance</p>
              <ul className="space-y-1">
                {data.filed.map((f) => (
                  <li key={f.id} className="flex justify-between gap-2 text-xs">
                    <Link href={`/documents/${f.id}`} className="truncate underline underline-offset-2">{f.name.replace(/^doc:/, "")}</Link>
                    <span className="text-muted-foreground shrink-0">{when(f.uploaded_at, { time: false })}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </Section>
  );
}
