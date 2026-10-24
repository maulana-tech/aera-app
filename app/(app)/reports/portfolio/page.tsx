import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { api, idr } from "@/app/lib";
import { Markdown } from "@/components/markdown";
import { ReportFiles } from "@/components/report-files";
import { ReportSend } from "@/components/report-send";
import { Empty, PageHeader, Section } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";

export const dynamic = "force-dynamic";

type Portfolio = {
  title: string;
  markdown: string;
  summary_by: string | null;
  summary?: string | null;
  sheets?: { name: string; rows: number }[];
  handlings?: {
    id: string; title: string; kind: string; status: string; mode: string;
    started_at: string; finished_at: string | null; steps: number; tools: number;
    actions: number; token_cost_idr: number | null;
  }[];
  actions?: {
    id: string; run_id: string; title: string; kind: string; status: string;
    autonomous: boolean; what: string; cost_idr: number | null; created_at: string;
    outcome: string | null;
  }[];
  metrics: {
    runs_total: number;
    by_status: Record<string, number>;
    actions_total: number;
    actions_sent: number;
    actions_pending: number;
    predicted_idr_total: number;
    settled_actions: number;
    settled_predicted_idr?: number;
    settled_actual_idr?: number;
    settled_delta_idr: number;
    decided_on_trusted: number;
    decided_with_untrusted: number;
  };
};

const when = (t: string) =>
  new Date(t).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

/* One tile. The number leads; the label and any note sit under it. */
function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-1 font-mono text-xl font-semibold tracking-tight tabular-nums">{value}</p>
      {note && <p className="text-muted-foreground mt-0.5 text-[11px]">{note}</p>}
    </div>
  );
}

const th = "text-muted-foreground px-4 py-2.5 text-left text-xs font-normal whitespace-nowrap";
const td = "px-4 py-2.5 align-top";

