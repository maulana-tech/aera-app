"""The books: receipts, the monthly report and the reconciliation against the vault.

Every figure here is computed in code from the record (payments, orders, runs) and, where there is a
vault, from the chain. A model never writes a number into a receipt or a report: the Finance agent
reads these figures, explains them and flags what does not add up, and cannot move money (only the
Treasurer can, through the vault).

    receipt_pdf(order_id)   the customer's receipt for a paid order, the same bytes every time
    report(month)           revenue, refunds, revenue shares, vendor spend, AI cost and margin
    report_markdown(...)    the report as a document, figures from code, commentary from the agent
    reconcile()             AERA's ledger against the vault on chain, with every difference named
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core import store


def _month_bounds(month: Optional[str]) -> Tuple[str, str, str]:
    """'2026-11' -> (start, end, label); None is the current month (UTC)."""
    now = datetime.now(timezone.utc)
    if month:
        y, m = (int(x) for x in month.split("-", 1))
    else:
        y, m = now.year, now.month
    start = datetime(y, m, 1, tzinfo=timezone.utc)
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc)
    return start.isoformat(), end.isoformat(), start.strftime("%B %Y")


def _usd(x: float) -> str:
    return f"${x:,.2f}"


# ------------------------------------------------------------------ receipt
def receipt_data(order_id: str) -> Optional[Dict[str, Any]]:
    """What a receipt states, or None while the order is not paid."""
    o = store.get_order(order_id)
    if not o or o["status"] in ("awaiting_payment",):
        return None
    from core import business, chain
    p = business.current()
    offering = next((x for x in p.get("offerings", []) if x.get("id") == o["offering"]), {})
    with store.connect() as c:
        pay = c.execute("SELECT rail, counterparty, amount_usd, tx_hash, created_at FROM payments WHERE direction='in'"
                        " AND detail LIKE ? ORDER BY created_at LIMIT 1", (f'%"{order_id}"%',)).fetchone()
        refunded = c.execute("SELECT COALESCE(SUM(amount_usd),0) FROM payments WHERE direction='refund' AND status='sent'"
                             " AND detail LIKE ?", (f'%"{order_id}"%',)).fetchone()[0]
    rail = pay["rail"] if pay else "simulated"
    delivery = o.get("delivery") or {}
    if isinstance(delivery, str):
        try:
            delivery = json.loads(delivery)
        except ValueError:
            delivery = {}
    return {
        "number": f"R-{order_id.removeprefix('ord_').upper()}",
        "business": p.get("name") or "AERA business",
        "order_id": order_id,
        "offering": offering.get("title") or o["offering"],
        "amount_usd": float(pay["amount_usd"] if pay else o["amount_usd"]),
        "token": "USDC",
        "paid_at": (pay["created_at"] if pay else o["updated_at"]),
        "paid_by": (pay["counterparty"] if pay else o.get("customer")) or "-",
        "rail": rail,
        "network": chain.network() if rail == "vault" else None,
        "vault": chain.vault_id() if rail == "vault" else None,
        "tx_hash": (pay["tx_hash"] if pay else None) or o.get("paid_tx"),
        "status": o["status"],
        "refunded_usd": float(refunded or 0),
        "delivered_hash": delivery.get("hash"),
    }


def receipt_pdf(order_id: str) -> Optional[bytes]:
    r = receipt_data(order_id)
    if not r:
        return None
    from engine.export import Doc
    paid = datetime.fromisoformat(r["paid_at"])
    d = Doc(f"Receipt {r['number']}", kicker=r["business"], subtitle=f"Order {r['order_id']}",
            footer=f"{r['business']} · receipt {r['number']}", created=paid)
    d.facts([("Receipt", r["number"]), ("Paid", paid.strftime("%d %b %Y, %H:%M UTC")), ("Amount", f"{_usd(r['amount_usd'])} {r['token']}"),
             ("For", r["offering"]), ("Paid by", r["paid_by"]), ("Order", r["order_id"])])
    d.h2("Payment")
    if r["rail"] == "vault":
        d.facts([("Received by", r["vault"]), ("Network", f"NEAR {r['network']}"), ("Transaction", r["tx_hash"] or "recorded by the vault")], cols=3)
        d.p("The payment went to the business's vault contract on NEAR and is recorded there under this order id: "
            "anyone can check it on a NEAR explorer.", muted=True)
    else:
        d.note("SIMULATED payment: this business has no vault yet, so no money moved on any chain.")
    if r["refunded_usd"]:
        d.h2("Refund")
        d.p(f"{_usd(r['refunded_usd'])} of this payment was refunded.")
    if r["delivered_hash"]:
        d.h2("Delivery")
        d.p("The deliverable's fingerprint, also written to the vault when it was delivered:", muted=True)
        d.mono(f"sha256 {r['delivered_hash']}")
    d.space(10)
    d.p(f"Thank you for your order. This receipt was produced by {r['business']}'s books from the payment record; "
        "no part of it was written by a model.", size=8.5, muted=True)
    return d.render()


# ------------------------------------------------------------------- report
def report(month: Optional[str] = None) -> Dict[str, Any]:
    start, end, label = _month_bounds(month)
    with store.connect() as c:
        pays = [dict(r) for r in c.execute(
            "SELECT direction, rail, counterparty, amount_usd, status, tx_hash, detail, created_at FROM payments"
            " WHERE created_at >= ? AND created_at < ? ORDER BY created_at", (start, end))]
        model = c.execute("SELECT COALESCE(SUM(cost_usd),0), count(*) FROM runs WHERE started_at >= ? AND started_at < ?",
                          (start, end)).fetchone()
        orders = [dict(r) for r in c.execute("SELECT id, offering, amount_usd, status FROM orders"
                                             " WHERE created_at >= ? AND created_at < ?", (start, end))]
    sent = lambda d: [p for p in pays if p["direction"] == d and p["status"] == "sent"]  # noqa: E731
    revenue = sum(p["amount_usd"] for p in sent("in"))
    refunds = sum(p["amount_usd"] for p in sent("refund"))
    shares = sum(p["amount_usd"] for p in sent("split"))
    vendors = sum(p["amount_usd"] for p in sent("out"))
    waiting = sum(p["amount_usd"] for p in pays if p["direction"] == "out" and p["status"] in ("pending_onchain", "submitted"))
    ai = float(model[0] or 0)
    by_offering: Dict[str, Dict[str, Any]] = {}
    for o in orders:
        if o["status"] == "awaiting_payment":
            continue
        b = by_offering.setdefault(o["offering"], {"offering": o["offering"], "orders": 0, "revenue_usd": 0.0})
        b["orders"] += 1
        b["revenue_usd"] += o["amount_usd"]
    by_vendor: Dict[str, float] = {}
    for p in sent("out"):
        by_vendor[p["counterparty"]] = by_vendor.get(p["counterparty"], 0) + p["amount_usd"]
    net = revenue - refunds - shares - vendors - ai
    simulated = any(p["rail"] == "simulated" for p in pays)
    return {
        "month": start[:7], "label": label, "start": start, "end": end,
        "revenue_usd": round(revenue, 2), "refunds_usd": round(refunds, 2), "revenue_shares_usd": round(shares, 2),
        "vendor_spend_usd": round(vendors, 2), "ai_cost_usd": round(ai, 4), "net_usd": round(net, 2),
        "margin_pct": round(100 * net / revenue, 1) if revenue else None,
        "orders_paid": sum(b["orders"] for b in by_offering.values()), "orders_unpaid": sum(1 for o in orders if o["status"] == "awaiting_payment"),
        "runs": int(model[1] or 0), "ai_cost_per_order_usd": round(ai / max(1, sum(b["orders"] for b in by_offering.values())), 4),
        "waiting_out_usd": round(waiting, 2),
        "by_offering": sorted(by_offering.values(), key=lambda b: -b["revenue_usd"]),
        "by_vendor": [{"vendor": k, "paid_usd": round(v, 2)} for k, v in sorted(by_vendor.items(), key=lambda kv: -kv[1])],
        "entries": [{"at": p["created_at"], "direction": p["direction"], "counterparty": p["counterparty"],
                     "amount_usd": p["amount_usd"], "status": p["status"], "rail": p["rail"], "tx": p["tx_hash"]} for p in pays],
        "includes_simulated": simulated,
    }


def report_markdown(r: Dict[str, Any], commentary: str = "", recon: Optional[Dict[str, Any]] = None) -> str:
    """The report as a document. The tables come from `report`; only `commentary` is the agent's."""
    lines = [f"# Monthly report — {r['label']}", "",
             "| | |", "|---|---:|",
             f"| Revenue | {_usd(r['revenue_usd'])} |", f"| Refunds | −{_usd(r['refunds_usd'])} |",
             f"| Revenue shares paid | −{_usd(r['revenue_shares_usd'])} |", f"| Vendors | −{_usd(r['vendor_spend_usd'])} |",
             f"| AI (model) cost | −{_usd(r['ai_cost_usd'])} |", f"| **Net** | **{_usd(r['net_usd'])}** |", "",
             f"Orders paid: {r['orders_paid']} · unpaid checkouts: {r['orders_unpaid']} · team runs: {r['runs']} · "
             f"AI cost per paid order: {_usd(r['ai_cost_per_order_usd'])}"
             + (f" · margin {r['margin_pct']}%" if r["margin_pct"] is not None else ""), ""]
    if r["by_offering"]:
        lines += ["## By offering", "", "| Offering | Orders | Revenue |", "|---|---:|---:|"]
        lines += [f"| {b['offering']} | {b['orders']} | {_usd(b['revenue_usd'])} |" for b in r["by_offering"]] + [""]
    if r["by_vendor"]:
        lines += ["## Vendors paid", "", "| Vendor | Paid |", "|---|---:|"]
        lines += [f"| {v['vendor']} | {_usd(v['paid_usd'])} |" for v in r["by_vendor"]] + [""]
    if recon:
        lines += ["## Reconciliation with the vault", "",
                  f"Result: **{recon['status']}**. " + (recon.get("summary") or ""), ""]
        for d in recon.get("differences") or []:
            lines.append(f"- {d}")
        lines.append("")
    if r["includes_simulated"]:
        lines += ["_Some entries this month are SIMULATED: no money moved for them._", ""]
    if commentary.strip():
        lines += ["## Finance notes", "", commentary.strip(), ""]
    lines += ["_Figures computed by AERA's books from the payment record; the notes above are the Finance agent's._"]
    return "\n".join(lines)


