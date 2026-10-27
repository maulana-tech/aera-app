export const UPSTREAM = process.env.SIGAP_API ?? "http://127.0.0.1:8787";

export type Step = {
  seq: number; stage: string; agent: string; agent_name: string;
  summary: string; tools: string[]; origin: string | null; source: string | null;
  detail: Record<string, unknown>; at: string;
};
export type Delivery = {
  to: string | null; status: string; why?: string; error?: string | null;
  reference?: string | null; sent_at?: string | null; meant_for?: string | null;
};
export type Action = {
  id: string; kind: string; autonomous: number; status: string;
  payload: Record<string, unknown>; sap_reference: string | null; created_at: string;
  /** Where an approved message to a supplier or a customer goes, or went. */
  delivery?: Delivery;
  /**
   * What actually happened, once somebody read reality: one of delivered, late,
   * short, failed, cancelled (store.OUTCOMES). Null until recorded, and written
   * only once. `outcome_detail.actual_idr` is the realized cost when it is
   * known as a figure — absent means not known, never zero.
   */
  outcome?: string | null;
  outcome_at?: string | null;
  outcome_detail?: Record<string, unknown> | null;
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
  token_cost_idr: number; decision: { recommendation?: string; reason?: string; agents_called?: string[]; untrusted_on_board?: string[] } | null; error: string | null;
  steps?: Step[]; actions?: Action[]; approvals?: Approval[];
};

export const idr = (n: number) => "Rp " + (n ?? 0).toLocaleString("en-US");

/* Jakarta, always, and labelled.
 *
 * The stamps are UTC and the PDFs and workbooks are written in WIB
 * (engine/report.py), so a page that formatted in the reader's own zone put a
 * different time on the same event than its own download did — invisible in
 * Jakarta and wrong everywhere else. One formatter, one zone, and the zone is
 * written out so nobody has to guess which one they are reading.
 */
export const WIB = "Asia/Jakarta";
export function wib(t?: string | null, opts: {
  /** false for the date alone */
  time?: boolean;
  /** seconds too, for a trace where the order of two calls is the point */
  seconds?: boolean;
  /** drop the "WIB" marker where a column header or nearby line already says it */
  mark?: boolean;
} = {}): string {
  if (!t) return "-";
  const at = new Date(t);
  if (Number.isNaN(at.getTime())) return t;
  const date = at.toLocaleDateString("en-GB", { timeZone: WIB, day: "2-digit", month: "short", year: "numeric" });
  if (opts.time === false) return date;
  const time = at.toLocaleTimeString("en-GB", {
    timeZone: WIB, hour: "2-digit", minute: "2-digit",
    ...(opts.seconds ? { second: "2-digit" } : {}),
  });
  return `${date} ${time}${opts.mark === false ? "" : " WIB"}`;
}

export type Me = { name: string; email: string; role: string; limit_idr: number };

/** Call the agent service, carrying the session token from the httpOnly cookie. */
export async function apiResult<T>(path: string): Promise<
  { data: T; error: null } | { data: null; error: string }
