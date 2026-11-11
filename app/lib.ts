import { upstream } from "@/lib/upstream";

export const UPSTREAM = process.env.AERA_API ?? "http://127.0.0.1:8787";

/* ------------------------------------------------------------------ format */

/** Money is USD everywhere. Small amounts (model spend) keep their cents. */
export const usd = (n: number | null | undefined, opts: { precise?: boolean } = {}) => {
  const v = Number(n ?? 0);
  const digits = opts.precise || (v !== 0 && Math.abs(v) < 1) ? 4 : 2;
  return "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: digits });
};

/* UTC, always, and labelled. The server renders the page and the browser
 * hydrates it; formatting in the reader's own zone would make the two
 * disagree, and a record that reads differently on two screens is not one. */
export const ZONE = "UTC";
export function when(t?: string | null, opts: {
  /** false for the date alone */
  time?: boolean;
  /** seconds too, for a trace where the order of two calls is the point */
  seconds?: boolean;
  /** drop the "UTC" marker where a column header or nearby line already says it */
  mark?: boolean;
} = {}): string {
  if (!t) return "-";
  const at = new Date(t);
  if (Number.isNaN(at.getTime())) return t;
  const date = at.toLocaleDateString("en-GB", { timeZone: ZONE, day: "2-digit", month: "short", year: "numeric" });
  if (opts.time === false) return date;
  const time = at.toLocaleTimeString("en-GB", {
    timeZone: ZONE, hour: "2-digit", minute: "2-digit",
    ...(opts.seconds ? { second: "2-digit" } : {}),
  });
  return `${date} ${time}${opts.mark === false ? "" : " UTC"}`;
}

/** NearBlocks, for a transaction or an account, on the network in force. */
export function explorer(network: string | null | undefined, kind: "txns" | "address", id: string) {
  const base = network === "mainnet" ? "https://nearblocks.io" : "https://testnet.nearblocks.io";
  return `${base}/${kind}/${id}`;
}

/** A proof's model is "nearai:org/model"; the attestation route takes "org/model". */
export const bareModel = (m: string) => m.replace(/^[a-z]+:/, "");

/* ------------------------------------------------------------------ fetch */

/** Call the agent service, carrying the session token from the httpOnly cookie. */
export async function apiResult<T>(path: string): Promise<
  { data: T; error: null } | { data: null; error: string }
