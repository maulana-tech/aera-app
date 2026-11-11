import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { publicApi, usd, type PublicOfferings } from "@/app/lib";
import { PublicShell } from "@/components/public-shell";
import { Checkout } from "./Checkout";

export const dynamic = "force-dynamic";

const DELIVERED_AS: Record<string, string> = {
  pdf: "a PDF document, sent to your email",
  xlsx: "a spreadsheet, sent to your email",
  message: "a written reply, sent to your email",
  file: "a file, sent to your email",
  service: "a service, done for you",
};

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
  const simulated = !info.vault;

  return (
    <PublicShell business={info.business} simulated={simulated}>
      <p className="text-muted-foreground text-xs">{info.business}</p>
      <h1 className="mt-1 text-xl font-semibold tracking-tight md:text-2xl">{o.title}</h1>
      {o.description && <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{o.description}</p>}

      <dl className="mt-5 grid gap-x-6 gap-y-3 rounded-lg border p-4 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground text-xs">Price</dt>
          <dd className="mt-0.5 font-mono text-lg font-semibold tabular-nums">{usd(o.price_usd)}</dd>
          <dd className="text-muted-foreground text-[11px]">{simulated ? "simulated: no money moves" : "in USDC, one payment"}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">What you get</dt>
          <dd className="mt-0.5">{DELIVERED_AS[o.delivery] ?? o.delivery}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">When</dt>
          <dd className="mt-0.5">within {o.sla_hours} hours of payment</dd>
        </div>
      </dl>

      {simulated ? (
        <p className="mt-4 rounded-lg border border-amber-500/50 bg-amber-500/10 px-4 py-2.5 text-xs leading-relaxed text-amber-900 dark:text-amber-200">
          SIMULATED checkout. This business has not connected a vault yet, so you will not be asked to pay and
          no money moves. The owner confirms the order by hand, and then the team starts on it.
        </p>
      ) : (
        <p className="text-muted-foreground mt-4 text-xs leading-relaxed">
          You pay from your own NEAR wallet to the business&apos;s vault contract{" "}
          <span className="font-mono">{info.vault}</span> ({info.network}). The vault records the order on chain;
          nobody can take the money out past the limits its owner set.
        </p>
      )}

      <section className="mt-8">
        <h2 className="text-sm font-medium">Your order</h2>
        <div className="mt-3">
          <Checkout offering={o} network={info.network} open={info.open} />
        </div>
      </section>

      <section className="mt-10 border-t pt-6">
        <h2 className="text-sm font-medium">What happens after you order</h2>
        <ol className="text-muted-foreground mt-3 space-y-2 text-sm leading-relaxed">
          <li><span className="text-foreground font-mono text-xs">1</span> &nbsp;{simulated ? "The owner marks the order paid." : "You pay in your wallet; the vault confirms it."}</li>
          <li><span className="text-foreground font-mono text-xs">2</span> &nbsp;The business&apos;s agent team starts on it. This page shows the status as it changes.</li>
          <li><span className="text-foreground font-mono text-xs">3</span> &nbsp;The team checks the result, and it is delivered{o.delivery === "service" ? "" : " to your email"}.
            {!simulated && " A fingerprint (sha256) of what you receive is written to the vault as a receipt."}</li>
        </ol>
      </section>

      {others.length > 0 && (
        <div className="mt-10 border-t pt-6">
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
