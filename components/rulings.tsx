import { cn } from "@/lib/utils";

export type Ruling = {
  id: string;
  option: string;
  allowed: boolean | null;
  reason: string | null;
  tkdn_before: number;
  tkdn_after: number | null;
  tkdn_floor: number;
  cost_idr: number;
  arrival_booked: string;
  arrival_effective: string | null;
  origin_country: string;
  new_origin: boolean;
};

const idr = (n: number) => "Rp " + n.toLocaleString("en-US");

/** Where a local-content ratio lands against the contract floor.
 *
 *  Same visual language as the charts: one hue, a dashed rule for the
 *  threshold. A blocked option is hatched rather than recoloured, because
 *  red against green fails the colour-blind separation check.
 */
function TkdnMeter({ before, after, floor, blocked }: {
  before: number; after: number; floor: number; blocked: boolean;
}) {
  const span = Math.max(after, before, floor) * 1.15;
  const pos = (v: number) => `${(v / span) * 100}%`;
  const worse = after < before;
  const gap = +(after - floor).toFixed(1);
  const move = +(after - before).toFixed(1);

  return (
    <div className="viz group/meter mt-2 max-w-md">
      <div className="flex items-baseline gap-2 font-mono text-xs tabular-nums">
        <span className="text-muted-foreground">{before}%</span>
        <span className="text-muted-foreground" aria-hidden>{"→"}</span>
        <span className={cn("font-medium", worse && "text-amber-700 dark:text-amber-400")}>
          {after}%
        </span>
        <span className="text-muted-foreground ml-1 text-[11px]">
          contract floor {floor}%
        </span>
      </div>
      <div
        className="relative mt-1.5 h-2 rounded-md"
        style={{ background: "var(--viz-track)" }}
      >
        <div
          className="absolute inset-y-0 left-0 rounded-md"
          style={{
            width: pos(after),
            background: blocked
              ? "repeating-linear-gradient(45deg, var(--viz-series) 0 2px, transparent 2px 5px)"
              : "var(--viz-series)",
            boxShadow: blocked ? "inset 0 0 0 1px var(--viz-series)" : undefined,
          }}
        />
        <span
          aria-hidden
          className="absolute -inset-y-1 w-0 border-l border-dashed"
          style={{ left: pos(floor), borderColor: "var(--viz-rule)" }}
        />
      </div>

      {/* Reserved height, so pointing at the bar does not nudge the page. */}
      <p className="text-muted-foreground mt-1 h-4 font-mono text-[11px] opacity-0 transition-opacity group-hover/meter:opacity-100">
        {move === 0
          ? "no change to local content"
          : `${move > 0 ? "up" : "down"} ${Math.abs(move)} points`}
        {", "}
        {gap >= 0
          ? `${gap} above the floor`
          : `${Math.abs(gap)} below the floor`}
      </p>
    </div>
  );
}

export function RulingList({ rulings }: { rulings: Ruling[] }) {
  return (
    <ul className="divide-y rounded-lg border">
      {rulings.map((r) => {
        const blocked = r.allowed === false;
        const slipped =
          r.arrival_effective && r.arrival_effective !== r.arrival_booked;
        return (
          <li key={r.id} className="px-5 py-4">
            <div className="max-w-3xl">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-muted-foreground font-mono text-xs">{r.id}</span>
              <h3 className="text-sm font-medium">{r.option}</h3>
              <span
                className={cn(
                  "font-mono text-[11px]",
                  blocked ? "text-amber-700 dark:text-amber-400" : "text-muted-foreground",
                )}
              >
                {blocked ? "blocked" : "allowed"}
              </span>
              <span className="text-muted-foreground ml-auto font-mono text-xs tabular-nums">
                {idr(r.cost_idr)}
              </span>
            </div>

            {r.tkdn_after !== null && (
              <TkdnMeter
                before={r.tkdn_before}
                after={r.tkdn_after}
                floor={r.tkdn_floor}
                blocked={blocked}
              />
            )}

            {r.reason && (
              <p className="text-muted-foreground mt-2.5 max-w-2xl text-xs leading-relaxed">
                {r.reason}
              </p>
            )}

            {slipped && (
              <p className="text-muted-foreground mt-1.5 font-mono text-[11px]">
                arrives {r.arrival_booked}, effective {r.arrival_effective}
              </p>
            )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
