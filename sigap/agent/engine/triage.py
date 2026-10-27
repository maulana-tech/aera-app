"""The verdict: what, if anything, a person still owes this handling.

A queue of twenty disruptions is useless if the reader has to open each one to
learn which needs them. So every handling carries a verdict — and the verdict
is ARITHMETIC, not an opinion.

That is not fussiness. A model that says "this is critical" has made exactly
the kind of confident, unlabelled claim the rest of this system refuses: it
cannot be recomputed, it cannot be argued with, and it would drift the day the
specialists move to a cheaper model (which they are meant to be able to do).
Kira's veto is Python for the same reason. So is this.

Two rules hold the whole file together:

  * A verdict never says a word without the number that earns it. Not
    "critical" but "Rp 94,000,000 waiting, stock out in 3 days". Every line in
    `because` is a fact a reader can go and check.

  * A verdict is about what is OWED, not about how dramatic something is.
    "needs you now" and "handled" are instructions; "high" and "medium" are
    adjectives, and nobody has ever known what to do with an adjective.

The verdict is viewer-independent on purpose: it names the lowest role that can
approve, and the page compares that with whoever is signed in. Computing it per
viewer would mean the alert and the screen could disagree.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.identity import ROLE_LIMITS

WIB = timezone(timedelta(hours=7))

#: Cover at or under which a pending approval is treated as time-bound. Below
#: this the plant runs out before a new order could realistically land, so the
#: approval is not merely waiting, it is late.
URGENT_DAYS = 7

#: An outcome nobody has recorded after this long is stale enough to chase in
#: its own right rather than only in the digest's tail.
STALE_OUTCOME_DAYS = 14

#: In order of what they demand of a person. The rank is the sort key for the
#: queue, so the top of the screen is always the thing most owed.
STATES = (
    "needs_you_now",    # a decision is waiting AND the clock has run out
    "needs_you",        # a decision is waiting
    "held",             # the system refused to decide: it needs data, not a decision
    "failed",           # it broke; somebody has to look
    "owes_outcome",     # it was carried out and nobody wrote down what happened
    "running",          # still working
    "handled",          # done, within its own authority, nothing owed
)
RANK = {s: i for i, s in enumerate(STATES)}

#: What each state asks for, in the imperative, for a subject line.
ASKS = {
    "needs_you_now": "Approve now",
    "needs_you": "Approve",
    "held": "Needs data",
    "failed": "Failed",
    "owes_outcome": "Record what happened",
    "running": "Working",
    "handled": "Handled",
}


@dataclass(frozen=True)
class Verdict:
    state: str
    rank: int
    #: One line: the ask, then the figures that justify it.
    headline: str
    #: Each fact on its own, so a reader can check them one at a time.
    because: List[str] = field(default_factory=list)
    value_idr: int = 0
    approver: Optional[str] = None
    days_of_cover: Optional[int] = None
    depleted_on: Optional[str] = None
    untrusted: int = 0
    owed: int = 0
    oldest_owed_days: Optional[int] = None
    compliance_cost_idr: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def approver_for(value_idr: int, kind: str = "") -> str:
    """The lowest role that may approve this. Outward messages have their own
    floor regardless of value: a customer notice is not a small thing because
    it is cheap."""
    import outreach
    if kind in outreach.APPROVERS:
        return outreach.APPROVERS[kind][0]
    roles = [r for r, limit in sorted(ROLE_LIMITS.items(), key=lambda x: x[1])
             if limit > 0 and value_idr <= limit and r != "admin"]
    return roles[0] if roles else "nobody below admin"


# ---------------------------------------------------------------- the record
def tool_results(run: dict) -> List[tuple]:
    """(step, tool name, result) for every tool call that returned something
    and did not fail. The one place a run's tool output is read back."""
    out = []
    for s in run.get("steps") or []:
        if s.get("stage") != "TOOL":
            continue
        d = s.get("detail") or {}
        if d.get("error"):
            continue
        out.append((s, str(d.get("name") or (s.get("tools") or ["?"])[0]), d.get("result")))
    return out


