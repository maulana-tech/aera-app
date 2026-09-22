"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

type Putusan = "disetujui" | "ditolak" | "dinaikkan";

export default function Putusan({ aksiId, nilaiIdr, batasIdr }: {
  aksiId: string; nilaiIdr: number; batasIdr: number;
}) {
  const r = useRouter();
  const [sibuk, setSibuk] = useState<Putusan | null>(null);
  const [galat, setGalat] = useState("");
  const diluarWewenang = batasIdr <= 0 || nilaiIdr > batasIdr;

  async function kirim(putusan: Putusan) {
    setSibuk(putusan);
    setGalat("");
    try {
      // Identitas TIDAK dikirim dari sini — server mengambilnya dari token sesi.
      const res = await fetch(`/api/sigap/aksi/${aksiId}/putusan`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ putusan }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.galat ?? "gagal");
      r.refresh();
    } catch (e) {
      setGalat(e instanceof Error ? e.message : "gagal");
    } finally {
      setSibuk(null);
    }
  }

  return (
    <div className="mt-3">
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={!!sibuk || diluarWewenang}
          onClick={() => kirim("disetujui")}
        >
          {sibuk === "disetujui" ? "Mengirim…" : "Setujui"}
        </Button>
        <Button
          variant="outline" size="sm" disabled={!!sibuk}
          onClick={() => kirim("dinaikkan")}
        >
          Naikkan
        </Button>
        <Button
          variant="ghost" size="sm" className="text-destructive" disabled={!!sibuk}
          onClick={() => kirim("ditolak")}
        >
          Tolak
        </Button>
      </div>
      {diluarWewenang && (
        <p className="text-muted-foreground mt-2 text-[11px] leading-relaxed">
          Di luar wewenangmu{batasIdr > 0 && ` (batas Rp ${batasIdr.toLocaleString("id-ID")})`}.
          Gunakan Naikkan.
        </p>
      )}
      {galat && <p className="mt-2 font-mono text-xs text-rose-700 dark:text-rose-400">{galat}</p>}
    </div>
  );
}
