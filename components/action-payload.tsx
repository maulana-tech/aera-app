import { cn } from "@/lib/utils";

/* An action's payload is what a person is being asked to approve, so it has to
 * read like a sentence someone could check, not like the dict it is stored as.
 * "cost_idr=22000000" tells a buyer nothing. */

const LABELS: Record<string, string> = {
  material: "Material",
  supplier: "Supplier",
  from_plant: "From plant",
  to_plant: "To plant",
  qty: "Quantity",
  needed_by: "Needed by",
  cost_idr: "Value",
  role: "Told",
  message: "Message",
  reference: "Reference",
};

// Order matters: money last, so the eye lands on it.
const ORDER = ["material", "supplier", "from_plant", "to_plant", "qty",
               "needed_by", "role", "message", "reference", "cost_idr"];

const idr = (n: number) => "Rp " + n.toLocaleString("en-US");

export function ActionPayload({ payload }: { payload: Record<string, any> }) {
  const keys = Object.keys(payload)
    .filter((k) => !k.startsWith("_"))
    .sort((a, b) => {
      const ia = ORDER.indexOf(a), ib = ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });

  return (
    <dl className="mt-3 grid gap-x-8 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
      {keys.map((k) => {
        const money = k === "cost_idr";
        return (
          <div key={k} className="min-w-0">
            <dt className="text-muted-foreground text-xs">{LABELS[k] ?? k}</dt>
            <dd
              className={cn(
                "mt-0.5 truncate font-mono text-sm tabular-nums",
                money && "font-medium",
              )}
            >
              {money && typeof payload[k] === "number" ? idr(payload[k]) : String(payload[k])}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
