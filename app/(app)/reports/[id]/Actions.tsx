"use client";

import { Check, Copy, FileDown } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

/** The report's text, to paste into a message or keep as Markdown. */
export function ReportActions({ markdown, title }: { markdown: string; title: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function download() {
    const name = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([markdown], { type: "text/markdown" }));
    a.download = `${name || "report"}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={download} title="Download as Markdown">
        <FileDown className="size-3.5" />
        Markdown
      </Button>
      <Button variant="ghost" size="sm" onClick={copy} title="Copy the report as text">
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        {copied ? "Copied" : "Copy"}
      </Button>
    </>
  );
}
