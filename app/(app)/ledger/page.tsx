import Link from "next/link";

import { api, apiResult, type Health, type Ledger } from "@/app/lib";
import { LedgerView } from "@/components/ledger-view";
import { PageHeader } from "@/components/shell";

export const dynamic = "force-dynamic";

export default async function LedgerPage({ searchParams }: { searchParams: Promise<{ days?: string }> }) {
  const days = Math.max(1, Math.min(365, Number((await searchParams).days) || 30));
  const [led, health] = await Promise.all([apiResult<Ledger>(`ledger?days=${days}`), api<Health>("health")]);

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Ledger"
        lead="The business's public figures: what came in, what went out, how revenue was split, what the models cost, and how many decisions the team made on its own against those a person made. No customer data."
        aside={<Link href="/ledger-public" className="text-muted-foreground hover:text-foreground text-xs underline underline-offset-2">public page</Link>}
      />
      <nav className="mt-4 flex flex-wrap gap-2 text-xs">
        {[7, 30, 90, 365].map((d) => (
          <Link key={d} href={`/ledger?days=${d}`}
            className={`rounded-full border px-3 py-1 ${d === days ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30"}`}>
            {d} days
          </Link>
        ))}
      </nav>
      {led.data ? <LedgerView led={led.data} network={health?.network ?? "testnet"} /> : <p className="text-muted-foreground mt-6 text-sm">{led.error}</p>}
    </main>
  );
}
