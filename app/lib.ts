export const UPSTREAM = process.env.SIGAP_API ?? "http://127.0.0.1:8787";

export type Step = {
  seq: number; stage: string; agent: string; agent_name: string;
  summary: string; tools: string[]; origin: string | null; source: string | null;
  detail: Record<string, unknown>; at: string;
};
export type Action = {
  id: string; kind: string; autonomous: number; status: string;
  payload: Record<string, any>; sap_reference: string | null; created_at: string;
};
export type Approval = {
  id: number; action_id: string; decided_by: string; role: string;
  decision: string; note: string | null; at: string;
};
export type Run = {
  id: string; title: string; kind: string; trigger: string;
  signal_source?: string;
  mode: "autonomous" | "guided"; status: string;
  started_at: string; finished_at: string | null;
  token_cost_idr: number; decision: Record<string, any> | null; error: string | null;
  steps?: Step[]; actions?: Action[]; approvals?: Approval[];
};

export const idr = (n: number) => "Rp " + (n ?? 0).toLocaleString("en-US");

export type Me = { name: string; email: string; role: string; limit_idr: number };

/** Call the agent service, carrying the session token from the httpOnly cookie. */
export async function api<T>(path: string): Promise<T | null> {
  const { cookies } = await import("next/headers");
  const token = (await cookies()).get("sigap_session")?.value;
  try {
    const r = await fetch(`${UPSTREAM}/${path}`, {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

export async function me(): Promise<Me | null> {
  return api<Me>("me");
}

export type Tool = { name: string; installed: boolean; description: string | null };
export type Agent = {
  code: string; nickname: string; title: string; brief: string; effort: string;
  veto: boolean; lead: boolean; ready: boolean; tools: Tool[];
  installed: number; tool_count: number; used_in: number;
};
export type AgentSummary = {
  agent_count: number; tools_installed: number; tools_total: number;
  prompts_written: number; model_ready: boolean; sap_ready: boolean;
};

export type Column = { k: string; l: string; n?: boolean; rp?: boolean };

/* One chart payload per domain, discriminated on `kind`.
 *
 * A view carries at most one chart, and the shape of that chart is a property
 * of the domain, so a union with a tag is what the data actually is. A bag of
 * optional fields would let a page ask for the demand band on stock data and
 * find out at render time.
 */
export type DemandChartData = {
  kind: "demand";
  material: string; plant: string; unit: string; confidence: number;
  planned_rate: number | null; mape_pct: number | null;
  observed: { on: string; qty: number; mean: number }[];
  window_days?: number;
  points: { on: string; point: number; lower: number; upper: number }[];
};
export type CoverChartData = {
  kind: "cover";
  unit: string;
  /** every line the table shows, so the chart can say how much it left out */
  total: number;
  threshold: number;
  threshold_label: string;
  items: {
    material: string; plant: string; description: string;
    days: number; qty: number; unit: string; daily: number;
    depleted_on: string | null;
  }[];
};
export type ArrivalChartData = {
  kind: "arrival";
  total: number;
  /** the scenario's as-of date, which is what "today" means on this page */
  today: string;
  items: {
    reference: string; material: string; port: string; status: string;
    booked: string; revised: string; slip: number;
  }[];
};
/* Concentration, as a Pareto: each supplier's share of the purchase-order book
 * against the running total. Both series are percentages of the same book, so
 * they share one axis — a second scale would let a bar and a line wear the same
 * unit and mean two different things.
 */
export type PortfolioChartData = {
  kind: "portfolio";
  /** suppliers on the approved list */
  total: number;
  /** of those, the ones that actually hold orders */
  active: number;
  /** the cumulative share the rule is drawn at */
  rule_pct: number;
  /** how many suppliers it takes to reach rule_pct — the point of the chart */
  cover_n: number;
  items: {
    supplier: string; name: string; country: string;
    share: number; cumulative: number;
    volume: number; unit: string | null;
    orders: number; late: number; slip: number | null; tkdn: number | null;
  }[];
};
/* The quotation comparison: price against lead time, one dot per offer.
 *
 * Those two are different units, and there is no honest way to put them on one
 * axis or on two that share a name — a rupiah and a day drawn as a bar and a
 * line would be two scales arguing about which is which. A scatter sidesteps it:
 * one axis each, and the shape of the cloud is the trade-off itself. Bottom-left
 * is cheap and quick, which is where nobody stays for long.
 */
export type OffersChartData = {
  kind: "offers";
  material: string;
  /** the purchasing unit the price is quoted in, such as TON */
  unit: string;
  /** the quantity every offer in this comparison was priced for */
  qty: number;
  /** offers still valid on the as-of date */
  live: number;
  total: number;
  points: {
    supplier: string; name: string; country: string;
    price: number; lead: number;
    live: boolean;
    /** on the line nothing beats on both axes at once */
    on_line: boolean;
    tkdn: number | null;
  }[];
};
export type DomainChart =
  | DemandChartData | CoverChartData | ArrivalChartData | PortfolioChartData
  | OffersChartData;

/** One table row. Keys are the column `k`s, so a view can hand its columns and
 *  its rows straight to DataTable without remapping either. */
export type Row = Record<string, any>;

/* One section of an agent's desk: a heading, the finding under it, a table, and
 * a chart when the domain has one. Most domains have exactly one section and
 * return its fields flat; a desk with two questions to answer returns `sections`
 * instead, and the page renders both shapes the same way.
 */
export type ViewSection = {
  title: string;
  note?: string;
  columns: Column[];
  rows: Row[];
  origin: string;
  source: string;
  chart?: DomainChart;
};

export type View = {
  domain: string; agent: string;
  columns?: Column[]; rows?: Row[];
  origin?: string; source?: string; note?: string;
  chart?: DomainChart;
  sections?: ViewSection[];
};
export type Summary = {
  runs: Record<string, number>; actions: Record<string, number>;
  approved_value_idr: number; pending_value_idr: number; model_cost_idr: number;
  critical_stock: { material: string; description: string; plant: string;
                    days_left: number | null; depleted_on: string | null }[];
  recent: { title: string; status: string; started_at: string }[];
  sap_ready: boolean; model_ready: boolean;
};
export type Upload = {
  id: string; entity: string; filename: string; rows: number;
  uploaded_by: string; uploaded_at: string; synthetic?: number;
};
export type Contact = {
  id: string; name: string; role: string; email: string; notify_for: string;
};

export type Finding = {
  severity: "critical" | "serious" | "warning" | "note";
  category: string;
  title: string;
  detail: string;
  evidence: string[];
  value_idr: number | null;
  action: string;
};
export type AuditReport = {
  findings: Finding[];
  counts: Record<string, number>;
  coverage: Record<string, number>;
  origins: Record<string, { origin: string; source: string; note: string }>;
  weakest_origin: string;
  note: string;
};
