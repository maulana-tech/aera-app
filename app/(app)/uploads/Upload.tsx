"use client";

import { Upload as UploadIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";

const ENTITIES = [
  { v: "MaterialStock", l: "Material stock", columns: "Material, Plant, MatlWrhsStkQtyInMatlBaseUnit, BaseUnit, DailyConsumption, Description" },
  { v: "PurchaseOrder", l: "Purchase orders", columns: "PurchaseOrder, Material, Plant, OrderQuantity, Supplier, LoadingPort, DeliveryDate, RevisedDeliveryDate, Status" },
  { v: "SalesOrder", l: "Customer orders", columns: "SalesOrder, Material, Customer, NetAmount, RequestedDeliveryDate" },
  { v: "BillOfMaterial", l: "Product structure", columns: "Material, FinishedGood, Description, ComponentQuantity" },
  { v: "AlternateSource", l: "Supply options", columns: "id, label, Supplier, Material, Quantity, ArrivalDate, ExtraCostIDR, TkdnAfterPct, Origin, NewOrigin" },
];

export default function Upload({ signedIn }: { signedIn: boolean }) {
  const router = useRouter();
  const [entity, setEntity] = useState(ENTITIES[0].v);
  const [filename, setFilename] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const chosen = ENTITIES.find((e) => e.v === entity)!;

  async function read(f: File) {
    setFilename(f.name);
    setBody(await f.text());
    setMessage(null);
  }

  async function submit() {
    setBusy(true);
    setMessage(null);
    try {
      const res = await fetch("/api/sigap/uploads", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ entity, filename: filename || "pasted.csv", csv: body }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "failed");
      setMessage({ ok: true, text: `${d.rows} rows saved as ${d.entity}` });
      setBody("");
      setFilename("");
      router.refresh();
    } catch (e) {
      setMessage({ ok: false, text: e instanceof Error ? e.message : "failed" });
    } finally {
      setBusy(false);
    }
  }

  if (!signedIn) {
    return (
      <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
        Sign in to upload. Uploads are recorded against your account.
      </p>
    );
  }

  return (
    <div className="space-y-4 rounded-xl border p-5">
      <div className="flex flex-wrap gap-2">
        {ENTITIES.map((e) => (
          <button
            key={e.v}
            onClick={() => setEntity(e.v)}
            className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
              entity === e.v ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30"
            }`}
          >
            {e.l}
          </button>
        ))}
      </div>

      <p className="text-muted-foreground break-words font-mono text-[11px] leading-relaxed">
        Recognised columns: {chosen.columns}
      </p>

      <label className="hover:border-foreground/30 flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed p-6 text-sm transition-colors">
        <UploadIcon className="size-4" />
        {filename || "Choose a CSV file, or paste its contents below"}
        <input
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && read(e.target.files[0])}
        />
      </label>

      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={6}
        placeholder="Material,Plant,MatlWrhsStkQtyInMatlBaseUnit,BaseUnit,DailyConsumption&#10;M-4471,KRW1,84,TON,9.2"
        className="w-full resize-y rounded-lg border p-3 font-mono text-xs outline-none"
      />

      {message && (
        <p className={`text-xs ${message.ok ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"}`}>
          {message.text}
        </p>
      )}

      <div className="flex items-center justify-between gap-3">
        <p className="text-muted-foreground text-xs leading-relaxed">
          Uploaded data outranks the modelled data, and its label changes to{" "}
          <span className="font-mono">cached</span>.
        </p>
        <Button onClick={submit} disabled={busy || !body.trim()} size="sm">
          {busy ? "Uploading…" : "Upload"}
        </Button>
      </div>
    </div>
  );
}
