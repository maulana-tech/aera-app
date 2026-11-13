import { ExternalLink } from "lucide-react";
import Link from "next/link";

import { api, apiResult, mayManage, me, usd, when, type LeadDetail, type LeadsPayload } from "@/app/lib";
import { Empty, Fact, Metric, PageHeader, Rail, Section } from "@/components/shell";
import { StatusBadge } from "@/components/status-badge";
import { LeadActions, PasteReply } from "./LeadActions";

export const dynamic = "force-dynamic";

const pct = (x: number | null) => (x == null ? "-" : `${Math.round(x * 100)}%`);
const STAGE_LABEL: Record<string, string> = {
  new: "found", contacted: "written to", replied: "answered", interested: "interested", won: "won",
  lost: "lost", no_reply: "no answer", opted_out: "asked to stop",
};

function Setup({ s }: { s: LeadsPayload["setup"] }) {
  const rows: [string, boolean, string][] = [
    ["Web search", s.search !== "duckduckgo", s.search === "duckduckgo"
      ? "keyless DuckDuckGo, best effort: set AERA_BRAVE_API_KEY or AERA_TAVILY_API_KEY (free tiers)"
      : `${s.search}`],
    ["E-mail out", s.email_out, s.email_out ? "SMTP or Gmail connected" : "set AERA_SMTP_HOST and AERA_MAIL_FROM, or connect Gmail"],
    ["Outside this install", s.outward_redirect, s.outward_redirect
      ? "production, or redirected to a test address"
      : "not production and no AERA_EXTERNAL_REDIRECT: approved messages are recorded, not sent"],
    ["Inbox", s.inbox || s.inbound_webhook, s.inbox ? "IMAP read every 2 minutes"
      : s.inbound_webhook ? "forwarded to /public/inbound/email" : `paste replies here, or set ${s.inbox_missing.join(", ")}`],
  ];
  return (
    <ul className="space-y-2 text-xs">
      {rows.map(([k, ok, v]) => (
        <li key={k}>
          <div className="flex items-center gap-2"><StatusBadge status={ok ? "ok" : "off"}>{ok ? "on" : "off"}</StatusBadge>
            <span className="font-medium">{k}</span></div>
          <p className="text-muted-foreground mt-0.5 leading-relaxed">{v}</p>
        </li>
      ))}
    </ul>
  );
}

