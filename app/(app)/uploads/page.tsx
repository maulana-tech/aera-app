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
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Data
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Upload data</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Until SAP is connected, company data can come in as CSV. This is not a substitute
          for the SAP connection — once <span className="font-mono">SAP_API_KEY</span> is set,
          the tools read live data and uploads are ignored.
        </p>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <Upload signedIn={!!user} />

        <aside>
          <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
            Uploads · {d?.uploads.length ?? 0}
          </h2>
          {!d?.uploads.length ? (
            <p className="text-muted-foreground mt-3 rounded-xl border border-dashed p-5 text-sm">
              None yet. The system is using modelled data.
            </p>
          ) : (
            <ul className="mt-3 divide-y rounded-xl border">
              {d.uploads.map((u) => (
                <li key={u.id} className="flex items-start gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">{u.filename}</p>
                    <p className="text-muted-foreground mt-0.5 font-mono text-[11px]">
                      {u.entity} · {u.rows} rows · {u.uploaded_by}
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
        </aside>
      </div>
    </main>
  );
}
