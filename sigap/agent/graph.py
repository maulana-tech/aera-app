"""The agent team. The lead calls specialists; each runs its own tool loop.

The pattern: specialists are exposed as tools belonging to the lead. The lead
decides who to call based on the last finding, there is no fixed sequence.
Each specialist runs its own tool-use loop to completion, then hands back a
summary along with the origin labels of the data behind it.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agents.definitions import ALL, SPECIALISTS, SUPERVISOR, Agent
import tools  # noqa: F401  (registers every tool; see tools/__init__.py)
from core import registry
from core.config import CFG
from core.provenance import Result

# Reference rates for the cost cap. Bedrock has its own pricing, replace these
# from aws.amazon.com/bedrock/pricing before going to production.
INPUT_IDR_PER_MILLION = 82_000
OUTPUT_IDR_PER_MILLION = 410_000
MAX_SPECIALIST_ROUNDS = 8
MAX_LEAD_ROUNDS = 14

#: Rounds and rupiah are not the only ways a handling can run away. One slow
#: specialist inside the round budget still blocks the queue behind it, so the
#: whole handling carries a deadline as well.
MAX_SECONDS_PER_EVENT = 600


class BudgetExhausted(RuntimeError):
    pass


class DeadlineExceeded(RuntimeError):
    pass


class ModelNotReady(RuntimeError):
    pass


@dataclass(frozen=True)
class Entry:
    """One finding, with where it came from, kept together.

    The board used to be three parallel dicts keyed by the same string, which
    meant a value could exist without its origin. Since the origin is the whole
    point, they travel as one record.
    """
    value: Any
    origin: str
    source: str
    at: str


@dataclass
class Board:
    """The shared blackboard. Every specialist reads and writes here."""
    entries: Dict[str, Entry] = field(default_factory=dict)

    def write(self, key: str, r: Result) -> None:
        self.entries[key] = Entry(r.value, r.origin.value, r.source,
                                  r.fetched_at.isoformat(timespec="seconds"))

    # Read shapes the rest of the system already expects.
    @property
    def findings(self) -> Dict[str, Any]:
        return {k: e.value for k, e in self.entries.items()}

    @property
    def origin(self) -> Dict[str, str]:
        return {k: e.origin for k, e in self.entries.items()}

    @property
    def source(self) -> Dict[str, str]:
        return {k: e.source for k, e in self.entries.items()}

    def untrusted_keys(self) -> List[str]:
        return [k for k, e in self.entries.items()
                if e.origin not in ("live", "cached", "derived")]

    def summary(self) -> str:
        lines = [f"- {k}: {e.origin} ({e.source})" for k, e in self.entries.items()]
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
    try:
        from anthropic import AnthropicBedrock
        return AnthropicBedrock(aws_region=CFG.aws_region)
    except Exception:
        from anthropic import AnthropicBedrockMantle
        return AnthropicBedrockMantle(aws_region=CFG.aws_region)


# --------------------------------------------------------------------------- #
def _tool_loop(cl, agent: Agent, task: str, board: Board,
               cost: Cost, report: Callable[[str, dict], None],
               deadline: Optional[float] = None,
               history: Optional[List[dict]] = None) -> str:
    """One specialist works to completion. Returns the summary it wrote.

    `history` is earlier turns of the same conversation, already trimmed by the
    caller. Without it a follow-up question like "and the other plant?" has
    nothing to refer to, and the transcript on screen would be a record of a
    conversation the agent was never actually having.
    """
    tools = registry.schemas_for_model(agent.code)
    messages: List[dict] = [*(history or []), {
        "role": "user",
        "content": (
            f"{task}\n\n"
            f"What is on the shared board right now:\n{board.summary()}\n\n"
            "Use your tools as needed, then write up what you found. If data you "
            "need is unavailable, say what is missing, do not guess."
        ),
    }]

    for _ in range(MAX_SPECIALIST_ROUNDS):
        if cost.idr > CFG.cost_cap_per_event_idr:
            raise BudgetExhausted(f"over Rp {CFG.cost_cap_per_event_idr:,} per event")
        if deadline and time.monotonic() > deadline:
            raise DeadlineExceeded(
                f"{agent.title} still working after {MAX_SECONDS_PER_EVENT}s")

        req = {
            "model": CFG.model,
            "max_tokens": 8000,
            "system": agent.instructions,
            "tools": tools,
            "messages": messages,
        }
        if "haiku" not in CFG.model.lower():
            req["thinking"] = {"type": "adaptive"}
            req["output_config"] = {"effort": agent.effort}
        r = cl.messages.create(**req)
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
        "description": (f"{a.nickname} ({a.title}), {a.brief}"
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
    deadline = time.monotonic() + MAX_SECONDS_PER_EVENT

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
        if time.monotonic() > deadline:
            raise DeadlineExceeded(f"handling ran past {MAX_SECONDS_PER_EVENT}s")

        lead_req = {
            "model": CFG.model,
            "max_tokens": 16000,
            "system": SUPERVISOR.instructions,
            "tools": lead_tools,
            "messages": messages,
        }
        if "haiku" not in CFG.model.lower():
            lead_req["thinking"] = {"type": "adaptive"}
            lead_req["output_config"] = {"effort": SUPERVISOR.effort}
        r = cl.messages.create(**lead_req)
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
                summary = _tool_loop(cl, specialist, b.input["task"], board, cost,
                                     report, deadline)
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
                   report: Optional[Callable[[str, dict], None]] = None,
                   history: Optional[List[dict]] = None) -> dict:
    """Ask one specialist directly, outside of disruption handling.

    This is what the per-agent conversation page uses. Same specialist, same
    tools, the only difference is that no lead is deciding the turn order.
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

    start_time = time.monotonic()
    cl = client()
    answer = _tool_loop(cl, agent, question, board, cost, capture, history=history)
    duration_s = round(time.monotonic() - start_time, 2)
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
        "thinking_time": duration_s,
        "tokens": {
            "input": cost.input_tokens,
            "output": cost.output_tokens,
            "total": cost.input_tokens + cost.output_tokens,
        },
    }


