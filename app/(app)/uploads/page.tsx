import { api, me, type Upload as UploadRecord } from "@/app/lib";
import Upload from "./Upload";
import { DeleteUpload } from "./Delete";

export const dynamic = "force-dynamic";

export default async function UploadsPage() {
  const [d, user] = await Promise.all([
    api<{ uploads: UploadRecord[] }>("uploads"),
    me(),
  ]);

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-4 md:px-6 md:py-8">
      <header className="border-b pb-4 md:pb-5">
        <h1 className="mt-1 text-xl font-semibold tracking-tight md:mt-2 md:text-2xl">Upload data</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          Until SAP is connected, company data can come in as CSV. This is not a substitute
          for the SAP connection. Once <span className="font-mono">SAP_API_KEY</span> is set,
          the tools read live data and uploads are ignored.
        </p>
      </header>

      <div className="mt-8 space-y-10">
        <Upload signedIn={!!user} />

        <section>
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
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">{u.filename}</p>
                    <p className="text-muted-foreground mt-0.5 font-mono text-[11px]">
                      {u.entity}, {u.rows} rows, {u.uploaded_by}
                    </p>
                    <p className="text-muted-foreground mt-1 text-[11px]">
                      declared {u.synthetic ? "a generated sample, labelled modelled"
                                            : "real master data, labelled cached"}
                    </p>
                    <p className="text-muted-foreground mt-0.5 font-mono text-[10px]">
                      {new Date(u.uploaded_at).toLocaleString("en-GB")}
                    </p>
                  </div>
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
