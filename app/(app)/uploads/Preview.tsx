"use client";

import { useEffect, useState } from "react";

import { wib, type Upload as UploadRecord } from "@/app/lib";
import { OriginBadge } from "@/components/status-badge";
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger,
} from "@/components/ui/sheet";

/* What came back from GET /uploads/{id}/rows. `rows` is the file's own count;
 * `shown` is how many of them travelled, which are different numbers whenever
 * the file is long. */
type Preview = UploadRecord & {
  columns: string[];
  preview: Record<string, unknown>[];
  shown: number;
  truncated: boolean;
};

/* A row count is a claim. This is the drawer that lets somebody check it.
 *
 * The list used to say "1,395 rows" and nothing else, so the only way to see
 * what SIGAP had actually been given was to open the CSV again — and the file
 * on a laptop is not necessarily the file in the record. The rows are fetched
 * when the drawer opens rather than with the page, because a page listing
 * twenty uploads would otherwise carry every one of them.
 */
export function PreviewUpload({ upload, children }: {
  upload: UploadRecord;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Preview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || data) return;
    let live = true;
    fetch(`/api/sigap/uploads/${upload.id}/rows`)
      .then(async (r) => {
        const d = await r.json();
        if (!r.ok) throw new Error(d.error ?? `HTTP ${r.status}`);
        return d as Preview;
      })
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e instanceof Error ? e.message : "could not be read"));
    return () => { live = false; };
  }, [open, data, upload.id]);

  // The same label the tools will put on every figure that comes out of this
  // file, decided by what the uploader declared, not by looking at the rows.
  const origin = upload.synthetic ? "modelled" : "cached";

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>{children}</SheetTrigger>
      {/* The width carries the variant prefix, as AskDrawer's comment explains:
        * without it the base sm:max-w-sm wins and a table sits in 384px. */}
      <SheetContent
        side="right"
        className="flex w-full data-[side=right]:w-full flex-col gap-0 p-0 sm:data-[side=right]:max-w-[860px]"
      >
        <SheetHeader className="border-b px-5 py-3.5">
          <SheetTitle className="text-sm font-medium">{upload.filename}</SheetTitle>
          <SheetDescription className="text-xs">
            {upload.entity} · {upload.rows.toLocaleString("en-US")} rows
          </SheetDescription>
        </SheetHeader>

        <div className="border-b px-5 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <OriginBadge origin={origin} source={`upload:${upload.filename}`} />
            <span className="text-muted-foreground font-mono text-[11px]">
              {upload.uploaded_by}
            </span>
            <span className="text-muted-foreground font-mono text-[11px]">
              {wib(upload.uploaded_at)}
            </span>
          </div>
          <p className="text-muted-foreground mt-2 max-w-2xl text-[11px] leading-relaxed">
            {upload.synthetic
              ? "Declared a generated sample, so every figure read from it is labelled modelled and the calculator will refuse to state rupiah on it."
              : "Declared real master data, so figures read from it are labelled cached — which is what lets the calculator state rupiah at all."}
          </p>
        </div>

        <div className="min-h-0 flex-1 overflow-auto">
          {error ? (
            <p className="text-destructive px-5 py-4 text-sm">{error}</p>
          ) : !data ? (
            <p className="text-muted-foreground px-5 py-4 text-sm">Reading the rows…</p>
          ) : data.preview.length === 0 ? (
            <p className="text-muted-foreground px-5 py-4 text-sm">This upload holds no rows.</p>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-muted/40 sticky top-0 z-10">
                <tr className="border-b">
                  <th className="text-muted-foreground w-10 px-3 py-2 text-right font-mono text-[10px] font-medium">
                    #
                  </th>
                  {data.columns.map((c) => (
                    <th
                      key={c}
                      className="text-muted-foreground whitespace-nowrap px-3 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-wider"
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.preview.map((row, i) => (
                  <tr key={i} className="hover:bg-muted/30">
                    <td className="text-muted-foreground px-3 py-1.5 text-right font-mono text-[10px] tabular-nums">
                      {i + 1}
                    </td>
                    {data.columns.map((c) => {
                      const v = row[c];
                      const empty = v === null || v === undefined || v === "";
                      return (
                        <td
                          key={c}
                          className={`whitespace-nowrap px-3 py-1.5 ${
                            typeof v === "number" ? "text-right font-mono tabular-nums" : ""
                          }`}
                        >
                          {empty ? (
                            <span className="text-muted-foreground">-</span>
                          ) : typeof v === "number" ? (
                            v.toLocaleString("en-US")
                          ) : (
                            String(v)
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* A preview that silently showed 200 of 1,395 rows would be a small
          * lie of exactly the kind this system refuses elsewhere. */}
        {data?.truncated && (
          <p className="text-muted-foreground border-t px-5 py-3 text-[11px] leading-relaxed">
            Showing the first {data.shown.toLocaleString("en-US")} of{" "}
            {data.rows.toLocaleString("en-US")} rows. The tools read all of them; only this
            drawer is cut.
          </p>
        )}
      </SheetContent>
    </Sheet>
  );
}
