"use client";

import { Check, X } from "lucide-react";
import { useState } from "react";

import { Chip, Dot, Panel } from "@/components/dort";

/* The approval a person makes in Treasury, drawn small and clickable (example data). */

function Window({ path, children }: { path: string; children: React.ReactNode }) {
  return (
    <Panel className="overflow-hidden">
      <div className="bg-raised flex items-center gap-1.5 border-b px-3 py-2">
        <span className="size-2 rounded-full bg-[#d6e4fb]" /><span className="size-2 rounded-full bg-[#d6e4fb]" /><span className="size-2 rounded-full bg-[#d6e4fb]" />
        <span className="text-muted-foreground ml-3 truncate font-mono text-[11px]">aera.utdi.me{path}</span>
        <span className="text-muted-foreground ml-auto shrink-0 rounded-sm border px-1.5 text-[10px]">example data</span>
      </div>
      <div className="p-4 md:p-5">{children}</div>
    </Panel>
  );
}

export function Approve() {
  const [decided, setDecided] = useState<null | "approved" | "rejected">(null);
  return (
    <Window path="/treasury">
      <div className="rounded-lg border p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone={decided === "approved" ? "ok" : decided === "rejected" ? "bad" : "warn"}>{decided ?? "pending"}</Chip>
          <span className="text-fg font-mono text-[14px]">$8.00</span>
          <span className="text-muted-foreground text-[12px]">payment to DataCo · vendor.testnet</span>
        </div>
        <p className="text-body mt-2 text-[12.5px]">Full regional dataset for the weekly coffee brief.</p>
        <ul className="mt-3 space-y-1 text-[12px]">
          <li className="flex items-center gap-2"><Dot tone="ok" /><span className="text-body">on record · allowlisted · paid before</span></li>
          <li className="flex items-center gap-2"><Dot tone="warn" /><span className="text-body">$8.00 is over the autonomous $5.00 per payment</span></li>
        </ul>
        {decided === null ? (
          <div className="mt-4 flex gap-2">
            <button type="button" onClick={() => setDecided("approved")}
              className="bg-brand inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-[12.5px] text-white hover:bg-[var(--brand-lit)]">
              <Check className="size-3.5" /> Approve
            </button>
            <button type="button" onClick={() => setDecided("rejected")}
              className="text-text hover:bg-raised inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-[12.5px]">
              <X className="size-3.5" /> Reject
            </button>
          </div>
        ) : (
          <div className="bg-inner-grad mt-4 rounded-md border px-3 py-2.5 text-[12.5px]">
            {decided === "approved" ? (
              <p className="text-body"><span className="text-fg">Approved in AERA.</span> The vault holds it until an approver signs
                <span className="font-mono"> approve(request_id)</span> with 1 yoctoNEAR in their own wallet.</p>
            ) : (
              <p className="text-body"><span className="text-fg">Rejected.</span> Nothing was sent; the team is told why on the run.</p>
            )}
            <button type="button" onClick={() => setDecided(null)} className="text-brand mt-1.5 text-[12px] underline-offset-2 hover:underline">try again</button>
          </div>
        )}
      </div>
      <p className="text-muted-foreground mt-3 text-[11.5px]">Approval limits come from your role: operator $100, approver $1,000, owner more.</p>
    </Window>
  );
}
