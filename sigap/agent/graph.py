"""The agent team. The lead calls specialists; each runs its own tool loop.

The pattern: specialists are exposed as tools belonging to the lead. The lead
decides who to call based on the last finding, there is no fixed sequence.
Each specialist runs its own tool-use loop to completion, then hands back a
summary along with the origin labels of the data behind it.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.definitions import ALL, SPECIALISTS, SUPERVISOR, Agent
import tools  # noqa: F401  (registers every tool; see tools/__init__.py)
from core import exploration as ex
from core import llm, registry
from core.config import CFG
from core.provenance import Result
from engine import dispatch, planner

# The rate for tokens whose model is not known, which in practice means the
# self-checks below that set token counts by hand. Opus 5's list price at
# 16,400 IDR/USD. Every real call is priced at its own model's rate instead,
# from the table in core/llm.py.
INPUT_IDR_PER_MILLION = 82_000
OUTPUT_IDR_PER_MILLION = 410_000
MAX_SPECIALIST_ROUNDS = 8
MAX_LEAD_ROUNDS = 14

#: Rounds and rupiah are not the only ways a handling can run away. One slow
#: specialist inside the round budget still blocks the queue behind it, so the
#: whole handling carries a deadline as well.
MAX_SECONDS_PER_EVENT = 600

#: Rows of one tool result a model is shown. A live tenant answers a broad
#: question with thousands of lines (the SAP sandbox holds over 2,000 open
#: order lines for one material), which is more than a context holds. Past
#: this the model gets the first rows, the total, and a request to narrow.
MODEL_ROWS = 50


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
        _mirror_to_graph(key, r)

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
    """Tokens and rupiah for one handling.

    With one model for the whole team a single rate was enough. With a model
    per agent it is not: a million MiniMax tokens cost a fifteenth of a million
    Opus ones. So each call is priced when it is added, at the rate of the
    model that actually answered (the fallback's, if it was the fallback), and
    `by_model` keeps the split, which is the figure that says whether the
    cheaper specialists were in fact cheaper.
    """
    input_tokens: int = 0
    output_tokens: int = 0
    priced_idr: float = 0.0
    priced_input: int = 0
    priced_output: int = 0
    by_model: Dict[str, Dict[str, float]] = field(default_factory=dict)

    @property
    def idr(self) -> int:
        # Tokens added without a model (set by hand) are priced at the default
        # rate: high, so a count of unknown origin can only trip the cap early.
        unpriced_in = self.input_tokens - self.priced_input
        unpriced_out = self.output_tokens - self.priced_output
        return round(self.priced_idr + unpriced_in / 1e6 * INPUT_IDR_PER_MILLION
                     + unpriced_out / 1e6 * OUTPUT_IDR_PER_MILLION)

    def add(self, usage) -> None:
        inp = ((getattr(usage, "input_tokens", 0) or 0)
               + (getattr(usage, "cache_read_input_tokens", 0) or 0)
               + (getattr(usage, "cache_creation_input_tokens", 0) or 0))
        out = getattr(usage, "output_tokens", 0) or 0
        self.input_tokens += inp
        self.output_tokens += out
        spec = getattr(usage, "spec", None)
        if spec is None:
            return                         # a stand-in client: default rate applies
        idr = llm.price_idr(usage)
        self.priced_input += inp
        self.priced_output += out
        self.priced_idr += idr
        m = self.by_model.setdefault(str(spec), {"input": 0, "output": 0, "idr": 0.0, "calls": 0})
        m["input"] += inp
        m["output"] += out
        m["idr"] += idr
        m["calls"] += 1

    def add_cost(self, other: "Cost") -> None:
        """Fold a specialist's own Cost into this one. The async dispatcher gives
        each lead its own Cost (so concurrent threads never race on one counter)
        and sums them here, on the single dispatcher thread."""
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.priced_idr += other.priced_idr
        self.priced_input += other.priced_input
        self.priced_output += other.priced_output
        for k, v in other.by_model.items():
            m = self.by_model.setdefault(k, {"input": 0, "output": 0, "idr": 0.0, "calls": 0})
            for f in m:
                m[f] += v[f]

    def split(self) -> Dict[str, dict]:
        """`by_model` rounded, for a run's record."""
        return {k: {**v, "idr": round(v["idr"])} for k, v in self.by_model.items()}


def client(agent: Optional[Agent] = None) -> llm.Router:
    """The model client for one handling (or one conversation, for `agent`).

    It routes each request to the model named in it, so one client serves an
    Opus lead and MiniMax specialists alike (core/llm.py). Checked against the
    agent that has to run first, the lead by default: if neither its model nor
    the fallback can be called, nothing is started and nothing is guessed."""
    agent = agent or SUPERVISOR
    spec = llm.spec_for(agent)
    if not llm.usable(spec):
        why = llm.ready(spec)[1]
        raise ModelNotReady(
            f"{agent.title}'s model {spec} cannot be called: {why}. The agent team "
            "cannot run without model access. ENV.md, under Models, has the setup."
        )
    return llm.Router()


def _shown(res) -> Tuple[Any, dict]:
    """The value a model sees, and the provenance it travels with."""
    value, brief = res.value, res.brief()
    if isinstance(value, list) and len(value) > MODEL_ROWS:
        brief["rows_total"] = len(value)
        brief["note"] = "; ".join(x for x in (
            brief["note"], f"showing the first {MODEL_ROWS} of {len(value)} rows; ask again "
                           "with a narrower filter (a plant, a port, a material) for the rest") if x)
        value = value[:MODEL_ROWS]
    return value, brief


def _model_request(agent: Agent, **req) -> dict:
    """The fields every model request carries, named for this agent. Thinking
    and effort are always asked for; core/llm.py drops them for a model that
    cannot take them, which is what the old `"haiku" in model` test did for one
    model by name."""
    spec = llm.spec_for(agent)
    fb = llm.fallback_for(agent, spec)
    return {"model": str(spec), **({"fallback": str(fb)} if fb else {}),
            "thinking": {"type": "adaptive"}, "output_config": {"effort": agent.effort},
            **req}


def _note_fallback(r, agent: Agent, report: Callable[[str, dict], None],
                   noted: List[bool]) -> None:
    """Write it to the trail, once per loop, when another model answered."""
    gone = getattr(r, "fell_back_from", None)
    if gone and not noted:
        noted.append(True)
        report("fallback", {"agent": agent.code, "name": agent.nickname,
                            "summary": f"{gone[0]} failed, so {getattr(r, 'model', '?')} "
                                       f"answered instead ({gone[1]})"})


# --------------------------------------------------------------------------- #
def _build_user_content(prompt_text: str,
                        attachments: Optional[List[dict]] = None) -> Any:
    """Build Anthropic message content from prompt text and optional file/image attachments."""
    if not attachments:
        return prompt_text

    blocks: List[dict] = []
    text_parts: List[str] = []
    allowed_images = {"image/jpeg", "image/png", "image/gif", "image/webp"}

    for att in attachments:
        if not isinstance(att, dict):
            continue
        name = str(att.get("name") or "attachment")
        mime = str(att.get("mime_type") or "").lower()
        b64 = att.get("data")
        txt = att.get("text_content")

        if mime in allowed_images and isinstance(b64, str) and b64:
            blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": b64,
                },
            })
        elif mime == "application/pdf" and isinstance(b64, str) and b64:
            blocks.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64,
                },
            })
        elif isinstance(txt, str) and txt:
            text_parts.append(
                f"Attached file '{name}' ({mime or 'text'}):\n```\n{txt[:30000]}\n```"
            )
        else:
            text_parts.append(f"[Attached file: {name} ({mime or 'binary'})]")

    combined_text = ("\n\n".join(text_parts) + "\n\n" + prompt_text) if text_parts else prompt_text
    if blocks:
        return [*blocks, {"type": "text", "text": combined_text}]
    return combined_text


