import { ArrowRight, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import {
  api, apiResult, mayManage, mayStop, me, noBusiness, usd, when,
  type Action, type BusinessPayload, type Health, type Ledger, type RunRow,
} from "@/app/lib";
import { AutoRefresh } from "@/components/auto-refresh";
import { Bars, Figure, type Datum } from "@/components/charts";
import { KillSwitch } from "@/components/kill-switch";
import { Empty, Metric, PageHeader, Section } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { gist } from "@/lib/gist";

export const dynamic = "force-dynamic";

const SETTLED = new Set(["sent", "approved"]);

export default async function Dashboard() {
  const biz = await apiResult<BusinessPayload>("business");
  if (!biz.data) {
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">The agent service is not responding</h1>
        <p className="text-muted-foreground mt-2 text-sm">{biz.error}</p>
        <pre className="bg-card mt-4 rounded-lg border p-4 font-mono text-sm">cd aera/agent{"\n"}python3 api.py</pre>
      </main>
    );
  }
  if (noBusiness(biz.data)) redirect("/onboarding");

  const [led, pending, runs, health, user] = await Promise.all([
    api<Ledger>("ledger?days=30"),
    api<{ actions: Action[] }>("actions?status=pending"),
    api<{ runs: RunRow[] }>("runs"),
    api<Health>("health"),
    me(),
  ]);
  const p = biz.data.profile;
  const money = led?.money ?? [];
  const sum = (dir: string) => money.filter((m) => m.direction === dir && SETTLED.has(m.status)).reduce((s, m) => s + m.total, 0);
  const revenue = sum("in");
  const spend = sum("out") + (led?.model_spend_usd ?? 0);
  const waiting = pending?.actions ?? [];
  const waitingValue = waiting.reduce((s, a) => s + a.value_usd, 0);
  const proofs = led?.proofs ?? {};
  const proofsTotal = Object.values(proofs).reduce((s, v) => s + (v ?? 0), 0);
  const recent = (runs?.runs ?? []).slice(0, 8);
  const decisions = led?.decisions ?? [];
  const autonomous = decisions.filter((d) => d.autonomous).reduce((s, d) => s + d.n, 0);
  const human = decisions.filter((d) => !d.autonomous && d.status !== "pending" && d.status !== "blocked").reduce((s, d) => s + d.n, 0);
  const blockedN = decisions.filter((d) => d.status === "blocked").reduce((s, d) => s + d.n, 0);

  const who: Datum[] = [
    { label: "The team, alone", value: autonomous, display: String(autonomous), sub: "within the limits" },
    { label: "A person", value: human, display: String(human), sub: "approved or rejected" },
    { label: "Waiting", value: waiting.length, display: String(waiting.length), sub: "for a person" },
    { label: "Blocked", value: blockedN, display: String(blockedN), sub: "by the guardian, final", hatched: true },
  ];

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title={p.name}
        lead={p.mission}
        aside={<>
          <AutoRefresh active={recent.some((r) => r.status === "running")} />
          {health && <StatusBadge status={health.rail === "vault" ? "vault" : "simulated"}>{health.rail === "vault" ? `vault · ${health.network}` : "SIMULATED rail"}</StatusBadge>}
          {health && <StatusBadge status={health.model_ready ? "done" : "held"}>model {health.model_ready ? "ready" : "not set"}</StatusBadge>}
        </>}
      />

      {p.kill_switch && (
        <div className="mt-6"><KillSwitch on mayStop={mayStop(user)} mayResume={mayManage(user)} /></div>
      )}

      <div className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-5">
        <Metric label="Revenue (30 days)" value={usd(revenue)} note={`${money.filter((m) => m.direction === "in").reduce((s, m) => s + m.n, 0)} payments in`} />
        <Metric label="Spend (30 days)" value={usd(spend)} note={`${usd(led?.model_spend_usd ?? 0)} of it on models`} />
        <Metric label="Waiting for approval" value={String(waiting.length)} note={waitingValue ? `${usd(waitingValue)} in value` : undefined} />
        <Metric label="Blocked by the guardian" value={String(led?.blocked_by_guardian ?? 0)} note="checks that said no" />
        <Metric label="TEE proofs attested" value={`${proofs.attested ?? 0}/${proofsTotal}`} note={proofs.pending ? `${proofs.pending} being verified` : undefined} />
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0">
          <Section title="Recent work" className="mt-0" action={<Link href="/work" className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs">all work <ArrowRight className="size-3" /></Link>}>
            {recent.length === 0 ? (
              <Empty what="The team has not worked on anything yet." why="Give it a request on the Work page, or share a checkout link so a paid order arrives on its own." />
            ) : (
              <ul className="divide-y rounded-lg border">
                {recent.map((r) => (
                  <li key={r.id}>
                    <Link href={`/work/${r.id}`} className="hover:bg-muted/40 flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3">
                      <StatusBadge status={r.status} />
                      <span className="text-muted-foreground font-mono text-[11px]">{r.kind}</span>
                      <div className="min-w-0 flex-1 basis-56">
                        <p className="truncate text-sm font-medium">{r.title}</p>
                        <p className="text-muted-foreground line-clamp-1 text-xs">{gist(r.decision?.recommendation) || r.decision?.reason || r.error || ""}</p>
                      </div>
                      <span className="text-muted-foreground inline-flex items-center gap-1 font-mono text-[11px]">
                        {r.proofs > 0 && <><ShieldCheck className="size-3" />{r.attested}/{r.proofs} · </>}
                        {when(r.started_at)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
        <aside className="space-y-6">
          <Figure title="Who decided (30 days)" blurb="Actions the team took on its own authority against those a person decided.">
            <Bars data={who} />
          </Figure>
          {waiting.length > 0 && (
            <div className="rounded-lg border p-4">
              <p className="text-sm font-medium">{waiting.length} waiting for a person</p>
              <ul className="mt-2 space-y-1.5">
                {waiting.slice(0, 5).map((a) => (
                  <li key={a.id} className="flex items-center gap-2 text-xs">
                    <span className="font-mono">{a.kind}</span>
                    <span className="font-mono tabular-nums">{usd(a.value_usd)}</span>
                    <Link href={`/work/${a.run_id}`} className="text-muted-foreground min-w-0 flex-1 truncate underline-offset-2 hover:underline">{a.work_title}</Link>
                  </li>
                ))}
              </ul>
              <Button asChild size="sm" variant="outline" className="mt-3"><Link href="/treasury">Decide in Treasury</Link></Button>
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}
