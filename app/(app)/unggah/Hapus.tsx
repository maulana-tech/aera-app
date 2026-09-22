"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";

export function HapusUnggahan({ id }: { id: string }) {
  const r = useRouter();
  const [sibuk, setSibuk] = useState(false);
  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-7 shrink-0"
      disabled={sibuk}
      aria-label="Hapus unggahan"
      onClick={async () => {
        setSibuk(true);
        await fetch(`/api/sigap/unggahan/${id}/hapus`, { method: "POST" });
        r.refresh();
        setSibuk(false);
      }}
    >
      <Trash2 className="size-3.5" />
    </Button>
  );
}
