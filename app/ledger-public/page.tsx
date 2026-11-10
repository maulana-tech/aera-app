import type { Metadata } from "next";

import { publicApi, type Ledger, type PublicOfferings } from "@/app/lib";
import { LedgerView } from "@/components/ledger-view";
import { PublicShell } from "@/components/public-shell";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Public ledger", description: "What this autonomous business earned, spent and decided." };

export default async function PublicLedger() {
  const [led, info] = await Promise.all([publicApi<Ledger>("ledger"), publicApi<PublicOfferings>("offerings")]);
  return (
    <PublicShell business={info?.business}>
      <h1 className="text-xl font-semibold tracking-tight md:text-2xl">Public ledger</h1>
      <p className="text-muted-foreground mt-1.5 text-sm leading-relaxed">
        Every figure this business is run on, for anyone to check: money in and out, revenue split,
        model spend, and how many decisions its agents made alone against those a person made. Last 30 days.
      </p>
      {led ? <LedgerView led={led} network={info?.network ?? "testnet"} /> : (
        <p className="text-muted-foreground mt-6 text-sm">The ledger is not available right now.</p>
      )}
    </PublicShell>
  );
}
