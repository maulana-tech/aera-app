import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { publicApi, usd, type PublicOfferings } from "@/app/lib";
import { PublicShell } from "@/components/public-shell";
import { Checkout } from "./Checkout";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ offering: string }> }): Promise<Metadata> {
  const { offering } = await params;
  const info = await publicApi<PublicOfferings>("offerings");
  const o = info?.offerings.find((x) => x.id === offering);
  return { title: o ? `${o.title} · ${info?.business}` : "Checkout", description: o?.description };
}

export default async function BuyPage({ params }: { params: Promise<{ offering: string }> }) {
  const { offering } = await params;
  const info = await publicApi<PublicOfferings>("offerings");
  if (!info) {
    return (
      <PublicShell>
        <h1 className="text-xl font-semibold">Checkout is not available</h1>
        <p className="text-muted-foreground mt-2 text-sm">The business could not be reached. Try again in a moment.</p>
      </PublicShell>
    );
  }
  const o = info.offerings.find((x) => x.id === offering);
  if (!o) notFound();
  const others = info.offerings.filter((x) => x.id !== o.id);

  return (
    <PublicShell business={info.business}>
      <p className="text-muted-foreground text-xs">{info.business}</p>
      <h1 className="mt-1 text-xl font-semibold tracking-tight md:text-2xl">{o.title}</h1>
      {o.description && <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{o.description}</p>}
      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs">
        <span className="text-base font-semibold">{usd(o.price_usd)}</span>
        <span className="text-muted-foreground self-end">delivered as {o.delivery}</span>
        <span className="text-muted-foreground self-end">within {o.sla_hours}h</span>
        <span className="text-muted-foreground self-end">{info.vault ? `paid to vault ${info.vault} (${info.network})` : "simulated payment"}</span>
      </div>

      <div className="mt-8">
        <Checkout offering={o} network={info.network} open={info.open} />
      </div>

      {others.length > 0 && (
        <div className="mt-12 border-t pt-6">
          <p className="text-muted-foreground mb-2 text-xs">Also from {info.business}</p>
          <ul className="space-y-1">
            {others.map((x) => (
              <li key={x.id}><Link href={`/buy/${x.id}`} className="text-sm underline underline-offset-2">{x.title}</Link> <span className="text-muted-foreground font-mono text-xs">{usd(x.price_usd)}</span></li>
            ))}
          </ul>
        </div>
      )}
    </PublicShell>
  );
}