def _run_tool(agent: Agent, b, board: Board, report: Callable[[str, dict], None],
              round_no: int, thinking: str) -> dict:
    """Run one tool call, record it on the trail, and return its tool_result.

    The trail keeps the whole result, with what it needs to be traced: its
    provenance, how long it took, which model turn asked for it. Only the
    model's copy is cut to MODEL_ROWS."""
    t0 = time.monotonic()
    step = {"agent": agent.code, "name": b.name, "arguments": b.input,
            "call_id": b.id, "round": round_no, "thinking": thinking}
    try:
        res = registry.run(b.name, dict(b.input))
    except Exception as e:                                           # noqa: BLE001
        err_msg = f"{type(e).__name__}: {e}"
        report("tool", {**step, "error": err_msg, "ms": round((time.monotonic() - t0) * 1000)})
        return {"type": "tool_result", "tool_use_id": b.id, "content": err_msg, "is_error": True}
    ms = round((time.monotonic() - t0) * 1000)
    board.write(f"{agent.code}.{b.name}", res)
    shown, brief = _shown(res)
    report("tool", {**step, "result": res.value, "origin": res.origin.value,
                    "source": res.source, "note": res.note, "fetched_at": brief["fetched_at"],
                    "rows": len(res.value) if isinstance(res.value, list) else None,
                    "rows_shown": len(shown) if isinstance(shown, list) else None,
                    "ms": ms})
    return {"type": "tool_result", "tool_use_id": b.id,
            "content": json.dumps({"value": shown, **brief}, ensure_ascii=False, default=str)}


