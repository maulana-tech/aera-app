import { ExternalLink } from "lucide-react";
import Link from "next/link";

import {
  apiResult, explorer, fromBase, mayManage, mayStop, me, toBase, usd, when, type Payment, type Treasury,
} from "@/app/lib";
import { ActionCard } from "@/components/action-card";
import { KillSwitch } from "@/components/kill-switch";
import { Empty, Fact, Metric, PageHeader, Rail, Section } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";
import { SyncButton } from "@/components/run-controls";
import { ApproveOnChain, FreezeOnChain, RefundOnChain, WalletStatus } from "./VaultActions";

export const dynamic = "force-dynamic";

function TxLink({ network, tx }: { network: string; tx: string | null }) {
  if (!tx) return <span className="text-muted-foreground">-</span>;
  return (
    <a href={explorer(network, "txns", tx)} target="_blank" rel="noopener noreferrer"
       className="inline-flex items-center gap-1 underline underline-offset-2">
      {tx.slice(0, 10)}… <ExternalLink className="size-3" />
    </a>
  );
}

function PaymentRow({ p, network }: { p: Payment; network: string }) {
  return (
    <tr className="align-top">
      <td className="px-4 py-2.5"><StatusBadge status={p.status} /></td>
      <td className="px-4 py-2.5 font-mono text-xs">{p.direction}</td>
      <td className="px-4 py-2.5"><StatusBadge status={p.rail === "vault" ? "vault" : "simulated"}>{p.rail}</StatusBadge></td>
      <td className="max-w-48 truncate px-4 py-2.5 font-mono text-xs">{p.counterparty}</td>
      <td className="px-4 py-2.5 text-right font-mono tabular-nums">{usd(p.amount_usd)}</td>
      <td className="px-4 py-2.5 font-mono text-[11px]"><TxLink network={network} tx={p.tx_hash} /></td>
      <td className="text-muted-foreground px-4 py-2.5 font-mono text-[10px]">{when(p.created_at)}</td>
    </tr>
  );
}

