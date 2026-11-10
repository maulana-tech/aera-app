import Link from "next/link";

import { AeraMark } from "@/components/aera-mark";
import { ThemeToggle } from "@/components/theme";

/** The frame for pages a customer or the public sees: no sidebar, no session. */
export function PublicShell({ business, children }: { business?: string | null; children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b px-4 md:px-6">
        <AeraMark className="size-6 shrink-0" />
        <span className="truncate text-sm font-semibold">{business || "AERA"}</span>
        <div className="ml-auto flex items-center gap-3">
          <Link href="/ledger-public" className="text-muted-foreground hover:text-foreground text-xs">Public ledger</Link>
          <ThemeToggle />
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6 md:px-6 md:py-10">{children}</main>
      <footer className="text-muted-foreground border-t px-4 py-4 text-center text-[11px] md:px-6">
        Run by AERA agents on TEE-attested models. Money moves only through an on-chain vault with human-set limits.
      </footer>
    </div>
  );
}
