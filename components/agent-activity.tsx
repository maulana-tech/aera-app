import { Markdown } from "@/components/markdown";

const toolLabels: Record<string, string> = {
  detect_disruption: "Checking the disruption signal",
  get_materials: "Checking material data",
  get_open_purchase_orders: "Checking open purchase orders",
  get_material_stock: "Checking material stock",
  get_bom_explosion: "Tracing product components",
  get_sales_order_commitments: "Checking customer order commitments",
  get_demand_signal: "Checking demand signals",
  get_production_schedule: "Checking the production schedule",
  forecast_demand: "Forecasting material demand",
  get_quality_holds: "Checking stock quality holds",
  get_safety_stock_policy: "Checking safety stock requirements",
  assess_transfer: "Assessing a stock transfer",
  find_alternate_sources: "Looking for alternative suppliers",
  find_internal_transfers: "Looking for stock at other plants",
  get_supplier_master: "Checking supplier records",
  get_supplier_performance: "Reviewing supplier performance",
  get_quotations: "Checking supplier quotations",
  compare_quotations: "Comparing supplier quotations",
  propose_purchase_order: "Preparing a purchase order proposal",
  get_shipment_status: "Checking shipment status",
  estimate_eta: "Estimating arrival dates",
  check_local_constraints: "Checking compliance requirements",
  simulate_scenario: "Comparing scenario costs",
  search_past_incidents: "Reviewing similar past incidents",
  create_stock_transfer: "Requesting a stock transfer",
  create_draft_po: "Preparing a draft purchase order",
  notify: "Sending a notification",
  monitor_shipment: "Monitoring the shipment",
  create_sourcing_event: "Preparing a sourcing event",
  propose_safety_stock_change: "Proposing a safety stock adjustment",
  scan_supply_exposure: "Checking supply risks",
  get_supplier_certifications: "Checking supplier certifications",
};

const agentNames: Record<string, string> = {
  supervisor: "Arya", impact: "Elsa", demand: "Dara", inventory: "Iris",
  sourcing: "Clint", procurement: "Prita", logistics: "Milo", compliance: "Kira",
  simulation: "Tara", precedent: "Otto", execution: "Bram", exposure: "Vega",
};

export function toolLabel(name: string): string {
  if (Object.hasOwn(toolLabels, name)) return toolLabels[name];
  const specialist = name.startsWith("ask_") ? name.slice(4) : "";
  return Object.hasOwn(agentNames, specialist)
    ? `Consulting ${agentNames[specialist]}`
    : "Running a system check";
}

export function stepAgentName(step: { agent: string; agent_name: string }): string {
  return Object.hasOwn(agentNames, step.agent) ? agentNames[step.agent] : step.agent_name;
}

const stageLabels: Record<string, string> = {
  DELEGATE: "Delegation",
  TOOL: "Data Check",
  FINDING: "Finding",
  SPECIALIST_START: "Delegation",
  SPECIALIST_DONE: "Finding",
  START: "Trigger",
  DONE: "Completed",
};

export function stageLabel(stage: string): string {
  const normalized = stage.toUpperCase().trim();
  if (Object.hasOwn(stageLabels, normalized)) return stageLabels[normalized];
  return stage.charAt(0).toUpperCase() + stage.slice(1).toLowerCase();
}

export function ToolActivity({ tools }: { tools: string[] }) {
  if (!tools.length) return null;
  return (
    <div className="text-muted-foreground mt-1 text-xs">
      <p>{tools.map(toolLabel).join(" · ")}</p>
    </div>
  );
}

export function StepSummary({ step }: {
  step: { stage: string; summary: string; tools: string[] };
}) {
  const toolOnly = step.stage === "TOOL" || step.tools.includes(step.summary.trim());
  return (
    <>
      {!toolOnly && <Markdown>{step.summary}</Markdown>}
      <ToolActivity tools={step.tools.length ? step.tools : toolOnly ? [step.summary] : []} />
    </>
  );
}
