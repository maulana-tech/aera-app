"""The eleven agents. Their instructions live in prompts/, not here."""
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
    effort: str = "medium"       # supervisor & compliance run "high" — see TECHNICAL.md
    veto: bool = False

    @property
    def instructions(self) -> str:
        f = PROMPTS / f"{self.code}.txt"
        if not f.exists():
            # This used to return a placeholder string, which meant the agent
            # was still sent to the model with that placeholder as its system
            # prompt — a silent failure. Better to stop here.
            raise PromptMissing(
                f"{self.nickname} ({self.code}) has no instructions yet. "
                f"Write prompts/{self.code}.txt before running this agent."
            )
        return f.read_text()

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
          "customer commitments genuinely at risk.",
          ["get_open_purchase_orders", "get_material_stock",
           "get_bom_explosion", "get_sales_order_commitments"]),
    Agent("demand", "Dara", "Demand",
          "Owns the demand side. Daily consumption is a variable that moves, not a fixed number.",
          ["get_demand_signal", "get_production_schedule"]),
    Agent("inventory", "Iris", "Stock Validity",
          "Which stock may actually be used — quality holds, rejected batches, safety floors.",
          ["get_quality_holds", "get_safety_stock_policy"]),
    Agent("sourcing", "Clint", "Sourcing",
          "Finds and qualifies replacement supply: other suppliers, internal stock, fast freight.",
          ["find_alternate_sources"]),
    Agent("logistics", "Milo", "Logistics",
          "Models arrival dates that survive contact with reality: port dwell, transhipment, "
          "customs, transport mode.",
          ["get_shipment_status", "estimate_eta"]),
    Agent("compliance", "Kira", "Rules",
          "Tests every candidate against TKDN, LARTAS, contract clauses, and the holiday "
          "calendar. Her rejection cannot be overturned on cost.",
          ["check_local_constraints"], effort="high", veto=True),
    Agent("simulation", "Tara", "Costing",
          "Costs the options that cleared the rules, and their combinations. Deterministic — "
          "she calls engine/simulate.py rather than reasoning it out.",
          ["simulate_scenario"]),
    Agent("precedent", "Otto", "Precedent",
          "Institutional memory: what was done last time something like this happened, "
          "and how it turned out.",
          ["search_past_incidents"]),
    Agent("execution", "Bram", "Execution",
          "Writes back to SAP within its authority, tells the affected roles, and watches "
          "through to receipt.",
          ["create_stock_transfer", "create_draft_po", "notify", "monitor_shipment",
           "create_sourcing_event", "propose_safety_stock_change"]),   # last two: Prevent mode
    Agent("exposure", "Vega", "Risk Scanner",
          "Prevent mode: hunts risk that has not happened yet — single sources, concentrated "
          "lanes, certificates about to lapse.",
          ["scan_supply_exposure", "get_supplier_certifications"]),
]

ALL = {a.code: a for a in [SUPERVISOR, *SPECIALISTS]}


def demo() -> None:
    assert len(ALL) == 11, len(ALL)
    tools = [t for a in ALL.values() for t in a.tools]
    assert len(tools) == len(set(tools)), "a tool is claimed by two agents"
    assert len(tools) == 23, len(tools)
    veto = [a.code for a in ALL.values() if a.veto]
    assert veto == ["compliance"], veto
    nicknames = [a.nickname for a in ALL.values()]
    assert len(nicknames) == len(set(nicknames)), "nicknames must be unique"
    assert len({n[0] for n in nicknames}) == len(nicknames), "first letters must all differ"
    print(f"definitions ok — {len(ALL)} agents, {len(tools)} tools, veto: {veto[0]}")
    print("  " + " · ".join(f"{a.nickname} ({a.title})" for a in ALL.values()))

    pending = [f"{a.nickname} ({a.code})" for a in ALL.values() if not a.ready]
    if pending:
        print(f"\n  {len(pending)} agent(s) have no instructions yet — invoking one raises"
              f" PromptMissing rather than running on an empty prompt:")
        for p in pending:
            print(f"    · {p}")


if __name__ == "__main__":
    demo()
