import { api, idr, type Board, type RunRow } from "@/app/lib";
import { AutoRefresh } from "@/components/auto-refresh";
import { DisruptionCard } from "@/components/disruption-card";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

export default async function Queue() {
  const [data, health] = await Promise.all([
    api<{ runs: RunRow[]; board?: Board }>("runs"),
    api<{ env: string; sap_ready: boolean; model_ready: boolean }>("health"),
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
  // The board comes back already sorted by what is owed, so the top of the
  // screen is the thing most owed, not the thing most recent.
  const board = data.board;

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-4 md:gap-4 md:pb-5">
        <div>
          <h1 className="mt-1 text-xl font-semibold tracking-tight md:mt-2 md:text-2xl">Supply disruptions</h1>
          {/* One line that says whether to open anything. It may only read
              "nothing needs a person" when nothing waits, nothing is held,
              nothing failed and nothing owes an outcome — a board that says
              all clear while four handlings sit held is believed once. */}
          <p className={`mt-1 text-xs md:text-sm ${
            board?.clear ? "text-emerald-700 dark:text-emerald-400"
                         : board?.needs_a_person ? "text-amber-700 dark:text-amber-400"
                         : "text-muted-foreground"}`}>
            {board?.line ?? `${runs.length} handlings`}
          </p>
          {board && board.needs_a_person > 0 && (
            <p className="text-muted-foreground mt-0.5 font-mono text-[11px]">
              {runs.length} handlings · {idr(board.value_idr)} waiting on a person
            </p>
          )}
        </div>
        {health && (
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
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
        <div className="mt-10 rounded-lg border border-dashed border-border p-8">
          <p className="text-sm text-muted-foreground">No events yet. Send one:</p>
          <pre className="mt-3 overflow-x-auto rounded-lg border border-border bg-card p-4 font-mono text-xs">
{`curl -X POST localhost:8787/events \\
  -H "Authorization: Bearer $TOKEN" \\
  -H 'content-type: application/json' \\
  -d '{"kind":"port_closure","title":"Ningbo closed 6 days",
       "trigger":"maritime advisory","payload":{"port":"CNNGB"}}'`}
          </pre>
        </div>
      ) : (
        <ul className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {runs.map((r) => (
            <li key={r.id} className="flex">
              <DisruptionCard r={r} />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
