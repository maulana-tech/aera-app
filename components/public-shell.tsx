import Link from "next/link";

import { AeraMark } from "@/components/aera-mark";
import { CanvasChip } from "@/components/dort";

/** The frame for pages a customer or the public sees: no navigation, no session. */
export function PublicShell({ business, simulated, children }: {
  business?: string | null;
  /** no vault: say so instead of promising one */
  simulated?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex h-16 shrink-0 items-center gap-3 px-4 text-white md:px-6">
        <AeraMark className="size-6 shrink-0" />
        <span className="truncate text-[17px] tracking-[-0.01em]">{business || "aera"}</span>
        <div className="ml-auto flex items-center gap-2">
          {simulated && <CanvasChip tone="warn" className="hidden sm:inline-flex">simulated payments</CanvasChip>}
          <Link href="/samples" className="rounded-md px-3 py-1.5 text-[13.5px] text-white/90 hover:bg-white/10 hover:text-white">
            Free samples
          </Link>
          <Link href="/ledger-public" className="rounded-md px-3 py-1.5 text-[13.5px] text-white/90 hover:bg-white/10 hover:text-white">
            Public ledger
          </Link>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-3 pb-6 md:px-6">
        <div className="bg-card-grad shadow-float rounded-xl border border-white/40 px-4 py-6 md:px-8 md:py-10">{children}</div>
      </main>
      <footer className="text-on-canvas-dim px-4 pb-6 text-center text-[12px] md:px-6">
        {simulated
          ? "Run by AERA agents on TEE-attested models. This business has no vault yet: payments here are SIMULATED and no money moves."
          : "Run by AERA agents on TEE-attested models. Money moves only through an on-chain vault with human-set limits."}
      </footer>
    </div>
  );
}
