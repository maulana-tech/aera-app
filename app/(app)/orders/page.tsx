import Link from "next/link";

import {
  api, apiResult, explorer, mayManage, me, usd, when, type BusinessPayload, type Health, type Order, type WorkItem,
} from "@/app/lib";
import { AutoRefresh } from "@/components/auto-refresh";
import { Empty, PageHeader } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";
import { MarkPaid } from "./MarkPaid";

export const dynamic = "force-dynamic";

export default async function OrdersPage() {
  const [orders, health, user, biz, work] = await Promise.all([
    apiResult<{ orders: Order[] }>("orders"),
    api<Health>("health"),
    me(),
    api<BusinessPayload>("business"),
    api<{ items: WorkItem[] }>("work"),
  ]);
  const simulated = health?.rail !== "vault";
  const titles = new Map((biz?.profile.offerings ?? []).map((o) => [o.id, o.title]));
  const runOf = new Map((work?.items ?? []).map((w) => [w.id, w.run_id]));
  const list = orders.data?.orders ?? [];

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Orders"
        lead={simulated
          ? "No vault is configured, so payments run on the SIMULATED rail: a customer's order waits until an owner marks it paid here. Every such order is labelled simulated in the ledger."
          : "Customers pay USDC to the vault from their own wallet; the vault records the order and splits revenue, and the paid order becomes work for the team."}
        aside={<>
          <AutoRefresh active={list.some((o) => o.status === "paid" || o.status === "working")} />
          <StatusBadge status={simulated ? "simulated" : "vault"}>{simulated ? "SIMULATED rail" : `vault · ${health?.network}`}</StatusBadge>
        </>}
      />

      {!orders.data ? (
        <p className="text-muted-foreground mt-6 text-sm">{orders.error}</p>
      ) : list.length === 0 ? (
        <div className="mt-6">
          <Empty what="No orders yet." why="Share a checkout link from the Business page. Each offering has one at /buy/<id>."
            fix={biz?.profile.offerings[0] ? `/buy/${biz.profile.offerings[0].id}` : undefined} />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-lg border">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="text-muted-foreground border-b text-left font-mono text-[10px] uppercase tracking-wider">
                <th className="px-4 py-2.5 font-medium">Order</th>
                <th className="px-4 py-2.5 font-medium">Offering</th>
                <th className="px-4 py-2.5 font-medium">Inputs</th>
                <th className="px-4 py-2.5 text-right font-medium">Amount</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Paid</th>
                <th className="px-4 py-2.5 text-right font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {list.map((o) => {
                const run = o.work_item_id ? runOf.get(o.work_item_id) : null;
                return (
                  <tr key={o.id} className="align-top">
                    <td className="px-4 py-2.5">
                      <p className="font-mono text-xs">{o.id}</p>
                      <p className="text-muted-foreground font-mono text-[10px]">{when(o.created_at)}</p>
                    </td>
                    <td className="px-4 py-2.5">{titles.get(o.offering) ?? o.offering}</td>
                    <td className="text-muted-foreground max-w-56 px-4 py-2.5 text-xs">
                      {Object.entries(o.inputs).map(([k, v]) => <span key={k} className="block truncate">{k}: {v}</span>)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums">{usd(o.amount_usd)}</td>
                    <td className="px-4 py-2.5"><StatusBadge status={o.status} /></td>
                    <td className="px-4 py-2.5 font-mono text-[11px]">
                      {o.paid_tx ? (
                        <a href={explorer(health?.network, "txns", o.paid_tx)} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                          {o.paid_tx.slice(0, 10)}…
                        </a>
                      ) : o.status !== "awaiting_payment" && simulated ? <span className="text-amber-700 dark:text-amber-400">simulated</span> : "-"}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {run ? (
                        <Link href={`/work/${run}`} className="text-xs underline underline-offset-2">the work</Link>
                      ) : o.status === "awaiting_payment" && simulated && mayManage(user) ? (
                        <MarkPaid id={o.id} />
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
