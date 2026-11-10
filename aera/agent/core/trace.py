"""Step recorder. Its output is what the dashboard reads."""
from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.provenance import Result


@dataclass
class Step:
    seq: int
    stage: str                 # DETECT · SCOPE · IMPACT · ...
    agent: str                 # agent code
    agent_name: str
    summary: str
    tools: List[str] = field(default_factory=list)
    origin: Optional[str] = None    # combined provenance of this step
    source: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)
    at: str = ""


class Trace:
    def __init__(self, title: str, trigger: str, mode: str = "autonomous"):
        self.title = title
        self.trigger = trigger
        self.mode = mode                  # "autonomous" | "guided"
        self.started_at = datetime.now(timezone.utc)
        self.steps: List[Step] = []
        self.decision: Dict[str, Any] = {}

    def record(self, stage: str, agent, summary: str, tools=None,
               result: Optional[Result] = None, **detail) -> None:
        self.steps.append(Step(
            seq=len(self.steps) + 1,
            stage=stage,
            agent=agent.code, agent_name=agent.title,
            summary=summary,
            tools=list(tools or []),
            origin=result.origin.value if result else None,
            source=result.source if result else None,
            detail=detail,
            at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ))

    @property
    def agents_used(self) -> List[str]:
        out, seen = [], set()
        for s in self.steps:
            if s.agent not in seen:
                seen.add(s.agent); out.append(s.agent)
        return out

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "trigger": self.trigger,
            "mode": self.mode,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "agents_used": self.agents_used,
            "step_count": len(self.steps),
            "steps": [asdict(s) for s in self.steps],
            "decision": self.decision,
        }

    def write(self, path) -> None:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.as_dict(), indent=2, ensure_ascii=False) + "\n")
