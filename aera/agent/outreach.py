"""Tells parties outside the company: a supplier asked about its order, a
customer told theirs will be late. Only what a person approved, only as they
saw it.

Bram drafts the email (tools/execution.py): subject, body and the address the
record holds for the partner, all in the action's payload. A person approves it
in the decision queue. This file then puts it in the outbox the alerts use, so
notify.py delivers it with the same retries, and once the mailbox has taken it
the action is stamped sent with the message id. Nothing is composed here: the
subject and body are the draft's, word for word.

Who may approve which (api.py asks before it records the approval):

  supplier_request   a buyer or above
  customer_notice    a procurement lead or above: it speaks for the company
                     to a customer about a commitment

Outside production nothing reaches a real supplier or customer. Partner
records can carry real people's addresses, so every message is
sent to AERA_EXTERNAL_REDIRECT instead, marked as a test and naming the address
it was meant for. With no redirect set, nothing is sent and the action says
why. In production, AERA_EXTERNAL_DOMAINS, when set, is the only list of
domains AERA may write to.

    python3 outreach.py            # queue what is approved, then deliver
    python3 outreach.py --check    # the self-check, on a scratch database
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Tuple

from core import store
from core.config import CFG

KINDS = ("supplier_request", "customer_notice")
APPROVERS = {"supplier_request": ("buyer", "procurement_lead", "admin"),
             "customer_notice": ("procurement_lead", "admin")}


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def refusal(kind: str, role: str) -> Optional[str]:
    """Why `role` may not approve this outward message, or None when it may."""
    allowed = APPROVERS.get(kind)
    if allowed and role not in allowed:
        return (f"a {role} cannot approve a {kind.replace('_', ' ')}: it goes outside the "
                f"company (needs {' or '.join(allowed)})")
    return None


def _domain(address: str) -> str:
    return address.rsplit("@", 1)[-1].lower() if "@" in address else ""


def destination(payload: dict) -> Tuple[Optional[str], str]:
    """(where it goes, why) or (None, why not)."""
    to = str(payload.get("to") or "").strip()
    if not to or "@" not in to:
        return None, "no email on record for the partner; a person must send it"
    if not CFG.production:
        redirect = _env("AERA_EXTERNAL_REDIRECT")
        if not redirect:
            return None, (f"AERA is not in production ({CFG.env}), so nothing goes to {to}; "
                          "set AERA_EXTERNAL_REDIRECT to a test address to see it sent")
        return redirect, f"a test: sent to {redirect} instead of {to}"
    allowed = [d.strip().lower() for d in _env("AERA_EXTERNAL_DOMAINS").split(",") if d.strip()]
    if allowed and _domain(to) not in allowed:
        return None, f"{_domain(to)} is not in AERA_EXTERNAL_DOMAINS"
    return to, ""


def message(payload: dict, address: str) -> Dict[str, str]:
    subject, body = str(payload.get("subject") or ""), str(payload.get("body") or "")
    to = str(payload.get("to") or "")
    if address != to:
        subject = f"[TEST] {subject}"
        body = (f"TEST from AERA, which is not in production. This message was approved "
                f"for {to} and sent here instead.\n\n{body}")
    return {"subject": subject, "body": body}


def queue(action_id: str, again: bool = False) -> Dict[str, object]:
    """Put an approved outward message in the outbox. Asking twice queues it
    once; `again` queues a fresh copy after a send that failed."""
    a = store.get_action(action_id)
    if not a or a["kind"] not in KINDS:
        return {"queued": False, "why": "not an outward message"}
    if a["status"] != "approved":
        return {"queued": False, "why": f"the action is {a['status']}, not approved"}
    last = store.notification_for_action(action_id)
    if last and (not again or last["status"] in ("pending", "sent")):
        return {"queued": False, "why": f"already {last['status']}", "to": last["address"]}
    address, why = destination(a["payload"])
    if not address:
        return {"queued": False, "why": why}
    msg = message(a["payload"], address)
    tries = len([n for n in store.list_notifications(500) if n.get("action_id") == action_id])
    key = f"outreach:{action_id}" + (f":{tries}" if tries else "")
    ok = store.enqueue_notification(key, "outreach", "email", address, msg["subject"], msg["body"],
                                    run_id=a["run_id"], action_id=action_id)
    return {"queued": ok, "to": address, "why": why}


def queue_approved() -> int:
    """Every approved outward message not yet in the outbox: the decision may
    have been recorded while the mailbox was not connected."""
    with store.connect() as c:
        ids = [r["id"] for r in c.execute(
            f"SELECT id FROM actions WHERE status='approved' AND kind IN ({','.join('?' * len(KINDS))})"
            " ORDER BY created_at", KINDS).fetchall()]
    return sum(1 for i in ids if queue(i)["queued"])


def delivered(action_id: str, reference: Optional[str]) -> None:
    store.mark_sent(action_id, f"email {reference}" if reference else "email")


def state(action: dict) -> Optional[Dict[str, object]]:
    """For the decision queue: where an outward message will go, or went."""
    if action.get("kind") not in KINDS:
        return None
    payload = action.get("payload") or {}
    last = store.notification_for_action(action["id"])
    if last:
        return {"to": last["address"], "status": last["status"], "error": last.get("error"),
                "reference": last.get("reference"), "sent_at": last.get("sent_at")}
    address, why = destination(payload)
    return {"to": address, "status": "not queued", "why": why, "meant_for": payload.get("to")}


def demo() -> None:
    """Against a scratch database: the __main__ block guarantees one."""
    import json
    import notify
    from clients import channels

    saved = {k: os.environ.pop(k, None) for k in ("AERA_EXTERNAL_REDIRECT", "AERA_EXTERNAL_DOMAINS")}
    sent: List[tuple] = []
    real_send = channels.send

    def fake_send(channel, address, subject, body, extra=None, files=()):
        if address == "down@test.example":
            raise channels.DeliveryFailed("421 try again later")
        sent.append((channel, address, subject, body))
        return f"<msg-{len(sent)}@test>"

    channels.send = fake_send
    try:
        assert refusal("customer_notice", "buyer") and not refusal("customer_notice", "procurement_lead")
        assert not refusal("supplier_request", "buyer") and refusal("supplier_request", "planner")
        assert refusal("stock_transfer", "planner") is None, "money limits are decide()'s, not ours"

        eid = store.record_event("supplier_failure", "Qingdao Baowu misses a shipment", "check",
                                 {}, "outreach-check")
        rid = store.start_run(eid, "guided")
        payload = {"purchase_order": "4500018876", "supplier": "SUP-2209",
                   "to": "sales@sup-2209.example", "subject": "Purchase order 4500018876: request",
                   "body": "Please confirm the revised date.\n\nPurchase order: 4500018876"}
        act = store.record_action(rid, "k-outreach-1", "supplier_request", False, payload)
        aid = act["id"]

        assert queue(aid)["why"].startswith("the action is pending"), "nothing goes before approval"
        store.decide_action(aid, "buyer@co", "buyer", "approved")
        q = queue(aid)
        assert not q["queued"] and "not in production" in q["why"], q
        assert queue_approved() == 0, "outside production, no redirect: nothing is sent"

        os.environ["AERA_EXTERNAL_REDIRECT"] = "tester@co.example"
        assert queue_approved() == 1 and queue(aid)["queued"] is False, "queued once"
        notify.deliver()
        (ch, addr, subject, body), = sent
        assert addr == "tester@co.example" and subject.startswith("[TEST] ") \
            and "approved for sales@sup-2209.example" in body \
            and body.endswith(payload["body"]), (addr, subject, body)
        a = store.get_action(aid)
        assert a["status"] == "sent" and a["reference"] == "email <msg-1@test>", a
        assert state(a)["status"] == "sent"

        # A send that fails three times leaves the action approved, and can be queued again.
        act2 = store.record_action(rid, "k-outreach-2", "customer_notice", False,
                                   dict(payload, to="buyer@cus-1001.example", subject="Your order"))
        store.decide_action(act2["id"], "lead@co", "procurement_lead", "approved")
        os.environ["AERA_EXTERNAL_REDIRECT"] = "down@test.example"
        assert queue(act2["id"])["queued"]
        for _ in range(notify.MAX_ATTEMPTS):
            notify.deliver()
        assert state(store.get_action(act2["id"]))["status"] == "failed"
        assert store.get_action(act2["id"])["status"] == "approved"
        os.environ["AERA_EXTERNAL_REDIRECT"] = "tester@co.example"
        assert queue(act2["id"])["queued"] is False, "a failed one is not retried by itself"
        assert queue(act2["id"], again=True)["queued"] is True
        notify.deliver()
        assert store.get_action(act2["id"])["status"] == "sent"

        # Production: the partner's own address, inside the allowed domains only.
        real = CFG.env
        object.__setattr__(CFG, "env", "prod")
        try:
            assert destination(payload) == ("sales@sup-2209.example", "")
            os.environ["AERA_EXTERNAL_DOMAINS"] = "partner.example"
            assert destination(payload)[0] is None
            assert destination({"to": None})[0] is None
        finally:
            object.__setattr__(CFG, "env", real)
        assert json.loads(json.dumps(state(store.get_action(aid))))
        store.close_run(rid, "done", decision={"status": "done"})
    finally:
        channels.send = real_send
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    print("  outreach: nothing before approval ✓ · customer notice needs a procurement lead ✓ "
          "· outside production redirected or not sent ✓ · sent as approved, stamped with its id ✓ "
          "· a failed send stays approved and can be sent again ✓ · production keeps to its domains ✓")
    print("outreach ok")


if __name__ == "__main__":
    if "--check" in sys.argv:
        from core import config
        config.fixtures_only(__file__, "AERA_OUTREACH_CHECK")
        demo()
    else:
        import notify
        print(f"queued {queue_approved()} outward message(s)")
        print(notify.deliver_summary())
