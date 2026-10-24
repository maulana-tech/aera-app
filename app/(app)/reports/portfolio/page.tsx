import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { api, idr } from "@/app/lib";
import { Markdown } from "@/components/markdown";

export const dynamic = "force-dynamic";

type Portfolio = {
  title: string;
  markdown: string;
  summary_by: string | null;
  metrics: {
    runs_total: number;
    by_status: Record<string, number>;
    actions_total: number;
    actions_sent: number;
    actions_pending: number;
    predicted_idr_total: number;
    settled_actions: number;
    settled_delta_idr: number;
    decided_on_trusted: number;
    decided_with_untrusted: number;
  };
};

/* One tile. The number leads; the label and any note sit under it. */
function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-1 text-xl font-semibold tracking-tight tabular-nums">{value}</p>
      {note && <p className="text-muted-foreground mt-0.5 text-[11px]">{note}</p>}
    </div>
  );
}

export default async function PortfolioReport() {
  const p = await api<Portfolio>("portfolio");

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <Link
        href="/reports"
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs"
      >
        <ArrowLeft className="size-3" />
        Reports
      </Link>

      <header className="mt-3 border-b pb-4 md:pb-5">
        <h1 className="text-xl font-semibold tracking-tight md:text-2xl">Operations report</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Every handling rolled up: how much was handled, what it was predicted to cost, and
          — once outcomes are recorded — what it actually cost. The figures are computed from
          the record; a written summary is added only when the auxiliary model is available.
        </p>
      </header>

      {!p ? (
        <p className="text-muted-foreground mt-6 rounded-lg border border-dashed p-6 text-sm">
          The report could not be assembled — the agent service may be unavailable.
        </p>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile
              label="Handlings"
              value={String(p.metrics.runs_total)}
              note={Object.entries(p.metrics.by_status).map(([k, v]) => `${v} ${k}`).join(" · ")}
            />
            <Tile
              label="Actions raised"
              value={String(p.metrics.actions_total)}
              note={`${p.metrics.actions_sent} sent · ${p.metrics.actions_pending} awaiting`}
            />
            <Tile label="Committed (predicted)" value={idr(p.metrics.predicted_idr_total)} />
            <Tile
              label="Realized vs predicted"
              value={
                p.metrics.settled_actions
                  ? (p.metrics.settled_delta_idr <= 0 ? "" : "+") + idr(p.metrics.settled_delta_idr)
                  : "—"
              }
              note={
                p.metrics.settled_actions
                  ? `${p.metrics.settled_actions} settled`
                  : "no outcomes recorded yet"
              }
            />
          </div>

          <div className="mt-6 max-w-3xl rounded-lg border p-5">
            <Markdown>{p.markdown}</Markdown>
            {p.summary_by === null && (
              <p className="text-muted-foreground mt-4 border-t pt-3 text-[11px] leading-relaxed">
                No written summary: the auxiliary model is not configured, so the figures are
                shown without prose. The report is complete without it.
              </p>
            )}
          </div>
        </>
      )}
    </main>
  );
}
