"use client";

import { Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";

const ENTITAS = [
  { v: "MaterialStock", l: "Stok material", kolom: "Material, Plant, MatlWrhsStkQtyInMatlBaseUnit, BaseUnit, DailyConsumption, Description" },
  { v: "PurchaseOrder", l: "Pesanan pembelian", kolom: "PurchaseOrder, Material, Plant, OrderQuantity, Supplier, LoadingPort, DeliveryDate, RevisedDeliveryDate, Status" },
  { v: "SalesOrder", l: "Pesanan pelanggan", kolom: "SalesOrder, Material, Customer, NetAmount, RequestedDeliveryDate" },
  { v: "BillOfMaterial", l: "Struktur produk", kolom: "Material, FinishedGood, Description, ComponentQuantity" },
  { v: "AlternateSource", l: "Sumber pasokan", kolom: "id, label, Supplier, Material, Quantity, ArrivalDate, ExtraCostIDR, TkdnAfterPct, Origin, NewOrigin" },
];

export default function Unggah({ masuk }: { masuk: boolean }) {
  const r = useRouter();
  const [entitas, setEntitas] = useState(ENTITAS[0].v);
  const [berkas, setBerkas] = useState("");
  const [isi, setIsi] = useState("");
  const [sibuk, setSibuk] = useState(false);
  const [pesan, setPesan] = useState<{ ok: boolean; teks: string } | null>(null);

  const pilih = ENTITAS.find((e) => e.v === entitas)!;

  async function baca(f: File) {
    setBerkas(f.name);
    setIsi(await f.text());
    setPesan(null);
  }

  async function kirim() {
    setSibuk(true);
    setPesan(null);
    try {
      const res = await fetch("/api/sigap/unggahan", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ entitas, berkas: berkas || "tempel.csv", csv: isi }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.galat ?? "gagal");
      setPesan({ ok: true, teks: `${d.baris} baris tersimpan sebagai ${d.entitas}` });
      setIsi("");
      setBerkas("");
      r.refresh();
    } catch (e) {
      setPesan({ ok: false, teks: e instanceof Error ? e.message : "gagal" });
    } finally {
      setSibuk(false);
    }
  }

  if (!masuk) {
    return (
      <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
        Masuk dulu untuk mengunggah. Unggahan tercatat atas nama akunmu.
      </p>
    );
  }

  return (
    <div className="space-y-4 rounded-xl border p-5">
      <div className="flex flex-wrap gap-2">
        {ENTITAS.map((e) => (
          <button
            key={e.v}
            onClick={() => setEntitas(e.v)}
            className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
              entitas === e.v ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30"
            }`}
          >
            {e.l}
          </button>
        ))}
      </div>

      <p className="text-muted-foreground break-words font-mono text-[11px] leading-relaxed">
        Kolom yang dikenali: {pilih.kolom}
      </p>

      <label className="hover:border-foreground/30 flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed p-6 text-sm transition-colors">
        <Upload className="size-4" />
        {berkas || "Pilih berkas CSV, atau tempel isinya di bawah"}
        <input
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && baca(e.target.files[0])}
        />
      </label>

      <textarea
        value={isi}
        onChange={(e) => setIsi(e.target.value)}
        rows={6}
        placeholder="Material,Plant,MatlWrhsStkQtyInMatlBaseUnit,BaseUnit,DailyConsumption&#10;M-4471,KRW1,84,TON,9.2"
        className="w-full resize-y rounded-lg border p-3 font-mono text-xs outline-none"
      />

      {pesan && (
        <p className={`text-xs ${pesan.ok ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"}`}>
          {pesan.teks}
        </p>
      )}

      <div className="flex items-center justify-between gap-3">
        <p className="text-muted-foreground text-xs leading-relaxed">
          Data yang diunggah dipakai lebih dulu daripada data contoh, dan labelnya berubah
          jadi <span className="font-mono">simpanan</span>.
        </p>
        <Button onClick={kirim} disabled={sibuk || !isi.trim()} size="sm">
          {sibuk ? "Mengunggah…" : "Unggah"}
        </Button>
      </div>
    </div>
  );
}
