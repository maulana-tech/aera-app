"use client";

import { Briefcase, Inbox, Landmark, Users } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Chip, Dot } from "@/components/dort";
import { cn } from "@/lib/utils";
import { Approve } from "./app-tour";

/*
 * 'How it works', after the Dort landing's 'Four layers, one local run': a huge faint index, the steps on
 * the left as you scroll, and on the right one product window that holds still and changes with the step
 * in view. On phones every step shows its own window inline.
 */

function Profile() {
  return (
    <div className="space-y-2.5 text-[12.5px]">
      <div className="flex items-center gap-2"><Briefcase className="text-brand size-4" /><span className="text-fg text-[14px]">Lumen Research</span><Chip tone="ok" className="ml-auto">v7 in force</Chip></div>
      <p className="text-body">Short, sourced market briefs for founders and small businesses in Southeast Asia.</p>
      {[["Offering", "Market brief (5 pages) · $15.00 · PDF in 2 h"], ["Ideal customer", "Agencies and founders in Indonesia"],
        ["On its own", "up to $5.00 a payment, $20.00 a day"], ["Always a person", "refunds · new vendors · discounts · first messages"],
        ["Never", "promise investment returns"]].map(([k, v]) => (
        <div key={k} className="bg-inner-grad flex gap-3 rounded-md border px-3 py-2"><span className="text-muted-foreground w-28 shrink-0">{k}</span><span className="text-fg">{v}</span></div>
      ))}
    </div>
  );
}

function Team() {
  const roles: [string, boolean][] = [["Supervisor", true], ["Guardian", true], ["Treasurer", true], ["Lead Researcher", false], ["Sales", false],
    ["Researcher", false], ["Writer", false], ["Quality Review", false], ["Fulfilment", false], ["Finance", false], ["Legal & Compliance", false]];
  return (
    <div>
      <div className="flex items-center gap-2"><Users className="text-brand size-4" /><span className="text-fg text-[14px]">The Composer proposes</span><span className="text-muted-foreground ml-auto font-mono text-[11px]">11 agents</span></div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {roles.map(([r, core], i) => (
          <span key={r} style={{ animationDelay: `${i * 60}ms` }}
            className={cn("animate-in fade-in zoom-in-95 inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[12px] duration-500",
              core ? "bg-brand text-white" : "bg-raised text-text")}>
            <span className={cn("size-1.5 rounded-full", core ? "bg-white" : "bg-info")} />{r}
          </span>
        ))}
      </div>
      <p className="text-body mt-4 text-[12.5px] leading-relaxed">The same profile always yields the same team. Treasury, guardian and supervisor are locked to their roles in code.</p>
    </div>
  );
}

function Queue() {
  const items: [string, string, "ok" | "info" | "warn"][] = [
    ["order", "Order ord_7f2a: market brief · $15.00 paid", "ok"],
    ["goal", "Weekly: publish one free sample brief", "info"],
    ["reply", "Reply from Rina S. (Studio Kopi Digital)", "info"],
    ["follow_up", "Follow up with Dewi P. (1 of 2)", "warn"],
  ];
  return (
    <div>
      <div className="flex items-center gap-2"><Inbox className="text-brand size-4" /><span className="text-fg text-[14px]">Work</span><span className="text-muted-foreground ml-auto font-mono text-[11px]">every 20 s</span></div>
      <ul className="mt-3 space-y-1.5">
        {items.map(([k, t, tone], i) => (
          <li key={t} style={{ animationDelay: `${i * 90}ms` }} className="bg-inner-grad animate-in fade-in slide-in-from-right-2 flex items-center gap-2.5 rounded-md border px-3 py-2 text-[12.5px] duration-500">
            <Dot tone={tone} /><span className="text-muted-foreground w-[4.6rem] shrink-0 font-mono text-[10.5px]">{k}</span><span className="text-fg truncate">{t}</span>
          </li>
        ))}
      </ul>
      <p className="text-body mt-4 text-[12.5px] leading-relaxed">Paid orders, standing goals, replies and follow-ups each become a work item; the Supervisor delegates one step at a time.</p>
    </div>
  );
}

