import { api, apiResult, type Agent, type McpPayload } from "@/app/lib";
import { PageHeader } from "@/components/shell";
import { Servers } from "./Servers";

export const dynamic = "force-dynamic";

export default async function McpPage() {
  const [{ data, error }, roster] = await Promise.all([
    apiResult<McpPayload>("mcp/servers"),
    api<{ agents: Agent[] }>("agents"),
  ]);
  const team = (roster?.agents ?? []).map((a) => ({ code: a.code, name: a.nickname }));

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="MCP"
        lead={
          <>
            AERA speaks MCP (Model Context Protocol) both ways. Other agents and apps call in to
            use the business&apos;s tools; AERA calls out to tools somebody else operates. Add a
            server below and choose which agents may use it. Nothing is needed here to run the
            business.
          </>
        }
      />

      {!data ? (
        <p className="text-muted-foreground mt-8 rounded-lg border border-dashed p-6 text-sm">
          {error ?? "The agent service did not answer."}
        </p>
      ) : (
        <>
          <section className="mt-8 rounded-lg border">
            <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
              <p className="text-sm font-medium">What AERA serves</p>
              <span className="text-muted-foreground ml-auto font-mono text-[10px]">
                {data.ours.endpoint} · protocol {data.ours.protocol}
              </span>
            </div>
            <div className="grid gap-4 px-4 py-4 sm:grid-cols-3">
              <div>
                <p className="text-2xl font-medium tracking-tight">{data.ours.tools_total}</p>
                <p className="text-muted-foreground mt-0.5 text-xs leading-relaxed">
                  tools, of which <b>{data.ours.tools_writing}</b> raise an action. Each one
                  carries a readOnlyHint, so a client that did not write AERA can tell a read
                  from a write instead of treating all of them as dangerous.
                </p>
              </div>
              <div>
                <p className="text-2xl font-medium tracking-tight">
                  {data.ours.resources.length}
                </p>
                <p className="text-muted-foreground mt-0.5 text-xs">resources</p>
                <ul className="mt-1.5 space-y-0.5">
                  {data.ours.resources.map((r) => (
                    <li key={r} className="font-mono text-[11px] break-all">{r}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-2xl font-medium tracking-tight">
                  {data.ours.prompts.length}
                </p>
                <p className="text-muted-foreground mt-0.5 text-xs">
                  prompts a connected client can start from
                </p>
                <ul className="mt-1.5 space-y-0.5">
                  {data.ours.prompts.map((p) => (
                    <li key={p} className="font-mono text-[11px]">{p}</li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          <Servers data={data} team={team} />

          <section className="mt-6 rounded-lg border px-4 py-4">
            <h2 className="text-sm font-medium">What a remote tool does not get</h2>
            <p className="text-muted-foreground mt-1.5 max-w-3xl text-xs leading-relaxed">
              A tool from somebody else&apos;s server is namespaced before anything sees it, so
              a remote tool called <span className="font-mono">check_local_constraints</span>{" "}
              can never shadow Guardian&apos;s. Whatever it returns is labelled with the server it
              came from and is never promoted to live: a figure from a tool we do not operate
              is not a figure from our own records, however confident it sounds. A server that says
              nothing about whether a tool writes is read as a writer.
            </p>
            <p className="text-muted-foreground mt-2 max-w-3xl text-xs leading-relaxed">
              <span className="text-fg">Tools that change things</span> (append a row, publish a post) are off until an
              owner allows one with <span className="font-mono">Allow with approval</span>. Even then an agent&apos;s call
              writes nothing: it becomes an action the Guardian checks and a person approves, and only then does AERA
              run it, after checking again that it is still allowed. And once a run has read anything from outside
              AERA (a web page, a remote tool), any payment, refund or outside change in that run waits for a person:
              what an outsider wrote is never the whole reason something happens.
            </p>
          </section>
        </>
      )}
    </main>
  );
}