export default async function PortfolioReport() {
  const p = await api<Portfolio>("portfolio");
  const m = p?.metrics;
  const handlings = p?.handlings ?? [];
  const actions = p?.actions ?? [];

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <Link
        href="/reports"
        className="text-muted-foreground hover:text-foreground mb-3 inline-flex items-center gap-1.5 text-xs md:mb-5"
      >
        <ArrowLeft className="size-3" />
        Reports
      </Link>

      <PageHeader
        title="Operations report"
        lead="Every handling rolled up: how much was handled, what it was predicted to cost and,
              once outcomes are recorded, what it actually cost. The figures are computed from the
              record; a written summary is added only when the auxiliary model is available."
        aside={p && (
          <>
            <ReportFiles base="portfolio" sheets={p.sheets?.length} primary />
            <ReportSend base="portfolio" title="Operations report" />
          </>
        )}
      />

      {!p || !m ? (
        <p className="text-muted-foreground mt-6 rounded-lg border border-dashed p-6 text-sm">
          The report could not be assembled. The agent service may be unavailable.
        </p>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile
              label="Handlings"
              value={String(m.runs_total)}
              note={Object.entries(m.by_status).map(([k, v]) => `${v} ${k}`).join(" · ")}
            />
            <Tile
              label="Actions raised"
              value={String(m.actions_total)}
              note={`${m.actions_sent} sent · ${m.actions_pending} awaiting`}
            />
            <Tile
              label="Committed (predicted)"
              value={idr(m.predicted_idr_total)}
              note={`${m.decided_on_trusted} decided on trusted evidence · ${m.decided_with_untrusted} with a caveat`}
            />
            <Tile
              label="Realized vs predicted"
              value={m.settled_actions ? (m.settled_delta_idr <= 0 ? "" : "+") + idr(m.settled_delta_idr) : "-"}
              note={m.settled_actions ? `${m.settled_actions} settled` : "no outcomes recorded yet"}
            />
          </div>

          {p.summary && (
            <Section title="Summary" note="Phrased by the auxiliary model from the figures above. It was given no number to invent.">
              <div className="rounded-lg border p-5">
                <Markdown>{p.summary}</Markdown>
              </div>
            </Section>
          )}

          <Section title={`Handlings (${handlings.length})`}>
            {handlings.length === 0 ? (
              <Empty what="No handling on record." why="Nothing has been handled yet, so there is nothing to roll up." />
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full min-w-[720px] text-sm">
                  <thead className="bg-muted/40 border-b">
                    <tr>
                      <th className={th}>Handling</th>
                      <th className={th}>Kind</th>
                      <th className={th}>Status</th>
                      <th className={th}>Started</th>
                      <th className={`${th} text-right`}>Steps</th>
                      <th className={`${th} text-right`}>Actions</th>
                      <th className={`${th} text-right`}>Model time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {handlings.map((h) => (
                      <tr key={h.id} className="hover:bg-muted/30">
                        <td className={td}>
                          <Link href={`/reports/${h.id}`} className="font-medium hover:underline">{h.title}</Link>
                        </td>
                        <td className={`${td} text-muted-foreground font-mono text-xs`}>{h.kind}</td>
                        <td className={td}><StatusBadge status={h.status} /></td>
                        <td className={`${td} text-muted-foreground font-mono text-xs whitespace-nowrap`}>{when(h.started_at)}</td>
                        <td className={`${td} text-right font-mono tabular-nums`}>{h.steps}</td>
                        <td className={`${td} text-right font-mono tabular-nums`}>{h.actions}</td>
                        <td className={`${td} text-right font-mono tabular-nums whitespace-nowrap`}>
                          {h.token_cost_idr ? idr(h.token_cost_idr) : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          <Section title={`Actions (${actions.length})`}>
            {actions.length === 0 ? (
              <Empty what="No action has been raised." why="No handling has reached the point of proposing a change." />
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full min-w-[820px] text-sm">
                  <thead className="bg-muted/40 border-b">
                    <tr>
                      <th className={th}>Action</th>
                      <th className={th}>What it does</th>
                      <th className={th}>Handling</th>
                      <th className={`${th} text-right`}>Value</th>
                      <th className={th}>Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {actions.map((a) => (
                      <tr key={a.id} className="hover:bg-muted/30">
                        <td className={`${td} font-mono text-xs whitespace-nowrap`}>
                          {a.kind}
                          {a.autonomous && <span className="text-muted-foreground block font-sans text-[11px]">own authority</span>}
                        </td>
                        <td className={`${td} text-xs leading-relaxed`}>
                          <span className="line-clamp-3">{a.what || "-"}</span>
                        </td>
                        <td className={`${td} text-xs`}>
                          <Link href={`/reports/${a.run_id}`} className="text-muted-foreground hover:text-foreground hover:underline">{a.title}</Link>
                        </td>
                        <td className={`${td} text-right font-mono tabular-nums whitespace-nowrap`}>
                          {typeof a.cost_idr === "number" ? idr(a.cost_idr) : "-"}
                        </td>
                        <td className={td}><StatusBadge status={a.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          <Section title="Realized vs predicted">
            {m.settled_actions ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Tile label="Predicted" value={idr(m.settled_predicted_idr ?? 0)} note={`${m.settled_actions} settled action(s)`} />
                <Tile label="Actual" value={idr(m.settled_actual_idr ?? 0)} />
                <Tile label="Delta" value={(m.settled_delta_idr > 0 ? "+" : "") + idr(m.settled_delta_idr)}
                      note={m.settled_delta_idr < 0 ? "came in under prediction" : m.settled_delta_idr > 0 ? "came in over prediction" : "exactly at prediction"} />
              </div>
            ) : (
              <p className="text-muted-foreground rounded-lg border border-dashed p-5 text-sm leading-relaxed">
                No action has a recorded outcome yet, so realized cost cannot be stated. The predicted
                figures above stand alone.
              </p>
            )}
          </Section>
        </>
      )}
    </main>
  );
}
