"use client";

import { CornerDownLeft, Loader2, Wrench } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { AsalBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

type Balasan = {
  jawab: string;
  alat_dipakai: string[];
  papan: Record<string, { asal: string; sumber: string }>;
  tidak_tepercaya: string[];
  biaya_idr: number;
};
type Pesan =
  | { dari: "orang"; teks: string }
  | { dari: "agent"; balasan: Balasan }
  | { dari: "galat"; teks: string; petunjuk?: string };

export default function Percakapan({
  kode, nama, contoh, masuk,
}: { kode: string; nama: string; contoh: string[]; masuk: boolean }) {
  const [pesan, setPesan] = useState<Pesan[]>([]);
  const [teks, setTeks] = useState("");
  const [sibuk, setSibuk] = useState(false);
  const bawah = useRef<HTMLDivElement>(null);
  const kolom = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bawah.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [pesan, sibuk]);

  async function kirim(isi: string) {
    const t = isi.trim();
    if (!t || sibuk) return;
    setPesan((p) => [...p, { dari: "orang", teks: t }]);
    setTeks("");
    setSibuk(true);
    try {
      const r = await fetch(`/api/sigap/agent/${kode}/tanya`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ tanya: t }),
      });
      const d = await r.json();
      setPesan((p) => [
        ...p,
        r.ok
          ? { dari: "agent", balasan: d as Balasan }
          : { dari: "galat", teks: d.galat ?? "gagal", petunjuk: d.petunjuk },
      ]);
    } catch {
      setPesan((p) => [...p, { dari: "galat", teks: "layanan agent tidak merespons" }]);
    } finally {
      setSibuk(false);
      kolom.current?.focus();
    }
  }

  return (
    <div className="flex h-[calc(100vh-13rem)] flex-col rounded-xl border">
      <div className="flex-1 space-y-4 overflow-y-auto p-5">
        {pesan.length === 0 && (
          <div className="text-muted-foreground space-y-3 text-sm">
            <p>Tanya {nama} langsung. Dia memakai alat yang sama seperti saat bekerja dalam tim.</p>
            <div className="flex flex-wrap gap-2">
              {contoh.map((c) => (
                <button
                  key={c}
                  onClick={() => kirim(c)}
                  disabled={!masuk}
                  className="hover:border-foreground/30 hover:text-foreground rounded-full border px-3 py-1.5 text-left text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        )}

        {pesan.map((m, i) =>
          m.dari === "orang" ? (
            <div key={i} className="flex justify-end">
              <p className="bg-primary text-primary-foreground max-w-[80%] rounded-2xl rounded-br-sm px-4 py-2 text-sm">
                {m.teks}
              </p>
            </div>
          ) : m.dari === "galat" ? (
            <div key={i} className="max-w-[85%] rounded-2xl rounded-bl-sm border p-4">
              <p className="text-destructive text-sm">{m.teks}</p>
              {m.petunjuk && (
                <p className="text-muted-foreground mt-2 text-xs leading-relaxed">{m.petunjuk}</p>
              )}
            </div>
          ) : (
            <div key={i} className="max-w-[85%] space-y-2">
              <div className="bg-muted/50 rounded-2xl rounded-bl-sm border p-4">
                <p className="whitespace-pre-line text-sm leading-relaxed">{m.balasan.jawab}</p>
              </div>
              {m.balasan.alat_dipakai.length > 0 && (
                <p className="text-muted-foreground flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
                  <Wrench className="size-3" />
                  {m.balasan.alat_dipakai.join(" · ")}
                </p>
              )}
              {Object.keys(m.balasan.papan).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(m.balasan.papan).map(([k, v]) => (
                    <AsalBadge key={k} asal={v.asal} sumber={v.sumber} />
                  ))}
                </div>
              )}
            </div>
          ),
        )}

        {sibuk && (
          <p className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="size-3.5 animate-spin" />
            {nama} sedang bekerja…
          </p>
        )}
        <div ref={bawah} />
      </div>

      {!masuk ? (
        <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
          <p className="text-muted-foreground text-sm">
            Masuk dulu untuk bertanya. Percakapan tercatat atas nama akunmu.
          </p>
          <Button asChild size="sm" variant="outline">
            <Link href="/masuk">Masuk</Link>
          </Button>
        </div>
      ) : (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          kirim(teks);
        }}
        className="flex items-end gap-2 border-t p-3"
      >
        <textarea
          ref={kolom}
          rows={1}
          value={teks}
          onChange={(e) => setTeks(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              kirim(teks);
            }
          }}
          placeholder={`Tanya ${nama}…`}
          className="max-h-32 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
        />
        <Button type="submit" size="sm" disabled={sibuk || !teks.trim()}>
          <CornerDownLeft className="size-3.5" />
          Kirim
        </Button>
      </form>
      )}
    </div>
  );
}
