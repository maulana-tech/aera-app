import { ShieldCheck } from "lucide-react";
import Link from "next/link";

import {
  api, apiResult, usd, when, type BusinessPayload, type RunRow, type WorkItem,
} from "@/app/lib";
import { AutoRefresh } from "@/components/auto-refresh";
import { Empty, PageHeader } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";
import { gist } from "@/lib/gist";
import { NewWork } from "./NewWork";

export const dynamic = "force-dynamic";

export default async function WorkPage({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const { status } = await searchParams;
  const [items, runs, biz] = await Promise.all([
    apiResult<{ items: WorkItem[] }>(`work${status ? `?status=${encodeURIComponent(status)}` : ""}`),
    api<{ runs: RunRow[] }>("runs"),
    api<BusinessPayload>("business"),
  ]);
  const byRun = new Map((runs?.runs ?? []).map((r) => [r.id, r]));
  const list = items.data?.items ?? [];
  const running = list.some((w) => w.status === "running" || w.status === "new");
  const stopped = !!biz?.profile.kill_switch;

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Work"
        lead="Everything the team has been given: paid orders, requests, standing goals and bills. Each one is a run: Arya plans it, specialists do it, Kira rules on anything that leaves, Tara handles the money."
        aside={<><AutoRefresh active={running} /><NewWork disabled={stopped} /></>}
      />

      <nav className="mt-4 flex flex-wrap gap-2 text-xs">
        {["", "running", "held", "done", "failed"].map((s) => (
          <Link key={s || "all"} href={s ? `/work?status=${s}` : "/work"}
            className={`rounded-full border px-3 py-1 ${(status ?? "") === s ? "bg-primary text-primary-foreground border-primary" : "hover:border-foreground/30"}`}>
            {s || "all"}
          </Link>
        ))}
      </nav>

      {!items.data ? (
        <p className="text-muted-foreground mt-6 text-sm">{items.error}</p>
      ) : list.length === 0 ? (
        <div className="mt-6">
          <Empty what="No work yet." why="Give the team a request, or share a checkout link: a paid order becomes work on its own." />
        </div>
      ) : (
        <ul className="mt-6 divide-y rounded-lg border">
          {list.map((w) => {
            const r = w.run_id ? byRun.get(w.run_id) : undefined;
            const line = gist(r?.decision?.recommendation) || r?.decision?.reason || r?.error || "";
            const body = (
              <div className="flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3">
                <StatusBadge status={r?.status ?? w.status} />
                <span className="text-muted-foreground font-mono text-[11px]">{w.kind}</span>
                <div className="min-w-0 flex-1 basis-60">
                  <p className="truncate text-sm font-medium">{w.title}</p>
                  {line && <p className="text-muted-foreground mt-0.5 line-clamp-2 text-xs leading-relaxed">{line}</p>}
                </div>
                <div className="text-muted-foreground flex shrink-0 flex-wrap items-center gap-x-3 font-mono text-[11px] tabular-nums">
                  {r && r.action_count > 0 && <span>{r.action_count} actions</span>}
                  {r && r.proofs > 0 && (
                    <span className="inline-flex items-center gap-1"><ShieldCheck className="size-3" />{r.attested}/{r.proofs}</span>
                  )}
                  {r && r.cost_usd > 0 && <span>{usd(r.cost_usd)}</span>}
                  <span>{w.source}</span>
                  <span>{when(w.received_at)}</span>
                </div>
              </div>
            );
            return (
              <li key={w.id}>
                {w.run_id ? <Link href={`/work/${w.run_id}`} className="hover:bg-muted/40 block">{body}</Link> : body}
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
