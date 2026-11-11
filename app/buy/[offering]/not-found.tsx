import Link from "next/link";
import { Suspense } from "react";

import { publicApi, usd, type PublicOfferings } from "@/app/lib";
import { PublicShell } from "@/components/public-shell";

/** An offering id that is not on sale: say so, and show what is. The page
 *  itself is synchronous so the 404 renders on the server; what is on sale
 *  streams in after it. */
export default function OfferingNotFound() {
  return (
    <PublicShell>
      <h1 className="text-xl font-semibold tracking-tight">This offering is not on sale</h1>
      <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
        The link may be old, or the business may have changed what it sells. Nothing was ordered and nothing was charged.
      </p>
      <Suspense fallback={null}><OnSale /></Suspense>
    </PublicShell>
  );
}

async function OnSale() {
  const info = await publicApi<PublicOfferings>("offerings");
  const offerings = info?.offerings ?? [];
  return (
    <>
      {offerings.length > 0 ? (
        <div className="mt-6">
          <p className="text-muted-foreground mb-2 text-xs">On sale{info?.business ? ` from ${info.business}` : ""}</p>
          <ul className="divide-y rounded-lg border">
            {offerings.map((o) => (
              <li key={o.id}>
                <Link href={`/buy/${o.id}`} className="hover:bg-muted/40 flex items-center justify-between gap-3 px-4 py-3">
                  <span className="text-sm font-medium">{o.title}</span>
                  <span className="font-mono text-xs tabular-nums">{usd(o.price_usd)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-muted-foreground mt-6 text-sm">Nothing is on sale right now.</p>
      )}
    </>
  );
}
