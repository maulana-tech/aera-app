"""Sends approved actions to SAP.

Kept apart from the agents on purpose: the agents propose, a human approves,
this file sends. Run it on a schedule.

An action SIGAP may take on its own authority comes through here too, the
moment it is raised (tools/execution.py): it starts approved, the autonomy
limit standing in for the approver, and is `sent` only once SAP has taken it.
A write that fails leaves it approved, so the next pass tries it again, the
same as an action a person approved.

    python3 sender.py                # one pass
    python3 sender.py --check        # self-check, against a fake SAP
"""
from __future__ import annotations

import sys
import threading
from typing import Dict, Optional

from clients import sap_s4
from core import store

TARGETS = {
    "draft_po": ("API_PURCHASEREQ_PROCESS_SRV", "A_PurchaseRequisitionHeader"),
    "stock_transfer": ("API_STOCK_TRANSFER_SRV", "A_StockTransfer"),
    "create_sourcing_event": ("API_SOURCING_PROJECT_SRV", "A_SourcingProject"),
}

# One poster at a time. The schedule's pass and a handling's autonomous
# transfer can reach the same row together; whoever holds the lock reads the
# status again first, so the other finds it already sent and posts nothing.
_LOCK = threading.Lock()


def send_one(action_id: str) -> Dict[str, Optional[str]]:
    """Post one approved action now. {"sent": True, "reference": ...}, or
    {"sent": False, "why": ...} with the action left as it was."""
    if not sap_s4.available():
        return {"sent": False, "why": "SAP is not connected (SAP_API_KEY is not set)"}
    with _LOCK:
        a = store.get_action(action_id)
        if a is None:
            return {"sent": False, "why": f"no action {action_id}"}
        if a["status"] != "approved":
            return {"sent": a["status"] == "sent", "reference": a.get("sap_reference"),
                    "why": f"the action is {a['status']}"}
        if a["kind"] not in TARGETS:
            return {"sent": False, "why": f"kind '{a['kind']}' is not mapped to SAP yet"}
        service, entity = TARGETS[a["kind"]]
        try:
            r = sap_s4.post(service, entity, a["payload"], idempotency_key=a["idempotency_key"])
        except Exception as e:                                       # noqa: BLE001
            # A failure does NOT change the status. The action stays 'approved'
            # and is retried later, the idempotency key prevents a double order.
            return {"sent": False, "why": f"{service}: {type(e).__name__}: {e}"}
        ref = str((r.get("d") or {}).get("PurchaseRequisition")
                  or (r.get("d") or {}).get("MaterialDocument") or "sent")
        store.mark_sent(a["id"], ref)
        return {"sent": True, "reference": ref}


def send_approved() -> int:
    if not sap_s4.available():
        print("SAP_API_KEY is not set. Nothing sent.")
        return 0

    with store.connect() as c:
        queued = c.execute("SELECT id, kind FROM actions WHERE status='approved'").fetchall()

    import outreach
    sent = 0
    for a in queued:
        kind = a["kind"]
        if kind in outreach.KINDS:
            continue                      # an email, sent by outreach.py, not a SAP document
        if kind not in TARGETS:
            print(f"  skip {a['id']}: kind '{kind}' is not mapped to SAP yet")
            continue
        r = send_one(a["id"])
        if r["sent"]:
            print(f"  ✓ {a['id']} → {TARGETS[kind][0]} · {r['reference']}")
            sent += 1
        else:
            print(f"  ✗ {a['id']}: {r['why']}", file=sys.stderr)
    return sent


def check() -> None:
    from tools.execution import idempotency_key

    posted = []
    down = {"on": False}
    real = sap_s4.available, sap_s4.post
    sap_s4.available = lambda: True

    def fake_post(service, entity, payload, idempotency_key=None):
        if down["on"]:
            raise ConnectionError("sandbox unreachable")
        posted.append((service, idempotency_key))
        return {"d": {"MaterialDocument": f"49000{len(posted):05d}"}}

    sap_s4.post = fake_post
    try:
        eid = store.record_event("port_closure", "Typhoon closes Ningbo", "check", {}, "sender-check")
        rid = store.start_run(eid, "autonomous")
        body = {"material": "M-4471", "from_plant": "SBY1", "to_plant": "KRW1",
                "qty": 22.0, "cost_idr": 22_000_000}
        a = store.record_action(rid, idempotency_key("stock_transfer", **body),
                                "stock_transfer", True, body, status="approved")

        # SAP down: nothing changes, and the action is still there to retry.
        down["on"] = True
        r = send_one(a["id"])
        assert not r["sent"] and "unreachable" in r["why"], r
        assert store.get_action(a["id"])["status"] == "approved"

        # Back up: the next pass sends it, once, with the action's own key.
        down["on"] = False
        assert send_approved() == 1
        got = store.get_action(a["id"])
        assert got["status"] == "sent" and got["sap_reference"] == "4900000001", got
        assert posted == [("API_STOCK_TRANSFER_SRV", a["idempotency_key"])], posted
        assert send_one(a["id"]) == {"sent": True, "reference": "4900000001",
                                     "why": "the action is sent"}
        assert send_approved() == 0 and len(posted) == 1, "a sent action is never posted again"

        # Waiting for a person: never posted.
        p = store.record_action(rid, "k-sender-pending", "draft_po", False, {"cost_idr": 1})
        assert not send_one(p["id"])["sent"] and len(posted) == 1
    finally:
        sap_s4.available, sap_s4.post = real
    print("sender ok: a failed write stays approved and is retried; a sent one is never posted twice")


if __name__ == "__main__":
    if "--check" in sys.argv:
        from core.config import fixtures_only
        fixtures_only(__file__, "SIGAP_SENDER_CHECK")
        check()
    else:
        n = send_approved()
        print(f"{n} action(s) sent.")
