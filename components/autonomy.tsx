import Link from "next/link";

import { usd, type EconomicsPayload } from "@/app/lib";
import { Dot } from "@/components/dort";

/** How much ran without a person, and whether each order paid for itself. Every figure is counted by
 *  the agent service (core/economics.py); this only lays it out. */
export function Autonomy({ data }: { data: EconomicsPayload }) {
  const a = data.autonomy;
  const e = data.economics;
  const pct = a.autonomy_pct;
  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-medium">Autonomy ({a.days} days)</p>
        <Link href="/agents/finance" className="text-muted-foreground text-xs hover:underline">Finance →</Link>
      </div>
      <p className="mt-2 font-mono text-2xl font-medium tabular-nums">{pct === null ? "—" : `${pct}%`}</p>
      <p className="text-muted-foreground text-xs leading-relaxed">
        of finished work needed no person ({a.done_alone} of {a.finished}). {a.stopped_by_guardian} stopped by the Guardian, with no person needed.
      </p>
      {a.touches.length > 0 && (
        <div className="mt-3">
          <p className="text-muted-foreground text-xs">A person stepped in {a.people_touches}×</p>
          <ul className="mt-1 space-y-0.5 text-xs">
            {a.touches.map((t) => (
              <li key={t.what} className="flex justify-between gap-2"><span>{t.what}</span><span className="font-mono tabular-nums">{t.count}</span></li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-4 border-t pt-3">
        <p className="text-muted-foreground text-xs">Per offering · target margin {e.target_margin_pct}% after AI</p>
        <ul className="mt-1.5 space-y-1.5 text-xs">
          {e.offerings.map((o) => (
            <li key={o.offering} className="flex flex-wrap items-center gap-x-2">
              <Dot tone={o.below_target ? "warn" : o.orders ? "ok" : "neutral"} />
              <span className="font-mono">{o.offering}</span>
              <span className="text-muted-foreground min-w-0 flex-1 text-right font-mono tabular-nums">
                {o.price_usd !== null ? usd(o.price_usd) : "—"}
                {o.ai_per_order_usd !== null ? ` · AI ${usd(o.ai_per_order_usd)}/order · floor ${usd(o.floor_price_usd ?? 0)}` : " · no orders yet"}
              </span>
            </li>
          ))}
        </ul>
        <p className="text-muted-foreground mt-3 text-xs leading-relaxed">
          Revenue {usd(e.revenue_usd)}{e.gross_margin_pct !== null && ` · ${e.gross_margin_pct}% after AI`} · overhead {usd(e.overhead.vendors_usd)} vendors + {usd(e.overhead.ai_usd)} AI outside orders · net{" "}
          <span className={e.net_usd < 0 ? "text-bad" : "text-fg"}>{usd(e.net_usd)}</span>
        </p>
      </div>
    </div>
  );
}
