import { apiResult, type SapSettings } from "@/app/lib";
import { PageHeader } from "@/components/shell";
import { Connect } from "./Connect";

export const dynamic = "force-dynamic";

/* Each step is something the reader does, in the order they do it, with the
 * exact text they will see on SAP's own page. "Get a key from SAP" is not an
 * instruction; "open the API page, press Show API Key" is. */
const STEPS: { n: string; head: string; body: React.ReactNode }[] = [
  {
    n: "01",
    head: "Get a key",
    body: (
      <>
        Sign in at <span className="font-mono">api.sap.com</span> with an SAP ID — free, and
        your own, not the team&apos;s. Open any <span className="font-mono">SAP S/4HANA Cloud</span>{" "}
        API, press <b>Show API Key</b>, copy it.
      </>
    ),
  },
  {
    n: "02",
    head: "Paste it above and save",
    body: (
      <>
        A key saved here beats the one in the server&apos;s{" "}
        <span className="font-mono">.env</span>, so nothing has to be redeployed. Leave the base
        URL as the sandbox unless you have your own tenant.
      </>
    ),
  },
  {
    n: "03",
    head: "Press Test connection",
    body: (
      <>
        It makes one real call and says which of three things happened:{" "}
        <b>answered</b>, <b>refused</b> (the key is wrong), or <b>quota spent</b> (the key is
        right, but the sandbox&apos;s shared allowance is used up).
      </>
    ),
  },
  {
    n: "04",
    head: "Upload your master data",
    body: (
      <>
        On <span className="font-mono">Settings → Upload data</span>. The sandbox carries SAP&apos;s
        demo dataset, not your materials, so suppliers, alternate sources and TKDN certificates
        come from a CSV. Every figure read this way is labelled{" "}
        <span className="font-mono">uploaded</span>, never <span className="font-mono">live</span>.
      </>
    ),
  },
];

export default async function SapPage() {
  const { data, error } = await apiResult<SapSettings>("settings/sap");

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="SAP connection"
        lead={
          <>
            Where SIGAP reads enterprise data from. Bring your own key: a key saved here is used
            instead of the one in the server&apos;s environment, so a deployment can be pointed at
            your tenant without a redeploy. The key is write-only — once saved, no page and no
            API ever sends it back.
          </>
        }
      />

      {data ? (
        <Connect data={data} />
      ) : (
        <p className="text-muted-foreground mt-8 rounded-lg border border-dashed p-6 text-sm">
          {error ?? "The agent service did not answer."}
        </p>
      )}

      <section className="mt-10">
        <h2 className="text-sm font-medium">Setting it up</h2>
        <ol className="mt-3 grid gap-3 sm:grid-cols-2">
          {STEPS.map((s) => (
            <li key={s.n} className="rounded-lg border px-4 py-3">
              <div className="flex items-baseline gap-3">
                <span className="text-muted-foreground font-mono text-xs">{s.n}</span>
                <span className="text-sm font-medium">{s.head}</span>
              </div>
              <p className="text-muted-foreground mt-1.5 text-xs leading-relaxed">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-8 rounded-lg border px-4 py-4">
        <h2 className="text-sm font-medium">If SAP will not answer</h2>
        <p className="text-muted-foreground mt-1.5 max-w-3xl text-xs leading-relaxed">
          The sandbox&apos;s quota is shared and small, and it reports a spent quota as an{" "}
          <span className="font-mono">HTTP 500</span>, which reads like an outage rather than a
          limit. Switch to <b>Demo mode</b> in the sidebar: the tools stop calling SAP and read
          your uploads and the shipped fixtures instead. Nothing is invented — each figure still
          says whether it is uploaded, derived or modelled — and a handling runs end to end.
        </p>
        <p className="text-muted-foreground mt-2 max-w-3xl text-xs leading-relaxed">
          This matters more than it sounds. With a key present but its quota spent, every tool
          raises and a handling finishes with no action at all. With SAP off, the same event on
          the same data runs to completion.
        </p>
      </section>
    </main>
  );
}
