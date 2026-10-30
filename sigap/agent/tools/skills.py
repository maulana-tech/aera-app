"""Running a skill, as an act an agent takes rather than a paragraph it read.

core/skills.py writes the procedures down. Until this module existed nothing
called them: the catalogue was a description of how agents were meant to work,
the steps lived only in hand-written prompts, and store.record_skill_use - the
ledger the skills page reads - was never once written to. Every counter on
that page was zero, and would have stayed zero.

What `use_skill` does is small and deliberate: it hands the agent the steps of
a named procedure at the moment it needs them, and records that it did. Three
things come out of that which prompts alone could not give:

  * The order is the one somebody decided once, not the one the model happens
    to reconstruct today. That is the whole reason a skill is not a prompt.
  * A skill restricted to an agent is enforced rather than merely written
    down. Bram's close_the_loop is refused to anybody else, with the reason.
  * A skill asked for by a name nobody wrote is recorded too, and that count
    is the useful one: a model reaching for a procedure that does not exist is
    a gap in the catalogue, and the only evidence of it.

What it deliberately is NOT is evidence. A procedure describes how to look,
not what was found, so tools/execution.py excludes it from what an action may
rest on - for the same reason precedent is excluded there.
"""
from __future__ import annotations

from core import registry, skills, store
from core.provenance import Origin, Result
from core.registry import register

#: Named in the tool description so a model can see what exists. Not an enum
#: in the schema on purpose: a closed list would make it impossible to ask for
#: a skill nobody wrote, and that request is exactly what the not_found count
#: is for.
def _catalogue_line() -> str:
    return ", ".join(s.name for s in skills.CATALOGUE)


@register(
    "use_skill", registry.SHARED,
    "Work through a written procedure instead of improvising the order. Returns "
    "its steps and the tools it composes. Available: " + _catalogue_line() + ".",
    {"name": {"type": "string", "description": "The skill to work through."}},
    ["name"],
)
def use_skill(name: str) -> Result:
    agent = _calling_agent()
    wanted = (name or "").strip()
    skill = skills.get(wanted)
    if skill is None:
        store.record_skill_use(wanted, agent, found=False, run_id=registry.current_run())
        known = _catalogue_line()
        return Result(None, Origin.MISSING, "SIGAP skill catalogue",
                      note=f"there is no skill called '{wanted}'. Written down: {known}")

    if skill.agents and agent not in skill.agents:
        # Recorded as a use, because it was one: the skill was found and the
        # caller was turned away. A refusal nobody counts is a limit nobody
        # can see the cost of.
        store.record_skill_use(skill.name, agent, found=True, run_id=registry.current_run())
        from agents.definitions import ALL
        who = ", ".join(ALL[c].nickname if c in ALL else c for c in skill.agents)
        return Result(None, Origin.MISSING, "SIGAP skill catalogue",
                      note=(f"'{skill.name}' is {who}'s procedure, not yours. "
                            "Ask them for it rather than working through it here."))

    store.record_skill_use(skill.name, agent, found=True, run_id=registry.current_run())
    return Result(
        {"skill": skill.name, "title": skill.title, "why": skill.description,
         "steps": list(skill.steps), "tools": list(skill.tools)},
        # Our own written procedure, not a reading of the world. Labelled
        # openly, and kept out of what an action may rest on.
        Origin.MODELLED, "SIGAP skill catalogue",
        note="a procedure, not a finding: it says how to look, not what is there",
    )


def _calling_agent() -> str:
    """Whose call this is, from the loop rather than from the model.

    A tool parameter naming the agent would be a parameter the model could
    fill with somebody else's code, which would make the restriction above
    decorative. graph._run_tool binds it instead.
    """
    return registry.current_agent() or "unknown"


def demo() -> None:
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_SKILLS_CHECK")

    # An unrestricted skill reaches any agent, with its steps in the written order.
    with registry.bind_agent("impact"):
        got = use_skill("investigate_disruption")
    assert got.value["skill"] == "investigate_disruption", got.value
    assert got.value["steps"] == skills.get("investigate_disruption").steps
    assert got.origin is Origin.MODELLED, got.origin

    # A restricted one is refused to everybody else, and says whose it is.
    with registry.bind_agent("impact"):
        refused = use_skill("close_the_loop")
    assert refused.value is None and refused.origin is Origin.MISSING
    assert "Bram's procedure" in refused.note, refused.note
    with registry.bind_agent("execution"):
        allowed = use_skill("close_the_loop")
    assert allowed.value["tools"] == ["record_outcome"], allowed.value

    # A name nobody wrote is an answer and a recorded gap, not an exception.
    with registry.bind_agent("sourcing"):
        nope = use_skill("negotiate_everything")
    assert nope.value is None and "no skill called" in nope.note, nope.note
    # The catalogue is named in the refusal, so the next attempt can be right.
    assert "investigate_disruption" in nope.note, nope.note

    ledger = store.skill_usage(days=1)
    assert ledger["investigate_disruption"]["calls"] == 1, ledger
    # The refusal counted as a use of a skill that exists: a limit nobody
    # counts is a limit nobody can see the cost of.
    assert ledger["close_the_loop"]["calls"] == 2, ledger
    assert ledger["close_the_loop"]["by_agent"] == {"impact": 1, "execution": 1}, ledger
    # And the invented name counted as a gap in the catalogue, not as nothing.
    assert ledger["negotiate_everything"]["not_found"] == 1, ledger

    # Outside a loop there is no agent, and a restricted skill stays shut.
    assert registry.current_agent() is None
    assert use_skill("close_the_loop").value is None

    print("  a written procedure reaches the agent that may run it, is refused to the "
          "agent that may not, and a skill nobody wrote is counted \u2713")
    print(f"skills tools ok, {len(skills.CATALOGUE)} procedures callable")


if __name__ == "__main__":
    demo()
