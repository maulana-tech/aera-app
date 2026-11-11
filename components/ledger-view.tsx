import { ExternalLink } from "lucide-react";

import { explorer, usd, when, type Ledger } from "@/app/lib";
import { Empty, Metric, Section } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";

/** Money that counts as moved: settled on the vault or recorded on the simulated rail. */
const SETTLED = new Set(["sent", "approved", "paid"]);

function totals(led: Ledger) {
  const by = (dir: string, settledOnly = true) =>
    led.money.filter((m) => m.direction === dir && (!settledOnly || SETTLED.has(m.status)))
      .reduce((s, m) => s + m.total, 0);
  const n = (pred: (d: Ledger["decisions"][number]) => boolean) =>
    led.decisions.filter(pred).reduce((s, d) => s + d.n, 0);
  const proofsTotal = Object.values(led.proofs).reduce((s, v) => s + (v ?? 0), 0);
  return {
    moneyIn: by("in"), moneyOut: by("out"), split: by("split"), refunds: by("refund"),
    pendingOut: led.money.filter((m) => m.direction === "out" && !SETTLED.has(m.status) && m.status !== "rejected" && m.status !== "failed")
      .reduce((s, m) => s + m.total, 0),
    autonomous: n((d) => !!d.autonomous),
    human: n((d) => !d.autonomous && ["approved", "rejected", "sent", "failed"].includes(d.status)),
    waiting: n((d) => d.status === "pending"),
    blockedActions: n((d) => d.status === "blocked"),
    attested: led.proofs.attested ?? 0,
    proofsTotal,
  };
}

/** The public figures (GET /ledger, /public/ledger): no customer data, every
 *  entry with its transaction on NearBlocks when it has one. */
export function LedgerView({ led, network }: { led: Ledger; network: string }) {
  const t = totals(led);
  const simulated = led.entries.some((e) => e.rail === "simulated");
  return (
    <>
      <div className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-4">
        <Metric label="Money in" value={usd(t.moneyIn)} note={`last ${led.days} days`} />
        <Metric label="Money out" value={usd(t.moneyOut)} note={t.pendingOut ? `${usd(t.pendingOut)} still pending` : undefined} />
        <Metric label="Revenue split" value={usd(t.split)} note={t.refunds ? `${usd(t.refunds)} refunded` : undefined} />
        <Metric label="Model spend" value={usd(led.model_spend_usd)} note="TEE inference on NEAR AI Cloud" />
      </div>
      <div className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-4">
        <Metric label="Decided by the team" value={String(t.autonomous)} note="within the limits, no person needed" />
        <Metric label="Decided by a person" value={String(t.human)} note={t.waiting ? `${t.waiting} still waiting` : undefined} />
        <Metric label="Blocked by the guardian" value={String(led.blocked_by_guardian)} note={`${t.blockedActions} actions stopped`} />
        <Metric label="TEE proofs attested" value={`${t.attested}/${t.proofsTotal}`}
          note={led.proofs.pending ? `${led.proofs.pending} still being verified` : undefined} />
      </div>

      {simulated && (
        <p className="mt-6 rounded-lg border border-amber-500/50 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-900 dark:text-amber-200">
          Some entries are on the SIMULATED rail: recorded by AERA, not on any chain. They have no transaction to check.
        </p>
      )}

      <Section title={`Entries (${led.entries.length})`}>
        {led.entries.length === 0 ? (
          <Empty what="No money has moved yet." why="Paid orders, splits, payments and refunds appear here as they settle." />
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[600px] text-sm">
              <thead>
                <tr className="text-muted-foreground border-b text-left font-mono text-[10px] uppercase tracking-wider">
                  <th className="px-4 py-2.5 font-medium">When</th>
                  <th className="px-4 py-2.5 font-medium">Direction</th>
                  <th className="px-4 py-2.5 font-medium">Rail</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 text-right font-medium">Amount</th>
                  <th className="px-4 py-2.5 font-medium">Transaction</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {led.entries.map((e, i) => (
                  <tr key={e.id ?? i}>
                    <td className="text-muted-foreground px-4 py-2.5 font-mono text-[11px]">{when(e.created_at)}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{e.direction}{e.counterparty ? <span className="text-muted-foreground"> · {e.counterparty}</span> : null}</td>
                    <td className="px-4 py-2.5"><StatusBadge status={e.rail === "simulated" ? "simulated" : "vault"}>{e.rail === "simulated" ? "SIMULATED" : e.rail}</StatusBadge></td>
                    <td className="px-4 py-2.5"><StatusBadge status={e.status} /></td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums">{usd(e.amount_usd)}</td>
                    <td className="px-4 py-2.5 font-mono text-[11px]">
                      {e.tx_hash ? (
                        <a href={explorer(network, "txns", e.tx_hash)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-2">
                          {e.tx_hash.slice(0, 12)}… <ExternalLink className="size-3" />
                        </a>
                      ) : <span className="text-muted-foreground">{e.rail === "simulated" ? "simulated" : "-"}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </>
  );
}
