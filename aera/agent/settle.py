"""Carrying out approved actions, and reading money that arrived.

    python3 settle.py            # one pass: execute approved, reconcile, ingest orders
    python3 settle.py --check    # the self-check, on a scratch database

What each kind of approved action becomes:

  payment        vault.request_payment with the agent's function-call key. The
                 vault applies its own allowlist and caps; a payment over its
                 cap comes back `pending` and waits for an approver's wallet.
                 With no vault configured it is recorded on the SIMULATED rail.
  refund         cannot be sent from here: the vault only takes a refund signed
                 by an approver's wallet. It waits as `approved` until the
                 vault reports it (reconcile), or a person marks it done.
  message        queued in the outbox (notify.py delivers it).
  deliver_order  the document is rendered, sent to the customer, and its hash
                 written to the vault (deliver_receipt) as proof of delivery.

One executor at a time per action (a lock, and the status re-read inside it),
so the job and a handling that reach the same row together cannot both send.
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
from typing import Any, Dict, List

from core import chain, store

_LOCK = threading.Lock()


def execute(action_id: str) -> Dict[str, Any]:
    """Carry out one approved action now. Returns {ok, summary, ...}."""
    with _LOCK:
        a = store.get_action(action_id)
        if a is None:
            return {"ok": False, "summary": f"no action {action_id}"}
        if a["status"] != "approved":
            return {"ok": a["status"] == "sent", "summary": f"the action is {a['status']}"}
        fn = {"payment": _pay, "refund": _refund, "message": _message,
              "deliver_order": _deliver, "external_write": _external}.get(a["kind"])
        if fn is None:
            return {"ok": False, "summary": f"nothing executes a '{a['kind']}'"}
        try:
            return fn(a)
        except Exception as e:                                         # noqa: BLE001
            store.move_action(a["id"], "failed", reason=f"{type(e).__name__}: {e}")
            return {"ok": False, "summary": f"failed: {type(e).__name__}: {e}"}


def _pay(a: Dict[str, Any]) -> Dict[str, Any]:
    p = a["payload"]
    receiver, amount = p["receiver"], float(p["amount_usd"])
    existing = store.payment_for_action(a["id"])
    if existing and existing["status"] in ("submitted", "sent", "pending_onchain"):
        return {"ok": True, "summary": f"already {existing['status']}"}
    if not chain.configured():
        pay = store.record_payment("out", "simulated", receiver, amount, "usdc", "sent", action_id=a["id"],
                                   request_id=chain.request_id(a["idempotency_key"]),
                                   detail={"simulated": True, "why": "no vault configured"})
        store.move_action(a["id"], "sent", reference=f"simulated:{pay['id']}")
        return {"ok": True, "summary": f"SIMULATED payment of ${amount:.2f} to {receiver} (no vault configured)",
                "payment": pay}
    pay = store.record_payment("out", "vault", receiver, amount, "usdc", "submitted", action_id=a["id"],
                               request_id=chain.request_id(a["idempotency_key"]))
    out = chain.request_payment(a["idempotency_key"], receiver, amount, p.get("purpose", ""), a["id"])
    status = str(out.get("result_json") or "").strip('"') or "sent"
    detail = {"events": out.get("events"), "explorer": out.get("explorer")}
    if status == "pending":
        store.update_payment(pay["id"], "pending_onchain", tx_hash=out.get("tx_hash"), detail=detail)
        return {"ok": True, "summary": f"the vault holds ${amount:.2f} for an approver's signature "
                                       f"(over its own cap); tx {out.get('tx_hash')}", "explorer": out.get("explorer")}
    if chain.payment_failed(out, a["idempotency_key"]):
        why = "the token refused the transfer (does the receiver hold USDC storage? storage_deposit first)"
        store.update_payment(pay["id"], "failed", tx_hash=out.get("tx_hash"), detail=detail)
        store.move_action(a["id"], "failed", reference=out.get("tx_hash"), reason=why)
        return {"ok": False, "summary": f"payment of ${amount:.2f} to {receiver} failed on chain: {why}; "
                                        f"tx {out.get('tx_hash')}", "explorer": out.get("explorer")}
    store.update_payment(pay["id"], "sent", tx_hash=out.get("tx_hash"), detail=detail)
    store.move_action(a["id"], "sent", reference=out.get("tx_hash"))
    return {"ok": True, "summary": f"paid ${amount:.2f} to {receiver}; tx {out.get('tx_hash')}",
            "explorer": out.get("explorer")}


def _refund(a: Dict[str, Any]) -> Dict[str, Any]:
    if chain.configured():
        return {"ok": True, "summary": "approved; an approver signs vault.refund from their wallet (Treasury page)"}
    p = a["payload"]
    order = store.get_order(p["order_id"]) or {}
    pay = store.record_payment("refund", "simulated", str(order.get("customer") or p.get("to") or "?"),
                               float(p["amount_usd"]), "usdc", "sent", action_id=a["id"],
                               detail={"simulated": True, "order_id": p["order_id"]})
    store.move_action(a["id"], "sent", reference=f"simulated:{pay['id']}")
    if order:
        store.update_order(order["id"], status="refunded")
    return {"ok": True, "summary": f"SIMULATED refund of ${float(p['amount_usd']):.2f} (no vault configured)"}


def _external(a: Dict[str, Any]) -> Dict[str, Any]:
    """Perform an approved write on a remote MCP server, if the owner still allows it there."""
    from clients import mcp_client
    p = a["payload"]
    srv = next((r for r in store.mcp_servers(include_token=True) if r["name"] == p.get("server")), None)
    tool = next((t for t in (srv or {}).get("tools") or [] if t.get("name") == p.get("tool")), None)
    if not srv or not srv.get("enabled") or not tool or not tool.get("write_allowed"):
        why = "the server or the tool is no longer allowed to write"
        store.move_action(a["id"], "failed", reason=why)
        return {"ok": False, "summary": why}
    out = mcp_client.call(srv["url"], srv.get("token"), p["tool"], dict(p.get("arguments") or {}))
    if not out.get("ok"):
        why = str(out.get("error") or "the server did not answer")[:300]
        store.move_action(a["id"], "failed", reason=why)
        return {"ok": False, "summary": f"{p['server']}.{p['tool']} failed: {why}"}
    store.move_action(a["id"], "sent", reference=str(out.get("text") or "done")[:300])
    return {"ok": True, "summary": f"{p['server']}.{p['tool']} done"}


def _message(a: Dict[str, Any]) -> Dict[str, Any]:
    p = a["payload"]
    key = f"msg:{a['id']}"
    ok = store.enqueue_notification(key, "outreach", "email", p["to"], p.get("subject") or "(no subject)",
                                    p.get("body") or "", action_id=a["id"])
    store.move_action(a["id"], "sent", reference=key)
    return {"ok": True, "summary": f"queued to {p['to']}" + ("" if ok else " (already queued)")}


def render_document(doc: Dict[str, Any]) -> bytes:
    """A stored document as the bytes the customer receives (PDF)."""
    from engine.export import Doc
    meta = json.loads(doc.get("mime", "").split(";", 1)[1]) if ";" in doc.get("mime", "") else {}
    from datetime import datetime
    try:
        created = datetime.fromisoformat(doc.get("uploaded_at") or "")
    except ValueError:
        created = None
    d = Doc(meta.get("title") or doc["name"], created=created)
    d.md(doc["text"])
    return d.render()


def _deliver(a: Dict[str, Any]) -> Dict[str, Any]:
    p = a["payload"]
    order = store.get_order(p["order_id"])
    doc = store.get_file(p["document_id"])
    if not order or not doc:
        raise RuntimeError("the order or the document is gone")
    body = render_document(doc)
    digest = hashlib.sha256(body).hexdigest()
    receipt: Dict[str, Any] = {"hash": digest, "document_id": doc["id"], "bytes": len(body)}
    if p.get("to"):
        store.enqueue_notification(f"deliver:{a['id']}", "delivery", "email", p["to"],
                                   p.get("subject") or f"Your order {order['id']}", p.get("note") or "",
                                   action_id=a["id"],
                                   attachments=[{"document": doc["id"], "format": "pdf"}])
        receipt["sent_to"] = p["to"]
    if chain.configured():
        out = chain.deliver_receipt(order["id"], digest)
        receipt["tx_hash"], receipt["explorer"] = out.get("tx_hash"), out.get("explorer")
    store.update_order(order["id"], status="delivered", delivery=receipt)
    store.move_action(a["id"], "sent", reference=receipt.get("tx_hash") or f"sha256:{digest[:16]}")
    return {"ok": True, "summary": f"delivered order {order['id']} (sha256 {digest[:12]}…)"
                                   + (f", receipt on chain {receipt['tx_hash']}" if receipt.get("tx_hash") else "")}


# ------------------------------------------------------------- reconcile
def reconcile() -> int:
    """Follow payments the vault is holding for an approver."""
    if not chain.readable():
        return 0
    moved = 0
    for pay in store.list_payments(status="pending_onchain"):
        try:
            req = chain.view("get_request", {"request_id": pay["request_id"]})
        except Exception:                                              # noqa: BLE001
            continue
        st = (req or {}).get("status")
        if st in ("approved", "sent"):
            store.update_payment(pay["id"], "sent", detail={"vault": req})
            if pay["action_id"]:
                store.move_action(pay["action_id"], "sent", reference=pay.get("tx_hash"))
            moved += 1
        elif st in ("rejected", "failed"):
            store.update_payment(pay["id"], st, detail={"vault": req})
            if pay["action_id"]:
                store.move_action(pay["action_id"], "failed", reason=f"vault: {st} {req.get('reason') or ''}")
            moved += 1
    # The vault answers "sent" when it STARTS the transfer; a transfer the token
    # then refuses comes back as "failed" in on_transfer. So a vault payment
    # marked sent in the last day is read once more, and a failure is recorded.
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    for pay in store.list_payments(status="sent"):
        if pay["rail"] != "vault" or pay["direction"] != "out" or not pay.get("request_id") \
                or pay["created_at"] < since or (pay.get("detail") or {}).get("confirmed"):
            continue
        try:
            req = chain.view("get_request", {"request_id": pay["request_id"]})
        except Exception:                                              # noqa: BLE001
            continue
        st = (req or {}).get("status")
        if st == "failed":
            store.update_payment(pay["id"], "failed", detail={"vault": req})
            if pay["action_id"]:
                store.move_action(pay["action_id"], "failed", reason="vault: the token refused the transfer")
            moved += 1
        elif st in ("sent", "approved"):
            store.update_payment(pay["id"], "sent", detail={"confirmed": True})
    return moved


def ingest_orders() -> List[str]:
    """Orders paid to the vault since the last pass become work items."""
    if not chain.readable():
        return []
    start = int(store.get_setting("vault.orders_seen") or 0)
    try:
        rows = chain.view("list_orders", {"from_index": start, "limit": 50}) or []
    except Exception:                                                  # noqa: BLE001
        return []
    raised = []
    for o in rows:
        amount = chain.from_base(o.get("amount", 0))
        raised += order_paid(o["order_id"], payer=o.get("payer"), amount_usd=amount, offering=o.get("offering"),
                             tx=chain.order_tx(o["order_id"], o.get("payer") or "", amount), rail="vault")
    if rows:
        store.set_setting("vault.orders_seen", str(start + len(rows)), by="settle")
    return raised


#: A vault order whose transaction is not found yet is looked up again on later passes (the explorer
#: indexes a little after the chain), at most this many times.
TX_LOOKUPS = 6


def fill_order_txs(lookup=None) -> int:
    """Vault orders recorded without their transaction get it, once the chain confirms which one it was.

    Finance reads the payment's transaction for the receipt and the books; an order paid to the vault
    comes in without one (list_orders does not carry it). Returns how many were filled."""
    lookup = lookup or chain.order_tx
    filled = 0
    for pay in store.list_payments(status="sent"):
        d = pay.get("detail") or {}
        if pay["direction"] != "in" or pay["rail"] != "vault" or pay.get("tx_hash") or not d.get("order_id") \
                or int(d.get("tx_lookups") or 0) >= TX_LOOKUPS:
            continue
        tx = lookup(d["order_id"], pay["counterparty"], pay["amount_usd"])
        if tx:
            store.update_payment(pay["id"], "sent", tx_hash=tx, detail={"tx_confirmed_by": "order_paid event"})
            store.update_order(d["order_id"], paid_tx=tx)
            filled += 1
        else:
            store.update_payment(pay["id"], "sent", detail={"tx_lookups": int(d.get("tx_lookups") or 0) + 1})
    return filled


def fill_approval_txs(lookup=None) -> int:
    """A payment the vault held gets the transaction that actually paid it: the approver's approve call.

    Until then it carries the agent's request_payment hash, which only parked the payment. That hash is
    kept as detail.request_tx. Gives up after TX_LOOKUPS tries, like fill_order_txs."""
    lookup = lookup or chain.approval_tx
    filled = 0
    for pay in store.list_payments(status="sent"):
        d = pay.get("detail") or {}
        v = d.get("vault") or {}
        if pay["direction"] != "out" or pay["rail"] != "vault" or not v.get("decided_by") \
                or d.get("request_tx") or int(d.get("tx_lookups") or 0) >= TX_LOOKUPS:
            continue
        tx = lookup(pay["request_id"], pay["counterparty"], pay["amount_usd"], v["decided_by"])
        if tx:
            store.update_payment(pay["id"], "sent", tx_hash=tx,
                                 detail={"request_tx": pay.get("tx_hash"), "tx_confirmed_by": "payment_approved event"})
            if pay["action_id"]:
                store.move_action(pay["action_id"], "sent", reference=tx)
            filled += 1
        else:
            store.update_payment(pay["id"], "sent", detail={"tx_lookups": int(d.get("tx_lookups") or 0) + 1})
    return filled


def order_paid(order_id: str, *, payer: Any, amount_usd: float, offering: Any, tx: Any, rail: str) -> List[str]:
    """Mark an order paid and raise its work item (once)."""
    order = store.get_order(order_id) or store.create_order(order_id, offering or "unknown", amount_usd, {},
                                                            customer=payer, status="awaiting_payment")
    if order["status"] != "awaiting_payment":
        return []
    store.record_payment("in", rail, str(payer or order.get("customer") or "?"), amount_usd, "usdc", "sent",
                         tx_hash=tx, detail={"order_id": order_id})
    wid = store.record_work_item("order", f"Order {order_id}: {order['offering']}", rail,
                                 {"order_id": order_id, "offering": order["offering"], "inputs": order["inputs"],
                                  "customer": order.get("customer"), "amount_usd": amount_usd},
                                 dedup_key=f"order:{order_id}")
    store.update_order(order_id, status="paid", paid_tx=tx, work_item_id=wid,
                       customer=order.get("customer") or payer)
    return [wid] if wid else []


def run_once() -> str:
    done = 0
    for a in store.list_actions(status="approved"):
        if a["kind"] in ("payment", "message", "deliver_order", "external_write") or (a["kind"] == "refund" and not chain.configured()):
            if execute(a["id"]).get("ok"):
                done += 1
    moved = reconcile()
    raised = ingest_orders()
    filled = (fill_order_txs() + fill_approval_txs()) if chain.readable() else 0
    return f"{done} executed · {moved} reconciled · {len(raised)} order(s) in" + (f" · {filled} tx found" if filled else "")


def check() -> None:
    from core import business, registry
    from core.actions import raise_action
    store.save_profile(business.EXAMPLE, by="check")
    wid = store.record_work_item("request", "check", "api", {})
    rid = store.start_run(wid)
    ok = {"verdict": "allow", "reasons": []}
    with registry.bind_run(rid):
        r = raise_action("payment", {"receiver": "dataco.testnet", "amount_usd": 2.0, "purpose": "api"}, ok,
                         value_usd=2.0)
    a = store.get_action(r.value["id"])
    assert a["status"] == "sent" and a["reference"].startswith("simulated:"), a
    pay = store.payment_for_action(a["id"])
    assert pay["rail"] == "simulated" and pay["detail"]["simulated"], pay
    assert execute(a["id"])["summary"] == "the action is sent", "a sent action is never sent twice"

    store.create_order("ord_1", "brief", 15.0, {"industry": "coffee"}, customer="alice.testnet")
    w = order_paid("ord_1", payer="alice.testnet", amount_usd=15.0, offering="brief", tx="tx9", rail="simulated")
    assert w and order_paid("ord_1", payer="x", amount_usd=15, offering="brief", tx="tx9", rail="simulated") == []
    assert store.get_order("ord_1")["status"] == "paid"
    assert store.get_work_item(w[0])["payload"]["inputs"] == {"industry": "coffee"}

    # a vault order recorded without its transaction gets it once the chain confirms it, and stops asking after a few tries
    store.create_order("ord_v", "brief", 15.0, {}, customer="bob.testnet")
    order_paid("ord_v", payer="bob.testnet", amount_usd=15.0, offering="brief", tx=None, rail="vault")
    asked = []
    assert fill_order_txs(lambda *a: asked.append(a)) == 0 and asked == [("ord_v", "bob.testnet", 15.0)]
    assert fill_order_txs(lambda *a: "TxV") == 1
    assert store.get_order("ord_v")["paid_tx"] == "TxV" and fill_order_txs(lambda *a: "again") == 0
    store.create_order("ord_w", "brief", 5.0, {}, customer="eve.testnet")
    order_paid("ord_w", payer="eve.testnet", amount_usd=5.0, offering="brief", tx=None, rail="vault")
    for _ in range(TX_LOOKUPS + 2):
        fill_order_txs(lambda *a: asked.append(a))
    assert sum(1 for a in asked if a[0] == "ord_w") == TX_LOOKUPS, "gives up after a few lookups"
    # a payment the vault held shows the approver's transaction, not the request that parked it
    held = store.record_payment("out", "vault", "dataco.testnet", 8.0, "usdc", "pending_onchain",
                                request_id="payment:h1", tx_hash="TxRequest")
    store.update_payment(held["id"], "sent", detail={"vault": {"status": "approved", "decided_by": "owner.testnet"}})
    asked = []
    assert fill_approval_txs(lambda *a: asked.append(a)) == 0 and asked == [("payment:h1", "dataco.testnet", 8.0, "owner.testnet")]
    assert fill_approval_txs(lambda *a: "TxApprove") == 1
    got = next(p for p in store.list_payments() if p["id"] == held["id"])
    assert got["tx_hash"] == "TxApprove" and got["detail"]["request_tx"] == "TxRequest", got
    assert fill_approval_txs(lambda *a: "again") == 0, "filled once"
    print("settle ok: simulated rail labelled ✓ · never sent twice ✓ · a paid order raises one work item ✓ · vault order tx filled once confirmed ✓ · held payment shows the approval tx ✓")


if __name__ == "__main__":
    if "--check" in sys.argv:
        from core.config import fixtures_only
        fixtures_only(__file__, "AERA_SETTLE_CHECK")
        check()
    else:
        print(run_once())
