import { Download, ExternalLink, FileText } from "lucide-react";
import Link from "next/link";

import { documentPdf, explorer, when, type DocumentRow, type OrderDelivery } from "@/app/lib";
import { Button } from "@/components/ui/button";

/** One document the team wrote, with the PDF a customer receives. */
export function DocumentList({ docs, empty }: { docs: DocumentRow[]; empty?: React.ReactNode }) {
  if (!docs.length) return <>{empty ?? <p className="text-muted-foreground text-sm">No documents.</p>}</>;
  return (
    <ul className="divide-y rounded-lg border">
      {docs.map((d) => (
        <li key={d.id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-3">
          <FileText className="text-muted-foreground size-4 shrink-0" aria-hidden />
          <div className="min-w-0 flex-1 basis-48">
            <Link href={`/documents/${d.id}`} className="block truncate text-sm font-medium underline-offset-2 hover:underline">
              {d.title}
            </Link>
            <p className="text-muted-foreground font-mono text-[10px]">
              {d.format ?? "draft"}
              {d.order_id && <> · order {d.order_id}</>}
              {" · "}{d.uploaded_by.replace(/^agent:/, "")} · {when(d.uploaded_at)}
            </p>
          </div>
          <Button asChild size="xs" variant="outline">
            <a href={documentPdf(d.id)} download aria-label={`Download ${d.title} as PDF`}>
              <Download /> PDF
            </a>
          </Button>
        </li>
      ))}
    </ul>
  );
}

/** The proof of delivery: the PDF's sha256 and, on the vault rail, the
 *  deliver_receipt transaction that wrote that same hash on chain. */
export function DeliveryReceipt({ delivery, network, compact }: {
  delivery: OrderDelivery; network: string | null | undefined; compact?: boolean;
}) {
  const tx = delivery.tx_hash;
  return (
    <div className={compact ? "space-y-0.5" : "space-y-1.5 rounded-lg border p-3"}>
      {delivery.hash && (
        <p className="font-mono text-[10px] break-all" title={delivery.hash}>
          <span className="text-muted-foreground">sha256 </span>
          {compact ? `${delivery.hash.slice(0, 16)}…` : delivery.hash}
        </p>
      )}
      {tx ? (
        <p className="font-mono text-[10px]">
          <span className="text-muted-foreground">receipt </span>
          <a href={delivery.explorer || explorer(network, "txns", tx)} target="_blank" rel="noopener noreferrer"
             className="inline-flex items-center gap-1 underline underline-offset-2">
            {tx.slice(0, 10)}… <ExternalLink className="size-3" aria-hidden />
          </a>
          {!compact && <span className="text-muted-foreground"> · this hash is what the vault recorded</span>}
        </p>
      ) : delivery.hash ? (
        <p className="text-muted-foreground text-[10px]">
          {compact ? "no on-chain receipt (simulated)" : "No on-chain receipt: delivered on the SIMULATED rail, so the hash is AERA's own record."}
        </p>
      ) : null}
      {delivery.sent_to && <p className="text-muted-foreground text-[10px]">sent to {delivery.sent_to}</p>}
    </div>
  );
}
