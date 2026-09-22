"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";

export function DeleteUpload({ id }: { id: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-7 shrink-0"
      disabled={busy}
      aria-label="Delete upload"
      onClick={async () => {
        setBusy(true);
        await fetch(`/api/sigap/uploads/${id}/delete`, { method: "POST" });
        router.refresh();
        setBusy(false);
      }}
    >
      <Trash2 className="size-3.5" />
    </Button>
  );
}