def _tool_loop(cl, agent: Agent, task: str, board: Board,
               cost: Cost, report: Callable[[str, dict], None],
               deadline: Optional[float] = None,
               history: Optional[List[dict]] = None,
               attachments: Optional[List[dict]] = None) -> str:
    """One specialist works to completion. Returns the summary it wrote.

    `history` is earlier turns of the same conversation, already trimmed by the
    caller. Without it a follow-up question like "and the other plant?" has
    nothing to refer to, and the transcript on screen would be a record of a
    conversation the agent was never actually having.
    """
    tools = (
        (_specialist_tools() + registry.schemas_for_model(agent.code))
        if agent.code == "supervisor"
        else registry.schemas_for_model(agent.code)
    )
    prompt_text = (
        f"{task}\n\n"
        f"What is on the shared board right now:\n{board.summary()}\n\n"
        "Use your tools as needed, then write up what you found. If data you "
        "need is unavailable, say what is missing, do not guess."
    )
    messages: List[dict] = [*(history or []), {
        "role": "user",
        "content": _build_user_content(prompt_text, attachments),
    }]
    noted: List[bool] = []
    called = 0
    # What this loop spent, for the trace. The lead's figures include the
    # specialists it ran, since they share its Cost.
    began = time.monotonic()
    spent_from = (cost.input_tokens, cost.output_tokens, cost.idr)
    answered_by: List[str] = []

    def stats(rounds: int) -> dict:
        return {"model": answered_by[-1] if answered_by else str(llm.spec_for(agent)),
                "models": sorted(set(answered_by)), "rounds": rounds,
                "input_tokens": cost.input_tokens - spent_from[0],
                "output_tokens": cost.output_tokens - spent_from[1],
                "idr": cost.idr - spent_from[2],
                "seconds": round(time.monotonic() - began, 1)}

    for round_no in range(1, MAX_SPECIALIST_ROUNDS + 1):
        if cost.idr > CFG.cost_cap_per_event_idr:
            raise BudgetExhausted(f"over Rp {CFG.cost_cap_per_event_idr:,} per event")
        if deadline and time.monotonic() > deadline:
            raise DeadlineExceeded(
                f"{agent.title} still working after {MAX_SECONDS_PER_EVENT}s")

        req = _model_request(
            agent,
            max_tokens=16000 if agent.code == "supervisor" else 8000,
            system=agent.instructions,
            tools=tools,
            messages=messages,
        )
        r = cl.messages.create(**req)
        cost.add(r.usage)
        answered_by.append(str(getattr(r.usage, "spec", None) or getattr(r, "model", None)
                               or req["model"]))
        _note_fallback(r, agent, report, noted)
        messages.append({"role": "assistant", "content": r.content})

        thinking_text = "\n\n".join(
            getattr(b, "thinking", "")
            for b in r.content
            if getattr(b, "type", None) == "thinking" and getattr(b, "thinking", "")
        ).strip()
        note_text = "\n\n".join(
            getattr(b, "text", "")
            for b in r.content
            if getattr(b, "type", None) == "text" and getattr(b, "text", "")
        ).strip()

        if r.stop_reason != "tool_use":
            text = "".join(b.text for b in r.content if b.type == "text")
            if agent.code == "supervisor":
                report("summary", {"agent": "supervisor", "name": "Arya",
                                   "summary": "Formulating final mitigation recommendation",
                                   "full_summary": text,
                                   "thinking": thinking_text,
                                   "tool_calls": called, "stats": stats(round_no)})
            else:
                report("specialist_done", {"agent": agent.code, "name": agent.nickname,
                                           "summary": text[:400],
                                           "full_summary": text,
                                           "thinking": thinking_text,
                                           "tool_calls": called,
                                           "stats": stats(round_no)})
                if tools and not called:
                    # Seen on a small model: Bram wrote "here's what I'm
                    # executing" and called nothing, and the lead reported the
                    # transfers as done. The lead cannot tell prose from a
                    # recorded action, so code tells it.
                    return (f"[SIGAP: {agent.nickname} called no tool in this turn. Nothing "
                            "below was read from a source or carried out; no action was "
                            "recorded. Treat any figure in it, and any claim that something "
                            f"was done, as unverified.]\n\n{text}")
            return text

        # every tool_result MUST go back in ONE user message
        results: List[dict] = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            called += 1
            if b.name.startswith("ask_") and b.name[len("ask_"):] in ALL:
                code = b.name[len("ask_"):]
                specialist = ALL[code]
                task_text = b.input.get("task", "")
                report("specialist_start", {"agent": code, "name": specialist.nickname,
                                            "task": task_text, "call_id": b.id,
                                            "by": agent.code, "round": round_no,
                                            "thinking": thinking_text or note_text})
                summary = _run_specialist_isolated(cl, specialist, task_text, board,
                                                   cost, report, deadline)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": summary})
                continue

            results.append(_run_tool(agent, b, board, report, round_no,
                                     thinking_text or note_text))
        messages.append({"role": "user", "content": results})

    stopped = f"[{agent.title} stopped: exceeded {MAX_SPECIALIST_ROUNDS} tool rounds]"
    if agent.code != "supervisor":
        report("specialist_done", {"agent": agent.code, "name": agent.nickname,
                                   "summary": stopped, "full_summary": stopped, "error": True,
                                   "tool_calls": called, "stats": stats(MAX_SPECIALIST_ROUNDS)})
    return stopped


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


