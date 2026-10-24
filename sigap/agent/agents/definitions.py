"""The twelve agents. Their instructions live in prompts/, not here."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import List

PROMPTS = pathlib.Path(__file__).resolve().parent.parent / "prompts"


class PromptMissing(RuntimeError):
    """An agent was invoked before its instructions were written."""


@dataclass
class Agent:
    code: str
    nickname: str           # the short name people use: "Elsa", "Kira"
    title: str              # the functional role: "Impact", "Rules"
    brief: str
    tools: List[str] = field(default_factory=list)
    effort: str = "medium"       # supervisor & compliance run "high", see TECHNICAL.md
    veto: bool = False

    @property
    def instructions(self) -> str:
        f = PROMPTS / f"{self.code}.txt"
        if not f.exists():
            # This used to return a placeholder string, which meant the agent
            # was still sent to the model with that placeholder as its system
            # prompt, a silent failure. Better to stop here.
            raise PromptMissing(
                f"{self.nickname} ({self.code}) has no instructions yet. "
                f"Write prompts/{self.code}.txt before running this agent."
            )
        # The limit is configuration (SIGAP_AUTONOMOUS_LIMIT_IDR), so a prompt
        # names it through a placeholder rather than a number that goes stale.
        from core.config import CFG
        return f.read_text().replace("{AUTONOMOUS_LIMIT}", CFG.autonomous_limit_text)

    @property
    def ready(self) -> bool:
        return (PROMPTS / f"{self.code}.txt").exists()


SUPERVISOR = Agent(
    "supervisor", "Arya", "Team lead",
    "Pulls specialists onto the team as the findings warrant, judges when the evidence "
    "is enough, and writes the recommendation with its trade-offs and residual risk.",
    ["detect_disruption"], effort="high",
)

SPECIALISTS = [
    Agent("impact", "Elsa", "Impact",
          "Traces a disruption through orders, stock, and the bill of materials to the "
          "customer commitments genuinely at risk, from a port, a material or a supplier "
          "that failed.",
          ["get_open_purchase_orders", "get_material_stock",
           "get_bom_explosion", "get_sales_order_commitments"]),
    Agent("demand", "Dara", "Demand",
          "Owns the demand side. Daily consumption is a variable that moves, not a fixed number.",
          ["get_demand_signal", "get_production_schedule", "forecast_demand"]),
    Agent("inventory", "Iris", "Stock Validity",
          "Which stock may actually be used: quality holds, rejected batches, safety floors.",
          ["get_quality_holds", "get_safety_stock_policy", "assess_transfer"]),
    Agent("sourcing", "Clint", "Sourcing",
          "Finds and qualifies replacement supply: other suppliers, internal stock, fast "
          "freight, and substitute materials with whether each is approved for the product.",
          ["find_alternate_sources", "find_internal_transfers", "find_substitute_materials"]),
    Agent("procurement", "Prita", "Procurement",
          "Owns the supplier book as a whole: who the company buys from, in what volume, "
          "from which country, on what certificate, and whether each of them kept the "
          "date on its own purchase orders. Reads the quotations on file, compares them "
          "on price against lead time, and drafts the purchase order that follows from "
          "the comparison, with the reference rate for a price quoted in another currency.",
          ["get_supplier_master", "get_supplier_performance", "get_quotations",
           "compare_quotations", "propose_purchase_order", "get_exchange_rate"]),
    Agent("logistics", "Milo", "Logistics",
          "Models arrival dates that survive contact with reality: port dwell measured on "
          "past customs releases, where an import stands in customs and why it is held, "
          "transhipment, transport mode. Reads the outside world for the lane: the weather "
          "and hazards at a port, the news, and the holidays at either end.",
          ["get_shipment_status", "estimate_eta", "get_customs_status", "get_port_conditions",
           "search_news", "get_public_holidays", "web_brief"]),
    Agent("compliance", "Kira", "Rules",
          "Tests every candidate against TKDN and the contract floor, LARTAS licensing for a "
          "new origin, and the holiday calendar, from the rule pack, and says which rules "
          "are verified and which are assumptions. Her rejection cannot be overturned on cost.",
          ["check_local_constraints", "get_rule_pack"], effort="high", veto=True),
    Agent("simulation", "Tara", "Costing",
          "Costs the options that cleared the rules, and their combinations, and when the "
          "material cannot cover every customer order, which orders to serve first and what "
          "the late ones pay. Deterministic: she calls engine/simulate.py and "
          "engine/allocate.py rather than reasoning it out.",
          ["simulate_scenario", "allocate_short_supply"]),
    Agent("precedent", "Otto", "Precedent",
          "Institutional memory: what was done last time something like this happened, "
          "and how it turned out.",
          ["search_past_incidents"]),
    Agent("execution", "Bram", "Execution",
          "Writes back to SAP within its authority, tells the affected roles, drafts the "
          "notice to a customer whose order is late and the request to a supplier for a "
          "new date (both wait for a person to send), watches through to receipt, and "
          "records what actually happened so the next incident can learn from this one.",
          ["create_stock_transfer", "create_draft_po", "notify", "draft_customer_notice",
           "request_supplier_update", "monitor_shipment", "record_outcome",
           "create_sourcing_event", "propose_safety_stock_change"]),   # last two: Prevent mode
    Agent("exposure", "Vega", "Risk Scanner",
          "Prevent mode: hunts risk that has not happened yet. Single sources, concentrated "
          "lanes, certificates about to lapse, and natural hazards closing in on a port "
          "or plant we depend on.",
          ["scan_supply_exposure", "get_supplier_certifications", "rank_po_slip_risk",
           "scan_live_hazards"]),
]

ALL = {a.code: a for a in [SUPERVISOR, *SPECIALISTS]}


def demo() -> None:
    assert len(ALL) == 12, len(ALL)
    tools = [t for a in ALL.values() for t in a.tools]
    assert len(tools) == len(set(tools)), "a tool is claimed by two agents"

    # The count used to be written here as a number, which tested the number
    # rather than the thing worth testing and went stale on every new tool.
    # What matters is that what the agents claim and what is actually
    # registered are the same set, in both directions.
    import tools as _tools  # noqa: F401  (registers every tool)
    from core import registry

    declared, installed = set(tools), set(registry.all_tools())
    assert not declared - installed, f"claimed but not written: {sorted(declared - installed)}"
    assert not installed - declared, f"written but no agent owns it: {sorted(installed - declared)}"
    # What a person sees in place of a tool's name: the API's phrase for the
    # activity feed, and the web's label. A tool missing from either shows up
    # as "Running a system check", which says nothing about what it did.
    import api
    unlabelled = sorted(declared - set(api._TOOL_LABELS))
    assert not unlabelled, f"no activity phrase in api.py for {unlabelled}"
    web = PROMPTS.parents[2] / "components" / "agent-activity.tsx"
    if web.exists():
        text = web.read_text()
        unlabelled = sorted(t for t in declared if f"  {t}:" not in text)
        assert not unlabelled, f"no label in components/agent-activity.tsx for {unlabelled}"
    veto = [a.code for a in ALL.values() if a.veto]
    assert veto == ["compliance"], veto
    nicknames = [a.nickname for a in ALL.values()]
    assert len(nicknames) == len(set(nicknames)), "nicknames must be unique"
    assert len({n[0] for n in nicknames}) == len(nicknames), "first letters must all differ"
    print(f"definitions ok, {len(ALL)} agents, {len(tools)} tools, veto: {veto[0]}")
    print("  " + " · ".join(f"{a.nickname} ({a.title})" for a in ALL.values()))

    # A prompt that still names the limit as a number goes stale the day the
    # limit is configured; the placeholder is filled from the config instead.
    for a in ALL.values():
        if a.ready:
            text = (PROMPTS / f"{a.code}.txt").read_text()
            assert "50 million" not in text, f"prompts/{a.code}.txt names the limit as a number"
            assert "{AUTONOMOUS_LIMIT}" not in a.instructions

    pending = [f"{a.nickname} ({a.code})" for a in ALL.values() if not a.ready]
    if pending:
        print(f"\n  {len(pending)} agent(s) have no instructions yet, invoking one raises"
              f" PromptMissing rather than running on an empty prompt:")
        for p in pending:
            print(f"    · {p}")


if __name__ == "__main__":
    demo()
