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
  unit_price_idr: "Unit price",
  quotation: "Quotation",
  lead_time_days: "Lead time",
  tkdn_certified_pct: "TKDN cert %",
  rationale: "Why",
  cost_idr: "Value",
  role: "Told",
  message: "Message",
  reference: "Reference",
  plant: "Plant",
  new_level: "New floor",
  sales_order: "Customer order",
  customer: "Customer",
  customer_name: "Customer name",
  finished_good: "Product",
  requested_date: "Requested",
  new_date: "Now expected",
  purchase_order: "Purchase order",
  delivery_date: "Promised",
  revised_date: "Revised",
  question: "Question",
};

// An outward message carries the email itself. Those fields are shown as the
// email, once, rather than as a row each beside the text they were made from.
const EMAIL = new Set(["to", "to_source", "to_origin", "subject", "body", "message", "question"]);

// Order matters: money last, so the eye lands on it.
const ORDER = ["sales_order", "customer", "customer_name", "purchase_order", "material",
               "finished_good", "supplier", "plant", "from_plant", "to_plant", "qty",
               "new_level", "needed_by", "requested_date", "delivery_date", "revised_date",
               "new_date", "unit_price_idr", "quotation", "lead_time_days",
               "tkdn_certified_pct", "role", "message", "question", "reference", "cost_idr"];

// Fields that are a sentence rather than a fact. Truncating one would cut the
// only part the approver has to read, so they take the whole row instead.
const PROSE = new Set(["rationale", "message", "question"]);

const idr = (n: number) => "Rp " + n.toLocaleString("en-US");

export function ActionPayload({ payload }: { payload: Record<string, unknown> }) {
  const email = typeof payload.subject === "string" && typeof payload.body === "string";
  const keys = Object.keys(payload)
    .filter((k) => !k.startsWith("_") && !(email && EMAIL.has(k)))
    .sort((a, b) => {
      const ia = ORDER.indexOf(a), ib = ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });

  return (
    <>
    <dl className="mt-3 grid gap-x-8 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
      {keys.map((k) => {
        const money = k === "cost_idr" || k === "unit_price_idr";
        const prose = PROSE.has(k);
        return (
          <div key={k} className={prose ? "col-span-full min-w-0" : "min-w-0"}>
            <dt className="text-muted-foreground text-xs">{LABELS[k] ?? k}</dt>
            <dd
              className={cn(
                "mt-0.5 font-mono text-sm tabular-nums",
                money && "font-medium",
                prose ? "break-words whitespace-pre-wrap" : "truncate",
              )}
            >
              {money && typeof payload[k] === "number" ? idr(payload[k]) : String(payload[k])}
            </dd>
          </div>
        );
      })}
    </dl>
    {email && (
      <div className="bg-muted/40 mt-3 rounded-md border px-4 py-3">
        <p className="text-muted-foreground text-xs">
          To{" "}
          <span className="text-foreground font-mono">{payload.to ? String(payload.to) : "no address on record"}</span>
          {payload.to_source ? <span> · from {String(payload.to_source)}</span> : null}
        </p>
        <p className="mt-1 text-sm font-medium">{String(payload.subject)}</p>
        <p className="mt-2 text-sm leading-relaxed break-words whitespace-pre-wrap">{String(payload.body)}</p>
      </div>
    )}
    </>
  );
}
