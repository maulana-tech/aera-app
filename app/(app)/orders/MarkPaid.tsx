"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { errorText, post } from "@/lib/post";

/** Demo only, with no vault: mark an order paid on the SIMULATED rail. The
 *  ledger and the order carry the label wherever they are shown. */
export function MarkPaid({ id }: { id: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <span className="inline-flex flex-col items-end gap-1">
      <Button size="xs" variant="outline" disabled={busy} onClick={async () => {
        setBusy(true);
        setError(null);
        try {
          await post(`orders/${id}/simulate-paid`);
          router.refresh();
        } catch (e) {
          setError(errorText(e));
        } finally {
          setBusy(false);
        }
      }}>
        {busy && <Loader2 className="animate-spin" />}
        Mark paid (simulated)
      </Button>
      {error && <span className="text-[11px] text-bad ">{error}</span>}
    </span>
  );
}
