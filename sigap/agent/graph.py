"""The agent team. The lead calls specialists; each runs its own tool loop.

The pattern: specialists are exposed as tools belonging to the lead. The lead
decides who to call based on the last finding — there is no fixed sequence.
Each specialist runs its own tool-use loop to completion, then hands back a
summary along with the origin labels of the data behind it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agents.definitions import ALL, SPECIALISTS, SUPERVISOR, Agent
from core import registry
from core.config import CFG
from core.provenance import Result

# Reference rates for the cost cap. Bedrock has its own pricing — replace these
# from aws.amazon.com/bedrock/pricing before going to production.
INPUT_IDR_PER_MILLION = 82_000
OUTPUT_IDR_PER_MILLION = 410_000
MAX_SPECIALIST_ROUNDS = 8
MAX_LEAD_ROUNDS = 14


class BudgetExhausted(RuntimeError):
    pass


class ModelNotReady(RuntimeError):
    pass


@dataclass
class Board:
    """The shared blackboard. Every specialist reads and writes here."""
    findings: Dict[str, Any] = field(default_factory=dict)
    origin: Dict[str, str] = field(default_factory=dict)
    source: Dict[str, str] = field(default_factory=dict)

    def write(self, key: str, r: Result) -> None:
        self.findings[key] = r.value
        self.origin[key] = r.origin.value
        self.source[key] = r.source

    def untrusted_keys(self) -> List[str]:
        return [k for k, v in self.origin.items()
                if v not in ("live", "cached", "derived")]

    def summary(self) -> str:
        lines = [f"- {k}: {self.origin[k]} ({self.source[k]})" for k in self.findings]
        return "\n".join(lines) or "(the board is still empty)"


@dataclass
class Cost:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def idr(self) -> int:
        return round(self.input_tokens / 1e6 * INPUT_IDR_PER_MILLION
                     + self.output_tokens / 1e6 * OUTPUT_IDR_PER_MILLION)

    def add(self, usage) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.input_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0


def client():
    if not CFG.model_ready:
        raise ModelNotReady(
            "AWS_REGION is not set. The agent team cannot run without model access. "
            "Check that the region offers Claude in the Bedrock console."
        )
    # imported here so a dev machine without the SDK can still run the rest
    from anthropic import AnthropicBedrockMantle
    return AnthropicBedrockMantle(aws_region=CFG.aws_region)


# --------------------------------------------------------------------------- #
def _tool_loop(cl, agent: Agent, task: str, board: Board,
               cost: Cost, report: Callable[[str, dict], None]) -> str:
    """One specialist works to completion. Returns the summary it wrote."""
    tools = registry.schemas_for_model(agent.code)
    messages: List[dict] = [{
        "role": "user",
        "content": (
            f"{task}\n\n"
            f"What is on the shared board right now:\n{board.summary()}\n\n"
            "Use your tools as needed, then write up what you found. If data you "
            "need is unavailable, say what is missing — do not guess."
        ),
    }]

    for _ in range(MAX_SPECIALIST_ROUNDS):
        if cost.idr > CFG.cost_cap_per_event_idr:
            raise BudgetExhausted(f"over Rp {CFG.cost_cap_per_event_idr:,} per event")

        r = cl.messages.create(
            model=CFG.model,
            max_tokens=8000,
            system=agent.instructions,
            thinking={"type": "adaptive"},
            output_config={"effort": agent.effort},
            tools=tools,
            messages=messages,
        )
        cost.add(r.usage)
        messages.append({"role": "assistant", "content": r.content})

        if r.stop_reason != "tool_use":
            text = "".join(b.text for b in r.content if b.type == "text")
            report("specialist_done", {"agent": agent.code, "summary": text[:400]})
            return text

        # every tool_result MUST go back in ONE user message
        results: List[dict] = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            report("tool", {"agent": agent.code, "name": b.name, "arguments": b.input})
            try:
                res = registry.run(b.name, dict(b.input))
                board.write(f"{agent.code}.{b.name}", res)
                body = json.dumps({"value": res.value, **res.brief()},
                                  ensure_ascii=False, default=str)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": body})
            except Exception as e:                                   # noqa: BLE001
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": f"{type(e).__name__}: {e}", "is_error": True})
        messages.append({"role": "user", "content": results})

    return f"[{agent.title} stopped: exceeded {MAX_SPECIALIST_ROUNDS} tool rounds]"


def _specialist_tools() -> List[dict]:
    """Each specialist appears as one tool belonging to the lead."""
    return [{
        "name": f"ask_{a.code}",
        "description": (f"{a.nickname} ({a.title}) — {a.brief}"
                        + (" HAS VETO." if a.veto else "")),
        "input_schema": {
            "type": "object",
            "properties": {"task": {
                "type": "string",
                "description": "the specific question for this specialist, with the context they need",
            }},
            "required": ["task"],
            "additionalProperties": False,
        },
        "strict": True,
    } for a in SPECIALISTS]


def run(event: dict, report: Callable[[str, dict], None]) -> dict:
    """Handle one event. `report` is called on every piece of progress."""
    cl = client()
    board = Board()
    cost = Cost()
    called: List[str] = []

    lead_tools = _specialist_tools() + registry.schemas_for_model("supervisor")
    messages: List[dict] = [{
        "role": "user",
        "content": (
            f"Incoming event:\n{json.dumps(event, ensure_ascii=False, indent=2)}\n\n"
            "Handle it. Call only the specialists that are relevant, one at a time, "
            "based on what the previous one found. Stop as soon as your evidence is "
            "enough to decide."
        ),
    }]

    for _ in range(MAX_LEAD_ROUNDS):
        if cost.idr > CFG.cost_cap_per_event_idr:
            raise BudgetExhausted(f"over Rp {CFG.cost_cap_per_event_idr:,}")

        r = cl.messages.create(
            model=CFG.model,
            max_tokens=16000,
            system=SUPERVISOR.instructions,
            thinking={"type": "adaptive"},
            output_config={"effort": SUPERVISOR.effort},
            tools=lead_tools,
            messages=messages,
        )
        cost.add(r.usage)
        messages.append({"role": "assistant", "content": r.content})

        if r.stop_reason != "tool_use":
            text = "".join(b.text for b in r.content if b.type == "text")
            return {
                "status": "done",
                "recommendation": text,
                "agents_called": called,
                "cost_idr": cost.idr,
                "untrusted_on_board": board.untrusted_keys(),
            }

        results: List[dict] = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            if b.name.startswith("ask_"):
                code = b.name[len("ask_"):]
                specialist = ALL[code]
                called.append(code)
                report("specialist_start", {"agent": code, "name": specialist.nickname,
                                            "task": b.input.get("task", "")})
                summary = _tool_loop(cl, specialist, b.input["task"], board, cost, report)
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": summary})
            else:
                try:
                    res = registry.run(b.name, dict(b.input))
                    board.write(f"supervisor.{b.name}", res)
                    results.append({"type": "tool_result", "tool_use_id": b.id,
                                    "content": json.dumps({"value": res.value, **res.brief()},
                                                          ensure_ascii=False, default=str)})
                except Exception as e:                               # noqa: BLE001
                    results.append({"type": "tool_result", "tool_use_id": b.id,
                                    "content": f"{type(e).__name__}: {e}", "is_error": True})
        messages.append({"role": "user", "content": results})

    return {"status": "stopped", "reason": f"exceeded {MAX_LEAD_ROUNDS} lead rounds",
            "agents_called": called, "cost_idr": cost.idr}


def ask_specialist(code: str, question: str,
                   report: Optional[Callable[[str, dict], None]] = None) -> dict:
    """Ask one specialist directly, outside of disruption handling.

    This is what the per-agent conversation page uses. Same specialist, same
    tools — the only difference is that no lead is deciding the turn order.
    """
    if code not in ALL:
        raise KeyError(code)
    agent = ALL[code]
    board, cost = Board(), Cost()
    trail: List[dict] = []

    def capture(kind: str, d: dict) -> None:
        trail.append({"kind": kind, **d})
        if report:
            report(kind, d)

    cl = client()
    answer = _tool_loop(cl, agent, question, board, cost, capture)
    return {
        "agent": code,
        "name": agent.nickname,
        "role": agent.title,
        "answer": answer,
        "tools_used": [t["name"] for t in trail if t["kind"] == "tool"],
        "board": {k: {"origin": board.origin[k], "source": board.source[k]}
                  for k in board.findings},
        "untrusted": board.untrusted_keys(),
        "cost_idr": cost.idr,
    }
