"""The deep-chain planner and the graph-aware gates.

Ported from the SmartX exploration graph's planner (graph-planner.ts) and its
graph-aware finding gates (exploration-graph-gates.ts), adapted to SIGAP.

SmartX's planner reads the exploration graph — what is already proven and what
is already being worked — and emits the NEXT steps that CHAIN forward from it,
never a flat re-scan of what is already known. It used an LLM, because its
domain (what to probe next on a web app) is open-ended.

SIGAP's mitigation chain is NOT open-ended. It is a known DAG of stages:

    event → impact → (per affected material) source → (per found option)
            rule → (only if the rule cleared it) price → recommend

So the planner here is DETERMINISTIC. It reads the same graph and emits the
same kind of thing — the next leads that are newly enabled by what is on the
board — but by domain rule, not by a model. That is the house law: no model
sits on the decision path (engine/simulate.py is the same principle for the
arithmetic). The planner reads the graph; it never guesses.

Two graph-aware gates come with it, both faithful to SmartX's:

  * `blocked_option_reject` — NEGATIVE KNOWLEDGE. Once Kira records a ruling
    that blocks an option, that ruling sits on the graph. No later step may
    re-price or choose that option; the gate reads the ruling and says no. This
    is what stops the cheapest-but-illegal option from creeping back in through
    a different lead — the exact thing SIGAP exists to prevent.

  * `option_already_priced` — DEDUP. An option already priced is not priced
    again; the planner will not spawn a second price lead for it.

Everything here is flag-gated (SIGAP_GRAPH) at the call site and fail-open: a
planner or gate error returns "nothing to add" / "do not reject", so it can
never break a handling.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from core import exploration as ex


def _payload(node: dict) -> dict:
    import json
    raw = node.get("payload")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:                     # noqa: BLE001  — fail-open
        return {}


def seed_from_event(c, run_id: str, event_id: str,
                    materials: Optional[List[str]] = None) -> List[str]:
    """Open the first leads of a handling, the way the main agent's recon seeds
    the initial intents. The event becomes the root node; an impact lead always
    opens; a source lead opens per affected material when they are known.

    Returns the lead keys opened. Fail-open: returns [] on any error.
    """
    try:
        root = ex.upsert_node(c, run_id, "event", f"event:{event_id}",
                              label="disruption", subject=event_id)
        opened: List[str] = []

        impact_key = ex.canonical_lead_key("impact", event_id)
        ex.ensure_open_lead(c, run_id, impact_key, label="trace the impact",
                            subject=event_id, priority=100, spawned_by=root)
        opened.append(impact_key)

        for m in materials or []:
            k = ex.canonical_lead_key("source", m)
            ex.ensure_open_lead(c, run_id, k, label=f"find a source for {m}",
                                subject=m, priority=80, spawned_by=root)
            opened.append(k)
        return opened
    except Exception:                     # noqa: BLE001
        return []


def plan_next_leads(c, run_id: str) -> List[Dict]:
    """Read the graph and open the next leads that are NEWLY ENABLED by what is
    already on it — the recursion that turns a found option into a ruling, and a
    cleared ruling into a price. It never re-opens a step already present, and
    it never prices an option a ruling has blocked (negative knowledge).

    Returns the lead specs it opened (each {lead_key, subject, stage}). The
    leads are already written to the graph as 'open'; the return value is for
    observability — so a live handling can SEE what the planner chained, exactly
    as the SmartX planner logs every step it emits.
    """
    if not ex.enabled():
        return []
    try:
        g = ex.get_graph(c, run_id)
        nodes = g["nodes"]
        by_kind: Dict[str, List[dict]] = {}
        for n in nodes:
            by_kind.setdefault(n["kind"], []).append(n)

        options = by_kind.get("option", [])
        rulings = {r["subject"]: r for r in by_kind.get("ruling", []) if r["subject"]}
        # leads already on the graph, by key — "do NOT repeat ALREADY TESTING".
        lead_keys = {n["lead_key"] for n in by_kind.get("lead", []) if n["lead_key"]}
        option_nodes = {o["subject"]: o["node_id"] for o in options if o["subject"]}

        opened: List[Dict] = []

        for opt in options:
            oid = opt["subject"]
            if not oid:
                continue

            # (1) A found option with no ruling yet → open a rule lead. The
            #     deepest-reachable rule: may we even use this at all?
            rule_key = ex.canonical_lead_key("rule", oid)
            if oid not in rulings and rule_key not in lead_keys:
                ex.ensure_open_lead(c, run_id, rule_key, label=f"rule on option {oid}",
                                    subject=oid, priority=70,
                                    spawned_by=option_nodes.get(oid))
                lead_keys.add(rule_key)
                opened.append({"lead_key": rule_key, "subject": oid, "stage": "rule"})

            # (2) A ruling that CLEARED the option → open a price lead, but only
            #     if it is not blocked and not already priced. A blocked option
            #     is dropped here: the negative knowledge stops the chain.
            ruling = rulings.get(oid)
            if ruling and (ruling.get("state") == "allowed"):
                price_key = ex.canonical_lead_key("price", oid)
                if (price_key not in lead_keys
                        and not option_already_priced(c, run_id, oid)):
                    ex.ensure_open_lead(c, run_id, price_key,
                                        label=f"price option {oid}", subject=oid,
                                        priority=60, spawned_by=option_nodes.get(oid))
                    lead_keys.add(price_key)
                    opened.append({"lead_key": price_key, "subject": oid, "stage": "price"})
            # ruling blocked ⇒ intentionally nothing: negative knowledge.

        return opened
    except Exception:                     # noqa: BLE001  — fail-open
        return []


# --------------------------------------------------------------------------- #
# Graph-aware gates
# --------------------------------------------------------------------------- #
def blocked_option_reject(c, run_id: str, option_id: str) -> Dict:
    """Negative knowledge. If the graph holds a ruling that BLOCKS this option,
    no later step may price or choose it. Returns {reject, message}. Fail-open:
    a graph-read error never blocks a legitimate step (returns reject=False).

    This is the gate that enforces SIGAP's whole premise at the graph level: a
    cost argument cannot overturn a rule, so once an option is blocked it stays
    blocked for every path that reaches it.
    """
    try:
        row = c.execute(
            "SELECT state, label FROM graph_nodes WHERE run_id=? AND kind='ruling' "
            "AND dedup_key=?", (run_id, f"ruling:{option_id}")).fetchone()
        if row and row["state"] == "blocked":
            return {"reject": True,
                    "message": (f"option {option_id} is struck out: "
                                f"{row['label'] or 'blocked by a rule'}. "
                                "A ruling on the graph blocks it, and cost cannot overturn it.")}
        return {"reject": False}
    except Exception:                     # noqa: BLE001
        return {"reject": False}


def option_already_priced(c, run_id: str, option_id: str) -> bool:
    """Dedup. True when the option already has a price fact or a concluded price
    lead, so the planner does not open a second one. Fail-open to False."""
    try:
        fact = c.execute(
            "SELECT 1 FROM graph_nodes WHERE run_id=? AND kind='fact' AND dedup_key=?",
            (run_id, f"fact:price:{option_id}")).fetchone()
        if fact:
            return True
        worked = c.execute(
            "SELECT 1 FROM graph_nodes WHERE run_id=? AND kind='lead' AND dedup_key=? "
            "AND state='worked'",
            (run_id, f"lead:{ex.canonical_lead_key('price', option_id)}")).fetchone()
        return worked is not None
    except Exception:                     # noqa: BLE001
        return False


# --------------------------------------------------------------------------- #
def demo() -> None:
    """Self-check on a scratch run: the recursion chains option → rule → price,
    a blocked option is never priced, and the dedup/negative-knowledge gates
    hold. Mirrors the reference scenario (E blocked, B cleared)."""
    import os
    os.environ["SIGAP_GRAPH"] = "1"       # the planner is a no-op when off
    from core import store

    eid = store.record_event("port_closure", "scratch", "trig:planner-demo",
                             {"q": "quake"}, "demo")
    rid = store.start_run(eid, "autonomous")

    with store.connect() as c:
        seeded = seed_from_event(c, rid, eid, materials=["M-4471"])
        assert "impact:" + eid in seeded and "source:M-4471" in seeded

        # Two options are found by sourcing (E cheap/illegal, B legal).
        ex.upsert_node(c, rid, "option", "option:E", subject="E",
                       label="cheapest China", payload={"ExtraCostIDR": 48_000_000})
        ex.upsert_node(c, rid, "option", "option:B", subject="B",
                       label="local Gresik", payload={"ExtraCostIDR": 94_000_000})

        # Round 1: both options with no ruling → the planner opens rule leads.
        opened = plan_next_leads(c, rid)
        stages = sorted((o["stage"], o["subject"]) for o in opened)
        assert stages == [("rule", "B"), ("rule", "E")], stages
        # It does not re-open what already exists.
        assert plan_next_leads(c, rid) == [], "the planner must not repeat a lead"

        # Kira rules: E blocked (TKDN), B allowed.
        ex.upsert_node(c, rid, "ruling", "ruling:E", state="blocked",
                       subject="E", label="TKDN drops to 34.8%, floor 40%")
        ex.upsert_node(c, rid, "ruling", "ruling:B", state="allowed",
                       subject="B", label="TKDN rises to 41.6%")

        # Round 2: only the cleared option (B) gets a price lead. E is dropped.
        opened = plan_next_leads(c, rid)
        assert [(o["stage"], o["subject"]) for o in opened] == [("price", "B")], opened

        # The negative-knowledge gate refuses to price the blocked option.
        assert blocked_option_reject(c, rid, "E")["reject"] is True
        assert blocked_option_reject(c, rid, "B")["reject"] is False

        # Dedup: once B is priced, no second price lead is opened.
        ex.upsert_node(c, rid, "fact", "fact:price:B", origin="derived",
                       source="engine/simulate.py", payload={"total_idr": 116_000_000})
        assert option_already_priced(c, rid, "B") is True
        assert plan_next_leads(c, rid) == [], "a priced option must not re-open a price lead"

    with store.connect() as c:
        c.execute("DELETE FROM graph_edges WHERE run_id=?", (rid,))
        c.execute("DELETE FROM graph_nodes WHERE run_id=?", (rid,))
        c.execute("DELETE FROM runs WHERE id=?", (rid,))
        c.execute("DELETE FROM events WHERE id=?", (eid,))

    print("planner ok, chains option→rule→price ✓ · blocked option never priced ✓ "
          "· negative-knowledge + dedup gates ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_PLANNER_SELFCHECK")
    demo()