def last_result(run: dict, tool: str) -> Optional[dict]:
    """The last result that tool produced in this run. The last one is the one
    the decision was taken on: a handling may cost a scenario, learn something
    and cost it again."""
    found = None
    for _step, name, result in tool_results(run):
        if name == tool and isinstance(result, dict):
            found = result
    return found


def _days_until(day: Optional[str], today: date) -> Optional[int]:
    if not day:
        return None
    try:
        return (date.fromisoformat(str(day)[:10]) - today).days
    except ValueError:
        return None


def _rp(n: Optional[float]) -> str:
    return f"Rp {int(n):,}" if isinstance(n, (int, float)) else "-"


def _when(day: Optional[str]) -> str:
    return str(day)[:10] if day else ""


# ----------------------------------------------------------------- the facts
def facts_from_run(run: dict, today: Optional[date] = None) -> Dict[str, Any]:
    """Reduce a whole run to the handful of figures a verdict rests on.

    Separate from `verdict()` so the queue can assemble the same figures with
    grouped SQL instead of loading every run, and both paths reach one answer.
    """
    from core import store
    today = today or datetime.now(WIB).date()
    actions = run.get("actions") or []
    pending = [a for a in actions if a.get("status") == "pending"]
    owed = [a for a in actions
            if not a.get("outcome") and a.get("status") in ("sent", "approved")
            and a.get("kind") in store.AWAITS_OUTCOME]

    oldest = None
    for a in owed:
        d = _days_until(a.get("created_at"), today)
        if d is not None:
            oldest = max(oldest or 0, -d)

    sim = last_result(run, "simulate_scenario") or {}
    cc = sim.get("compliance_cost") if isinstance(sim.get("compliance_cost"), dict) else None
    decision = run.get("decision") or {}
    untrusted = decision.get("untrusted_on_board")

    return {
        "status": run.get("status"),
        "pending": len(pending),
        "pending_value_idr": int(sum(float((a.get("payload") or {}).get("cost_idr") or 0)
                                     for a in pending)),
        "pending_kinds": [a.get("kind") for a in pending],
        "owed": len(owed),
        "oldest_owed_days": oldest,
        "depleted_on": sim.get("depleted_without_action"),
        "compliance_cost_idr": int(cc["idr"]) if cc and isinstance(cc.get("idr"), (int, float)) else None,
        "untrusted": len(untrusted) if isinstance(untrusted, list) else 0,
        "today": today,
    }


# --------------------------------------------------------------- the verdict
def verdict(facts: Dict[str, Any], today: Optional[date] = None) -> Verdict:
    """What this handling still asks of a person. Pure: same facts, same answer."""
    today = today or facts.get("today") or datetime.now(WIB).date()
    status = facts.get("status")
    pending = int(facts.get("pending") or 0)
    value = int(facts.get("pending_value_idr") or 0)
    owed = int(facts.get("owed") or 0)
    oldest = facts.get("oldest_owed_days")
    untrusted = int(facts.get("untrusted") or 0)
    cover = _days_until(facts.get("depleted_on"), today)
    kinds = facts.get("pending_kinds") or []
    approver = approver_for(value, kinds[0] if len(kinds) == 1 else "") if pending else None

    because: List[str] = []
    if pending:
        because.append(f"{pending} action(s) waiting, {_rp(value)} in all")
        because.append(f"the lowest role that can approve this is {approver}")
    if cover is not None:
        because.append(
            f"stock runs out on {_when(facts.get('depleted_on'))}"
            + (f", {cover} day(s) from now" if cover >= 0 else f", {-cover} day(s) ago"))
    if facts.get("compliance_cost_idr"):
        because.append(f"obeying the rules costs {_rp(facts['compliance_cost_idr'])} on this one")
    if untrusted:
        because.append(f"{untrusted} piece(s) of evidence are modelled or missing, not live")
    if owed:
        because.append(f"{owed} action(s) that went out still owe an outcome"
                       + (f", the oldest {oldest} day(s) ago" if oldest else ""))

    if status == "running":
        state = "running"
    elif status == "failed":
        state = "failed"
    elif status == "held":
        state = "held"
    elif pending:
        # Time-bound only when the record actually says when the stock runs
        # out. With no costing step there is no clock, and inventing one would
        # make every queue look like an emergency.
        state = "needs_you_now" if cover is not None and cover <= URGENT_DAYS else "needs_you"
    elif owed:
        state = "owes_outcome"
    else:
        state = "handled"

    return Verdict(
        state=state, rank=RANK[state], headline=_headline(state, facts, cover, approver),
        because=because, value_idr=value, approver=approver,
        days_of_cover=cover, depleted_on=_when(facts.get("depleted_on")),
        untrusted=untrusted, owed=owed, oldest_owed_days=oldest,
        compliance_cost_idr=facts.get("compliance_cost_idr"),
    )


