import { ArrowLeft, Download } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import {
  api, apiResult, documentPdf, orderDelivery, when, type DocumentFull, type Health, type Order, type WorkItem,
} from "@/app/lib";
import { DeliveryReceipt } from "@/components/documents";
import { Markdown } from "@/components/markdown";
import { Fact, Rail } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

export default async function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await apiResult<DocumentFull>(`documents/${id}`);
  if (!res.data) {
    if (res.error?.includes("no such document")) notFound();
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-medium">This document could not be read</h1>
        <p className="text-muted-foreground mt-2 text-sm">{res.error}</p>
      </main>
    );
  }
  const d = res.data;
  const [orders, work, health] = await Promise.all([
    d.order_id ? api<{ orders: Order[] }>("orders") : Promise.resolve(null),
    d.order_id ? api<{ items: WorkItem[] }>("work") : Promise.resolve(null),
    api<Health>("health"),
  ]);
  const order = orders?.orders.find((o) => o.id === d.order_id) ?? null;
  const delivery = order ? orderDelivery(order) : null;
  const delivered = delivery?.document_id === d.id ? delivery : null;
  const run = order?.work_item_id ? work?.items.find((w) => w.id === order.work_item_id)?.run_id : null;

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <Link href="/documents" className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs">
        <ArrowLeft className="size-3" />
        Documents
      </Link>
      <header className="mt-3 flex flex-wrap items-start justify-between gap-3 border-b pb-4 md:mt-5 md:pb-6">
        <div className="min-w-0">
          <h1 className="text-xl font-medium tracking-tight md:text-2xl">{d.title}</h1>
          <p className="text-muted-foreground mt-1 font-mono text-[11px]">
            {d.format ?? "draft"} · written by {d.uploaded_by.replace(/^agent:/, "")} · {when(d.uploaded_at)}
          </p>
        </div>
        <Button asChild size="sm">
          <a href={documentPdf(d.id)} download><Download /> Download PDF</a>
        </Button>
      </header>

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <article className="min-w-0 rounded-lg border p-4 md:p-6">
          <Markdown>{d.markdown}</Markdown>
        </article>
        <aside className="space-y-4">
          <Rail title="Fingerprint">
            <div className="px-4 py-3">
              <p className="text-muted-foreground text-xs">sha256 of the PDF</p>
              <p className="mt-1 font-mono text-[10px] break-all">{d.pdf_sha256}</p>
              <p className="text-muted-foreground mt-2 text-[11px] leading-relaxed">
                The fingerprint of the PDF as rendered now. When an order is delivered, the hash of the copy sent
                is kept on the order and, on the vault rail, written to the vault as the receipt.
              </p>
            </div>
          </Rail>
          {order && (
            <Rail title="Order">
              <Fact label="Order" value={order.id} />
              <Fact label="Status" value={<StatusBadge status={order.status} />} mono={false} />
              {run && <Fact label="Run" value={<Link href={`/work/${run}`} className="underline underline-offset-2">open the run</Link>} mono={false} />}
              <Fact label="All orders" value={<Link href="/orders" className="underline underline-offset-2">Orders</Link>} mono={false} />
            </Rail>
          )}
          {delivered && (
            <div>
              <p className="text-muted-foreground mb-1.5 text-xs font-medium">Delivered</p>
              <DeliveryReceipt delivery={delivered} network={health?.network} />
              {delivered.hash && (delivered.hash === d.pdf_sha256 ? (
                <p className="mt-2 text-[11px] text-ok ">
                  This PDF&apos;s sha256 matches the delivered hash on record: the download is byte-for-byte what the customer received.
                </p>
              ) : (
                <p className="mt-2 text-[11px] text-warn ">
                  This PDF&apos;s sha256 does not match the delivered hash on record (it was delivered before PDFs were made
                  reproducible). The delivered hash above is the one on record.
                </p>
              ))}
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}