# --------------------------------------------------------------------------- #
# Exploration-graph write-through (SIGAP_GRAPH, default off; fail-open).
#
# The in-memory Board is the live workspace; the persisted graph is its durable,
# typed mirror. Every tool result that lands on the board also lands on the
# graph as a fact carrying its provenance, and the two results that drive the
# mitigation chain — found options and Kira's rulings — become typed option and
# ruling nodes. The planner then grows the lead frontier off them (option →
# rule → price), so the graph records not just what was found but the shape of
# the reasoning that reached it.
#
# This is the SmartX "Phase 1" mirror: the graph is populated alongside the
# existing LLM loop WITHOUT changing its control flow. Flipping the frontier
# authoritative (claim-based dispatch) is a later phase; landing the mirror
# first is what their own phasing prescribes, and it keeps this non-breaking.
# Everything here is wrapped so a graph error can never disturb a handling.
def _mirror_to_graph(key: str, r: Result) -> None:
    if not ex.enabled():
        return
    run_id = registry.current_run()
    if not run_id:
        return                            # a chat question opens no run → no graph
    try:
        from core import store
        with store.connect() as c:
            fact_id = ex.write_fact(c, run_id, key, r)

            # Found options: a list of AlternateSource rows, each with an id.
            if key.endswith("find_alternate_sources") and isinstance(r.value, list):
                for opt in r.value:
                    if not isinstance(opt, dict) or "id" not in opt:
                        continue
                    oid = str(opt["id"])
                    node = ex.upsert_node(c, run_id, "option", f"option:{oid}",
                                          subject=oid, label=opt.get("label"),
                                          payload=opt)
                    ex.add_edge(c, run_id, fact_id, "yields", node)

            # A ruling: check_local_constraints returns {option_id, allowed, reason}.
            elif key.endswith("check_local_constraints") and isinstance(r.value, dict):
                oid = str(r.value.get("option_id", "")).strip()
                if oid:
                    state = "allowed" if r.value.get("allowed") else "blocked"
                    ruling = ex.upsert_node(c, run_id, "ruling", f"ruling:{oid}",
                                            subject=oid, state=state,
                                            label=r.value.get("reason"), payload=r.value)
                    opt = ex.find_node_by_dedup(c, run_id, f"option:{oid}")
                    if opt:
                        ex.add_edge(c, run_id, ruling, "rules_on", opt)

            # Grow the frontier: open the next leads newly enabled by the above.
            planner.plan_next_leads(c, run_id)
    except Exception as _e:               # noqa: BLE001  — the mirror must never break a handling
        if os.environ.get("SIGAP_DEBUG"):
            import traceback; traceback.print_exc()
        pass


