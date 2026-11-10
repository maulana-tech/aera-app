import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import {
  api, apiResult, me, usd, when, type BusinessPayload, type Run, type TeamPayload, type Trace,
} from "@/app/lib";
import { ActionCard } from "@/components/action-card";
import { AutoRefresh } from "@/components/auto-refresh";
import { GuardianRulings } from "@/components/guardian-rulings";
import { Markdown } from "@/components/markdown";
import { RetryButton } from "@/components/run-controls";
import { Fact, Rail, Section } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";
import TraceView from "@/components/trace-view";
import { VerifiedPanel } from "@/components/verified-panel";

export const dynamic = "force-dynamic";

const seconds = (a: string, b: string | null) =>
  b ? `${Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / 1000))}s` : "still running";

export default async function WorkRun({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ seq?: string }>;
}) {
  const { id } = await params;
  const seq = Number((await searchParams).seq) || null;
  const [res, trace, user, team, biz] = await Promise.all([
    apiResult<Run>(`runs/${id}`),
    api<Trace>(`runs/${id}/trace`),
    me(),
    api<TeamPayload>("team"),
    api<BusinessPayload>("business"),
  ]);
  if (!res.data) {
    if (res.error?.includes("no such run")) notFound();
    return (
      <main className="w-full px-6 py-16">
        <h1 className="text-xl font-semibold">This run could not be read</h1>
        <p className="text-muted-foreground mt-2 text-sm">{res.error}</p>
      </main>
    );
  }
  const r = res.data;
  const d = r.decision ?? {};
  const names = Object.fromEntries((team?.agents ?? []).map((a) => [a.code, a.nickname]));
  const outcome = d.recommendation || (d.reason ? `**${d.status ?? r.status}.** ${d.reason}` : "");
  const pending = r.actions.filter((a) => a.status === "pending").length;
  const blocked = r.actions.filter((a) => a.status === "blocked").length;
  const payloadText = typeof r.work_payload.text === "string" ? r.work_payload.text : null;

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <Link href="/work" className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs">
        <ArrowLeft className="size-3" />
        Work
      </Link>

      <header className="mt-3 border-b pb-4 md:mt-5 md:pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={r.status} />
          <span className="text-muted-foreground font-mono text-xs">{r.kind}</span>
          <span className="text-muted-foreground font-mono text-xs">{r.id}</span>
          <AutoRefresh active={r.status === "running"} />
        </div>
        <h1 className="mt-2 text-xl font-semibold tracking-tight md:text-2xl">{r.title}</h1>
        {payloadText && <p className="text-muted-foreground mt-1.5 max-w-3xl text-sm leading-relaxed whitespace-pre-wrap">{payloadText}</p>}
        {r.error && <p className="mt-2 font-mono text-xs text-rose-600 dark:text-rose-400">{r.error}</p>}
        {(r.status === "held" || r.status === "failed") && (
          <div className="mt-3"><RetryButton workItemId={r.work_item_id} /></div>
        )}
      </header>

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0">
          <Section title="Outcome" className="mt-0" note={d.agents_called?.length ? `Written by Arya after asking ${d.agents_called.map((c) => names[c] ?? c).join(", ")}.` : undefined}>
            {outcome ? (
              <div className="rounded-lg border p-4"><Markdown>{outcome}</Markdown></div>
            ) : (
              <p className="text-muted-foreground text-sm">{r.status === "running" ? "The team is still working." : "No outcome was written."}</p>
            )}
            {d.untrusted_on_board && d.untrusted_on_board.length > 0 && (
              <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">
                Rests partly on figures that are not live or derived: {d.untrusted_on_board.join(", ")}.
              </p>
            )}
          </Section>

          <Section title={`Actions (${r.actions.length})`}
            note={pending ? `${pending} waiting for a person.` : blocked ? `${blocked} blocked by the guardian.` : "Everything the team tried to send or pay."}>
            {r.actions.length === 0 ? (
              <p className="text-muted-foreground text-sm">The team raised no action: nothing left the business and no money moved.</p>
            ) : (
              <div className="space-y-3">
                {r.actions.map((a) => (
                  <ActionCard key={a.id} action={a} user={user} killSwitch={biz?.profile.kill_switch}
                    approvals={r.approvals.filter((p) => p.action_id === a.id)} />
                ))}
              </div>
            )}
          </Section>

          <Section title="Guardian rulings" note="Kira's checks on every outward action and counterparty, rule by rule.">
            <GuardianRulings checks={r.guardian} />
          </Section>
        </div>

        <aside className="space-y-4">
          <Rail title="Run">
            <Fact label="Started" value={when(r.started_at)} />
            <Fact label="Took" value={seconds(r.started_at, r.finished_at)} />
            <Fact label="Model spend" value={usd(r.cost_usd || d.cost_usd || 0)} />
            <Fact label="Source" value={r.work_source} />
            <Fact label="Profile version" value={r.profile_version != null ? `v${r.profile_version}` : "-"} />
            <Fact label="Steps" value={String(r.steps.length)} />
          </Rail>
          {d.cost_by_model && Object.keys(d.cost_by_model).length > 0 && (
            <Rail title="Spend by model">
              {Object.entries(d.cost_by_model).map(([m, v]) => (
                <Fact key={m} label={m} value={`${v.calls} calls · ${usd(v.usd)}`} />
              ))}
            </Rail>
          )}
          <VerifiedPanel proofs={r.proofs} names={names} />
        </aside>
      </div>

      <Section title="Orchestration" note="Who asked whom, which tool each called, and where every figure came from.">
        {trace && trace.calls.length > 0 ? (
          <TraceView trace={trace} focusSeq={seq} />
        ) : (
          <p className="text-muted-foreground text-sm">
            Nothing was recorded: the team has not taken a step yet, or the run was held before it started.
          </p>
        )}
      </Section>
    </main>
  );
}
