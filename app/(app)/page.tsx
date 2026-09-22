import Link from "next/link";

import { api, idr, type Run } from "@/app/lib";
import { AutoRefresh } from "@/components/auto-refresh";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

export default async function Queue() {
  const [data, health] = await Promise.all([
    api<{ runs: Run[] }>("runs"),
    api<Record<string, any>>("health"),
  ]);

  if (!data) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">The agent service is not responding</h1>
        <pre className="mt-4 rounded-lg border border-border bg-card p-4 font-mono text-sm">
          cd sigap/agent{"\n"}python3 api.py
        </pre>
      </main>
    );
  }

  const runs = data.runs;
  const needsAttention = runs.filter((r) => r.status === "running" || r.status === "held");

  return (
    <main className="w-full px-6 py-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-primary">
            SIGAP · Decision queue
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Supply disruptions</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {runs.length} handlings · {needsAttention.length} need attention
          </p>
        </div>
        {health && (
          <div className="flex flex-wrap items-center gap-2">
            <AutoRefresh active={runs.some((r) => r.status === "running")} />
            <Badge variant="outline" className="font-mono text-[10px]">{health.env}</Badge>
            <StatusBadge status={health.sap_ready ? "done" : "held"}>
              SAP {health.sap_ready ? "connected" : "not set"}
            </StatusBadge>
            <StatusBadge status={health.model_ready ? "done" : "held"}>
              model {health.model_ready ? "ready" : "not set"}
            </StatusBadge>
          </div>
        )}
      </header>

      {runs.length === 0 ? (
        <div className="mt-10 rounded-xl border border-dashed border-border p-8">
          <p className="text-sm text-muted-foreground">No events yet. Send one:</p>
          <pre className="mt-3 overflow-x-auto rounded-lg border border-border bg-card p-4 font-mono text-xs">
{`curl -X POST localhost:8787/events \\
  -H 'content-type: application/json' \\
  -d '{"kind":"port_closure","title":"Ningbo closed 6 days",
       "trigger":"maritime advisory","payload":{"port":"CNNGB"}}'`}
          </pre>
        </div>
      ) : (
        <ul className="mt-6 grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          {runs.map((r) => (
            <li key={r.id}>
              <Link
                href={`/disruptions/${r.id}`}
                className="block rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/50"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="font-medium">{r.title}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">{r.trigger}</p>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2 font-mono text-[11px]">
                    {r.mode === "guided" && <StatusBadge status="guided" />}
                    <StatusBadge status={r.status} />
                  </div>
                </div>

                {r.decision?.recommendation && (
                  <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
                    {r.decision.recommendation}
                  </p>
                )}
                {r.status === "held" && r.decision?.reason && (
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    {r.decision.reason}
                  </p>
                )}
                {r.error && (
                  <p className="mt-3 font-mono text-xs text-destructive">{r.error}</p>
                )}

                <p className="mt-3 font-mono text-[11px] text-muted-foreground">
                  {new Date(r.started_at).toLocaleString("en-GB")}
                  {r.token_cost_idr > 0 && ` · cost ${idr(r.token_cost_idr)}`}
                  {Array.isArray(r.decision?.agents_called) &&
                    ` · ${r.decision.agents_called.length} specialists called`}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
