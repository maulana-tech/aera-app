"""The team in force, as the agent loop sees it.

The team lives in the database (core/team.py composes it from the business
profile; a person edits it on the Team page). This module turns those rows
into Agent objects, every time it is asked, so a change on the Team page
reaches the next handling without a restart.

The capability lock is re-applied here when a row is read. A row edited by
hand in SQLite to give a writer the treasury still yields a writer without it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from agents import roles as R


class PromptMissing(RuntimeError):
    """An agent has no instructions."""


@dataclass
class Agent:
    code: str
    nickname: str
    title: str
    brief: str
    capabilities: List[str] = field(default_factory=list)
    effort: str = "medium"
    veto: bool = False
    core: bool = False
    prompt: str = ""
    version: int = 1
    role: str = ""

    @property
    def instructions(self) -> str:
        if not self.prompt.strip():
            raise PromptMissing(f"{self.nickname} ({self.code}) has no instructions.")
        from core import business
        from core.config import CFG
        p = business.current()
        text = self.prompt
        text = text.replace("{BUSINESS}", business.context_block(p))
        text = text.replace("{NAME}", p.get("name") or "the business")
        text = text.replace("{AUTONOMOUS_LIMIT}", CFG.autonomous_limit_text)
        if "{TEAM}" in text:
            text = text.replace("{TEAM}", team_listing(exclude=self.code))
        return text

    # The old Agent exposed `.title`, `.nickname`, `.brief`, `.veto`, `.effort`;
    # the loop and the API still read those names.


def _from_row(r: Dict) -> Agent:
    return Agent(code=r["code"], nickname=r["nickname"], title=r["title"], brief=r["brief"],
                 capabilities=R.allowed_capabilities(r["code"], r.get("capabilities") or []),
                 effort=r.get("effort") or "medium", veto=bool(r.get("veto")) and r["code"] == "guardian",
                 core=bool(r.get("core")), prompt=r.get("prompt") or "", version=int(r.get("version") or 1),
                 role=r.get("role") or "")


def load() -> Dict[str, Agent]:
    """Every ACTIVE agent, by code. Composes a team first if there is none."""
    from core import team
    rows = [r for r in team.ensure_team() if r.get("status") == "active"]
    return {r["code"]: _from_row(r) for r in rows}


def get(code: str) -> Agent:
    agents = load()
    if code not in agents:
        raise KeyError(code)
    return agents[code]


def supervisor() -> Agent:
    return get("supervisor")


def specialists() -> List[Agent]:
    """Everyone the supervisor can delegate to: the active team minus itself."""
    return [a for c, a in load().items() if c != "supervisor"]


def versions() -> Dict[str, int]:
    return {c: a.version for c, a in load().items()}


def team_listing(exclude: Optional[str] = None) -> str:
    lines = []
    for a in load().values():
        if a.code == exclude:
            continue
        flag = " [VETO]" if a.veto else (" [MONEY]" if "treasury" in a.capabilities else "")
        lines.append(f"- ask_{a.code}: {a.nickname}, {a.title}{flag}. {a.brief}")
    return "\n".join(lines) or "(no specialists yet)"


def demo() -> None:
    from core import business, store, team
    store.save_profile(business.EXAMPLE, by="check")
    team.apply(team.compose(), by="check")
    agents = load()
    assert agents["guardian"].veto and not agents["writer"].veto
    assert "treasury" in agents["treasurer"].capabilities
    sup = supervisor().instructions
    assert "Lumen Research" in sup and "ask_guardian" in sup and "ask_supervisor" not in sup, sup[:400]
    assert "{BUSINESS}" not in agents["writer"].instructions

    # Hand-edit a row to give the writer the treasury: the lock still holds.
    w = store.get_agent("writer")
    store.upsert_agent({**w, "capabilities": ["documents", "treasury"]}, by="tamper")
    assert "treasury" not in get("writer").capabilities
    print(f"roster ok, {len(agents)} active agents; lock re-applied on read ✓")


if __name__ == "__main__":
    from core.config import fixtures_only

    fixtures_only(__file__, "AERA_ROSTER_CHECK")
    demo()
