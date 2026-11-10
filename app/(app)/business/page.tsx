import Link from "next/link";
import { redirect } from "next/navigation";

import {
  api, apiResult, mayManage, mayStop, me, noBusiness, usd, when, type BusinessFile, type BusinessPayload,
} from "@/app/lib";
import { KillSwitch } from "@/components/kill-switch";
import { Problems } from "@/components/profile-editor";
import { Empty, Fact, PageHeader, Rail, Section } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Editor } from "./Editor";
import { Files } from "./Files";

export const dynamic = "force-dynamic";

function Chips({ items, empty = "none" }: { items: string[]; empty?: string }) {
  if (!items.length) return <span className="text-muted-foreground text-xs">{empty}</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((x) => <span key={x} className="rounded-full border px-2.5 py-0.5 text-xs">{x}</span>)}
    </div>
  );
}

export default async function BusinessPage() {
  const [biz, user, files] = await Promise.all([
    apiResult<BusinessPayload>("business"), me(), api<{ files: BusinessFile[] }>("files"),
  ]);
  if (!biz.data) {
    return (
      <main className="w-full px-4 py-4 md:px-6 md:py-8">
        <PageHeader title="Business" />
        <p className="text-muted-foreground mt-6 text-sm">{biz.error}</p>
      </main>
    );
  }
  if (noBusiness(biz.data)) redirect("/onboarding");
  const { profile: p, version, problems, history, context } = biz.data;
  const c = p.constraints;

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title={p.name}
        lead={p.mission}
        aside={biz.data.may_change && (
          <Button asChild size="sm" variant="ghost"><Link href="/onboarding">Re-run onboarding</Link></Button>
        )}
      />

      <div className="mt-6">
        {(mayStop(user) || p.kill_switch) && (
          <KillSwitch on={p.kill_switch} mayStop={mayStop(user)} mayResume={mayManage(user)} />
        )}
      </div>

      {problems.length > 0 && <div className="mt-6"><Problems problems={problems} /></div>}

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <Section title="Offerings" note="What customers can buy at the public checkout.">
            {p.offerings.length === 0 ? (
              <Empty what="Nothing on sale." why="Add an offering to take orders." />
            ) : (
              <ul className="divide-y rounded-lg border">
                {p.offerings.map((o) => (
                  <li key={o.id} className="flex flex-wrap items-start gap-3 px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{o.title} <span className="text-muted-foreground font-mono text-[11px]">{o.id}</span></p>
                      {o.description && <p className="text-muted-foreground mt-0.5 text-xs leading-relaxed">{o.description}</p>}
                      <p className="text-muted-foreground mt-1 font-mono text-[10px]">
                        {o.delivery} · within {o.sla_hours}h · needs {o.inputs.join(", ") || "nothing"}
                      </p>
                    </div>
                    <span className="font-mono text-sm font-medium tabular-nums">{usd(o.price_usd)}</span>
                    <Link href={`/buy/${o.id}`} className="text-muted-foreground hover:text-foreground text-xs underline underline-offset-2">checkout page</Link>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Rules the guardian enforces">
            <div className="grid gap-6 sm:grid-cols-2">
              <div><p className="text-muted-foreground mb-1.5 text-xs">Never</p><Chips items={c.forbidden} /></div>
              <div><p className="text-muted-foreground mb-1.5 text-xs">Always needs a person</p><Chips items={c.approval_required} /></div>
              <div><p className="text-muted-foreground mb-1.5 text-xs">Sensitive data</p><Chips items={p.privacy.sensitive} /></div>
              <div><p className="text-muted-foreground mb-1.5 text-xs">Channels</p><Chips items={p.channels} /></div>
            </div>
          </Section>

          {biz.data.may_change && (
            <Section title="Change the profile">
              <Editor profile={p} />
            </Section>
          )}

          <Section title="Business files" note="Price lists, style guides, past deliverables: text the agents with the knowledge capability can read.">
            <Files files={files?.files ?? []} mayChange={(user?.role ?? "viewer") !== "viewer"} />
          </Section>

          <Section title="What every agent reads" note="The profile as it is put in front of the team, word for word.">
            <pre className="bg-muted/40 overflow-x-auto rounded-lg border p-4 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">{context}</pre>
          </Section>
        </div>

        <aside className="space-y-4">
          <Rail title="Limits">
            <Fact label="Autonomous per payment" value={usd(c.autonomous_spend_usd.per_payment)} />
            <Fact label="Autonomous per day" value={usd(c.autonomous_spend_usd.per_day)} />
            <Fact label="Model spend per day" value={usd(c.inference_max_usd_per_day)} />
            <Fact label="Minimum price" value={usd(c.min_price_usd)} />
            <Fact label="TEE-only models" value={p.privacy.tee_only ? "yes" : "no"} tone={p.privacy.tee_only ? "plain" : "warn"} />
          </Rail>
          <Rail title="Revenue split">
            {p.revenue_split.length === 0
              ? <Fact label="Split" value="none" tone="quiet" />
              : p.revenue_split.map((s) => <Fact key={s.account} label={s.label || s.account} value={`${(s.bps / 100).toFixed(2)}% · ${s.account}`} />)}
          </Rail>
          <Rail title={`Version history (in force: v${version})`}>
            {history.map((h) => (
              <div key={h.version} className="px-4 py-2.5">
                <p className="font-mono text-xs">
                  v{h.version}{h.active ? " · in force" : ""}
                </p>
                <p className="text-muted-foreground mt-0.5 text-[11px]">{h.changed_by} · {when(h.at)}</p>
                {h.note && <p className="text-muted-foreground mt-0.5 text-[11px]">{h.note}</p>}
              </div>
            ))}
          </Rail>
        </aside>
      </div>
    </main>
  );
}
