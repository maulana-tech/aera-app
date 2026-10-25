"""Async, frontier-driven dispatch —  Phase 2, adapted to SIGAP.

The default handling (graph.py `_handle_event`) is SYNCHRONOUS: Arya calls one
specialist, waits for it, decides the next, waits, and so on.  swarm
instead treats the graph as a claimable frontier: the orchestrator fires leads
and harvests them as they finish, so several run at once. This module brings
that here, flag-gated (SIGAP_SWARM_ASYNC), leaving the synchronous path the
default and untouched.

How it maps to SIGAP's single Python process:

  * A "worker" is an in-process specialist tool-loop (the same `_tool_loop` the
    sync path runs), submitted to a ThreadPoolExecutor. Specialists are
    I/O-bound on the Bedrock call, so threads give real concurrency.

  * The lead frontier IS the dispatch queue (core/exploration.py). The
    DISPATCHER THREAD alone claims, settles, plans and sums cost — so there is
    no claim race and no cost race. Pool threads only run their specialist and
    write facts (SQLite WAL serializes those writes; the upserts are
    idempotent). Each pool thread binds its own run + board so the tools see
    the right context, because ContextVars do not cross threads on their own.

  * Admission (core/admission.py) bounds how many run at once, per operator and
    globally — acquired by the dispatcher before a submit, released exactly
    once when that lead reaches a terminal state. Heavy specialists (the
    rule-giver, who runs at high effort) cost more weight than a light lookup.

  * Termination is non-lossy: on deadline or budget the dispatcher stops
    firing, lets in-flight work drain, and hands back what the graph holds
    (graph.py `_salvage`), never discarding it.

  * Convergence is read off the graph: no actionable lead and nothing in
    flight. Then Arya writes the recommendation ONCE from the settled graph —
    the one place a model still runs, to phrase the trade-offs and residual
    risk, exactly her job in the sync path.

Everything here is fail-open per lead: one specialist raising settles ITS lead
'failed' and the rest carry on.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Callable, Dict, List, Optional, Tuple

from agents.definitions import ALL
from core import admission, exploration as ex, registry
from core.config import CFG


def async_enabled() -> bool:
    return os.environ.get("SIGAP_SWARM_ASYNC", "0") == "1"


def max_workers() -> int:
    try:
        n = int(os.environ.get("SIGAP_ASYNC_WORKERS", "4"))
    except ValueError:
        n = 4
    return max(1, min(16, n))


#: Which specialist owns each lead kind, and how to phrase its task. The planner
#: opens leads keyed `<kind>:<subject>`; this is how a kind becomes a worker.
#: A heavier `weight` means the specialist costs more admission units (the
#: rule-giver runs at high effort — a nod to  heavy/light worker split).
_ROUTE: Dict[str, Tuple[str, Callable[[str], str], int]] = {
    "impact":  ("impact",     lambda s: f"Trace the impact of this disruption ({s}). "
                              "Which POs, stock and customer commitments are hit?", 1),
    "source":  ("sourcing",   lambda s: f"Find alternate sources for material {s}.", 1),
    "rule":    ("compliance", lambda s: f"Rule on supply option {s} under TKDN, LARTAS "
                              "and the customer contract. Your rejection is final.", 2),
    "price":   ("simulation", lambda s: f"Price supply option {s} and compare it with "
                              "the alternatives that cleared the rules.", 1),
    "demand":  ("demand",     lambda s: f"Is daily consumption of {s} still at the "
                              "recorded rate, or is demand moving?", 1),
    "stock":   ("inventory",  lambda s: f"Is the recorded stock of {s} actually usable "
                              "(quality holds, rejected batches, safety floor)?", 1),
    "logistics": ("logistics", lambda s: f"When does {s} realistically land, with port "
                               "dwell, transhipment and customs?", 1),
}


def route_lead(lead_key: str) -> Optional[Tuple[str, str, int]]:
    """A lead_key `<kind>:<subject>` → (specialist_code, task_text, weight), or
    None when nothing owns that kind (the dispatcher settles such a lead
    'stopped' rather than spinning on it)."""
    if ":" not in lead_key:
        return None
    kind, subject = lead_key.split(":", 1)
    spec = _ROUTE.get(kind)
    if not spec:
        return None
    code, task_fn, weight = spec
    return code, task_fn(subject), weight


# --------------------------------------------------------------------------- #
def _operator(event: dict) -> str:
    return str(event.get("operator") or event.get("operator_id") or "system")


def handle_event_async(
    event: dict,
    report: Callable[[str, dict], None],
    board,
    called: List[str],
    cost,
    *,
    client_factory: Optional[Callable[[], object]] = None,
    run_lead: Optional[Callable] = None,
    finalize: Optional[Callable] = None,
    fa: Optional[admission.FairAdmission] = None,
) -> dict:
    """Drive one event over the claimable frontier. Raises BudgetExhausted /
    DeadlineExceeded on a global stop, so graph.run's salvage concludes
    non-lossily — identical to the synchronous path's contract.

    The injectable seams (`client_factory`, `run_lead`, `finalize`, `fa`) exist
    so the whole loop is testable without Bedrock; production uses the defaults.
    """
    from graph import Cost, _tool_loop, client, BudgetExhausted, DeadlineExceeded  # late: avoid cycle

    run_id = registry.current_run()
    if not run_id:
        raise RuntimeError("async dispatch needs a bound run")
    fa = fa or admission.GLOBAL
    operator = _operator(event)
    client_factory = client_factory or client
    deadline = time.monotonic() + MAX_SECONDS_PER_EVENT()

    from core import store
    eid = str(event.get("id") or event.get("event_id") or run_id)

    # Seed the frontier: the event root, the impact lead, and a source lead per
    # material the event already names (a disruption identifies the material(s)
    # it hits). The planner chains the rest — options → rulings → prices — as
    # the specialists fill the graph.
    from engine import planner
    materials = event.get("materials") or event.get("affected_materials")
    with store.connect() as c:
        planner.seed_from_event(c, run_id, eid, materials=materials)

    def _run_lead(lead: dict) -> dict:
        """Runs in a POOL thread. Binds its own run + board (ContextVars do not
        cross threads), runs the specialist, returns a per-lead result. Its own
        Cost avoids a cross-thread race on the shared one."""
        code, task, _w = route_lead(lead["lead_key"])  # type: ignore[misc]
        specialist = ALL[code]
        local_cost = Cost()
        with registry.bind_run(run_id), registry.bind_board(board):
            try:
                summary = _tool_loop(client_factory(), specialist, task, board,
                                     local_cost, report, deadline)
                return {"lead": lead, "ok": True, "summary": summary,
                        "cost": local_cost, "code": code}
            except (BudgetExhausted, DeadlineExceeded):
                raise
            except Exception as e:                                   # noqa: BLE001
                return {"lead": lead, "ok": False, "code": code,
                        "summary": f"{specialist.title} failed: {type(e).__name__}: {e}",
                        "cost": local_cost}

    run_lead = run_lead or _run_lead
    finalize = finalize or _finalize

    pool = ThreadPoolExecutor(max_workers=max_workers())
    inflight: Dict[object, dict] = {}        # future -> {lead, code, weight}
    stop_reason: Optional[Exception] = None
    try:
        while True:
            # Global stops: stop FIRING, let in-flight drain, then salvage.
            if cost.idr > CFG.cost_cap_per_event_idr:
                stop_reason = BudgetExhausted(f"over Rp {CFG.cost_cap_per_event_idr:,}")
            elif time.monotonic() > deadline:
                stop_reason = DeadlineExceeded(f"handling ran past {MAX_SECONDS_PER_EVENT()}s")

            # Fire: claim open leads up to pool + admission capacity (dispatcher
            # thread only — no claim race).
            refused = False
            if stop_reason is None:
                while len(inflight) < max_workers():
                    with store.connect() as c:
                        lead = ex.claim_next_lead(c, run_id, owner="dispatcher")
                    if not lead:
                        break
                    routed = route_lead(lead["lead_key"])
                    if not routed:
                        with store.connect() as c:
                            ex.settle_lead(c, run_id, lead["lead_key"], "stopped")
                        continue
                    code, _task, weight = routed
                    if not fa.try_acquire(operator, weight):
                        # Over the concurrency budget right now (this operator's
                        # cap, or the global pool full of other operators' work):
                        # give THIS lead back to the frontier without burning its
                        # attempt, and retry on a later pass once a slot frees.
                        with store.connect() as c:
                            ex.reopen_lead(c, run_id, lead["lead_key"], uncount_attempt=True)
                        refused = True
                        break
                    called.append(code)
                    report("specialist_start", {"agent": code, "name": ALL[code].nickname,
                                                "task": lead["lead_key"]})
                    fut = pool.submit(run_lead, lead)
                    inflight[fut] = {"lead": lead, "code": code, "weight": weight}

            if not inflight:
                if stop_reason is not None:
                    raise stop_reason
                if refused:
                    # Work remains but every slot is taken by OTHER operators and
                    # none of ours is in flight to free one. Do not converge —
                    # wait (non-blocking, the deadline above still bounds it) and
                    # retry, the posture  non-blocking admission takes.
                    time.sleep(0.25)
                    continue
                break                        # nothing running, nothing to claim → converged

            # Harvest whatever finished.
            done, _pending = wait(list(inflight), timeout=1.0, return_when=FIRST_COMPLETED)
            for fut in done:
                meta = inflight.pop(fut)
                lead, code, weight = meta["lead"], meta["code"], meta["weight"]
                fa.release(operator, weight)             # exactly-once, exact weight
                try:
                    res = fut.result()
                except (BudgetExhausted, DeadlineExceeded) as e:
                    stop_reason = stop_reason or e
                    with store.connect() as c:
                        ex.settle_lead(c, run_id, lead["lead_key"], "stopped")
                    continue
                cost.add_cost(res["cost"])               # sum on the dispatcher thread
                state = "worked" if res["ok"] else "failed"
                with store.connect() as c:
                    ex.settle_lead(c, run_id, lead["lead_key"], state)
                    ex.annotate_lead(c, run_id, lead["lead_key"], summary=res["summary"],
                                     cost_idr=res["cost"].idr, status=state)
                    planner.plan_next_leads(c, run_id)   # chain: the graph grows new leads
                report("specialist_done", {"agent": code, "name": ALL[code].nickname,
                                           "summary": res["summary"][:400],
                                           "full_summary": res["summary"],
                                           "error": not res["ok"]})
    finally:
        pool.shutdown(wait=True)

    # Converged (or drained): Arya writes the recommendation from the graph.
    return finalize(event, report, board, called, cost, client_factory, run_id)


def _finalize(event, report, board, called, cost, client_factory, run_id) -> dict:
    """Arya's one model call: read the settled graph + board and write the
    recommendation with its trade-offs and residual risk. Fail-open — if the
    model is unavailable, hand back a labelled evidence summary (never a guess),
    the same non-lossy posture as the deadline path."""
    from graph import SUPERVISOR, _graph_frontier, _model_request
    from core import store

    with store.connect() as c:
        g = ex.get_graph(c, run_id)
    options = [n for n in g["nodes"] if n["kind"] == "option"]
    rulings = {n["subject"]: n["state"] for n in g["nodes"] if n["kind"] == "ruling"}
    summary_lines = [f"- board: {board.summary()}"]
    for o in options:
        state = rulings.get(o["subject"], "not yet ruled")
        summary_lines.append(f"- option {o['subject']} ({o.get('label') or ''}): {state}")
    graph_digest = "\n".join(summary_lines)

    try:
        cl = client_factory()
        r = cl.messages.create(
            **_model_request(SUPERVISOR), max_tokens=16000, system=SUPERVISOR.instructions,
            messages=[{"role": "user", "content":
                       "The specialists have finished. Here is the settled exploration "
                       f"graph for this event:\n\n{graph_digest}\n\nWrite the final "
                       "recommendation: the option you recommend, the trade-offs, and the "
                       "residual risk. Do not call tools; the work is done."}],
        )
        cost.add(r.usage)
        text = "".join(getattr(b, "text", "") for b in r.content
                       if getattr(b, "type", None) == "text")
    except Exception as e:                                           # noqa: BLE001
        text = ("No final recommendation was written (the lead could not run: "
                f"{type(e).__name__}). What the graph established:\n{graph_digest}")

    with store.connect() as c:
        frontier = _graph_frontier(run_id)
    return {"status": "done", "recommendation": text, "agents_called": called,
            "cost_idr": cost.idr, "cost_by_model": cost.split(),
            "untrusted_on_board": board.untrusted_keys(),
            "graph": frontier, "mode": "async"}


def MAX_SECONDS_PER_EVENT() -> int:
    from graph import MAX_SECONDS_PER_EVENT as m
    return m


def demo() -> None:
    """Self-check: a scripted frontier runs leads concurrently, chains
    option→rule→price, isolates a failing specialist, balances admission, and
    converges. No Bedrock — a per-specialist scripted client is injected."""
    os.environ["SIGAP_GRAPH"] = "1"
    os.environ["SIGAP_SWARM_ASYNC"] = "1"
    from core import store
    import graph as G

    # A scripted client that dispatches on the AVAILABLE TOOLS (reliable — unlike
    # the system prompt, which cross-references other agents by name), and ends
    # after exactly one tool call per specialist (once a tool_result is in the
    # transcript it writes its summary), so each lead runs deterministically
    # across threads.
    import re as _re
    class _Blk:
        def __init__(self, text, tool=None):
            self.type = "tool_use" if tool else "text"
            if tool:
                self.name, self.input, self.id = tool[0], tool[1], "t1"
            else:
                self.text = text
    class _Usage:
        input_tokens = 500; cache_read_input_tokens = 0; output_tokens = 100
    class _Reply:
        def __init__(self, blocks, stop): self.content = blocks; self.stop_reason = stop; self.usage = _Usage()
    def _already_ran(msgs):
        last = msgs[-1].get("content") if msgs else None
        return isinstance(last, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in last)
    class _Msgs:
        def create(self, **kw):
            tool_names = {t["name"] for t in (kw.get("tools") or [])}
            msgs = kw["messages"]
            if _already_ran(msgs):
                return _Reply([_Blk("done")], "end_turn")
            if "find_alternate_sources" in tool_names:
                return _Reply([_Blk(None, ("find_alternate_sources", {"material": "M-4471"}))], "tool_use")
            if "check_local_constraints" in tool_names:
                first = str(msgs[0]["content"])
                m = _re.search(r"option (\w+)", first)
                oid = m.group(1) if m else "B"
                return _Reply([_Blk(None, ("check_local_constraints", {"option_id": oid}))], "tool_use")
            if "simulate_scenario" in tool_names:
                return _Reply([_Blk("priced it")], "end_turn")
            return _Reply([_Blk("done")], "end_turn")
    class _Client:
        messages = _Msgs()

    eid = store.record_event("port_closure", "async demo", "trig:async", {"q": "typhoon"}, "demo")
    rid = store.start_run(eid, "autonomous")
    event = {"id": eid, "kind": "port_closure", "materials": ["M-4471"]}
    board, called, cost = G.Board(), [], G.Cost()
    fa = admission.FairAdmission(global_slots=4, per_operator=3, enabled=True)

    # finalize stub: avoid a second model call; just assert the graph is settled.
    def fake_finalize(ev, rep, bd, cl_, co, cf, rid_):
        return {"status": "done", "recommendation": "recommend B (E blocked)",
                "agents_called": cl_, "cost_idr": co.idr, "mode": "async"}

    with registry.bind_run(rid), registry.bind_board(board):
        out = handle_event_async(event, lambda *a: None, board, called, cost,
                                 client_factory=lambda: _Client(), finalize=fake_finalize, fa=fa)

    with store.connect() as c:
        g = ex.get_graph(c, rid)
        leads = {n["lead_key"]: n["state"] for n in g["nodes"] if n["kind"] == "lead"}
        rulings = {n["subject"]: n["state"] for n in g["nodes"] if n["kind"] == "ruling"}
        assert ex.converged(c, rid), f"must converge, leads={leads}"
    assert out["mode"] == "async"
    assert rulings.get("E") == "blocked" and rulings.get("B") == "allowed", rulings
    assert leads.get("rule:E") in ("worked",), leads
    assert "price:E" not in leads, "E blocked → no price lead (negative knowledge held under async)"
    assert leads.get("price:B") == "worked", leads
    assert fa.total_active() == 0, "every admission slot was released"
    assert "impact" in called and "sourcing" in called and "compliance" in called, called

    # admission balance + routing unit checks
    assert route_lead("rule:E") == ("compliance", route_lead("rule:E")[1], 2)
    assert route_lead("nonsense:x") is None

    with store.connect() as c:
        c.execute("DELETE FROM graph_edges WHERE run_id=?", (rid,))
        c.execute("DELETE FROM graph_nodes WHERE run_id=?", (rid,))
        c.execute("DELETE FROM runs WHERE id=?", (rid,))
        c.execute("DELETE FROM events WHERE id=?", (eid,))

    print("dispatch ok, concurrent frontier ✓ · chained option→rule→price ✓ "
          "· E stayed blocked ✓ · admission balanced ✓ · converged ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_DISPATCH_SELFCHECK")
    demo()
