"""Issues approved actions as documents.

Kept apart from the agents on purpose: the agents propose, a human approves,
this file issues. Run it on a schedule.

An action AERA may take on its own authority comes through here too, the
moment it is raised (tools/execution.py): it starts approved, the autonomy
limit standing in for the approver, and is `sent` only once it has issued.

    python3 sender.py                # one pass
    python3 sender.py --check        # self-check
"""
from __future__ import annotations

import hashlib
import sys
import threading
from typing import Dict, Optional

from core import store

#: The kinds of action that issue as a document, and what that document is.
TARGETS = {
    "draft_po": "purchase requisition",
    "stock_transfer": "stock transfer",
    "create_sourcing_event": "sourcing project",
}

#: The number range each kind draws from. A document number is read, quoted
#: and searched for, so it is shaped like one rather than like a label.
RANGE = {
    "draft_po": 10_00000000,              # purchase requisition
    "stock_transfer": 49_00000000,        # material document
    "create_sourcing_event": 70_00000000,  # sourcing project
}


def reference(kind: str, idempotency_key: str) -> str:
    """A stable document number for an action.

    Derived from the idempotency key, so the same action issued twice gets the
    same number.
    """
    base = RANGE.get(kind, 90_00000000)
    n = int(hashlib.sha256(idempotency_key.encode()).hexdigest()[:8], 16) % 1_000_000
    return str(base + n)


# One poster at a time. The schedule's pass and a handling's autonomous
# transfer can reach the same row together; whoever holds the lock reads the
# status again first, so the other finds it already sent and posts nothing.
_LOCK = threading.Lock()


def send_one(action_id: str) -> Dict[str, Optional[str]]:
    """Issue one approved action now. {"sent": True, "reference": ...}, or
    {"sent": False, "why": ...} with the action left as it was."""
    with _LOCK:
        a = store.get_action(action_id)
        if a is None:
            return {"sent": False, "why": f"no action {action_id}"}
        if a["status"] != "approved":
            return {"sent": a["status"] == "sent", "reference": a.get("reference"),
                    "why": f"the action is {a['status']}"}
        if a["kind"] not in TARGETS:
            return {"sent": False, "why": f"kind '{a['kind']}' is not a document"}
        ref = reference(a["kind"], a["idempotency_key"])
        store.mark_sent(a["id"], ref)
        return {"sent": True, "reference": ref}


def send_approved() -> int:
    with store.connect() as c:
        queued = c.execute("SELECT id, kind FROM actions WHERE status='approved'").fetchall()

    import outreach
    sent = 0
    for a in queued:
        kind = a["kind"]
        if kind in outreach.KINDS:
            continue                      # an email, sent by outreach.py
        if kind not in TARGETS:
            continue                      # not a document; nothing to issue
        r = send_one(a["id"])
        if r["sent"]:
            print(f"  ✓ {a['id']} → {TARGETS[kind]} · {r['reference']}")
            sent += 1
        else:
            print(f"  ✗ {a['id']}: {r['why']}", file=sys.stderr)
    return sent


def check() -> None:
    from tools.execution import idempotency_key

    eid = store.record_event("port_closure", "Typhoon closes Ningbo", "check", {}, "sender-check")
    rid = store.start_run(eid, "autonomous")
    body = {"material": "M-4471", "from_plant": "SBY1", "to_plant": "KRW1",
            "qty": 22.0, "cost_idr": 22_000_000}
    a = store.record_action(rid, idempotency_key("stock_transfer", **body),
                            "stock_transfer", True, body, status="approved")

    # One pass issues it, once, with a number derived from its own key.
    assert send_approved() == 1
    got = store.get_action(a["id"])
    want = reference("stock_transfer", a["idempotency_key"])
    assert got["status"] == "sent" and got["reference"] == want, got
    assert want.isdigit() and want.startswith("49"), want
    assert send_one(a["id"]) == {"sent": True, "reference": want, "why": "the action is sent"}
    assert send_approved() == 0, "a sent action is never issued again"

    # Waiting for a person: never issued.
    p = store.record_action(rid, "k-sender-pending", "draft_po", False, {"cost_idr": 1})
    assert not send_one(p["id"])["sent"]

    # The same action issued twice keeps the same document number.
    assert reference("draft_po", "idem-abc") == reference("draft_po", "idem-abc")
    assert reference("stock_transfer", "idem-abc") != reference("draft_po", "idem-abc")
    print("sender ok: an approved action issues once, with a stable document number")


if __name__ == "__main__":
    if "--check" in sys.argv:
        from core.config import fixtures_only
        fixtures_only(__file__, "AERA_SENDER_CHECK")
        check()
    else:
        n = send_approved()
        print(f"{n} action(s) sent.")
