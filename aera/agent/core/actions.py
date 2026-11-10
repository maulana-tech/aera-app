"""Raising an action: the one door through which anything leaves or moves money.

Every outward act - a payment, a refund, a message, a delivery - is raised
here, and three guards hold for all of them:

  * idempotency: identical content yields an identical key, so a retry is
    never a second payment (and the key is the vault's request id, so it is
    idempotent on chain too);
  * no run, no row: an action nobody can trace to a handling is an action
    nobody can approve or refuse;
  * the guardian first: core/guardian.py rules before the row is written. A
    `block` is recorded as blocked and never issued; a `warn` waits for a
    person; only an `allow` within every limit goes on the team's authority.

Execution is settle.py's job. An autonomous action is handed to it straight
away; an approved one is picked up by the `settle` job.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from core import registry, store
from core.provenance import Origin, Result


def idempotency_key(kind: str, **details: Any) -> str:
    fingerprint = "|".join(f"{k}={details[k]}" for k in sorted(details))
    return f"{kind}:{hashlib.sha256(fingerprint.encode()).hexdigest()[:16]}"


def raise_action(kind: str, payload: Dict[str, Any], verdict: Dict[str, Any], *,
                 value_usd: float = 0.0, key_details: Optional[Dict[str, Any]] = None,
                 force_approval: bool = False, execute: bool = True) -> Result:
    """Record an action under the run in force, as the guardian's verdict allows.

    `verdict` is from core/guardian.py (check_action, possibly combined with
    check_counterparty by the caller). `force_approval` sends it to a person
    whatever the verdict (refunds)."""
    run_id = registry.current_run()
    if not run_id:
        return Result(None, Origin.MISSING, "actions",
                      note="no run is open, so this action has nothing to attach to; raise it from a work item")
    key = idempotency_key(kind, **(key_details or payload))
    v = verdict.get("verdict", "block")
    why = "; ".join(r["detail"] for r in verdict.get("reasons", []) if r["verdict"] == v) or v
    if v == "block":
        status, autonomous = "blocked", False
    elif v == "warn" or force_approval:
        status, autonomous = "pending", False
    else:
        status, autonomous = "approved", True
    action = store.record_action(run_id, key, kind, autonomous, {**payload, "guardian": verdict},
                                 value_usd=value_usd, status=status, reason=why)
    if action.get("repeated"):
        return Result(action, Origin.DERIVED, "action record",
                      note="an identical action was already raised; it was not raised again")
    if verdict.get("check_id"):
        with store.connect() as c:
            c.execute("UPDATE guardian_checks SET action_id=? WHERE id=?", (action["id"], verdict["check_id"]))

    note = {"blocked": f"BLOCKED by the guardian: {why}. This is final.",
            "pending": f"waiting for a person: {why}",
            "approved": "within the team's authority"}[status]
    if status == "approved" and execute:
        import settle
        out = settle.execute(action["id"])
        action = store.get_action(action["id"]) or action
        note += f"; {out.get('summary', '')}"
    return Result(action, Origin.DERIVED, "action record", note=note)


def demo() -> None:
    from core import business
    store.save_profile(business.EXAMPLE, by="check")
    wid = store.record_work_item("request", "check", "api", {})
    rid = store.start_run(wid)
    ok = {"verdict": "allow", "reasons": [{"rule": "x", "verdict": "allow", "detail": "fine"}]}
    warn = {"verdict": "warn", "reasons": [{"rule": "cap", "verdict": "warn", "detail": "over the cap"}]}
    block = {"verdict": "block", "reasons": [{"rule": "inj", "verdict": "block", "detail": "injection"}]}

    assert raise_action("message", {"to": "a@b.c"}, ok).origin is Origin.MISSING, "no run, no row"
    with registry.bind_run(rid):
        a = raise_action("message", {"to": "a@b.c", "body": "hi"}, warn, execute=False)
        assert a.value["status"] == "pending" and "over the cap" in a.note
        again = raise_action("message", {"to": "a@b.c", "body": "hi"}, warn, execute=False)
        assert again.value["id"] == a.value["id"] and "not raised again" in again.note
        b = raise_action("payment", {"receiver": "x.testnet", "amount_usd": 1}, block, execute=False)
        assert b.value["status"] == "blocked" and "final" in b.note
        c = raise_action("message", {"to": "c@d.e"}, ok, execute=False)
        assert c.value["status"] == "approved" and c.value["autonomous"]
        r = raise_action("refund", {"order_id": "o1"}, ok, force_approval=True, execute=False)
        assert r.value["status"] == "pending"
    print("actions ok: no run no row ✓ · idempotent ✓ · block final ✓ · warn waits ✓ · refunds always wait ✓")


if __name__ == "__main__":
    from core.config import fixtures_only

    fixtures_only(__file__, "AERA_ACTIONS_CHECK")
    demo()
