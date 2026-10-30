import { apiResult, type SkillsPayload } from "@/app/lib";
import { PageHeader } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

export default async function SkillsPage() {
  const { data, error } = await apiResult<SkillsPayload>("skills");

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Skills"
        lead={
          <>
            A tool is one call. A skill is a named procedure that composes several of them in
            an order somebody decided once, so the order is not re-derived — differently — on
            every handling. Each one names the agents that may run it and the tools it uses,
            and both are checked against the registry: a skill naming a tool that does not
            exist fails the build rather than a handling.
          </>
        }
      />

      {!data ? (
        <p className="text-muted-foreground mt-8 rounded-lg border border-dashed p-6 text-sm">
          {error ?? "The agent service did not answer."}
        </p>
      ) : (
        <>
          <div className="mt-8 space-y-4">
            {data.skills.map((s) => (
              <section key={s.name} className="rounded-lg border">
                <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
                  <p className="text-sm font-medium">{s.title}</p>
                  <span className="text-muted-foreground font-mono text-[10px]">{s.name}</span>
                  {s.external && (
                    <StatusBadge status="done">reachable over MCP and A2A</StatusBadge>
                  )}
                  <span className="text-muted-foreground ml-auto font-mono text-[10px]">
                    {s.usage.calls} run{s.usage.calls === 1 ? "" : "s"} in {data.days} days
                    {s.usage.not_found > 0 && ` · ${s.usage.not_found} named but missing`}
                  </span>
                </div>

                <div className="grid gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_320px]">
                  <div>
                    <p className="text-muted-foreground text-xs leading-relaxed">
                      {s.description}
                    </p>
                    <ol className="mt-3 space-y-1.5">
                      {s.steps.map((step, i) => (
                        <li key={i} className="flex gap-3 text-xs leading-relaxed">
                          <span className="text-muted-foreground font-mono">
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          <span>{step}</span>
                        </li>
                      ))}
                    </ol>
                  </div>

                  <div className="space-y-3">
                    <div>
                      <p className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
                        Who may run it
                      </p>
                      <p className="mt-1 font-mono text-xs">
                        {s.agents.length ? s.agents.join(", ") : "any agent"}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
                        Tools it composes
                      </p>
                      <ul className="mt-1 space-y-0.5">
                        {s.tools.map((t) => (
                          <li key={t} className="font-mono text-[11px]">{t}</li>
                        ))}
                      </ul>
                    </div>
                    {Object.keys(s.usage.by_agent).length > 0 && (
                      <div>
                        <p className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
                          Run by
                        </p>
                        <ul className="mt-1 space-y-0.5">
                          {Object.entries(s.usage.by_agent).map(([a, n]) => (
                            <li key={a} className="font-mono text-[11px]">
                              {a} · {n}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </section>
            ))}
          </div>

          <p className="text-muted-foreground mt-6 max-w-3xl text-xs leading-relaxed">
            Every invocation is counted, including the ones that name a skill nobody wrote.
            That last figure is the useful one: a model reaching for a procedure that does not
            exist is a gap in this catalogue, and it is only visible because those calls are
            recorded rather than dropped.
          </p>
        </>
      )}
    </main>
  );
}
