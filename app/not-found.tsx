import Link from "next/link";

import { PublicShell } from "@/components/public-shell";

export default function NotFound() {
  return (
    <PublicShell>
      <h1 className="text-xl font-semibold tracking-tight">Page not found</h1>
      <p className="text-muted-foreground mt-2 text-sm leading-relaxed">There is nothing at this address.</p>
      <p className="mt-4 text-sm"><Link href="/" className="underline underline-offset-2">Go to AERA</Link></p>
    </PublicShell>
  );
}