# --------------------------------------------------------------- reconcile
def reconcile() -> Dict[str, Any]:
    """AERA's record against the vault. Without a vault there is nothing on chain to compare."""
    from core import chain
    if not chain.readable():
        return {"status": "not applicable", "summary": "No vault: payments are simulated, so there is nothing on chain to reconcile.",
                "differences": []}
    with store.connect() as c:
        rows = [dict(r) for r in c.execute("SELECT direction, amount_usd, status, tx_hash, detail FROM payments WHERE rail='vault'")]
        local_orders = {r["id"] for r in c.execute("SELECT id FROM orders WHERE paid_tx IS NOT NULL OR status != 'awaiting_payment'")}
    vin = sum(r["amount_usd"] for r in rows if r["direction"] == "in" and r["status"] == "sent")
    vout = sum(r["amount_usd"] for r in rows if r["direction"] in ("out", "refund", "split") and r["status"] == "sent")
    expected = round(vin - vout, 2)
    balance = chain.vault_balance()
    diffs: List[str] = []
    if balance is None:
        return {"status": "unknown", "summary": "The vault did not answer; try again.", "differences": [], "expected_usd": expected}
    if abs(balance - expected) > 0.005:
        gap = round(balance - expected, 2)
        diffs.append(f"Vault balance {_usd(balance)} vs {_usd(expected)} expected from AERA's record "
                     f"({'more' if gap > 0 else 'less'} by {_usd(abs(gap))}): "
                     + ("money arrived that AERA did not record (a deposit, or an order not yet ingested)."
                        if gap > 0 else "money left that AERA did not record, or a recorded payment did not settle."))
    try:
        chain_orders = chain.view("list_orders", {"from_index": 0, "limit": 100}) or []
    except Exception:                                                  # noqa: BLE001
        chain_orders = []
    missing = [o["order_id"] for o in chain_orders if o.get("order_id") not in local_orders]
    if missing:
        diffs.append(f"{len(missing)} order(s) paid on chain but not in AERA's record: {', '.join(missing[:5])}")
    pending = [r for r in rows if r["status"] in ("submitted", "pending_onchain")]
    if pending:
        diffs.append(f"{len(pending)} vault payment(s) still in flight; they settle or fail on the next pass.")
    # Not a difference in money, but a gap in the evidence: the receipt and the books cite the transaction.
    untraced = [r for r in rows if r["direction"] == "in" and r["status"] == "sent" and not r["tx_hash"]]
    notes = ([f"{len(untraced)} payment(s) into the vault have no confirmed transaction yet; the settlement worker "
              "looks them up on the chain on its next passes."] if untraced else [])
    status = "balanced" if not diffs else ("in flight" if diffs and all("in flight" in d for d in diffs) else "differences")
    return {"status": status, "balance_usd": balance, "expected_usd": expected,
            "orders_on_chain": len(chain_orders), "differences": diffs, "notes": notes,
            "summary": (f"The vault holds {_usd(balance)}, exactly what AERA's record says it should." if not diffs
                        else f"The vault holds {_usd(balance)}; AERA's record expects {_usd(expected)}.")}


