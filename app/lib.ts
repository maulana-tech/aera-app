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
export type View = {
  domain: string; agent: string; columns: Column[]; rows: Record<string, any>[];
  origin: string; source: string; note: string;
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
  uploaded_by: string; uploaded_at: string;
};
export type Contact = {
  id: string; name: string; role: string; email: string; notify_for: string;
};
