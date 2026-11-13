import type { Metadata } from "next";

import { publicApi, type Ledger, type PublicOfferings } from "@/app/lib";
import { LedgerView } from "@/components/ledger-view";
import { PublicShell } from "@/components/public-shell";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Public ledger", description: "What this autonomous business earned, spent and decided." };

export default async function PublicLedger({ searchParams }: { searchParams: Promise<{ b?: string }> }) {
  const { b } = await searchParams;
  const [led, info] = await Promise.all([publicApi<Ledger>("ledger", b), publicApi<PublicOfferings>("offerings", b)]);
  return (
    <PublicShell business={info?.business} simulated={!info?.vault}>
      <h1 className="text-xl font-medium tracking-tight md:text-2xl">Public ledger</h1>
      <p className="text-muted-foreground mt-1.5 text-sm leading-relaxed">
        Every figure this business is run on, for anyone to check: money in and out, revenue split,
        model spend, and how many decisions its agents made alone against those a person made. Last 30 days, times in UTC.
      </p>
      <p className="text-muted-foreground mt-2 text-xs leading-relaxed">
        No customer data is shown: no names, emails, order inputs or deliverables. Entries paid through the vault link
        to their transaction on NearBlocks so anyone can check them; SIMULATED entries were recorded by AERA and
        never touched a chain.
      </p>
      {led ? <LedgerView led={led} network={info?.network ?? "testnet"} /> : (
        <p className="text-muted-foreground mt-6 text-sm">The ledger is not available right now.</p>
      )}
    </PublicShell>
  );
}