const STEPS = [
  { title: "Describe the business", lead: "What you sell, to whom, at what price, and what the team may never do. Or write a paragraph and a TEE model drafts it.", icon: Briefcase, view: <Profile /> },
  { title: "Get a team", lead: "The Composer turns the profile into roles with capabilities, not loose tools. Three core roles are always there.", icon: Users, view: <Team /> },
  { title: "Work arrives", lead: "The scheduler hands work to the team every 20 seconds, with no one typing: orders, goals, replies, follow-ups.", icon: Inbox, view: <Queue /> },
  { title: "Approve what passes the limits", lead: "Small things run alone. Above the caps a person decides, and the vault holds the money until they sign.", icon: Landmark, view: <Approve /> },
];

export function Steps() {
  const [on, setOn] = useState(0);
  const refs = useRef<(HTMLDivElement | null)[]>([]);
  useEffect(() => {
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) setOn(Number((e.target as HTMLElement).dataset.i));
    }, { rootMargin: "-45% 0px -45% 0px" });
    for (const el of refs.current) if (el) io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <section id="how-it-works" className="relative mx-auto max-w-[1240px] scroll-mt-24 px-4 py-24 md:px-6 md:py-32">
      <p className="lp-eyebrow"><span className="size-1.5 rounded-full bg-white/60" />How it works</p>
      <h2 className="mt-5 text-[clamp(32px,4.2vw,56px)] leading-[1.05] font-light tracking-[-0.03em] text-white">
        Four steps,<br /><span className="text-white/55">one running business.</span>
      </h2>

      <div className="mt-14 grid gap-10 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div>
          {STEPS.map((s, i) => {
            const I = s.icon;
            return (
              <div key={s.title} ref={(el) => { refs.current[i] = el; }} data-i={i} data-on={on === i}
                className="lw-step flex min-h-[46vh] flex-col justify-center border-t border-white/10 py-10 first:border-t-0 lg:min-h-[62vh]">
                <div className="flex items-center gap-3">
                  <span className="grid size-9 place-items-center rounded-full border border-white/20 bg-white/10 text-white"><I className="size-4" /></span>
                  <span className="text-on-canvas-dim font-mono text-[12px]">{String(i + 1).padStart(2, "0")} / 04</span>
                </div>
                <h3 className="mt-4 text-[24px] leading-tight text-white md:text-[28px]">{s.title}</h3>
                <p className="text-on-canvas-dim mt-3 max-w-[440px] text-[15px] leading-relaxed">{s.lead}</p>
                <div className="mt-6 lg:hidden">
                  <div className="bg-card-grad rounded-2xl border p-4 shadow-soft">{s.view}</div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="relative hidden lg:block">
          <div className="sticky top-[18vh]">
            <p aria-hidden="true" className="pointer-events-none absolute -top-24 right-0 font-mono text-[160px] leading-none font-light tracking-[-0.06em] text-white/[0.08] tabular-nums">
              {String(on + 1).padStart(2, "0")}
            </p>
            <div className="lp-blue-card relative rounded-[24px] p-6">
              <div className="bg-card-grad shadow-float relative min-h-[380px] rounded-2xl border p-5">
                {STEPS.map((s, i) => (
                  <div key={s.title} aria-hidden={on !== i}
                    className={cn("lw-view absolute inset-5", on === i ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-2 opacity-0")}>
                    {on === i && s.view}
                  </div>
                ))}
              </div>
              <div className="mt-5 flex items-center justify-center gap-2">
                {STEPS.map((s, i) => (
                  <span key={s.title} className={cn("h-1.5 rounded-full transition-all", on === i ? "w-6 bg-white" : "w-1.5 bg-white/35")} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
