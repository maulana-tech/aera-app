"use client";

import { ArrowRight, Check, Copy } from "lucide-react";
import { useState } from "react";

/** A transaction hash you can copy, with its NearBlocks link. */
export function CopyHash({ hash }: { hash: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <span className="mt-4 inline-flex items-center gap-1">
      <a href={`https://testnet.nearblocks.io/txns/${hash}`} target="_blank" rel="noopener noreferrer"
        className="text-brand inline-flex items-center gap-1.5 font-mono text-[12px] underline-offset-2 hover:underline">
        {hash.slice(0, 10)}… on NearBlocks <ArrowRight className="size-3" />
      </a>
      <button type="button" aria-label="Copy the transaction hash"
        onClick={async () => { try { await navigator.clipboard.writeText(hash); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* no clipboard */ } }}
        className="text-muted-foreground hover:text-fg hover:bg-raised inline-flex size-7 items-center justify-center rounded-md">
        {copied ? <Check className="text-ok size-3.5" /> : <Copy className="size-3.5" />}
      </button>
    </span>
  );
}
