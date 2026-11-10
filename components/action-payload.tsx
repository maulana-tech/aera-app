import { usd } from "@/app/lib";
import { cn } from "@/lib/utils";

/* An action's payload, as a person approving it needs to read it.
 * Field names are the tools' (tools/money.py, tools/messaging.py); a label
 * says what each one is, and money reads as money, not "amount_usd=12". */
const LABELS: Record<string, string> = {
  receiver: "Pays to",
  to: "To",
  contact_id: "Contact",
  order_id: "Order",
  amount_usd: "Amount",
  token: "Token",
  purpose: "For",
  reference: "Reference",
  reason: "Reason",
  subject: "Subject",
  channel: "Channel",
  offering: "Offering",
  document: "Document",
};

const ORDER = ["receiver", "to", "contact_id", "order_id", "amount_usd", "token", "purpose",
               "reference", "reason", "channel", "offering", "document", "subject", "body"];

/** Long text: given the full row and allowed to wrap. */
const PROSE = new Set(["reason", "purpose", "body", "message", "text"]);
/** Shown elsewhere on the page (the guardian's ruling) or internal. */
const HIDDEN = new Set(["guardian", "to_source"]);

const isMoney = (k: string) => k.endsWith("_usd");

function show(v: unknown): string {
  if (v === null || v === undefined || v === "") return "-";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function ActionPayload({ payload }: { payload: Record<string, unknown> }) {
  const email = typeof payload.subject === "string" && typeof payload.body === "string";
  const keys = Object.keys(payload)
    .filter((k) => !k.startsWith("_") && !HIDDEN.has(k) && !(email && (k === "subject" || k === "body" || k === "to")))
    .sort((a, b) => {
      const ia = ORDER.indexOf(a), ib = ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });

  return (
    <>
      <dl className="mt-3 grid gap-x-8 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
        {keys.map((k) => {
          const money = isMoney(k) && typeof payload[k] === "number";
          const prose = PROSE.has(k);
          return (
            <div key={k} className={prose ? "col-span-full min-w-0" : "min-w-0"}>
              <dt className="text-muted-foreground text-xs">{LABELS[k] ?? k.replace(/_/g, " ")}</dt>
              <dd className={cn("mt-0.5 font-mono text-sm tabular-nums", money && "font-medium",
                                prose ? "break-words whitespace-pre-wrap" : "truncate")}>
                {money ? usd(payload[k] as number) : show(payload[k])}
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