def _seed_graph(event: dict) -> None:
    """Open the event root + the impact lead on the graph (flag-gated, fail-open)."""
    if not ex.enabled():
        return
    run_id = registry.current_run()
    if not run_id:
        return
    try:
        from core import store
        eid = str(event.get("id") or event.get("event_id") or run_id)
        with store.connect() as c:
            planner.seed_from_event(c, run_id, eid)
    except Exception:                     # noqa: BLE001
        pass


def _graph_frontier(run_id: Optional[str]) -> dict:
    """A read-only snapshot of the graph's frontier for the run result, so a
    handling can report whether the lead frontier has drained (converged) and
    how deep the graph grew. Fail-open to an empty snapshot."""
    if not ex.enabled() or not run_id:
        return {}
    try:
        from core import store
        with store.connect() as c:
            g = ex.get_graph(c, run_id)
            return {
                "nodes": len(g["nodes"]),
                "open_leads": ex.count_open_leads(c, run_id),
                "active_leads": ex.count_active_leads(c, run_id),
                "converged": ex.converged(c, run_id),
            }
    except Exception:                     # noqa: BLE001
        return {}


# --------------------------------------------------------------------------- #
# Fail-open specialist isolation (#3) and non-lossy termination (#1).
#
# Before: one specialist raising, or the per-event budget/deadline tripping,
# propagated out and the whole handling was recorded `failed` — every finding
# already on the board discarded.  swarm never loses a verdict that
# way: a cancelled or timed-out run still harvests what it has. These two
# helpers bring that discipline to SIGAP, flag-gated so the default is
# unchanged.
def _run_specialist_isolated(cl, specialist: Agent, task: str, board: Board,
                             cost: Cost, report, deadline) -> str:
    """Run one specialist, isolating it. A BUDGET or DEADLINE stop is global and
    re-raised (it ends the whole handling, where the salvage below catches it).
    Any OTHER exception is this specialist's alone: it is reported, its lead is
    settled 'failed' on the graph, and an error note goes back to Arya so she
    carries on with the rest — one specialist does not take the handling down."""
    try:
        return _tool_loop(cl, specialist, task, board, cost, report, deadline)
    except (BudgetExhausted, DeadlineExceeded):
        raise
    except Exception as e:                                           # noqa: BLE001
        err = f"{specialist.title} could not complete: {type(e).__name__}: {e}"
        report("specialist_done", {"agent": specialist.code, "name": specialist.nickname,
                                   "summary": err, "full_summary": err, "error": True})
        if ex.enabled():
            try:
                from core import store
                run_id = registry.current_run()
                if run_id:
                    with store.connect() as c:
                        ex.settle_lead(c, run_id, ex.canonical_lead_key(specialist.code, "task"),
                                       "failed")
            except Exception:                                        # noqa: BLE001
                pass
        return f"[{err}. Continue with the other specialists; do not retry this one.]"