# --------------------------------------------------------------------------- #
# A scripted stand-in for Bedrock, so the loop above can be exercised without
# credentials. It is not a mock of the model's judgement: it plays a fixed
# sequence of tool calls and replies, which is enough to prove that the routing,
# the tool_result envelope, the board and the cost accounting all hold together.
# The real thing is still the real thing. This only means the first run against
# Bedrock is not also the first run of this file.
class _Reply:
    def __init__(self, blocks, stop_reason):
        self.content = blocks
        self.stop_reason = stop_reason
        self.usage = _Usage()


class _Usage:
    input_tokens = 1200
    cache_read_input_tokens = 0
    output_tokens = 300


class _Text:
    type = "text"

    def __init__(self, text): self.text = text


class _ToolUse:
    type = "tool_use"
    _n = 0

    def __init__(self, name, arguments):
        _ToolUse._n += 1
        self.id = f"toolu_{_ToolUse._n:03d}"
        self.name = name
        self.input = arguments


class ScriptedClient:
    """Replays a queue of replies, one per messages.create call."""

    def __init__(self, script):
        self._script = list(script)
        self.calls: List[dict] = []
        self.messages = self

    def create(self, **kwargs):
        # The envelope matters as much as the content: a malformed tool_result
        # is the failure that only shows up against the real API.
        for m in kwargs["messages"]:
            if m["role"] != "user" or not isinstance(m["content"], list):
                continue
            for block in m["content"]:
                if block.get("type") == "tool_result":
                    assert "tool_use_id" in block, "tool_result without tool_use_id"
                    assert isinstance(block["content"], str), "tool_result content must be text"
        self.calls.append({"system": kwargs["system"][:40],
                           "tools": [t["name"] for t in kwargs["tools"]]})
        if not self._script:
            return _Reply([_Text("nothing further")], "end_turn")
        return self._script.pop(0)