def _headline(state: str, facts: Dict[str, Any], cover: Optional[int],
              approver: Optional[str]) -> str:
    """The ask, and the single figure that earns it. Never the word alone."""
    ask = ASKS[state]
    value = int(facts.get("pending_value_idr") or 0)
    if state == "needs_you_now":
        when = ("stock is already out" if cover is not None and cover < 0
                else f"stock out in {cover} day(s)")
        return f"{ask} — {_rp(value)} waiting, {when}"
    if state == "needs_you":
        return f"{ask} — {_rp(value)} waiting, {approver} or above"
    if state == "held":
        n = int(facts.get("untrusted") or 0)
        return (f"{ask} — the system would not decide on {n} modelled or missing input(s)"
                if n else f"{ask} — the system would not decide on what it had")
    if state == "failed":
        return f"{ask} — the handling stopped on an error"
    if state == "owes_outcome":
        oldest = facts.get("oldest_owed_days")
        return (f"{ask} — {facts['owed']} action(s), the oldest {oldest} day(s) old"
                if oldest else f"{ask} — {facts['owed']} action(s) went out")
    if state == "running":
        return f"{ask} — the team is still on it"
    return f"{ask} — nothing is waiting on a person"


def verdict_for_run(run: dict, today: Optional[date] = None) -> Verdict:
    return verdict(facts_from_run(run, today), today)


