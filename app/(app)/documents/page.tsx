import Link from "next/link";

import { apiResult } from "@/app/lib";
import type { DocumentRow } from "@/app/lib";
import { DocumentList } from "@/components/documents";
import { Empty, PageHeader } from "@/components/shell";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

export default async function DocumentsPage({ searchParams }: { searchParams: Promise<{ order?: string }> }) {
  const { order } = await searchParams;
  const res = await apiResult<{ documents: DocumentRow[] }>(`documents${order ? `?order_id=${encodeURIComponent(order)}` : ""}`);
  const docs = res.data?.documents ?? [];

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Documents"
        lead="What the team wrote: deliverables for paid orders and drafts for requests. Open one to read it, or download the PDF exactly as the customer receives it."
        aside={order ? <Button asChild size="sm" variant="ghost"><Link href="/documents">All documents</Link></Button> : undefined}
      />
      {order && <p className="text-muted-foreground mt-4 text-xs">Only documents for order <span className="font-mono">{order}</span>.</p>}
      <div className="mt-6">
        {!res.data ? (
          <p className="text-muted-foreground text-sm">{res.error}</p>
        ) : (
          <DocumentList docs={docs} empty={
            <Empty what={order ? "No document for this order yet." : "The team has not written a document yet."}
              why="A document is saved when an agent writes one: a deliverable for a paid order, or a draft you asked for."
              action={<Button asChild size="sm" variant="outline"><Link href="/work">Give the team a request</Link></Button>} />
          } />
        )}
      </div>
    </main>
  );
}
