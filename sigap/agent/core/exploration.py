"""The exploration graph: a persisted, typed DAG of one event's handling.

Ported from the SmartX exploration graph (explorer-worker topology) and adapted
to SIGAP's domain and house rules. The shape is theirs; the discipline is ours.

What SmartX got right, and we keep:

  * The graph is the SINGLE shared record. The supervisor and the specialists
    read and write ONE graph, so a value can never exist without the edge that
    says where it came from. (SmartX had three parallel dicts; so did our
    in-memory Board. This is the fix.)

  * A node's identity is (run_id, dedup_key). Two specialists that surface the
    same fact collapse to ONE node — that is what lets the graph be a proper
    multi-parent DAG rather than a tree. A priced option two leads both reach
    is one option.

  * A 'lead' node IS the claimable frontier. `claim_next_lead` is a single
    `UPDATE … WHERE state='open'` whose `rowcount == 1` is the atomic CAS: if
    two specialists race for the same lead, exactly one wins. SQLite serializes
    writers, so this holds across concurrent handling without any lock.

  * The state machine is MONOTONE. A lead moves open → claimed → terminal
    (worked|capped|blocked|stopped), and a revive moves a terminal back to open
    exactly ONCE (the revived_once guard). Nothing resurrects a settled lead by
    accident, and the recursion cannot loop forever.

  * Convergence is read off the graph: no active lead left (open or claimed)
    means the frontier is drained and the lead may write its recommendation —
    instead of stopping only when a round counter runs out.

What we add, because it is the whole point of SIGAP:

  * Every 'fact' node carries its origin and source. The graph does not just
    say a fact exists; it says whether it is live, cached, derived, modelled or
    missing. A decision read back off this graph can be audited for the
    trustworthiness of the ground under it, which is exactly what
    engine/simulate.py refuses to proceed without.

The whole feature is flag-gated (SIGAP_GRAPH) at the call site and every write
through it is fail-open: a graph error returns a no-op, never breaks a handling
that already works without the graph.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core.provenance import Result
from core.store import connect, new_id, _now

#: Node kinds. 'lead' is the claimable unit of work ( 'intent').
NODE_KINDS = ("event", "lead", "fact", "option", "ruling")

#: Typed edges. A DAG, not a tree: a node may have several parents.
EDGE_RELS = ("spawns", "derived_from", "yields", "rules_on", "covers")

#: Terminal lead states. 'worked' = investigated to a conclusion, 'capped' =
#: ran out of attempts, 'blocked' = a rule struck it out, 'failed' = the
#: specialist working it raised (isolated, so it does not take the handling
#: down with it), 'stopped' = the handling ended before it was reached.
TERMINALS = ("worked", "capped", "blocked", "failed", "stopped")

#: A lead that has been dispatched this many times without concluding is
#: drained from the frontier. The recursion's depth guard, mirroring
#: attempts-cap: deep chaining without an infinite loop.
MAX_LEAD_ATTEMPTS = 3


def enabled() -> bool:
    """The graph is opt-in. Off ⇒ the call sites never touch it, so a handling
    runs exactly as it did before this module existed."""
    import os
    return os.environ.get("SIGAP_GRAPH", "0") == "1"


def canonical_lead_key(kind: str, subject: str) -> str:
    """One stable key for a line of investigation, so the same question asked
    twice is the same frontier node. E.g. 'source:M-4471', 'rule:E', 'price:B+C'.
    """
    return f"{kind.strip().lower()}:{subject.strip()}"


# --------------------------------------------------------------------------- #
# Knowledge nodes (event / fact / option / ruling): upserted, merge-on-conflict.
# A write that omits a field must never blank a field another write set, so
# every column is COALESCE(excluded, existing). The lead LIFECYCLE never goes
# through here — it uses the dedicated monotone UPDATEs below, because COALESCE
# would resurrect a terminal lead's state.
# --------------------------------------------------------------------------- #
def upsert_node(
    c,
    run_id: str,
    kind: str,
    dedup_key: str,
    *,
    state: Optional[str] = None,
    label: Optional[str] = None,
    subject: Optional[str] = None,
    lead_key: Optional[str] = None,
    origin: Optional[str] = None,
    source: Optional[str] = None,
    payload: Any = None,
    priority: Optional[int] = None,
) -> str:
    """Create or merge one knowledge node, returning its node_id."""
    now = _now()
    payload_json = None if payload is None else json.dumps(payload, ensure_ascii=False, default=str)
    c.execute(
        """INSERT INTO graph_nodes
             (node_id, run_id, kind, state, label, subject, lead_key, origin, source,
              dedup_key, payload, priority, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(run_id, dedup_key) DO UPDATE SET
             state    = COALESCE(excluded.state, state),
             label    = COALESCE(excluded.label, label),
             subject  = COALESCE(excluded.subject, subject),
             lead_key = COALESCE(excluded.lead_key, lead_key),
             origin   = COALESCE(excluded.origin, origin),
             source   = COALESCE(excluded.source, source),
             payload  = COALESCE(excluded.payload, payload),
             priority = COALESCE(excluded.priority, priority),
             updated_at = excluded.updated_at""",
        (new_id("node"), run_id, kind, state, label, subject, lead_key, origin, source,
         dedup_key, payload_json, priority, now, now),
    )
    # Read the id back rather than `RETURNING node_id`, which needs SQLite 3.35.
    # Servers still ship 3.34 (RHEL 9 does), and there the statement failed
    # outright, taking the planner and the async dispatcher down with it. Same
    # connection, same transaction, so this reads the row the upsert just wrote.
    row = c.execute("SELECT node_id FROM graph_nodes WHERE run_id=? AND dedup_key=?",
                    (run_id, dedup_key)).fetchone()
    return row["node_id"]


def add_edge(c, run_id: str, src: str, rel: str, dst: str) -> None:
    """Record a lineage edge. Idempotent: the same edge twice is one edge."""
    c.execute(
        """INSERT INTO graph_edges (run_id, src, rel, dst, created_at)
           VALUES (?,?,?,?,?)
           ON CONFLICT(run_id, src, rel, dst) DO NOTHING""",
        (run_id, src, rel, dst, _now()),
    )


def write_fact(c, run_id: str, key: str, result: Result,
               derived_from: Optional[str] = None) -> str:
    """Bridge a provenance Result onto the graph as a fact node, carrying its
    origin and source. `derived_from` is the node_id of the lead that surfaced
    it, so the fact's lineage is recorded, not just its value.

    This is the one call the orchestrator's board write-through uses, so every
    tool return that lands on the board lands on the graph WITH its provenance.
    """
    node_id = upsert_node(
        c, run_id, "fact", f"fact:{key}",
        label=key,
        origin=result.origin.value,
        source=result.source,
        payload={"value": result.value, **result.brief()},
    )
    if derived_from:
        add_edge(c, run_id, derived_from, "derived_from", node_id)
    return node_id


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get_graph(c, run_id: str) -> Dict[str, List[dict]]:
    """The whole graph for one run, nodes and edges, oldest first."""
    nodes = [dict(r) for r in c.execute(
        "SELECT * FROM graph_nodes WHERE run_id=? ORDER BY created_at ASC", (run_id,))]
    edges = [dict(r) for r in c.execute(
        "SELECT run_id, src, rel, dst, created_at FROM graph_edges WHERE run_id=? "
        "ORDER BY created_at ASC", (run_id,))]
    return {"nodes": nodes, "edges": edges}


def find_node_by_dedup(c, run_id: str, dedup_key: str) -> Optional[str]:
    """An existing node's id by identity, or None. Never mints a node."""
    row = c.execute(
        "SELECT node_id FROM graph_nodes WHERE run_id=? AND dedup_key=?",
        (run_id, dedup_key)).fetchone()
    return row["node_id"] if row else None


# --------------------------------------------------------------------------- #
# The lead lifecycle: the claimable frontier. Dedicated monotone UPDATEs.
# --------------------------------------------------------------------------- #
def ensure_open_lead(c, run_id: str, lead_key: str, *,
                     label: Optional[str] = None,
                     subject: Optional[str] = None,
                     priority: Optional[int] = None,
                     spawned_by: Optional[str] = None) -> str:
    """Make a lead exist as 'open' so it is claimable, without ever touching an
    existing one (a lead already claimed/worked/capped keeps its state). This is
    how a new line of investigation enters the frontier. Idempotent + monotone.
    Returns the lead node's id.
    """
    now = _now()
    c.execute(
        """INSERT INTO graph_nodes
             (node_id, run_id, kind, state, label, subject, lead_key, dedup_key,
              priority, created_at, updated_at)
           VALUES (?,?, 'lead', 'open', ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(run_id, dedup_key) DO NOTHING""",
        (new_id("node"), run_id, label or lead_key, subject, lead_key,
         f"lead:{lead_key}", priority, now, now),
    )
    node_id = find_node_by_dedup(c, run_id, f"lead:{lead_key}")
    if spawned_by and node_id:
        add_edge(c, run_id, spawned_by, "spawns", node_id)   # the recursion edge
    return node_id or ""


def claim_next_lead(c, run_id: str, owner: str) -> Optional[dict]:
    """Atomically claim the highest-priority open lead (oldest tiebreak) for
    `owner`. The UPDATE's rowcount == 1 IS the atomic CAS; a lost race returns
    None. A lead past its attempts cap is NOT claimable (it is drained first).
    """
    row = c.execute(
        """SELECT node_id, lead_key, subject, priority FROM graph_nodes
           WHERE run_id=? AND kind='lead' AND state='open' AND attempts < ?
           ORDER BY COALESCE(priority,0) DESC, created_at ASC LIMIT 1""",
        (run_id, MAX_LEAD_ATTEMPTS)).fetchone()
    if not row:
        return None
    cur = c.execute(
        """UPDATE graph_nodes
             SET state='claimed', owner=?, claimed_at=?,
                 dispatches=dispatches+1, attempts=attempts+1, updated_at=?
           WHERE node_id=? AND state='open'""",
        (owner, _now(), _now(), row["node_id"]))
    if cur.rowcount != 1:
        return None                      # lost the race to another claimer
    return {"node_id": row["node_id"], "lead_key": row["lead_key"],
            "subject": row["subject"], "priority": row["priority"]}


def settle_lead(c, run_id: str, lead_key: str, state: str) -> bool:
    """Move a claimed/open lead to a terminal state. Monotone: only ever down."""
    if state not in TERMINALS:
        raise ValueError(f"not a terminal state: {state}")
    cur = c.execute(
        """UPDATE graph_nodes SET state=?, updated_at=?
           WHERE run_id=? AND kind='lead' AND dedup_key=? AND state IN ('claimed','open')""",
        (state, _now(), run_id, f"lead:{lead_key}"))
    return cur.rowcount >= 1


def revive_lead(c, run_id: str, lead_key: str) -> bool:
    """Re-open a capped/blocked lead — ONCE. The deep-chain re-opener: a lead
    drained earlier becomes actionable again when a new fact changes its
    context. The revived_once guard is what keeps that from looping.
    """
    cur = c.execute(
        """UPDATE graph_nodes
             SET state='open', owner=NULL, claimed_at=NULL, revived_once=1, updated_at=?
           WHERE run_id=? AND kind='lead' AND dedup_key=?
             AND state IN ('capped','blocked') AND revived_once=0""",
        (_now(), run_id, f"lead:{lead_key}"))
    return cur.rowcount == 1


def reopen_lead(c, run_id: str, lead_key: str, uncount_attempt: bool = False) -> bool:
    """Put one claimed lead back to 'open' — used when the dispatcher claimed it
    but admission then refused the slot, so it was never actually worked.
    `uncount_attempt` undoes the attempt the claim added, so an admission
    refusal does not burn the lead toward its cap. Monotone: claimed→open only."""
    dec = ", attempts = MAX(0, attempts - 1)" if uncount_attempt else ""
    cur = c.execute(
        f"""UPDATE graph_nodes SET state='open', owner=NULL, claimed_at=NULL{dec}, updated_at=?
            WHERE run_id=? AND kind='lead' AND dedup_key=? AND state='claimed'""",
        (_now(), run_id, f"lead:{lead_key}"))
    return cur.rowcount == 1


def reopen_stale_claims(c, run_id: str, stale_seconds: int) -> int:
    """Self-heal: a lead claimed by a specialist that crashed or stalled longer
    than `stale_seconds` goes back to open (its attempt already counted, so the
    cap still bounds it). Returns how many were reopened.
    """
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=stale_seconds)).isoformat()
    cur = c.execute(
        """UPDATE graph_nodes SET state='open', owner=NULL, updated_at=?
           WHERE run_id=? AND kind='lead' AND state='claimed'
             AND claimed_at IS NOT NULL AND claimed_at < ?""",
        (_now(), run_id, cutoff))
    return cur.rowcount


