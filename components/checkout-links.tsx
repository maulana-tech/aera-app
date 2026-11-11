"use client";

import { Check, Copy, ExternalLink } from "lucide-react";
import { useState } from "react";

import type { Offering } from "@/app/lib";
import { usd } from "@/app/lib";

/* The public checkout for each offering: what a customer is sent. */
export function CheckoutLinks({ offerings, open }: { offerings: Offering[]; open: boolean }) {
  const [copied, setCopied] = useState("");
  if (!offerings.length) return <p className="text-muted-foreground text-sm">No offerings yet.</p>;
  return (
    <div className="space-y-2">
      {!open && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          The kill switch is on: these pages tell customers the business is not taking orders.
        </p>
      )}
      {offerings.map((o) => {
        return (
          <div key={o.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{o.title} <span className="text-muted-foreground font-normal">· {usd(o.price_usd)}</span></p>
              <p className="text-muted-foreground truncate font-mono text-xs">/buy/{o.id}</p>
            </div>
            <div className="flex items-center gap-1">
              <button type="button" className="hover:bg-muted rounded p-1.5" title="Copy link" aria-label={`Copy the checkout link for ${o.title}`}
                onClick={() => { void navigator.clipboard.writeText(`${window.location.origin}/buy/${o.id}`); setCopied(o.id); setTimeout(() => setCopied(""), 1500); }}>
                {copied === o.id ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              </button>
              <a href={`/buy/${o.id}`} target="_blank" rel="noopener noreferrer" className="hover:bg-muted rounded p-1.5" title="Open" aria-label={`Open the checkout page for ${o.title}`}>
                <ExternalLink className="size-3.5" />
              </a>
            </div>
          </div>
        );
      })}
    </div>
  );
}
