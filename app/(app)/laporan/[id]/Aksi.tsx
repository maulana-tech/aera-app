"use client";

import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

export function AksiLaporan({ markdown, judul }: { markdown: string; judul: string }) {
  const [disalin, setDisalin] = useState(false);

  async function salin() {
    await navigator.clipboard.writeText(markdown);
    setDisalin(true);
    setTimeout(() => setDisalin(false), 2000);
  }

  function unduh() {
    const nama = judul.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([markdown], { type: "text/markdown" }));
    a.download = `${nama || "laporan"}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={salin}>
        {disalin ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        {disalin ? "Tersalin" : "Salin"}
      </Button>
      <Button variant="outline" size="sm" onClick={unduh}>
        <Download className="size-3.5" />
        Unduh
      </Button>
    </div>
  );
}
