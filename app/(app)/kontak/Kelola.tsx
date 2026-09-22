"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Kontak } from "@/app/lib";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const PERAN = ["planner", "buyer", "procurement_lead", "qa", "oem"];
const JENIS = ["port_closure", "quality_hold", "customs_hold", "demand_spike", "supplier_failure"];

export function TambahKontak() {
  const r = useRouter();
  const [nama, setNama] = useState("");
  const [email, setEmail] = useState("");
  const [peran, setPeran] = useState(PERAN[0]);
  const [untuk, setUntuk] = useState<string[]>([]);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState("");

  async function kirim(e: React.FormEvent) {
    e.preventDefault();
    setSibuk(true);
    setGalat("");
    try {
      const res = await fetch("/api/sigap/kontak", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ nama, email, peran, untuk: untuk.join(",") || "*" }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.galat ?? "gagal");
      setNama(""); setEmail(""); setUntuk([]);
      r.refresh();
    } catch (err) {
      setGalat(err instanceof Error ? err.message : "gagal");
    } finally {
      setSibuk(false);
    }
  }

  return (
    <form onSubmit={kirim} className="space-y-4 rounded-xl border p-5">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">Nama</span>
          <Input value={nama} onChange={(e) => setNama(e.target.value)} required className="mt-1.5" />
        </label>
        <label className="block">
          <span className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">Email</span>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="mt-1.5" />
        </label>
      </div>

      <div>
        <span className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">Peran</span>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {PERAN.map((p) => (
            <button
              key={p} type="button" onClick={() => setPeran(p)}
              className={`rounded-full border px-3 py-1 font-mono text-[11px] transition-colors ${
                peran === p ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div>
        <span className="text-muted-foreground font-mono text-[10px] uppercase tracking-wider">
          Diberi tahu saat
        </span>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {JENIS.map((j) => {
            const on = untuk.includes(j);
            return (
              <button
                key={j} type="button"
                onClick={() => setUntuk((u) => (on ? u.filter((x) => x !== j) : [...u, j]))}
                className={`rounded-full border px-3 py-1 font-mono text-[11px] transition-colors ${
                  on ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30"
                }`}
              >
                {j}
              </button>
            );
          })}
        </div>
        <p className="text-muted-foreground mt-1.5 text-xs">
          Tidak ada yang dipilih berarti diberi tahu untuk semua jenis gangguan.
        </p>
      </div>

      {galat && <p className="text-destructive text-xs">{galat}</p>}
      <Button type="submit" size="sm" disabled={sibuk}>
        {sibuk ? "Menyimpan…" : "Tambah kontak"}
      </Button>
    </form>
  );
}

export function HapusKontak({ id }: { id: string }) {
  const r = useRouter();
  const [sibuk, setSibuk] = useState(false);
  return (
    <Button
      variant="ghost" size="icon" className="size-7 shrink-0" disabled={sibuk}
      aria-label="Hapus kontak"
      onClick={async () => {
        setSibuk(true);
        await fetch(`/api/sigap/kontak/${id}/hapus`, { method: "POST" });
        r.refresh();
        setSibuk(false);
      }}
    >
      <Trash2 className="size-3.5" />
    </Button>
  );
}

export function DaftarKontak({ kontak, bisaHapus }: { kontak: Kontak[]; bisaHapus: boolean }) {
  if (!kontak.length) {
    return (
      <p className="text-muted-foreground mt-3 rounded-xl border border-dashed p-5 text-sm">
        Belum ada kontak. Tanpa ini, rekomendasi agent tidak sampai ke siapa pun.
      </p>
    );
  }
  return (
    <ul className="mt-3 divide-y rounded-xl border">
      {kontak.map((k) => (
        <li key={k.id} className="flex items-start gap-3 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm">{k.nama}</p>
            <p className="text-muted-foreground mt-0.5 truncate font-mono text-[11px]">
              {k.email} · {k.peran}
            </p>
            <p className="text-muted-foreground mt-0.5 font-mono text-[10px]">
              {k.untuk === "*" ? "semua jenis gangguan" : k.untuk.split(",").join(" · ")}
            </p>
          </div>
          {bisaHapus && <HapusKontak id={k.id} />}
        </li>
      ))}
    </ul>
  );
}