def demo() -> None:
    from core import business
    store.save_profile(business.EXAMPLE, by="check")
    store.create_order("ord_abc123", "brief", 15, {"industry": "coffee"}, customer="ana.testnet", status="awaiting_payment")
    assert receipt_data("ord_abc123") is None, "no receipt before payment"
    store.record_payment("in", "simulated", "ana.testnet", 15, "usdc", "sent", detail={"order_id": "ord_abc123"})
    store.update_order("ord_abc123", status="paid")
    r = receipt_data("ord_abc123")
    assert r and r["number"] == "R-ABC123" and r["amount_usd"] == 15 and r["rail"] == "simulated", r
    pdf = receipt_pdf("ord_abc123")
    assert pdf and pdf.startswith(b"%PDF") and pdf == receipt_pdf("ord_abc123"), "the same bytes every time"
    store.record_payment("out", "simulated", "dataco.testnet", 3, "usdc", "sent")
    store.record_payment("out", "simulated", "dataco.testnet", 2, "usdc", "pending_onchain")
    rep = report()
    assert rep["revenue_usd"] == 15 and rep["vendor_spend_usd"] == 3 and rep["waiting_out_usd"] == 2, rep
    assert rep["net_usd"] == 12 and rep["orders_paid"] == 1 and rep["by_vendor"][0]["vendor"] == "dataco.testnet"
    md = report_markdown(rep, "Data spend was one purchase.", reconcile())
    assert "| **Net** | **$12.00** |" in md and "Finance notes" in md and "not applicable" in md
    assert _month_bounds("2026-12")[1].startswith("2027-01-01")
    print("finance ok: receipt only once paid, same bytes every time ✓ · report adds up ✓ · reconcile without a vault says so ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_FINANCE_CHECK")
    demo()