def _salvage(board: Board, called: List[str], cost: Cost, reason: str) -> dict:
    """Assemble the best honest statement from the evidence already on the board
    when a handling is stopped early — instead of failing and discarding it.

    It does NOT invent a recommendation (no model runs here, and guessing is the
    one thing SIGAP never does). It states plainly that the handling stopped,
    why, and exactly what was established and how trustworthy each piece is —
    the same provenance discipline the calculator enforces. A person reads this
    and decides, rather than being told nothing because the clock ran out."""
    trusted = [k for k, e in board.entries.items()
               if e.origin in ("live", "cached", "derived")]
    untrusted = board.untrusted_keys()
    lines = [f"Handling stopped early: {reason}.",
             "No final recommendation was produced. What was established so far, "
             "labelled by how far it can be trusted:"]
    for k, e in board.entries.items():
        lines.append(f"  - {k}: {e.origin} (from {e.source})")
    if not board.entries:
        lines.append("  (nothing was gathered before the stop)")
    return {
        "status": "partial",
        "reason": reason,
        "recommendation": "\n".join(lines),
        "agents_called": called,
        "cost_idr": cost.idr, "cost_by_model": cost.split(),
        "trusted_on_board": trusted,
        "untrusted_on_board": untrusted,
        "graph": _graph_frontier(registry.current_run()),
    }


def run(event: dict, report: Callable[[str, dict], None]) -> dict:
    """Handle one event. `report` is called on every piece of progress."""
    board = Board()
    # The board is the evidence in force for this handling. Binding it here
    # lets a tool ask how trustworthy the ground under it is without having to
    # be handed the board through every call: tools/execution.py refuses to act
    # on its own authority when anything under the decision is not trusted.
    called: List[str] = []
    cost = Cost()
    with registry.bind_board(board):
        try:
            if dispatch.async_enabled():
                #  Phase 2: fire leads over the claimable frontier and
                # harvest them as they finish, several at once. The frontier,
                # planner and convergence are the graph's; Arya writes the final
                # recommendation from the settled graph. (The dispatcher seeds
                # the frontier itself, so _seed_graph is the sync path's only.)
                return dispatch.handle_event_async(event, report, board, called, cost)
            # Seed the graph's root + first lead (flag-gated, fail-open). The
            # impact lead always opens; option/rule/price leads grow from what
            # the specialists find, via the write-through mirror.
            _seed_graph(event)
            return _handle_event(event, report, board, called, cost)
        except (BudgetExhausted, DeadlineExceeded) as e:
            # Non-lossy: a handling that hits its budget or deadline concludes on
            # the evidence it has, labelled — it is not thrown away.
            return _salvage(board, called, cost, str(e))


def _handle_event(event: dict, report: Callable[[str, dict], None], board: Board,
                  called: List[str], cost: Cost) -> dict:
    cl = client()
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
    noted: List[bool] = []
    began = time.monotonic()
    answered_by: List[str] = []

    for round_no in range(1, MAX_LEAD_ROUNDS + 1):
        if cost.idr > CFG.cost_cap_per_event_idr:
            raise BudgetExhausted(f"over Rp {CFG.cost_cap_per_event_idr:,}")
        if time.monotonic() > deadline:
            raise DeadlineExceeded(f"handling ran past {MAX_SECONDS_PER_EVENT}s")

        lead_req = _model_request(
            SUPERVISOR,
            max_tokens=16000,
            system=SUPERVISOR.instructions,
            tools=lead_tools,
            messages=messages,
        )
        r = cl.messages.create(**lead_req)
        cost.add(r.usage)
        answered_by.append(str(getattr(r.usage, "spec", None) or getattr(r, "model", None)
                               or lead_req["model"]))
        _note_fallback(r, SUPERVISOR, report, noted)
        messages.append({"role": "assistant", "content": r.content})
        thinking_text = "\n\n".join(
            getattr(b, "thinking", "") for b in r.content
            if getattr(b, "type", None) == "thinking" and getattr(b, "thinking", "")).strip()

        if r.stop_reason != "tool_use":
            text = "".join(b.text for b in r.content if b.type == "text")
            # The whole handling's spend: the lead's turns and every specialist's.
            report("summary", {"agent": "supervisor", "name": "Arya",
                               "summary": "Formulating final mitigation recommendation",
                               "full_summary": text, "thinking": thinking_text,
                               "stats": {"model": answered_by[-1],
                                         "models": sorted(set(answered_by)),
                                         "rounds": round_no,
                                         "input_tokens": cost.input_tokens,
                                         "output_tokens": cost.output_tokens,
                                         "idr": cost.idr, "by_model": cost.split(),
                                         "seconds": round(time.monotonic() - began, 1)}})
            return {
                "status": "done",
                "recommendation": text,
                "agents_called": called,
                "cost_idr": cost.idr, "cost_by_model": cost.split(),
                "untrusted_on_board": board.untrusted_keys(),
                "graph": _graph_frontier(registry.current_run()),
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
                                            "task": b.input.get("task", ""), "call_id": b.id,
                                            "by": "supervisor", "round": round_no,
                                            "thinking": thinking_text})
                summary = _run_specialist_isolated(cl, specialist, b.input["task"],
                                                   board, cost, report, deadline)
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": summary})
            else:
                results.append(_run_tool(SUPERVISOR, b, board, report, round_no, thinking_text))
        messages.append({"role": "user", "content": results})

    return {"status": "stopped", "reason": f"exceeded {MAX_LEAD_ROUNDS} lead rounds",
            "agents_called": called, "cost_idr": cost.idr, "cost_by_model": cost.split(),
            "graph": _graph_frontier(registry.current_run())}