def annotate_lead(c, run_id: str, lead_key: str, *,
                  summary: Optional[str] = None,
                  cost_idr: Optional[int] = None,
                  tokens: Optional[int] = None,
                  status: Optional[str] = None) -> None:
    """Record what a specialist's work on a lead produced — a one-line summary,
    its token cost, and how it ended — onto the lead node's payload. This is the
    worker run-state: a lead is not just 'claimed then worked', it carries what
    the work found and what it cost, so a handling can be inspected after the
    fact (which specialist stalled, what each one spent). Fail-open: a bad write
    never disturbs the lead's lifecycle, which the dedicated UPDATEs own."""
    import json
    try:
        row = c.execute("SELECT payload FROM graph_nodes WHERE run_id=? AND dedup_key=?",
                        (run_id, f"lead:{lead_key}")).fetchone()
        prior = {}
        if row and row["payload"]:
            try:
                prior = json.loads(row["payload"])
            except Exception:             # noqa: BLE001
                prior = {}
        work = prior.get("work", {})
        if summary is not None:
            work["summary"] = summary[:600]
        if cost_idr is not None:
            work["cost_idr"] = cost_idr
        if tokens is not None:
            work["tokens"] = tokens
        if status is not None:
            work["status"] = status
        prior["work"] = work
        c.execute("UPDATE graph_nodes SET payload=?, updated_at=? WHERE run_id=? AND dedup_key=?",
                  (json.dumps(prior, ensure_ascii=False, default=str), _now(),
                   run_id, f"lead:{lead_key}"))
    except Exception:                     # noqa: BLE001
        pass


