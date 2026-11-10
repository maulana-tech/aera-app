import { ChevronRight } from "lucide-react";

import { api, me, wib, type Upload as UploadRecord } from "@/app/lib";
import Upload from "./Upload";
import { DeleteUpload } from "./Delete";
import { PreviewUpload } from "./Preview";
import { PageHeader } from "@/components/shell";

export const dynamic = "force-dynamic";

export default async function UploadsPage() {
  const [d, user] = await Promise.all([
    api<{ uploads: UploadRecord[] }>("uploads"),
    me(),
  ]);

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader title="Upload data" lead={<>
          Company data comes in as CSV. Every tool reads the latest upload of its table, and
          falls back to the shipped sample data only where nothing has been uploaded. That
          includes stock, orders and suppliers as well as customs declarations, approved
          substitutes and partner emails.
        </>} />

      <div className="mt-8 grid gap-10 xl:grid-cols-2 xl:gap-12">
        <div className="min-w-0">
          <Upload signedIn={!!user} />
        </div>

        <section className="min-w-0">
          <h2 className="text-sm font-medium">
            Uploaded so far ({d?.uploads.length ?? 0})
          </h2>
          {!d?.uploads.length ? (
            <p className="text-muted-foreground mt-3 rounded-lg border border-dashed p-5 text-sm">
              None yet. The system is using modelled data.
            </p>
          ) : (
            <ul className="mt-3 divide-y rounded-lg border">
              {d.uploads.map((u) => (
                <li key={u.id} className="flex items-start gap-3 px-4 py-3">
                  {/* The row opens what was actually stored. A row count is a
                      claim, and this is where somebody checks it. */}
                  <PreviewUpload upload={u}>
                    <button
                      type="button"
                      className="hover:bg-muted/40 -my-1 -ml-2 min-w-0 flex-1 rounded-md px-2 py-1 text-left transition-colors"
                    >
                      <span className="flex items-center gap-1.5">
                        <span className="truncate text-sm">{u.filename}</span>
                        <ChevronRight className="text-muted-foreground size-3 shrink-0" />
                      </span>
                      <span className="text-muted-foreground mt-0.5 block font-mono text-[11px]">
                        {u.entity}, {u.rows.toLocaleString("en-US")} rows, {u.uploaded_by}
                      </span>
                      <span className="text-muted-foreground mt-1 block text-[11px]">
                        declared {u.synthetic ? "a generated sample, labelled modelled"
                                              : "real master data, labelled cached"}
                      </span>
                      <span className="text-muted-foreground mt-0.5 block font-mono text-[10px]">
                        {wib(u.uploaded_at)}
                      </span>
                    </button>
                  </PreviewUpload>
                  {user && <DeleteUpload id={u.id} />}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