def queue(limit: int = 50, today: Optional[date] = None) -> List[Dict[str, Any]]:
    """Every handling on the board, with its verdict, most owed first.

    Three queries, not one per run. A queue page that loaded each handling to
    decide whether it needed a person would do fifty round trips to draw one
    screen, and it is drawn on every visit.
    """
    import json
    from core import store
    today = today or datetime.now(WIB).date()
    runs = store.list_runs(limit)
    if not runs:
        return []
    ids = [r["id"] for r in runs]
    marks = ",".join("?" * len(ids))
    owed_kinds = ",".join("?" * len(store.AWAITS_OUTCOME))

    agg: Dict[str, Dict[str, Any]] = {i: {"pending": 0, "pending_value_idr": 0,
                                          "pending_kinds": [], "owed": 0,
                                          "oldest_owed_days": None} for i in ids}
    with store.connect() as c:
        for a in c.execute(
                f"SELECT run_id, kind, status, payload, outcome, created_at FROM actions"
                f" WHERE run_id IN ({marks})", ids):
            g = agg[a["run_id"]]
            if a["status"] == "pending":
                g["pending"] += 1
                g["pending_kinds"].append(a["kind"])
                try:
                    g["pending_value_idr"] += int(float(json.loads(a["payload"]).get("cost_idr") or 0))
                except Exception:                                   # noqa: BLE001
                    pass
            elif (not a["outcome"] and a["status"] in ("sent", "approved")
                  and a["kind"] in store.AWAITS_OUTCOME):
                g["owed"] += 1
                d = _days_until(a["created_at"], today)
                if d is not None:
                    g["oldest_owed_days"] = max(g["oldest_owed_days"] or 0, -d)
        # The costing step is what puts a clock on an approval. Narrow the scan
        # the way engine/report.py narrows its own, then let the parse decide.
        for s in c.execute(
                f"SELECT run_id, seq, detail FROM steps WHERE run_id IN ({marks})"
                " AND stage = 'TOOL' AND detail LIKE '%simulate_scenario%'"
                " ORDER BY run_id, seq", ids):
            try:
                d = json.loads(s["detail"])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(d, dict) or d.get("error") or d.get("name") != "simulate_scenario":
                continue
            res = d.get("result")
            if not isinstance(res, dict):
                continue
            g = agg[s["run_id"]]
            g["depleted_on"] = res.get("depleted_without_action")
            cc = res.get("compliance_cost")
            g["compliance_cost_idr"] = (int(cc["idr"]) if isinstance(cc, dict)
                                        and isinstance(cc.get("idr"), (int, float)) else None)
    out = []
    for r in runs:
        d = r.get("decision") or {}
        u = d.get("untrusted_on_board") if isinstance(d, dict) else None
        f = dict(agg[r["id"]], status=r["status"],
                 untrusted=len(u) if isinstance(u, list) else 0)
        out.append({**r, "verdict": verdict(f, today).as_dict()})
    out.sort(key=lambda x: (x["verdict"]["rank"], x.get("started_at") or ""))
    return out


def stale(v: Verdict) -> bool:
    """An outcome old enough to chase on its own, not only in the digest tail."""
    return v.state == "owes_outcome" and (v.oldest_owed_days or 0) >= STALE_OUTCOME_DAYS


def summarise(verdicts: List[Verdict]) -> Dict[str, Any]:
    """The queue in one line, for a digest or a header.

    `clear` is the claim nobody may make lightly: nothing needs a person. It is
    true only when nothing is waiting, nothing was held, nothing failed and
    nothing owes an outcome — because a screen that says "all clear" while four
    handlings sit held is a screen nobody believes twice.
    """
    counts = {s: 0 for s in STATES}
    for v in verdicts:
        counts[v.state] += 1
    waiting = counts["needs_you_now"] + counts["needs_you"]
    unresolved = waiting + counts["held"] + counts["failed"] + counts["owes_outcome"]
    return {
        "counts": counts,
        "needs_a_person": waiting,
        "value_idr": sum(v.value_idr for v in verdicts if v.state.startswith("needs_you")),
        "clear": unresolved == 0,
        "line": _summary_line(counts, waiting, verdicts),
    }


def _summary_line(counts: Dict[str, int], waiting: int, verdicts: List[Verdict]) -> str:
    if not verdicts:
        return "Nothing has been handled yet."
    if waiting == 0 and counts["held"] == 0 and counts["failed"] == 0 and counts["owes_outcome"] == 0:
        return (f"Nothing needs a person. {counts['handled']} handled within the system's own "
                "authority" + (f", {counts['running']} still running." if counts["running"] else "."))
    bits = []
    if counts["needs_you_now"]:
        bits.append(f"{counts['needs_you_now']} need you now")
    if counts["needs_you"]:
        bits.append(f"{counts['needs_you']} waiting for approval")
    if counts["held"]:
        bits.append(f"{counts['held']} held for want of data")
    if counts["failed"]:
        bits.append(f"{counts['failed']} failed")
    if counts["owes_outcome"]:
        bits.append(f"{counts['owes_outcome']} owe an outcome")
    value = sum(v.value_idr for v in verdicts if v.state.startswith("needs_you"))
    tail = f", {_rp(value)} in all" if value else ""
    return "; ".join(bits) + tail + "."