def count_open_leads(c, run_id: str) -> int:
    """Claimable frontier depth."""
    return c.execute(
        "SELECT COUNT(*) n FROM graph_nodes WHERE run_id=? AND kind='lead' "
        "AND state='open' AND attempts < ?",
        (run_id, MAX_LEAD_ATTEMPTS)).fetchone()["n"]


def count_active_leads(c, run_id: str) -> int:
    """Still-actionable or in-flight leads: a claimed lead, or an open lead not
    yet past its attempts cap. Zero of these is the convergence condition — the
    frontier is drained (nothing left that is both unclaimed and unexhausted)
    and nothing is being worked, so the lead may conclude. An open lead past its
    cap is a drained leftover, not actionable, so it does not hold convergence."""
    return c.execute(
        "SELECT COUNT(*) n FROM graph_nodes WHERE run_id=? AND kind='lead' "
        "AND (state='claimed' OR (state='open' AND attempts < ?))",
        (run_id, MAX_LEAD_ATTEMPTS)).fetchone()["n"]


def converged(c, run_id: str) -> bool:
    """Done when no lead is still actionable and none is in flight."""
    return count_active_leads(c, run_id) == 0


# --------------------------------------------------------------------------- #
def demo() -> None:
    """Self-check on a scratch run. Proves the DAG dedup, the atomic claim CAS,
    the monotone state machine, the revive-once guard, and convergence."""
    from core import store

    # a scratch event + run to hang the graph off (foreign keys are ON)
    eid = store.record_event("port_closure", "scratch", "trig:graph-demo",
                              {"q": "quake"}, "demo")
    rid = store.start_run(eid, "autonomous")

    with store.connect() as c:
        ev = upsert_node(c, rid, "event", f"event:{eid}", label="scratch disruption")

        # A lead enters the frontier, spawned by the event.
        src = ensure_open_lead(c, rid, canonical_lead_key("source", "M-4471"),
                               label="find an alternate source", subject="M-4471",
                               priority=10, spawned_by=ev)
        assert src and count_open_leads(c, rid) == 1

        # DAG dedup: the SAME fact written twice is ONE node, with two parents.
        from core.provenance import Origin, Result
        f1 = write_fact(c, rid, "stock:M-4471:KRW1",
                        Result({"qty": 84.0}, Origin.LIVE, "API_MATERIAL_STOCK_SRV"),
                        derived_from=src)
        f2 = write_fact(c, rid, "stock:M-4471:KRW1",
                        Result({"qty": 84.0}, Origin.LIVE, "API_MATERIAL_STOCK_SRV"),
                        derived_from=ev)
        assert f1 == f2, "the same fact must collapse to one node"
        g = get_graph(c, rid)
        fact_nodes = [n for n in g["nodes"] if n["kind"] == "fact"]
        assert len(fact_nodes) == 1, "dedup_key failed: two fact nodes"
        assert fact_nodes[0]["origin"] == "live", "a fact must keep its provenance"
        derived = [e for e in g["edges"] if e["rel"] == "derived_from" and e["dst"] == f1]
        assert len(derived) == 2, "the shared fact must have both parents (a DAG, not a tree)"

        # Atomic claim: exactly one owner wins the open lead.
        claim = claim_next_lead(c, rid, owner="clint")
        assert claim and claim["lead_key"] == "source:M-4471"
        assert claim_next_lead(c, rid, owner="elsa") is None, "a claimed lead is not claimable again"
        assert count_active_leads(c, rid) == 1 and count_open_leads(c, rid) == 0

        # A confirmed option spawns the next leads (the recursion / deep chain).
        opt = upsert_node(c, rid, "option", "option:E", label="cheapest source in China",
                          subject="E", payload={"ExtraCostIDR": 48_000_000})
        add_edge(c, rid, claim["node_id"], "yields", opt)
        rule = ensure_open_lead(c, rid, canonical_lead_key("rule", "E"),
                                label="rule on option E", subject="E", spawned_by=opt)
        assert count_open_leads(c, rid) == 1, "the option must have spawned a new lead"

        # Kira blocks it: a ruling node is the negative knowledge the planner reads.
        ruling = upsert_node(c, rid, "ruling", "ruling:E", state="blocked",
                             label="TKDN drops to 34.8%, floor 40%", subject="E")
        add_edge(c, rid, ruling, "rules_on", opt)
        assert settle_lead(c, rid, "rule:E", "blocked")
        assert settle_lead(c, rid, "source:M-4471", "worked")

        # A specialist's work record lands on the lead, and a raised specialist
        # settles its lead 'failed' without taking anything else down.
        annotate_lead(c, rid, "source:M-4471", summary="found options A–E",
                      cost_idr=1200, tokens=4800, status="worked")
        import json as _json
        wrow = c.execute("SELECT payload FROM graph_nodes WHERE run_id=? AND dedup_key=?",
                         (rid, "lead:source:M-4471")).fetchone()
        assert _json.loads(wrow["payload"])["work"]["cost_idr"] == 1200
        fkey = canonical_lead_key("price", "fails")
        ensure_open_lead(c, rid, fkey, subject="fails")
        claim_next_lead(c, rid, owner="tara")
        assert settle_lead(c, rid, fkey, "failed"), "a raised specialist settles its lead failed"

        # Monotone: a settled lead is not claimable, and revive works once only.
        assert claim_next_lead(c, rid, owner="x") is None
        assert revive_lead(c, rid, "rule:E") is True
        assert revive_lead(c, rid, "rule:E") is False, "revive must fire at most once"
        assert settle_lead(c, rid, "rule:E", "capped")

        # Attempts cap: a lead dispatched MAX times drains from the frontier.
        cap = ensure_open_lead(c, rid, canonical_lead_key("price", "loop"), subject="loop")
        for _ in range(MAX_LEAD_ATTEMPTS):
            claim_next_lead(c, rid, owner="t")
            c.execute("UPDATE graph_nodes SET state='open' WHERE dedup_key='lead:price:loop' AND run_id=?", (rid,))
        assert count_open_leads(c, rid) == 0, "a lead past its attempts cap must drain"

        assert converged(c, rid), "no active lead left ⇒ converged"

    # leave no scratch rows behind in the operator's record
    with store.connect() as c:
        c.execute("DELETE FROM graph_edges WHERE run_id=?", (rid,))
        c.execute("DELETE FROM graph_nodes WHERE run_id=?", (rid,))
        c.execute("DELETE FROM runs WHERE id=?", (rid,))
        c.execute("DELETE FROM events WHERE id=?", (eid,))

    print("exploration ok, DAG dedup ✓ · atomic claim CAS ✓ · monotone + revive-once ✓ "
          "· attempts cap ✓ · convergence ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_EXPLORATION_SELFCHECK")
    demo()