def demo() -> None:
    """Drive one event through the whole team with the scripted client."""
    from core import store

    seen: List[str] = []

    def report(kind, d):
        seen.append(f"{kind}:{d.get('agent', '')}")

    # Arya calls Elsa, then Kira, then writes up. Elsa reads stock, Kira rules.
    script = [
        _Reply([_ToolUse("ask_impact", {"task": "What does the Ningbo closure hit?"})], "tool_use"),
        _Reply([_ToolUse("get_material_stock", {"material": "M-4471", "plant": "KRW1"})], "tool_use"),
        _Reply([_Text("M-4471 at KRW1 has 84 t against 9.2 t/day.")], "end_turn"),
        _Reply([_ToolUse("ask_compliance", {"task": "Rule on the replacement options."})], "tool_use"),
        _Reply([_ToolUse("check_local_constraints", {"option_id": "E"})], "tool_use"),
        _Reply([_Text("Option E is blocked: TKDN falls to 34.8%.")], "end_turn"),
        _Reply([_Text("Recommend B+C. E is cheaper and is not available to us.")], "end_turn"),
    ]
    cl = ScriptedClient(script)

    event = {"id": "evt_demo", "kind": "port_closure",
             "title": "Typhoon closes the Port of Ningbo", "trigger": "maritime advisory"}

    board, cost, called = Board(), Cost(), []
    messages: List[dict] = [{"role": "user", "content": json.dumps(event)}]
    lead_tools = _specialist_tools() + registry.schemas_for_model("supervisor")

    # Mirror run() without its client() call, which needs a real region.
    for _ in range(MAX_LEAD_ROUNDS):
        r = cl.messages.create(model=CFG.model, max_tokens=16000,
                               system=SUPERVISOR.instructions, tools=lead_tools,
                               messages=messages)
        cost.add(r.usage)
        messages.append({"role": "assistant", "content": r.content})
        if r.stop_reason != "tool_use":
            recommendation = "".join(b.text for b in r.content if b.type == "text")
            break
        results = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            code = b.name[len("ask_"):]
            called.append(code)
            summary = _tool_loop(cl, ALL[code], b.input["task"], board, cost, report)
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": summary})
        messages.append({"role": "user", "content": results})

    assert called == ["impact", "compliance"], called
    assert "Recommend B+C" in recommendation, recommendation
    assert "impact.get_material_stock" in board.findings, list(board.findings)
    assert "compliance.check_local_constraints" in board.findings, list(board.findings)

    # The board must remember where each finding came from, because the
    # calculator's refusal downstream depends on exactly this. Today both are
    # modelled: the stock is a fixture, and Kira is ruling from fixture
    # parameters because references/ has not been written.
    assert board.origin["impact.get_material_stock"] == "modelled"
    assert board.origin["compliance.check_local_constraints"] == "modelled"
    assert sorted(board.untrusted_keys()) == [
        "compliance.check_local_constraints", "impact.get_material_stock",
    ], board.untrusted_keys()

    # Kira's ruling is derived from fixture parameters until references/ exists.
    ruling = board.findings["compliance.check_local_constraints"]
    assert ruling["allowed"] is False and "TKDN" in ruling["reason"], ruling

    assert cost.idr > 0, "token accounting never ran"

    # Value and origin are one record, so a finding cannot exist without saying
    # where it came from.
    for key, entry in board.entries.items():
        assert entry.origin and entry.source and entry.at, (key, entry)
    assert set(board.findings) == set(board.origin) == set(board.entries)
    assert seen.count("specialist_done:impact") == 1, seen

    _check_failure_paths()

    print(f"graph ok, {len(called)} specialists called: {' then '.join(called)}")
    print(f"  board     {len(board.findings)} findings, "
          f"{len(board.untrusted_keys())} not yet trustworthy")
    for k in sorted(board.untrusted_keys()):
        print(f"            {k} is {board.origin[k]} from {board.source[k]}")
    print(f"  cost      Rp {cost.idr:,} across {len(cl.calls)} model calls")
    print(f"  answer    {recommendation}")


def _check_failure_paths() -> None:
    """The happy path is the easy half. These are the ways a handling ends badly."""
    from agents.definitions import PromptMissing

    # Every agent must be reachable, have a prompt, and expose a valid schema.
    for code, agent in ALL.items():
        assert agent.instructions, code               # raises PromptMissing if absent
        for spec in registry.schemas_for_model(code):
            assert spec["input_schema"]["additionalProperties"] is False, spec["name"]
            assert spec["strict"] is True, spec["name"]

    # An agent with no prompt raises rather than being sent an empty one.
    ghost = Agent("ghost", "Nemo", "Nobody", "does not exist")
    try:
        ghost.instructions
        raise AssertionError("a missing prompt must raise")
    except PromptMissing:
        pass

    # A tool that throws comes back as an error result, not a crashed handling.
    board, cost = Board(), Cost()
    seen: List[str] = []
    boom = ScriptedClient([
        _Reply([_ToolUse("check_local_constraints", {"option_id": "nope"})], "tool_use"),
        _Reply([_Text("that option does not exist")], "end_turn"),
    ])
    out = _tool_loop(boom, ALL["compliance"], "rule on ZZ", board,
                     cost, lambda k, d: seen.append(k))
    assert "does not exist" in out, out

    # A tool name the registry does not know is refused the same way.
    board2 = Board()
    unknown = ScriptedClient([
        _Reply([_ToolUse("no_such_tool", {})], "tool_use"),
        _Reply([_Text("recovered")], "end_turn"),
    ])
    assert _tool_loop(unknown, ALL["impact"], "go", board2, Cost(),
                      lambda k, d: None) == "recovered"
    assert not board2.entries, "a failed tool must not write to the board"

    # The spend cap stops a handling rather than letting it run on.
    spent = Cost(input_tokens=10**9, output_tokens=10**9)
    assert spent.idr > CFG.cost_cap_per_event_idr
    try:
        _tool_loop(ScriptedClient([]), ALL["impact"], "go", Board(), spent,
                   lambda k, d: None)
        raise AssertionError("the spend cap did not fire")
    except BudgetExhausted:
        pass

    # So does the deadline, independently of the spend.
    try:
        _tool_loop(ScriptedClient([]), ALL["impact"], "go", Board(), Cost(),
                   lambda k, d: None, deadline=time.monotonic() - 1)
        raise AssertionError("the deadline did not fire")
    except DeadlineExceeded:
        pass

    # Asking for an agent that does not exist is a KeyError, not a silent default.
    try:
        ask_specialist("nobody", "hello")
        raise AssertionError("an unknown agent must raise")
    except KeyError:
        pass


if __name__ == "__main__":
    demo()