def ask_specialist(code: str, question: str,
                   report: Optional[Callable[[str, dict], None]] = None,
                   history: Optional[List[dict]] = None,
                   attachments: Optional[List[dict]] = None) -> dict:
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
    cl = client(agent)
    answer = _tool_loop(cl, agent, question, board, cost, capture,
                        history=history, attachments=attachments)
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
        "cost_idr": cost.idr, "cost_by_model": cost.split(),
        "thinking_time": duration_s,
        "trail": trail,
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

    _check_resilience()


def _check_resilience() -> None:
    """#1 non-lossy termination and #3 fail-open specialist isolation."""
    # --- #1: a stopped handling salvages a labelled statement, not nothing. ---
    board = Board()
    from core.provenance import Origin, Result
    board.write("impact.get_material_stock",
                Result({"qty": 84.0}, Origin.MODELLED, "fixture:MaterialStock"))
    board.write("logistics.estimate_eta",
                Result({"eta": "2026-09-19"}, Origin.DERIVED, "engine/forecast.py"))
    out = _salvage(board, ["impact", "logistics"], Cost(input_tokens=5000), "deadline reached")
    assert out["status"] == "partial", out
    assert "deadline reached" in out["recommendation"]
    assert out["untrusted_on_board"] == ["impact.get_material_stock"], out
    assert out["trusted_on_board"] == ["logistics.estimate_eta"], out
    # it never invents a recommendation — it reports evidence + provenance only
    assert "modelled" in out["recommendation"] and "derived" in out["recommendation"]

    # --- #3: a specialist that raises is isolated; Arya is told to continue. ---
    class _Raises:
        def __init__(self, exc): self._exc = exc
        class _M:
            def __init__(self, exc): self._exc = exc
            def create(self, **_): raise self._exc
        @property
        def messages(self): return _Raises._M(self._exc)

    seen: List[str] = []
    note = _run_specialist_isolated(_Raises(RuntimeError("SAP 500")), ALL["impact"],
                                    "trace it", Board(), Cost(),
                                    lambda k, d: seen.append(k), deadline=None)
    assert "could not complete" in note and "Continue with the other" in note, note
    assert "specialist_done" in seen, "a failed specialist must still report"

    # A global stop (budget/deadline) is NOT isolated — it re-raises so the
    # salvage path above can conclude on the whole board.
    for exc in (BudgetExhausted("cap"), DeadlineExceeded("clock")):
        try:
            _run_specialist_isolated(_Raises(exc), ALL["impact"], "go", Board(),
                                     Cost(), lambda k, d: None, deadline=None)
            raise AssertionError(f"{type(exc).__name__} must propagate, not be isolated")
        except (BudgetExhausted, DeadlineExceeded):
            pass


if __name__ == "__main__":
    # The assertions in demo() pin the orchestration loop, not the state of
    # anyone's .env. With a SAP key present the stock read comes back live and
    # the origin assertions flipped, reporting a failure that was only a key
    # being set.
    from core.config import fixtures_only

    fixtures_only(__file__, "SIGAP_GRAPH_CHECK")
    demo()
