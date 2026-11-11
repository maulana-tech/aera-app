import Link from "next/link";

import { Button } from "@/components/ui/button";

/** A run, document, agent or page that does not exist (or no longer does). */
export default function NotFound() {
  return (
    <main className="w-full px-4 py-12 md:px-6 md:py-16">
      <h1 className="text-xl font-semibold tracking-tight">Not found</h1>
      <p className="text-muted-foreground mt-2 max-w-xl text-sm leading-relaxed">
        There is nothing at this address. The link may be old, or the record was made on another AERA service.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button asChild size="sm" variant="outline"><Link href="/dashboard">Dashboard</Link></Button>
        <Button asChild size="sm" variant="ghost"><Link href="/work">Work</Link></Button>
      </div>
    </main>
  );
}
