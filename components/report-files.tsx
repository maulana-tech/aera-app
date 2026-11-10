import { FileSpreadsheet, FileText } from "lucide-react";

import { Button } from "@/components/ui/button";

/* A report's files. The agent service builds both from the stored record
 * (engine/report.py): the PDF to read or send on, the workbook with every
 * table the handling produced. Plain links, so the browser downloads them
 * under the name the service gives. `base` is the API path without the
 * extension, for instance "reports/run_x" or "portfolio". */
export function ReportFiles({
  base, excel = true, sheets, size = "sm", primary = false, period,
}: {
  base: string;
  /** Offer the workbook. Off when the report holds no table worth one. */
  excel?: boolean;
  /** How many sheets the workbook holds, said on the button when known. */
  sheets?: number;
  size?: "xs" | "sm" | "default";
  /** The PDF as the page's main action. */
  primary?: boolean;
  /** The period the page is showing, carried into the download so the file and
   *  the page cannot cover different months. */
  period?: Record<string, string>;
}) {
  const q = period && Object.keys(period).length ? `?${new URLSearchParams(period)}` : "";
  return (
    <>
      <Button asChild size={size} variant={primary ? "default" : "outline"}>
        <a href={`/api/aera/${base}.pdf${q}`} download>
          <FileText />
          PDF
        </a>
      </Button>
      {excel && (
        <Button asChild size={size} variant="outline">
          <a href={`/api/aera/${base}.xlsx${q}`} download
             title={sheets ? `A workbook with ${sheets} sheets` : "A workbook of every table in this report"}>
            <FileSpreadsheet />
            Excel{sheets ? <span className="text-muted-foreground font-mono text-[10px]">{sheets}</span> : null}
          </a>
        </Button>
      )}
    </>
  );
}