> {
  const { cookies } = await import("next/headers");
  const token = (await cookies()).get("sigap_session")?.value;
  try {
    const r = await fetch(`${UPSTREAM}/${path}`, {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    const body = await r.text();
    if (!r.ok) {
      let error = `The agent service returned HTTP ${r.status}`;
      try {
        const parsed = JSON.parse(body) as { error?: string };
        if (parsed.error) error = parsed.error;
      } catch {
        // An upstream proxy may return HTML. The status is safer to show than it.
      }
      return { data: null, error };
    }
    return { data: JSON.parse(body) as T, error: null };
  } catch {
    return { data: null, error: `The agent service is not responding at ${UPSTREAM}` };
  }
}

export async function api<T>(path: string): Promise<T | null> {
  return (await apiResult<T>(path)).data;
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
export type Row = Record<string, unknown>;

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
  /** the window the FLOW figures below cover; null means every handling on record */
  period?: { from: string | null; to: string | null; days: number | null; label: string } | null;
  period_label?: string;
  runs: Record<string, number>; actions: Record<string, number>;
  approved_value_idr: number; pending_value_idr: number; model_cost_idr: number;
  /** actions the system carried out on its own authority, under the limit */
  autonomous_actions?: number;
  /** the same board line the decision queue leads with */
  board?: Board;
  /** what obeying the rules cost, across every handling that priced it */
  rules_cost_idr?: number;
  rules_cost_cases?: number;
  /** the open half of the record */
  outcomes_owed?: number;
  oldest_owed_days?: number;
  /** how much of what the rulings rest on is still assumption */
  knowledge_base?: {
    pack: string | null; total: number; verified: number;
    unverified: string[]; problems: string[];
  };
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
  phone?: string | null; title?: string | null; department?: string | null;
  notes?: string | null; created_at?: string; updated_at?: string | null;
};

export type ChannelState = {
  ready: boolean; missing: string[];
  /** Email only: smtp or composio, the address it leaves from, and whether a
   * Gmail mailbox can be connected from here. */
  via?: "smtp" | "composio"; sender?: string | null; connectable?: boolean;
};
export type Notification = {
  id: string; run_id: string | null; kind: string; channel: string; address: string;
  subject: string; status: "pending" | "sent" | "failed" | "skipped"; attempts: number;
  error: string | null; created_at: string; sent_at: string | null;
  attachments?: { report: string; format: "pdf" | "xlsx" }[];
  action_id?: string | null; reference?: string | null;
};
export type NotificationsPayload = {
  channels: Record<"email" | "slack" | "telegram" | "webhook", ChannelState>;
  recent: Notification[]; web_url: string; may_change: boolean;
};

export type ScheduledJob = {
  name: string; what: string; cadence: string; signal: boolean; enabled: boolean;
  off: string | null; running: boolean; next_at: string | null;
  last_started: string | null; last_finished: string | null;
  last_status: "ok" | "failed" | null; last_detail: string | null;
  runs: number; failures: number;
};
export type SchedulePayload = {
  jobs: ScheduledJob[]; enabled: boolean; watch: boolean; may_change: boolean;
};

export type ModelListing = {
  model: string; label: string; vendor: string | null; note: string | null; via: string;
  usd_per_mtok: [number, number]; ready: boolean; why: string | null;
};
export type TeamModel = {
  agent: string; name: string; model: string; source: string; ready: boolean;
  why: string | null; fallback: string | null; fallback_ready: boolean | null;
};
export type ModelTest = { ok: boolean; said: string; seconds: number; at: string; by: string };
export type ModelsPayload = {
  catalog: ModelListing[];
  team: TeamModel[];
  fallback: string | null;
  aux: string;
  roles: { lead: string; specialists: string; fallback: string | null; aux: string };
  chosen: Record<string, { value: string; updated_by: string; updated_at: string }>;
  env: { lead: string; specialists: string | null; fallback: string | null; aux: string };
  tested: Record<string, ModelTest>;
  may_change: boolean;
  idr_per_usd: number;
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

/* The exploration graph (core/exploration.py): a persisted, typed DAG of one
 * run's handling. Served by GET /runs/:id/graph. Nodes carry their kind and,
 * for facts, the provenance SIGAP never lets go unlabelled. */
export type GraphNode = {
  node_id: string;
  kind: "event" | "lead" | "fact" | "option" | "ruling";
  state: string | null;
  label: string | null;
  subject: string | null;
  lead_key: string | null;
  origin: string | null;   // fact nodes: live | cached | derived | modelled | missing
  source: string | null;
  payload: string | null;  // JSON string
  priority: number | null;
};
export type GraphEdge = {
  src: string;
  rel: "spawns" | "derived_from" | "yields" | "rules_on" | "covers";
  dst: string;
};
export type ExplorationGraph = { nodes: GraphNode[]; edges: GraphEdge[] };

/* ---- trace: one handling as a topology (GET /runs/{id}/trace) ---- */
export type TraceNodeKind = "event" | "agent" | "tool" | "source" | "action";
export type TraceNode = {
  id: string; kind: TraceNodeKind; label: string; sub?: string;
  calls: number; errors: number; ms: number;
  agent?: string; tool?: string; origin?: string | null; state?: string;
  source?: string; source_kind?: string; tasks?: number;
  status?: string; autonomous?: boolean; cost_idr?: number | null; action_id?: string;
  stats?: TraceStats;
  /** agent: its role, from agents/definitions.py */
  brief?: string | null;
  /** event */
  trigger?: string | null; started_at?: string | null;
  /** action: what is being approved, and who has ruled on it */
  title?: string | null; payload?: Record<string, unknown>; created_at?: string | null;
  sap_reference?: string | null;
  approvals?: { decision: string; decided_by: string; role: string; note?: string | null; at: string }[];
};
export type TraceEdge = {
  id: string; from: string; to: string;
  rel: "triggers" | "delegates" | "calls" | "reads" | "raises";
  count: number; seqs: number[]; origin?: string | null;
};
export type TraceStats = {
  model?: string; models?: string[]; rounds?: number; input_tokens?: number;
  output_tokens?: number; idr?: number; seconds?: number;
  by_model?: Record<string, { input: number; output: number; idr: number; calls: number }>;
};
export type TraceCall = {
  seq: number; kind: "delegate" | "tool" | "finding" | "summary" | "fallback" | string;
  at: string | null; agent: string; agent_name?: string | null;
  node_ids: string[]; parent_seq?: number | null; thinking?: string | null;
  task?: string; by?: string; summary?: string; tool_calls?: number | null;
  tool?: string; arguments?: Record<string, unknown>; origin?: string | null;
  source?: string | null; note?: string | null; fetched_at?: string | null;
  ms?: number | null; rows?: number | null; rows_shown?: number | null;
  error?: string | boolean | null; result?: unknown; truncated?: boolean;
  round?: number | null; stats?: TraceStats | null;
};
export type Trace = {
  run: {
    id: string; title: string; kind: string; trigger: string; status: string; mode: string;
    started_at: string; finished_at: string | null; error: string | null;
    cost_idr: number | null; cost_by_model?: TraceStats["by_model"] | null;
  };
  totals: {
    steps: number; tool_calls: number; errors: number; agents: number; sources: number;
    actions: number; tool_ms: number; by_origin: Record<string, number>;
  };
  nodes: TraceNode[]; edges: TraceEdge[]; calls: TraceCall[];
};
/* What a handling still asks of a person, computed from the record by
 * engine/triage.py — never asked of a model. The word always travels with the
 * figures that earned it, so `headline` and `because` can be shown as they
 * come and still be checkable. */
export type VerdictState =
  | "needs_you_now" | "needs_you" | "held" | "failed"
  | "owes_outcome" | "running" | "handled";
export type Verdict = {
  state: VerdictState;
  /** sort key: lower is more owed */
  rank: number;
  headline: string;
  because: string[];
  value_idr: number;
  approver: string | null;
  days_of_cover: number | null;
  depleted_on: string | null;
  untrusted: number;
  owed: number;
  oldest_owed_days: number | null;
  compliance_cost_idr: number | null;
};
export type Board = {
  counts: Record<VerdictState, number>;
  needs_a_person: number;
  value_idr: number;
  /** true only when nothing waits, nothing is held, nothing failed and nothing owes an outcome */
  clear: boolean;
  line: string;
};

export type RunRow = Run & {
  step_count: number; tool_count: number; action_count?: number;
  verdict?: Verdict;
};
