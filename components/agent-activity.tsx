import { Markdown } from "@/components/markdown";

const toolLabels: Record<string, string> = {
  check_action: "Ruling on an outward action",
  check_counterparty: "Checking who would be paid",
  deliver_order: "Delivering a paid order",
  draft_message: "Drafting a message",
  find_contact: "Looking up a contact",
  freeze_payments: "Freezing payments",
  get_business_profile: "Reading the business profile",
  get_exchange_rate: "Checking the exchange rate",
  get_order: "Reading an order",
  get_public_holidays: "Checking the holiday calendar",
  get_work_item: "Reading the work item",
  ledger_summary: "Reading the ledger",
  list_business_files: "Listing the business's files",
  list_orders: "Listing orders",
  pay_vendor: "Paying a vendor on record",
  propose_refund: "Proposing a refund",
  read_business_file: "Reading a business file",
  read_document: "Reading a document",
  read_web_page: "Reading a web page (as untrusted text)",
  save_contact: "Saving a contact",
  search_news: "Searching the news",
  search_past_work: "Reviewing how past work went",
  treasury_status: "Checking the vault and today's spend",
  use_skill: "Working through a written procedure",
  write_document: "Writing a document",
};

/* The core roles' names are fixed; a specialist's name comes with its step. */
const agentNames: Record<string, string> = {
  supervisor: "Supervisor", guardian: "Guardian", treasurer: "Treasurer",
};

export function toolLabel(name: string): string {
  if (Object.hasOwn(toolLabels, name)) return toolLabels[name];
  // `mcp__<server>__<tool>` (core/registry.py REMOTE_PREFIX): a tool on an MCP
  // server AERA does not operate. It has to read as borrowed here, because
  // the generic fallback below would describe it as a system check of ours.
  if (name.startsWith("mcp__")) {
    const [server, ...rest] = name.slice(5).split("__");
    const tool = rest.join("__").replace(/_/g, " ").trim();
    if (server && tool) return `Asking ${server} (outside AERA): ${tool}`;
  }
  const specialist = name.startsWith("ask_") ? name.slice(4) : "";
  if (specialist) return `Consulting ${Object.hasOwn(agentNames, specialist) ? agentNames[specialist] : specialist}`;
  return name.replace(/_/g, " ");
}

export function stepAgentName(step: { agent: string; agent_name: string }): string {
  return Object.hasOwn(agentNames, step.agent) ? agentNames[step.agent] : step.agent_name;
}

const stageLabels: Record<string, string> = {
  DELEGATE: "Delegation",
  TOOL: "Tool",
  MODEL: "Model call",
  SUMMARY: "Outcome",
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
      <details className="mt-1">
        <summary className="cursor-pointer hover:text-foreground">Activity details</summary>
        <p className="mt-1 break-words text-foreground/80">
          {tools.map(toolLabel).join(" · ")}
        </p>
      </details>
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