export default async function LeadsPage({ searchParams }: { searchParams: Promise<{ stage?: string; lead?: string }> }) {
  const sp = await searchParams;
  const [res, user] = await Promise.all([
    apiResult<LeadsPayload>(`leads${sp.stage ? `?stage=${encodeURIComponent(sp.stage)}` : ""}`), me(),
  ]);
  const detail = sp.lead ? await api<LeadDetail>(`leads/${encodeURIComponent(sp.lead)}`) : null;
  if (!res.data) {
    return (
      <main className="w-full px-4 py-4 md:px-6 md:py-8">
        <PageHeader title="Leads" />
        <p className="text-muted-foreground mt-6 text-sm">{res.error}</p>
      </main>
    );
  }
  const d = res.data;
  const f = d.funnel;
  const manage = mayManage(user);

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Leads"
        lead={d.settings.ideal_customer
          ? <>The team looks for: <span className="text-foreground">{d.settings.ideal_customer}</span>. Every lead carries the public page
            that shows its address; the first message to anyone waits for your approval in Treasury; follow-ups go on
            day {d.settings.follow_up_days.slice(0, d.settings.follow_ups).join(" and ")} only while nobody has answered; a reply asking to stop is final.</>
          : "Set the ideal customer in Business (Prospecting) and the team composes a Lead Researcher and Sales to find and write to them."}
      />

      <div className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-5">
        <Metric label="Leads found (30 days)" value={String(f.leads)} />
        <Metric label="Written to" value={String(f.contacted)} note={`${d.today} of ${d.settings.per_day} cold today`} />
        <Metric label="Answered" value={String(f.replied)} note={`reply rate ${pct(f.reply_rate)}`} />
        <Metric label="Won" value={String(f.won)} note={f.revenue_usd ? `${usd(f.revenue_usd)} revenue` : `win rate ${pct(f.win_rate)}`} />
        <Metric label="AI per lead" value={f.cost_per_lead_usd == null ? "-" : usd(f.cost_per_lead_usd, { precise: true })}
          note={f.cost_per_win_usd == null ? `${usd(f.model_spend_usd, { precise: true })} in all` : `${usd(f.cost_per_win_usd, { precise: true })} a win`} />
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0">
          <nav className="flex flex-wrap gap-2 text-xs">
            <Link href="/leads" className={`rounded-full border px-2.5 py-1 ${!sp.stage ? "bg-raised font-medium" : ""}`}>all</Link>
            {Object.entries(d.counts).map(([k, n]) => (
              <Link key={k} href={`/leads?stage=${k}`}
                className={`rounded-full border px-2.5 py-1 ${sp.stage === k ? "bg-raised font-medium" : ""}`}>
                {STAGE_LABEL[k] ?? k} <span className="text-muted-foreground font-mono">{n}</span>
              </Link>
            ))}
          </nav>

          {detail && (
            <Section title={`${detail.lead.name} · ${detail.lead.company}`} className="mt-6"
              action={<Link href={`/leads${sp.stage ? `?stage=${sp.stage}` : ""}`} className="text-muted-foreground text-xs underline">close</Link>}>
              <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
                <Fact label="Stage" value={<StatusBadge status={detail.lead.stage}>{STAGE_LABEL[detail.lead.stage]}</StatusBadge>} />
                <Fact label="Address" value={detail.lead.email} mono />
                <Fact label="Fit" value={`${detail.lead.fit_score}/100 · ${detail.lead.why_fit || "-"}`} />
                <Fact label="Found on" value={<a href={detail.lead.source_url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 break-all underline underline-offset-2">{detail.lead.source_url} <ExternalLink className="size-3 shrink-0" /></a>} />
                <Fact label="Messages delivered" value={String(detail.lead.step)} />
                <Fact label="Next follow-up" value={detail.lead.next_follow_up_at ? when(detail.lead.next_follow_up_at) : "-"} />
                {detail.lead.note && <Fact label="Note" value={detail.lead.note} tone="quiet" />}
                {detail.optout && <Fact label="Asked to stop" value={`${when(detail.optout.at)} · ${detail.optout.reason}`} tone="warn" />}
              </div>
              {manage && <div className="mt-4"><LeadActions id={detail.lead.id} stage={detail.lead.stage} /></div>}

              <h3 className="mt-6 text-sm font-medium">What we wrote</h3>
              {detail.messages.length === 0 ? <p className="text-muted-foreground mt-2 text-sm">Nothing yet.</p> : (
                <ul className="mt-2 space-y-3">
                  {detail.messages.map((m) => (
                    <li key={m.action_id} className="rounded-lg border p-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <StatusBadge status={m.status} />
                        {m.delivery && <StatusBadge status={m.delivery}>{`e-mail ${m.delivery}`}</StatusBadge>}
                        <span className="text-muted-foreground">{m.kind?.replace("_", " ")}</span>
                        <Link href={`/work/${m.run_id}`} className="text-muted-foreground ml-auto font-mono text-[10px] underline">{when(m.created_at)}</Link>
                      </div>
                      <p className="mt-2 text-sm font-medium">{m.subject}</p>
                      <p className="text-muted-foreground mt-1 whitespace-pre-wrap text-xs leading-relaxed">{m.body}</p>
                      {(m.reason || m.delivery_error) && <p className="mt-2 text-[11px] text-warn">{m.delivery_error || m.reason}</p>}
                    </li>
                  ))}
                </ul>
              )}

              <h3 className="mt-6 text-sm font-medium">What they wrote</h3>
              {detail.received.length === 0 ? <p className="text-muted-foreground mt-2 text-sm">Nothing yet.</p> : (
                <ul className="mt-2 space-y-3">
                  {detail.received.map((r) => (
                    <li key={r.id} className="rounded-lg border p-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <StatusBadge status={r.kind === "unsubscribe" ? "opted_out" : r.kind === "reply" ? "replied" : "skipped"}>{r.kind.replace("_", " ")}</StatusBadge>
                        <span className="text-muted-foreground">via {r.via}</span>
                        <span className="text-muted-foreground ml-auto font-mono text-[10px]">{when(r.received_at)}</span>
                      </div>
                      <p className="mt-2 text-sm font-medium">{r.subject || "(no subject)"}</p>
                      <p className="text-muted-foreground mt-1 whitespace-pre-wrap text-xs leading-relaxed">{r.body.slice(0, 1500)}</p>
                      {r.work_item_id && <p className="text-muted-foreground mt-2 font-mono text-[10px]">handed to the team as {r.work_item_id}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          )}

          <Section title={`Pipeline (${d.leads.length})`} className="mt-6">
            {d.leads.length === 0 ? (
              <Empty what="No leads yet" why="Leads come from the Lead Researcher, on a standing goal or a request in Work."
                fix={'Add a goal such as "Find five new prospects that fit the ideal customer each week" in Business.'} />
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="text-muted-foreground bg-raised text-left text-[11px] uppercase tracking-wide">
                    <tr><th className="px-4 py-2">Stage</th><th className="px-4 py-2">Who</th><th className="px-4 py-2">Company</th>
                      <th className="px-4 py-2 text-right">Fit</th><th className="px-4 py-2 text-right">Sent</th><th className="px-4 py-2">Next</th></tr>
                  </thead>
                  <tbody className="divide-y">
                    {d.leads.map((l) => (
                      <tr key={l.id} className="align-top">
                        <td className="px-4 py-2.5"><StatusBadge status={l.stage}>{STAGE_LABEL[l.stage]}</StatusBadge></td>
                        <td className="px-4 py-2.5">
                          <Link href={`/leads?lead=${l.id}${sp.stage ? `&stage=${sp.stage}` : ""}`} className="font-medium underline-offset-2 hover:underline">{l.name}</Link>
                          <p className="text-muted-foreground font-mono text-[11px]">{l.email}</p>
                        </td>
                        <td className="px-4 py-2.5">{l.company}{l.title && <p className="text-muted-foreground text-[11px]">{l.title}</p>}</td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums">{l.fit_score}</td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums">{l.step}</td>
                        <td className="text-muted-foreground px-4 py-2.5 font-mono text-[10px]">{l.next_follow_up_at ? when(l.next_follow_up_at) : "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>
        </div>

        <aside className="space-y-6">
          <Rail title="Set up">
            <Setup s={d.setup} />
          </Rail>
          {manage && (
            <Rail title="A reply came in">
              <p className="text-muted-foreground mb-3 text-xs leading-relaxed">
                No inbox connected? Paste it here. A reply from a lead goes to the team as work; a request to stop opts the address out at once.
              </p>
              <PasteReply />
            </Rail>
          )}
          <Rail title="Rules held in code">
            <ul className="text-muted-foreground list-disc space-y-1.5 pl-4 text-xs leading-relaxed">
              <li>An address is saved only when the page it was found on shows it.</li>
              <li>The first message to a lead waits for a person; one message per lead waits at a time.</li>
              <li>At most {d.settings.per_day} cold messages a day; {d.settings.follow_ups} follow-up(s), never early.</li>
              <li>Every message says who it is from and how to stop it.</li>
              <li>{f.opted_out_total} address(es) asked to stop: the Guardian blocks any message to them, forever.</li>
              <li>A lead is won by a paid order from its address, not by an agent saying so.</li>
            </ul>
          </Rail>
        </aside>
      </div>
    </main>
  );
}
