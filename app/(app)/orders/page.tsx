import Link from "next/link";

import {
  api, apiResult, documentPdf, explorer, mayManage, me, orderDelivery, usd, when,
  type BusinessPayload, type DocumentRow, type Health, type Order, type WorkItem, withB, workspace } from "@/app/lib";
import { DeliveryReceipt } from "@/components/documents";
import { AutoRefresh } from "@/components/auto-refresh";
import { CheckoutLinks } from "@/components/checkout-links";
import { Empty, PageHeader } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";
import { MarkPaid } from "./MarkPaid";

export const dynamic = "force-dynamic";

const FILTERS = ["", "awaiting_payment", "paid", "working", "delivered", "refunded", "failed"];

export default async function OrdersPage({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const { status } = await searchParams;
  const ws = await workspace();
  const [orders, health, user, biz, work, docs] = await Promise.all([
    apiResult<{ orders: Order[] }>(`orders${status ? `?status=${encodeURIComponent(status)}` : ""}`),
    api<Health>("health"),
    me(),
    api<BusinessPayload>("business"),
    api<{ items: WorkItem[] }>("work"),
    api<{ documents: DocumentRow[] }>("documents"),
  ]);
  const docById = new Map((docs?.documents ?? []).map((d) => [d.id, d]));
  const docByOrder = new Map((docs?.documents ?? []).filter((d) => d.order_id).map((d) => [d.order_id!, d]));
  const simulated = health?.rail !== "vault";
  const titles = new Map((biz?.profile.offerings ?? []).map((o) => [o.id, o.title]));
  const runOf = new Map((work?.items ?? []).map((w) => [w.id, w.run_id]));
  const list = orders.data?.orders ?? [];

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Orders"
        lead={simulated
          ? "What customers bought, and where each order is. No vault is configured, so payments run on the SIMULATED rail: an order waits until an owner marks it paid here, then the team starts on it. Every such order is labelled simulated in the ledger."
          : "What customers bought, and where each order is. Customers pay USDC to the vault from their own wallet; the vault records the order and splits revenue, and the paid order becomes work for the team."}
        aside={<>
          <AutoRefresh active={list.some((o) => o.status === "paid" || o.status === "working")} />
          <StatusBadge status={simulated ? "simulated" : "vault"}>{simulated ? "SIMULATED rail" : `vault · ${health?.network}`}</StatusBadge>
        </>}
      />

      <details className="mt-6 rounded-lg border px-4 py-3" open={list.length === 0}>
        <summary className="cursor-pointer text-sm font-medium">Share checkout links</summary>
        <div className="mt-3">
          <CheckoutLinks offerings={biz?.profile.offerings ?? []} open={!biz?.profile.kill_switch} business={ws} />
        </div>
      </details>

      <nav className="mt-6 flex flex-wrap gap-2 text-xs" aria-label="Filter orders by status">
        {FILTERS.map((f) => (
          <Link key={f || "all"} href={f ? `/orders?status=${f}` : "/orders"}
            aria-current={(status ?? "") === f ? "page" : undefined}
            className={`rounded-full border px-3 py-1 ${(status ?? "") === f ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30"}`}>
            {f ? f.replace(/_/g, " ") : "all"}
          </Link>
        ))}
      </nav>

      {!orders.data ? (
        <p className="text-muted-foreground mt-6 text-sm">{orders.error}</p>
      ) : list.length === 0 ? (
        <div className="mt-6">
          <Empty what={status ? `No ${status.replace(/_/g, " ")} orders.` : "No orders yet."}
            why={status ? "Nothing is in this state right now." : "Share a checkout link (above) with a customer. Each offering has its own page at /buy/<id>; a paid order becomes work for the team on its own."}
            action={status ? <Link href="/orders" className="text-xs underline underline-offset-2">Show all orders</Link>
              : biz?.profile.offerings[0] ? <a href={withB(`/buy/${biz.profile.offerings[0].id}`, ws)} target="_blank" rel="noopener noreferrer" className="text-xs underline underline-offset-2">Open a checkout page</a> : undefined} />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-lg border">
          <table className="w-full min-w-[860px] text-sm">
            <thead>
              <tr className="text-muted-foreground border-b text-left font-mono text-[10px]">
                <th className="px-4 py-2.5 font-medium">Order</th>
                <th className="px-4 py-2.5 font-medium">Offering</th>
                <th className="px-4 py-2.5 font-medium">Inputs</th>
                <th className="px-4 py-2.5 text-right font-medium">Amount</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Paid</th>
                <th className="px-4 py-2.5 font-medium">Delivered</th>
                <th className="px-4 py-2.5 text-right font-medium"><span className="sr-only">Next step</span></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {list.map((o) => {
                const run = o.work_item_id ? runOf.get(o.work_item_id) : null;
                const dl = orderDelivery(o);
                const doc = (dl?.document_id ? docById.get(dl.document_id) : undefined) ?? docByOrder.get(o.id);
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
                      ) : o.status !== "awaiting_payment" && simulated ? <span className="text-warn ">simulated</span> : "-"}
                    </td>
                    <td className="px-4 py-2.5 text-xs">
                      {doc ? (
                        <div className="space-y-1">
                          <Link href={`/documents/${doc.id}`} className="block max-w-48 truncate underline underline-offset-2">{doc.title}</Link>
                          <a href={documentPdf(doc.id)} download className="text-muted-foreground hover:text-foreground font-mono text-[10px] underline underline-offset-2">download PDF</a>
                        </div>
                      ) : <span className="text-muted-foreground">-</span>}
                      {dl && <div className="mt-1"><DeliveryReceipt delivery={dl} network={health?.network} compact /></div>}
                      {o.status !== "awaiting_payment" && (
                        <a href={`/api/aera/orders/${o.id}/receipt.pdf`} download
                          className="text-muted-foreground hover:text-foreground mt-1 block font-mono text-[10px] underline underline-offset-2">receipt PDF</a>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {run ? (
                        <Link href={`/work/${run}`} className="text-xs whitespace-nowrap underline underline-offset-2">open the run</Link>
                      ) : o.status === "awaiting_payment" && simulated && mayManage(user) ? (
                        <MarkPaid id={o.id} />
                      ) : o.status === "awaiting_payment" ? (
                        <span className="text-muted-foreground text-[11px]">{simulated ? "an owner marks it paid" : "waiting for the customer's payment"}</span>
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
