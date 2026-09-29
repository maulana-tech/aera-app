"use client";

import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";

import type { AuditReport } from "@/app/lib";
import { Button } from "@/components/ui/button";

const idr = (n: number) => "Rp " + n.toLocaleString("en-US");

/** The same report as text, for pasting into an email or a ticket. */
function asMarkdown(a: AuditReport): string {
  const c = a.coverage;
  const lines: string[] = [
    "# Supply data audit",
    "",
    `Read across ${c.rows} rows. Deterministic: no model was involved, so every`,
    "finding can be recomputed from the same file.",
    "",
    "## Coverage",
    "",
    `- Materials: ${c.materials}`,
    `- Plants: ${c.plants}`,
    `- Suppliers: ${c.suppliers}`,
    `- Purchase orders: ${c.purchase_orders}`,
    `- Customer orders: ${c.customer_orders}`,
    `- Committed value: ${idr(c.committed_idr ?? 0)}`,
    "",
    "## Findings",
    "",
  ];
  for (const f of a.findings) {
    lines.push(`### ${f.severity.toUpperCase()}. ${f.title}`);
    lines.push("");
    if (f.value_idr !== null) lines.push(`Revenue that depends on this: ${idr(f.value_idr)}`);
    lines.push("");
    lines.push(f.detail);
    lines.push("");
    if (f.evidence.length) lines.push(`Evidence: ${f.evidence.join(", ")}`);
    lines.push(`Recommended: ${f.action}`);
    lines.push("");
  }
  lines.push("## Where the data came from", "");
  for (const [entity, o] of Object.entries(a.origins ?? {})) {
    lines.push(`- ${entity}: ${o.origin} from ${o.source}`);
  }
  lines.push("", `Weakest input: ${a.weakest_origin}. Every conclusion inherits it.`);
  return lines.join("\n");
}

export function AuditActions({ report }: { report: AuditReport }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(asMarkdown(report));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function download() {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(
      new Blob([asMarkdown(report)], { type: "text/markdown" }),
    );
    a.download = "supply-data-audit.md";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={copy}>
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        {copied ? "Copied" : "Copy"}
      </Button>
      <Button variant="outline" size="sm" onClick={download}>
        <Download className="size-3.5" />
        Download
      </Button>
    </div>
  );
}