export default async function TreasuryPage() {
  const [res, user] = await Promise.all([apiResult<Treasury>("treasury"), me()]);
  if (!res.data) {
    return (
      <main className="w-full px-4 py-4 md:px-6 md:py-8">
        <PageHeader title="Treasury" />
        <p className="text-muted-foreground mt-6 text-sm">{res.error}</p>
      </main>
    );
  }
  const t = res.data;
  const onChain = t.rail === "vault" && !!t.vault;
  const pol = t.policy ?? null;
  const approver = mayStop(user);

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Treasury"
        lead={onChain
          ? "Money moves only through the vault contract. The agent holds a function-call key: it can ask for a payment, never send one past the caps. Anything above them waits here for an approver's wallet."
          : "SIMULATED: no vault is configured. Payments and orders are recorded but no money moves on any chain. Configure AERA_VAULT_CONTRACT and the agent's function-call key (manage.py near-setup) to go on chain."}
        aside={<StatusBadge status={onChain ? "vault" : "simulated"} className="text-xs">{onChain ? `VAULT · ${t.network}` : "SIMULATED rail"}</StatusBadge>}
      />

      {onChain && <div className="mt-4"><SyncButton /></div>}

      {!onChain && (
        <div className="mt-6 rounded-lg border border-amber-500/50 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
          Simulated rail. Nothing on this page has touched a blockchain; figures are AERA&apos;s own record.
        </div>
      )}

      <div className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-4">
        <Metric label="Vault balance" value={t.balance_usd != null ? usd(t.balance_usd) : "-"} note={onChain ? t.token : "no vault"} />
        <Metric label="Paid today (autonomous)" value={usd(t.paid_today_usd)} note={`cap ${usd(t.caps.per_day)} / day`} />
        <Metric label="Autonomous per payment" value={usd(t.caps.per_payment)} />
        <Metric label="Waiting for a person" value={String(t.pending_actions.length + t.pending_onchain.length + t.approved_refunds.length)} />
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0">
          {onChain && t.vault && (
            <Section title="Your wallet" className="mt-0" note="Approvals, refunds and unfreeze are signed here, in your own wallet, with 1 yoctoNEAR as proof of a full-access key.">
              <WalletStatus network={t.network} />
            </Section>
          )}

          <Section title={`Actions waiting for a decision (${t.pending_actions.length})`} className={onChain ? undefined : "mt-0"}>
            {t.pending_actions.length === 0 ? (
              <p className="text-muted-foreground text-sm">Nothing waits for a decision in AERA.</p>
            ) : (
              <div className="space-y-3">
                {t.pending_actions.map((a) => <ActionCard key={a.id} action={a} user={user} killSwitch={t.kill_switch} showWork />)}
              </div>
            )}
          </Section>

          <Section title={`Payments pending on chain (${t.pending_onchain.length})`}
            note="Approved in AERA and above the vault's caps, so the vault holds them until an approver signs approve(request_id).">
            {t.pending_onchain.length === 0 ? (
              <p className="text-muted-foreground text-sm">None.</p>
            ) : (
              <ul className="space-y-3">
                {t.pending_onchain.map((p) => (
                  <li key={p.id} className="rounded-lg border p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-medium">{usd(p.amount_usd)}</span>
                      <span className="text-muted-foreground text-xs">to</span>
                      <span className="font-mono text-xs">{p.counterparty}</span>
                      <span className="text-muted-foreground ml-auto font-mono text-[10px]">request {p.request_id ?? "?"}</span>
                    </div>
                    {p.action_id && <p className="text-muted-foreground mt-1 font-mono text-[10px]">action {p.action_id} · tx <TxLink network={t.network} tx={p.tx_hash} /></p>}
                    <div className="mt-3">
                      {onChain && t.vault && p.request_id && approver
                        ? <ApproveOnChain contract={t.vault} network={t.network} requestId={p.request_id} />
                        : <p className="text-muted-foreground text-xs">{approver ? "No vault or request id to sign against." : "Only an approver can sign this."}</p>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title={`Refunds approved, awaiting a wallet signature (${t.approved_refunds.length})`}
            note="A refund is never sent by the agent. An approver signs vault.refund(order_id, amount) from their wallet.">
            {t.approved_refunds.length === 0 ? (
              <p className="text-muted-foreground text-sm">None.</p>
            ) : (
              <ul className="space-y-3">
                {t.approved_refunds.map((a) => {
                  const orderId = String(a.payload.order_id ?? "");
                  const amount = Number(a.payload.amount_usd ?? a.value_usd);
                  return (
                    <li key={a.id} className="rounded-lg border p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm font-medium">{usd(amount)}</span>
                        <span className="text-muted-foreground text-xs">refund of</span>
                        <span className="font-mono text-xs">{orderId}</span>
                        {a.work_title && <Link href={`/work/${a.run_id}`} className="text-muted-foreground ml-auto truncate text-xs underline">{a.work_title}</Link>}
                      </div>
                      {typeof a.payload.reason === "string" && <p className="text-muted-foreground mt-1 text-xs">{a.payload.reason}</p>}
                      <div className="mt-3">
                        {onChain && t.vault && approver
                          ? <RefundOnChain contract={t.vault} network={t.network} orderId={orderId} amountBase={toBase(amount)} />
                          : <p className="text-muted-foreground text-xs">{onChain ? "Only an approver can sign this." : "Simulated rail: there is no vault to refund from."}</p>}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </Section>

          <Section title={`Payments (${t.payments.length})`}>
            {t.payments.length === 0 ? (
              <Empty what="No payments yet." why="Money in arrives with paid orders; money out with approved payments." />
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full min-w-[680px] text-sm">
                  <thead>
                    <tr className="text-muted-foreground border-b text-left font-mono text-[10px] uppercase tracking-wider">
                      <th className="px-4 py-2.5 font-medium">Status</th>
                      <th className="px-4 py-2.5 font-medium">Dir</th>
                      <th className="px-4 py-2.5 font-medium">Rail</th>
                      <th className="px-4 py-2.5 font-medium">Counterparty</th>
                      <th className="px-4 py-2.5 text-right font-medium">Amount</th>
                      <th className="px-4 py-2.5 font-medium">Tx</th>
                      <th className="px-4 py-2.5 font-medium">At</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">{t.payments.map((p) => <PaymentRow key={p.id} p={p} network={t.network} />)}</tbody>
                </table>
              </div>
            )}
          </Section>
        </div>

        <aside className="space-y-4">
          <KillSwitch on={!!t.kill_switch} mayStop={approver} mayResume={mayManage(user)} compact />
          <Rail title="Rail">
            <Fact label="Rail" value={onChain ? "vault" : "SIMULATED"} tone={onChain ? "plain" : "warn"} />
            <Fact label="Network" value={t.network} />
            <Fact label="Vault" value={t.vault ? (
              <a href={t.explorer ?? explorer(t.network, "address", t.vault)} target="_blank" rel="noopener noreferrer" className="underline">{t.vault}</a>
            ) : "none"} />
            <Fact label="Agent (FC key)" value={t.agent ?? "none"} />
            <Fact label="Token" value={<span title={t.token}>{t.token.length > 24 ? `${t.token.slice(0, 10)}…${t.token.slice(-6)}` : t.token}</span>} />
          </Rail>
          {pol ? (
            <Rail title="Vault policy (live)">
              <Fact label="Frozen" value={pol.frozen ? "yes" : "no"} tone={pol.frozen ? "warn" : "plain"} />
              <Fact label="Per-tx cap" value={usd(fromBase(pol.per_tx_cap))} />
              <Fact label="Daily cap" value={usd(fromBase(pol.daily_cap))} />
              <Fact label="Spent today" value={usd(fromBase(pol.spent_today))} />
              <Fact label="Owner" value={pol.owner} />
              {pol.approvers.map((a) => <Fact key={a.account_id} label={`${a.role} ≤ ${usd(fromBase(a.limit))}`} value={a.account_id} />)}
              {pol.split.map((s, i) => <Fact key={i} label={`split ${(s.bps / 100).toFixed(2)}%`} value={s.account_id} />)}
            </Rail>
          ) : onChain ? (
            <p className="text-muted-foreground text-xs">The vault policy could not be read from the chain right now.</p>
          ) : null}
          {onChain && t.vault && approver && (
            <div className="rounded-lg border p-4">
              <p className="mb-2 text-xs font-medium">Vault brake</p>
              <FreezeOnChain contract={t.vault} network={t.network} frozen={!!pol?.frozen} />
            </div>
          )}
          {pol && Math.abs(fromBase(pol.per_tx_cap) - t.caps.per_payment) > 0.001 && (
            <p className="text-xs text-amber-700 dark:text-amber-400">
              The vault&apos;s per-tx cap ({usd(fromBase(pol.per_tx_cap))}) differs from the profile ({usd(t.caps.per_payment)}). The owner sets it with set_policy from their wallet.
            </p>
          )}
        </aside>
      </div>
    </main>
  );
}
