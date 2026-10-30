"""The skills SIGAP's agents work through.

A tool is one call. A SKILL is a named procedure that composes several of them
in an order somebody decided once, so the order is not re-derived - differently
- on every handling. That is the whole difference, and it is why skills are
written down here rather than left to a prompt: a procedure a model reinvents
each time is not a procedure.

Each skill states:

  who may run it   agent codes, or [] meaning any of them
  what it uses     the tools it composes, checked against the registry so a
                   skill naming a tool that does not exist is caught here and
                   not at three in the morning
  the steps        in order, each one a sentence about what the step decides

Every invocation is metered (core/store.record_skill_use), including the ones
that name a skill which does not exist. That last count is the useful one: a
model reaching for a skill nobody wrote is a gap in this catalogue, and
dropping those rows would hide the only evidence of it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Skill:
    name: str
    title: str
    description: str
    #: Agent codes that may run it. Empty means any agent.
    agents: List[str] = field(default_factory=list)
    #: Registry tool names it composes, in the order the steps use them.
    tools: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    #: Reachable from outside over MCP prompts and the A2A agent card.
    external: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "title": self.title, "description": self.description,
            "agents": list(self.agents), "tools": list(self.tools),
            "steps": list(self.steps), "external": self.external,
        }


CATALOGUE: List[Skill] = [
    Skill(
        name="investigate_disruption",
        title="Investigate a disruption",
        description=(
            "Take an event from a feed or a person through to a costed, ruled "
            "recommendation. The order matters: rule before you price, because an "
            "option that is not allowed has no price worth comparing."
        ),
        agents=[],
        tools=["get_material_stock", "get_open_purchase_orders", "get_bom_explosion",
               "find_alternate_sources", "check_local_constraints", "simulate_scenario",
               "search_past_incidents"],
        steps=[
            "Read what is actually affected: stock, open orders, and the finished goods "
            "underneath them.",
            "List replacement supply, including internal transfers and deadstock, before "
            "anyone prices freight.",
            "Rule every option against local content and import law. An option whose "
            "effect cannot be checked has not passed the check.",
            "Cost what survives at its LANDED price, so an import is not flattered by "
            "the duty nobody added.",
            "Check precedent: the second typhoon should not be handled like the first.",
        ],
        external=True,
    ),
    Skill(
        name="assess_option",
        title="Rule one option",
        description=(
            "Decide whether a single replacement option is allowed, and answer with the "
            "rules it was judged against rather than a bare verdict. A verdict without "
            "its rules is an instruction."
        ),
        agents=["compliance"],
        tools=["check_local_constraints", "get_rule_pack"],
        steps=[
            "Rule the option: local content against the contract floor, and the goods' "
            "HS heading against the restricted list.",
            "Report each rule used and whether anybody verified it. The ruling is only "
            "as strong as its weakest rule.",
            "Say what could not be checked, and treat it as not cleared rather than as "
            "cleared.",
        ],
        external=True,
    ),
    Skill(
        name="disruption_status",
        title="Report a handling",
        description=(
            "Read one handling back: where it got to, who worked on it, what it "
            "recommended, and what is still waiting on a person."
        ),
        agents=[],
        tools=["search_past_incidents"],
        steps=[
            "State the status and the recommendation as the record holds them.",
            "Name what still waits for approval, and who may approve it.",
            "Keep every origin label. A figure that was modelled stays modelled when "
            "it is quoted again.",
        ],
        external=True,
    ),
    Skill(
        name="scan_risk",
        title="Scan for risk that has not happened",
        description=(
            "Vega's sweep: single sources, concentrated lanes, cover below policy, and "
            "the purchase orders most likely to slip."
        ),
        agents=["exposure"],
        tools=["scan_supply_exposure", "rank_po_slip_risk", "get_supplier_certifications"],
        steps=[
            "Find the concentrations: one supplier, one lane, one port.",
            "Rank the orders by how likely each is to slip, and say which figures are "
            "predictions rather than history.",
            "Check the certificates behind the local-content position, because one "
            "lapsing is a disruption with a date on it.",
        ],
        external=True,
    ),
    Skill(
        name="close_the_loop",
        title="Record what actually happened",
        description=(
            "Write the realized outcome against an action that went out. Otto reads it "
            "back on the next handling, which is the point - but reading it back is his "
            "step, not this one. A skill that claims the consequence as its own work is "
            "a skill restricted to an agent who cannot run it."
        ),
        agents=["execution"],
        tools=["record_outcome"],
        steps=[
            "Record the outcome and, when it is known, the realized cost. Never infer "
            "a figure from prose.",
            "Leave the realized side blank rather than zero when nobody measured it. A "
            "blank is 'not known'.",
        ],
    ),
]

BY_NAME: Dict[str, Skill] = {s.name: s for s in CATALOGUE}


def get(name: str) -> Optional[Skill]:
    return BY_NAME.get(name)


def listing(usage: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """The catalogue, each with its usage when the ledger was read."""
    usage = usage or {}
    return [{**s.as_dict(), "usage": usage.get(s.name, {"calls": 0, "not_found": 0,
                                                        "by_agent": {}})}
            for s in CATALOGUE]


def demo() -> None:
    from core import registry
    import tools  # noqa: F401  (registers every tool)
    from agents.definitions import ALL

    known = set(registry.all_tools())
    for s in CATALOGUE:
        assert s.name and s.title and s.description, s.name
        assert s.steps, f"{s.name} has no steps, so it is a label rather than a procedure"
        # A skill naming a tool that does not exist fails here, not at three in
        # the morning on somebody's handling.
        missing = [t for t in s.tools if t not in known]
        assert not missing, f"{s.name} names tools that do not exist: {missing}"
        bad_agents = [a for a in s.agents if a not in ALL]
        assert not bad_agents, f"{s.name} names agents that do not exist: {bad_agents}"
        # A skill restricted to an agent must be composed of tools that agent
        # can actually reach, or it is a procedure nobody can run.
        for code in s.agents:
            reachable = set(ALL[code].tools)
            unreachable = [t for t in s.tools if t not in reachable]
            assert not unreachable, (
                f"{s.name} is restricted to {code}, who cannot reach {unreachable}")

    names = [s.name for s in CATALOGUE]
    assert len(names) == len(set(names)), "two skills share a name"

    # The four reachable from outside are exactly the ones MCP and A2A offer.
    external = {s.name for s in CATALOGUE if s.external}
    import mcp
    assert external == set(mcp._PROMPT_TEXT), (external, set(mcp._PROMPT_TEXT))

    out = listing({"assess_option": {"calls": 3, "not_found": 1, "by_agent": {"compliance": 3}}})
    assert len(out) == len(CATALOGUE)
    hit = next(o for o in out if o["name"] == "assess_option")
    assert hit["usage"]["calls"] == 3 and hit["usage"]["not_found"] == 1, hit
    cold = next(o for o in out if o["name"] == "close_the_loop")
    assert cold["usage"] == {"calls": 0, "not_found": 0, "by_agent": {}}, cold

    print(f"skills ok, {len(CATALOGUE)} in the catalogue, every tool and agent they "
          "name exists ✓ · a restricted skill is reachable by its own agent ✓ · "
          "the external four match MCP and A2A ✓")


if __name__ == "__main__":
    demo()