> {
  const { cookies } = await import("next/headers");
  const token = (await cookies()).get("aera_session")?.value;
  try {
    const r = await upstream(`${UPSTREAM}/${path}`, {
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

/** The customer-facing routes (/public/*): no session, never a token. */
export async function publicApi<T>(path: string): Promise<T | null> {
  try {
    const r = await upstream(`${UPSTREAM}/public/${path}`, { cache: "no-store" });
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

/* ------------------------------------------------------------------ people */

export type Role = "viewer" | "operator" | "approver" | "owner" | "admin";
export type Me = { name: string; email: string; role: Role; limit_usd: number };

export async function me(): Promise<Me | null> {
  return api<Me>("me");
}

/** Owner and admin edit the business, the team and payout details. */
export const mayManage = (u: Me | null | undefined) => u?.role === "owner" || u?.role === "admin";
/** Anyone with a limit may stop the business; only a manager may resume it. */
export const mayStop = (u: Me | null | undefined) => u?.role === "approver" || u?.role === "owner" || u?.role === "admin";

export type Health = {
  env: string; model_ready: boolean; model: string; private_mode: boolean; aux_model: string;
  vault: string | null; network: string; rail: "vault" | "simulated";
};

/* ---------------------------------------------------------------- business */

export type Delivery = "pdf" | "xlsx" | "message" | "file" | "service";
export const DELIVERIES: Delivery[] = ["pdf", "xlsx", "message", "file", "service"];
export const CHANNELS = ["web_checkout", "intents_checkout", "email", "telegram", "chat", "mcp"] as const;
export const APPROVAL_KINDS = [
  "refund", "new_vendor", "discount", "message_to_new_contact", "payment", "message", "deliver_order",
] as const;

export type Offering = {
  id: string; title: string; description?: string; price_usd: number;
  delivery: Delivery | string; sla_hours: number; inputs: string[];
};
export type ExtraRole = string | { title: string; brief?: string; capabilities?: string[] };
export type Profile = {
  name: string;
  mission: string;
  language: string;
  offerings: Offering[];
  customers: string;
  channels: string[];
  goals: string[];
  team: { preset: string; include: string[]; exclude: string[]; extra_roles: ExtraRole[] };
  constraints: {
    autonomous_spend_usd: { per_payment: number; per_day: number };
    inference_max_usd_per_day: number;
    min_price_usd: number;
    forbidden: string[];
    approval_required: string[];
  };
  revenue_split: { account: string; bps: number; label?: string }[];
  privacy: { sensitive: string[]; tee_only: boolean };
  kill_switch: boolean;
};
export type ProfileVersion = { version: number; active: number; changed_by: string; note: string | null; at: string };
export type BusinessPayload = {
  profile: Profile;
  version: number | null;
  problems: string[];
  history: ProfileVersion[];
  context: string;
  may_change: boolean;
  example: Profile;
};
/** True when nothing has been described yet. */
export const noBusiness = (b: BusinessPayload | null) => !b || b.version == null || !b.profile.name;

/* -------------------------------------------------------------------- team */

export type AgentStatus = "active" | "draft" | "disabled";
export type TeamAgent = {
  code: string; nickname: string; title: string; brief: string; role: string;
  core: boolean; veto: boolean; prompt: string; capabilities: string[];
  tools?: Record<string, string[]>;
  effort?: string; status: AgentStatus; version?: number;
  model?: string; origin: "composer" | "person" | "model" | string;
  updated_by?: string; updated_at?: string;
};
export type Capability = { name: string; description: string; locked_to: string | null; tools: string[] };
export type LibraryRole = { key: string; nickname: string; title: string; brief: string; capabilities: string[] };
export type TeamPayload = {
  agents: TeamAgent[]; capabilities: Capability[]; library: LibraryRole[]; may_change: boolean;
};
export type TeamDiff = { add: TeamAgent[]; remove: TeamAgent[]; change: { code: string; fields: string[] }[] };
export type ComposeResult = { team: TeamAgent[]; diff: TeamDiff };

/** GET /agents: the roster as the chat and per-agent pages read it. */
export type Tool = { name: string; installed: boolean; description: string | null };
export type Agent = {
  code: string; nickname: string; title: string; brief: string; effort: string;
  veto: boolean; core: boolean; lead: boolean; ready: boolean; capabilities: string[];
  tools: Tool[]; installed: number; tool_count: number; runs: number; model: string; version: number;
};

/* -------------------------------------------------------------------- work */

export type WorkKind = "request" | "goal" | "payable" | "order";
export const WORK_KINDS: WorkKind[] = ["request", "goal", "payable", "order"];
export type WorkItem = {
  id: string; kind: WorkKind | string; title: string; source: string;
  payload: Record<string, unknown>; dedup_key: string | null;
  status: string; received_at: string; run_id: string | null;
};

export type Step = {
  id?: number; run_id?: string;
  seq: number; stage: string; agent: string; agent_name: string;
  summary: string; tools: string[]; origin: string | null; source: string | null;
  detail: Record<string, unknown>; at: string;
};

export type GuardianReason = { rule: string; verdict: Verdict; detail: string; origin?: string | null };
export type Verdict = "allow" | "warn" | "block";
export type GuardianCheck = {
  id: string; run_id: string | null; action_id: string | null; kind: "action" | "counterparty" | string;
  subject: string; verdict: Verdict; reasons: GuardianReason[]; at: string;
};

export type ActionStatus = "pending" | "approved" | "rejected" | "sent" | "failed" | "blocked";
export type Action = {
  id: string; run_id: string; idempotency_key: string;
  kind: "payment" | "refund" | "message" | "deliver_order" | string;
  autonomous: boolean; value_usd: number;
  payload: Record<string, unknown> & { guardian?: { verdict?: Verdict; reasons?: GuardianReason[] } };
  status: ActionStatus | string; reason: string | null; reference: string | null;
  outcome: string | null; outcome_detail: Record<string, unknown> | null; outcome_at: string | null;
  created_at: string; work_title?: string;
};
export type Approval = {
  id: number; action_id: string; decided_by: string; role: string;
  decision: string; note: string | null; at: string;
};

export type ProofCheck = { name: string; status: "pass" | "fail" | "skipped" | string; detail: string; scope?: string };
export type ProofVerdict = "pending" | "attested" | "partial" | "failed";
export type Proof = {
  id: string; run_id: string | null; step_seq: number | null; agent: string; model: string;
  chat_id: string; signing_address: string | null; req_sha256: string | null; resp_sha256: string | null;
  checks: ProofCheck[]; verdict: ProofVerdict | string; created_at: string; verified_at: string | null;
};
export type Attestation =
  | { model: string; nonce: string; checks: ProofCheck[]; verdict: string; error?: undefined }
  | { model: string; error: string; nonce?: undefined; checks?: undefined; verdict?: undefined };

export type CostByModel = Record<string, { input: number; output: number; usd: number; calls: number }>;
export type Decision = {
  status?: string; recommendation?: string; reason?: string; retryable?: boolean;
  agents_called?: string[]; cost_usd?: number; cost_by_model?: CostByModel;
  trusted_on_board?: string[]; untrusted_on_board?: string[];
};
export type RunStatus = "running" | "done" | "partial" | "held" | "failed";
export type RunRow = {
  id: string; work_item_id: string; status: RunStatus | string;
  started_at: string; finished_at: string | null; cost_usd: number;
  team_version: Record<string, number>; profile_version: number | null;
  decision: Decision | null; error: string | null;
  title: string; kind: string; work_source: string;
  step_count: number; tool_count: number; action_count: number; attested: number; proofs: number;
};
export type Run = Omit<RunRow, "step_count" | "tool_count" | "action_count" | "attested" | "proofs"> & {
  work_payload: Record<string, unknown>;
  steps: Step[]; actions: Action[]; approvals: Approval[]; guardian: GuardianCheck[]; proofs: Proof[];
};

/* ------------------------------------------------------------------- money */

export type OrderStatus = "awaiting_payment" | "paid" | "working" | "delivered" | "refunded" | "failed";
export type Order = {
  id: string; offering: string; customer: string | null; inputs: Record<string, string>;
  amount_usd: number; status: OrderStatus | string; work_item_id: string | null;
  paid_tx: string | null; delivery: Record<string, unknown> | null;
  created_at: string; updated_at: string;
};
export type Payment = {
  id: string; action_id: string | null; direction: "out" | "in" | "split" | "refund" | string;
  rail: "vault" | "intents" | "simulated" | string; request_id: string | null;
  counterparty: string; amount_usd: number; token: string; status: string;
  tx_hash: string | null; detail: Record<string, unknown>; created_at: string; settled_at: string | null;
};
export type VaultPolicy = {
  owner: string; agent: string; token: string; per_tx_cap: string; daily_cap: string;
  spent_today: string; day: number; frozen: boolean;
  split: { account_id: string; bps: number }[];
  approvers: { account_id: string; role: string; limit: string }[];
};
export type Treasury = {
  network: string; vault: string | null; agent: string | null; token: string;
  rail: "vault" | "simulated"; caps: { per_payment: number; per_day: number };
  paid_today_usd: number; kill_switch: boolean;
  pending_actions: Action[]; pending_onchain: Payment[]; approved_refunds: Action[]; payments: Payment[];
  policy?: VaultPolicy | null; balance_usd?: number | null; explorer?: string;
  /** When the vault's caps and the profile's disagree: the exact set_policy arguments to sign. */
  policy_drift?: PolicyDrift;
};
export type PolicyDrift = {
  drift: boolean;
  vault: { per_payment: number; per_day: number };
  profile: { per_payment: number; per_day: number };
  set_policy: { per_tx_cap: string; daily_cap: string };
};
/** USDC has 6 decimals; vault figures arrive in base units. */
export const fromBase = (base: string | number | null | undefined) => Number(base ?? 0) / 1e6;
export const toBase = (amountUsd: number) => String(Math.round(amountUsd * 1e6));

export type LedgerEntry = {
  id?: string; direction: string; rail: string; counterparty?: string; amount_usd: number;
  token: string; status: string; tx_hash: string | null; created_at: string;
};
export type Ledger = {
  days: number;
  money: { direction: string; status: string; total: number; n: number }[];
  model_spend_usd: number;
  decisions: { autonomous: number; status: string; n: number }[];
  blocked_by_guardian: number;
  entries: LedgerEntry[];
  proofs: Partial<Record<ProofVerdict, number>>;
};

export type PublicOfferings = {
  business: string | null; mission: string | null; open: boolean; offerings: Offering[];
  vault: string | null; token: string; network: string;
};
export type Checkout = {
  order: Order;
  pay: {
    amount_usd: number; token: string; simulated?: boolean;
    ft_transfer_call?: { receiver_id: string; amount: string; msg: string };
  };
};
export type PublicOrder = Pick<Order, "id" | "offering" | "status" | "amount_usd" | "created_at" | "updated_at">;

/** A document the team wrote (write_document): a draft or a deliverable. */
export type DocumentRow = {
  id: string; title: string; format: string | null; order_id: string | null;
  uploaded_at: string; uploaded_by: string; size: number; name?: string;
};
export type DocumentFull = DocumentRow & { markdown: string; pdf_sha256: string };
/** What deliver_order wrote on the order: the PDF's sha256, and the vault receipt when there is one. */
export type OrderDelivery = { hash?: string; document_id?: string; sent_to?: string; tx_hash?: string | null; explorer?: string | null; bytes?: number };
export const orderDelivery = (o: Pick<Order, "delivery">): OrderDelivery | null =>
  o.delivery && typeof o.delivery === "object" ? (o.delivery as OrderDelivery) : null;
/** The PDF, through the proxy (which carries the session and passes the bytes through). */
export const documentPdf = (id: string) => `/api/aera/documents/${encodeURIComponent(id)}.pdf`;

export type BusinessFile = { id: string; name: string; mime: string; size: number; uploaded_by: string; uploaded_at: string };

/* ---------------------------------------------------------------- settings */

export type SkillRow = {
  name: string; title: string; description: string;
  agents: string[]; tools: string[]; steps: string[]; external: boolean;
  usage: { calls: number; not_found: number; by_agent: Record<string, number> };
  /** Written in core/skills.py rather than added here. Built-ins cannot be
   *  edited or removed from the UI, and only they are reachable over MCP. */
  builtin: boolean;
};
export type SkillsPayload = {
  skills: SkillRow[]; days: number;
  agents: { code: string; nickname: string }[];
  tools: string[];
  may_change: boolean;
};

export type McpTool = { name: string; description: string; read_only: boolean };
export type McpServer = {
  id: string; name: string; url: string; enabled: boolean;
  agents: string[]; tools: McpTool[]; token_set: boolean;
  /** How many of `tools` an agent can really call: writers, tools with no
   *  usable schema and tools whose name is already ours are dropped
   *  (aera/agent/core/registry.py, remote_tools). */
  offered: number;
  last_ok: string | null; last_error: string | null;
  added_by: string; added_at: string;
};
export type McpPayload = {
  ours: {
    endpoint: string; protocol: string;
    tools_total: number; tools_writing: number;
    resources: string[]; prompts: string[];
  };
  servers: McpServer[];
  may_change: boolean;
};

export type Column = { k: string; l: string; n?: boolean; usd?: boolean };

export type ContactRole = "customer" | "vendor" | "contributor" | "team" | "approver";
export const CONTACT_ROLES: ContactRole[] = ["customer", "vendor", "contributor", "team", "approver"];
export type Contact = {
  id: string; name: string; role: ContactRole | string; email: string; notify_for: string;
  near_account?: string | null; payout_chain?: string | null; payout_address?: string | null;
  address_changed_at?: string | null;
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
};

/* ---- trace: one handling as a topology (GET /runs/{id}/trace) ---- */
export type TraceNodeKind = "event" | "agent" | "tool" | "source" | "action";
export type TraceNode = {
  id: string; kind: TraceNodeKind; label: string; sub?: string;
  calls: number; errors: number; ms: number;
  agent?: string; tool?: string; origin?: string | null; state?: string;
  source?: string; source_kind?: string; tasks?: number;
  status?: string; autonomous?: boolean; value_usd?: number | null; action_id?: string;
  stats?: TraceStats;
  /** agent: its role */
  brief?: string | null;
  /** event */
  trigger?: string | null; started_at?: string | null;
  /** action: what is being approved, and who has ruled on it */
  title?: string | null; payload?: Record<string, unknown>; created_at?: string | null;
  reference?: string | null;
  approvals?: { decision: string; decided_by: string; role: string; note?: string | null; at: string }[];
};
export type TraceEdge = {
  id: string; from: string; to: string;
  rel: "triggers" | "delegates" | "calls" | "reads" | "raises";
  count: number; seqs: number[]; origin?: string | null;
};
export type TraceStats = {
  model?: string; models?: string[]; rounds?: number; input_tokens?: number;
  output_tokens?: number; usd?: number; seconds?: number;
  by_model?: CostByModel;
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
    id: string; title: string; kind: string; trigger: string | null; status: string; mode: string | null;
    started_at: string; finished_at: string | null; error: string | null;
    cost_usd: number | null; cost_by_model?: CostByModel | null;
  };
  totals: {
    steps: number; tool_calls: number; errors: number; agents: number; sources: number;
    actions: number; tool_ms: number; by_origin: Record<string, number>;
  };
  nodes: TraceNode[]; edges: TraceEdge[]; calls: TraceCall[];
};

/* ------------------------------------------------------------ trust center (core/trust.py) */
export type TrustProofModel = { model: string; provider: string; attested: number; partial: number; failed: number; pending: number };
export type TrustProof = { id: string; run_id: string | null; agent: string; model: string; verdict: string; at: string; provider: string };
export type TrustCheck = {
  id: string; run_id: string | null; kind: string; subject: string; verdict: string; at: string;
  rules: { rule: string; verdict: string; detail: string }[];
};
export type TrustPayload = {
  days: number; generated_at: string;
  privacy: {
    private_mode: boolean; attested_models: number; raw_prompts_stored: boolean;
    proofs: { total: number; by_verdict: Record<string, number>; chat_calls: number; by_model: TrustProofModel[]; recent: TrustProof[] };
    redaction: { redacted: number; not_redacted: number; recent: { id: string; channel: string; outcome: string; detail: string | null; at: string }[] };
    guardian_privacy_stops: TrustCheck[];
  };
  security: {
    vault: {
      configured: boolean; network: string; vault: string | null; agent: string | null; note?: string; balance_usd?: number | null;
      policy?: { per_tx_cap_usd: number; daily_cap_usd: number; spent_today_usd: number; frozen: boolean; owner: string; approvers: number };
      agent_keys?: { full_access: number; function_call: { receiver: string; methods: string[] }[] } | { error: string };
    };
    guardian: { total: number; by_verdict: Record<string, number>; by_rule: { rule: string; block: number; warn: number }[]; stopped: TrustCheck[] };
    decisions: { team_alone: number; person: number; waiting: number; blocked: number };
    kill_switch: { version: number; on: boolean; by: string; note: string | null; at: string }[];
    attack_demo: { at: string | null; network: string | null; vault: string | null; layers: { title: string; status: string | null; detail: string }[] } | null;
  };
};

/* ------------------------------------------------- what the profile's ids mean, in plain words */
export const CHANNEL_INFO: Record<(typeof CHANNELS)[number], { label: string; hint: string }> = {
  web_checkout: { label: "Checkout page", hint: "A public page per offering where customers order and pay" },
  intents_checkout: { label: "Pay from any chain", hint: "Customers pay with tokens on other chains through NEAR Intents" },
  email: { label: "Email", hint: "Deliveries and replies go to the customer's inbox" },
  telegram: { label: "Telegram", hint: "Customers reach the team through a Telegram bot" },
  chat: { label: "Chat", hint: "Customers ask the team questions in a chat window" },
  mcp: { label: "Other AI agents (MCP)", hint: "Other agents and apps can call the business's tools" },
};
export const DELIVERY_INFO: Record<Delivery, string> = {
  pdf: "PDF document", xlsx: "Spreadsheet (Excel)", message: "A message", file: "A file", service: "A service, done for them",
};
export const APPROVAL_INFO: Record<(typeof APPROVAL_KINDS)[number], { label: string; hint: string }> = {
  refund: { label: "Refunds", hint: "Money back to a customer" },
  new_vendor: { label: "Paying a new vendor", hint: "The first payment to anyone not paid before" },
  discount: { label: "Discounts", hint: "Selling below the listed price" },
  message_to_new_contact: { label: "First message to someone new", hint: "Anyone the team has not written to before" },
  payment: { label: "Every payment", hint: "Even small ones inside the spend limit" },
  message: { label: "Every outgoing message", hint: "Nothing is sent without you" },
  deliver_order: { label: "Every delivery", hint: "You see each deliverable before the customer does" },
};
export const LANGUAGES: { code: string; label: string }[] = [
  { code: "en", label: "English" }, { code: "id", label: "Bahasa Indonesia" }, { code: "ms", label: "Bahasa Melayu" },
  { code: "vi", label: "Tiếng Việt" }, { code: "th", label: "ไทย (Thai)" }, { code: "tl", label: "Filipino" },
  { code: "zh", label: "中文 (Chinese)" }, { code: "ja", label: "日本語 (Japanese)" }, { code: "ko", label: "한국어 (Korean)" },
  { code: "es", label: "Español" }, { code: "fr", label: "Français" }, { code: "de", label: "Deutsch" },
  { code: "pt", label: "Português" }, { code: "ar", label: "العربية (Arabic)" }, { code: "hi", label: "हिन्दी (Hindi)" },
];
/** An offering's id, made from its title: what the checkout link is built from. */
export const slugify = (s: string) =>
  s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 32);
