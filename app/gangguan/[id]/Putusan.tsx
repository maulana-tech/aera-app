"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/app/ui/Twenty";

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
          variant="solid" color="accent" size="sm"
          loading={sibuk === "disetujui"}
          disabled={!!sibuk || diluarWewenang}
          onClick={() => kirim("disetujui")}
        >
          Setujui
        </Button>
        <Button
          variant="outline" color="neutral" size="sm"
          loading={sibuk === "dinaikkan"} disabled={!!sibuk}
          onClick={() => kirim("dinaikkan")}
        >
          Naikkan
        </Button>
        <Button
          variant="ghost" color="danger" size="sm"
          loading={sibuk === "ditolak"} disabled={!!sibuk}
          onClick={() => kirim("ditolak")}
        >
          Tolak
        </Button>
      </div>
      {diluarWewenang && (
        <p className="mt-2 text-[11px] leading-relaxed text-amber-300">
          Di luar wewenangmu{batasIdr > 0 && ` (batas Rp ${batasIdr.toLocaleString("id-ID")})`}.
          Gunakan Naikkan.
        </p>
      )}
      {galat && <p className="mt-2 font-mono text-xs text-rose-300">{galat}</p>}
    </div>
  );
}
