"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function Putusan({ aksiId }: { aksiId: string }) {
  const r = useRouter();
  const [sibuk, setSibuk] = useState<string | null>(null);
  const [galat, setGalat] = useState("");

  async function kirim(putusan: "disetujui" | "ditolak" | "dinaikkan") {
    setSibuk(putusan);
    setGalat("");
    try {
      const res = await fetch(`/api/sigap/aksi/${aksiId}/putusan`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        // TODO: ganti dengan identitas dari sesi login begitu auth dipasang
        body: JSON.stringify({ oleh: "planner", peran: "buyer", putusan }),
      });
      if (!res.ok) throw new Error((await res.json()).galat ?? "gagal");
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
        <button onClick={() => kirim("disetujui")} disabled={!!sibuk}
          className="rounded-full bg-foreground px-4 py-1.5 text-sm font-medium text-background disabled:opacity-50">
          {sibuk === "disetujui" ? "Mengirim…" : "Setujui"}
        </button>
        <button onClick={() => kirim("dinaikkan")} disabled={!!sibuk}
          className="rounded-full border border-line px-4 py-1.5 text-sm disabled:opacity-50">
          Naikkan
        </button>
        <button onClick={() => kirim("ditolak")} disabled={!!sibuk}
          className="rounded-full border border-line px-4 py-1.5 text-sm text-rose-300 disabled:opacity-50">
          Tolak
        </button>
      </div>
      {galat && <p className="mt-2 font-mono text-xs text-rose-300">{galat}</p>}
    </div>
  );
}