def demo() -> None:
    """The verdict is arithmetic, so it is checked like arithmetic."""
    t = date(2026, 9, 4)

    # Nothing waiting, nothing owed: handled, and it says so without drama.
    done = verdict({"status": "done", "pending": 0, "owed": 0}, t)
    assert done.state == "handled" and done.value_idr == 0
    assert "nothing is waiting" in done.headline.lower(), done.headline

    # Waiting, with no costing step, so there is no clock to be late against.
    wait = verdict({"status": "done", "pending": 1, "pending_value_idr": 94_000_000,
                    "pending_kinds": ["draft_po"]}, t)
    assert wait.state == "needs_you" and wait.approver == "buyer", wait
    assert "Rp 94,000,000" in wait.headline and "buyer" in wait.headline, wait.headline

    # The same thing, with the stock running out inside the week.
    soon = verdict({"status": "done", "pending": 1, "pending_value_idr": 94_000_000,
                    "pending_kinds": ["draft_po"], "depleted_on": "2026-09-09"}, t)
    assert soon.state == "needs_you_now" and soon.days_of_cover == 5, soon
    assert "stock out in 5 day(s)" in soon.headline, soon.headline
    assert soon.rank < wait.rank < done.rank, "the queue sorts by what is owed"

    # Already out: the wording changes rather than printing a negative.
    out = verdict({"status": "done", "pending": 1, "pending_value_idr": 1,
                   "pending_kinds": ["draft_po"], "depleted_on": "2026-09-01"}, t)
    assert out.state == "needs_you_now" and "already out" in out.headline, out.headline

    # Above every role below admin: the verdict names that rather than a role
    # that cannot in fact approve it.
    big = verdict({"status": "done", "pending": 1, "pending_value_idr": 90_000_000_000,
                   "pending_kinds": ["draft_po"]}, t)
    assert big.approver == "nobody below admin", big.approver

    # An outward message has a floor of its own, whatever it costs.
    notice = verdict({"status": "done", "pending": 1, "pending_value_idr": 0,
                      "pending_kinds": ["customer_notice"]}, t)
    assert notice.approver == "procurement_lead", notice.approver

    # Held is not "critical" and not "fine": it is a request for data.
    held = verdict({"status": "held", "untrusted": 3}, t)
    assert held.state == "held" and "3 modelled or missing" in held.headline, held.headline

    # Carried out, nothing waiting, but the loop is open.
    owes = verdict({"status": "done", "pending": 0, "owed": 2, "oldest_owed_days": 21}, t)
    assert owes.state == "owes_outcome" and stale(owes), owes
    assert "oldest 21 day(s)" in owes.headline, owes.headline
    assert not stale(verdict({"status": "done", "owed": 1, "oldest_owed_days": 2}, t))

    # Every verdict carries the figures that earned it, never the word alone.
    assert any("Rp 94,000,000" in b for b in soon.because), soon.because
    assert any("buyer" in b for b in soon.because), soon.because

    # The summary may only call the board clear when it really is.
    s = summarise([done, done])
    assert s["clear"] and "Nothing needs a person" in s["line"], s
    for not_clear in (wait, held, owes, verdict({"status": "failed"}, t)):
        assert not summarise([done, not_clear])["clear"], not_clear.state
    mixed = summarise([soon, wait, held, owes, done])
    assert mixed["needs_a_person"] == 2 and not mixed["clear"]
    assert "1 need you now" in mixed["line"] and "held for want of data" in mixed["line"], mixed["line"]
    assert mixed["value_idr"] == 188_000_000, mixed["value_idr"]

    # Reading a run: the figures come off the record, not off a model.
    run = {
        "status": "done",
        "decision": {"untrusted_on_board": ["compliance.check_local_constraints"]},
        "actions": [
            {"status": "pending", "kind": "draft_po", "payload": {"cost_idr": 94_000_000}},
            {"status": "sent", "kind": "stock_transfer", "payload": {}, "created_at":
             (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()},
        ],
        "steps": [{"stage": "TOOL", "detail": {"name": "simulate_scenario", "result": {
            "depleted_without_action": "2026-09-13",
            "compliance_cost": {"idr": 46_000_000}}}}],
    }
    f = facts_from_run(run, t)
    assert f["pending"] == 1 and f["pending_value_idr"] == 94_000_000
    assert f["owed"] == 1 and f["depleted_on"] == "2026-09-13"
    assert f["compliance_cost_idr"] == 46_000_000 and f["untrusted"] == 1
    v = verdict_for_run(run, t)
    # Nine days of cover is not an emergency, and the verdict does not pretend
    # it is: the clock exists, and it has not run out.
    assert v.state == "needs_you" and v.days_of_cover == 9, v
    assert v.compliance_cost_idr == 46_000_000
    assert any("46,000,000" in b for b in v.because), v.because
    assert any("9 day(s) from now" in b for b in v.because), v.because
    assert v.as_dict()["state"] == "needs_you"
    # One day tighter and it is.
    assert verdict_for_run(run, date(2026, 9, 7)).state == "needs_you_now"

    # A run with no costing step gets no clock rather than a made-up one.
    bare = verdict_for_run({"status": "done", "actions": [
        {"status": "pending", "kind": "draft_po", "payload": {"cost_idr": 1_000}}]}, t)
    assert bare.state == "needs_you" and bare.days_of_cover is None, bare

    # The queue, read the way the page reads it: grouped, sorted, and reaching
    # the same answer as reading one run whole.
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_TRIAGE_CHECK")
    from core import store
    from tools.execution import idempotency_key

    e1 = store.record_event("port_closure", "Ningbo closed", "advisory", {}, "check")
    r1 = store.start_run(e1, "autonomous")
    store.save_step(r1, {"seq": 1, "stage": "TOOL", "agent": "simulation", "agent_name": "Tara",
                         "summary": "simulate_scenario", "tools": ["simulate_scenario"],
                         "origin": "derived", "source": "engine/simulate.py", "at": store._now(),
                         "detail": {"name": "simulate_scenario", "result": {
                             "depleted_without_action": "2026-09-09",
                             "compliance_cost": {"idr": 46_000_000}}}})
    store.record_action(r1, idempotency_key("draft_po", x=1), "draft_po", False,
                        {"cost_idr": 94_000_000})
    store.close_run(r1, "done", {"recommendation": "B+C", "untrusted_on_board": ["x"]})

    e2 = store.record_event("seismic", "Quake near KRW1", "BMKG", {}, "check")
    r2 = store.start_run(e2, "autonomous")
    store.record_action(r2, idempotency_key("stock_transfer", x=2), "stock_transfer", True,
                        {"cost_idr": 22_000_000}, status="sent")
    store.close_run(r2, "done", {"recommendation": "moved stock"})

    board = queue(today=t)
    assert len(board) == 2, board
    # Most owed first, whatever order they were handled in.
    assert board[0]["id"] == r1 and board[0]["verdict"]["state"] == "needs_you_now", board[0]["verdict"]
    assert board[0]["verdict"]["value_idr"] == 94_000_000
    assert board[0]["verdict"]["compliance_cost_idr"] == 46_000_000
    assert board[1]["verdict"]["state"] == "owes_outcome", board[1]["verdict"]
    # And the grouped read agrees with reading the run whole.
    whole = verdict_for_run(store.get_run(r1), t)
    assert whole.state == board[0]["verdict"]["state"], (whole, board[0]["verdict"])
    assert whole.value_idr == board[0]["verdict"]["value_idr"]

    print("triage ok, states ranked by what is owed ✓ · the figure is always beside the word ✓ "
          "· no costing step means no clock ✓ · clear only when truly clear ✓ "
          "· the queue reads grouped and agrees with reading one run whole ✓")


if __name__ == "__main__":
    demo()
