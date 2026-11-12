"""How autonomous the business is, and whether each order pays for itself.

Every number here is counted in code from the record: work items, runs, actions, the approvals a person
gave, payments and orders. Nothing is estimated by a model.

    autonomy(days)          of the work that finished, how much needed no person at all, and what the
                            people who did step in were asked to do
    unit_economics(days)    per order: revenue, the AI it took, the margin; per offering: the price below
                            which an order no longer pays for itself; overhead (vendors, goals, requests)
    overview(days)          both, for the API and the dashboard
    markdown(o, commentary) the same as a document: figures from code, the agent's commentary only

A "touch" is a person doing something the team could not: approving or rejecting an action, or running
work again after it stopped. What the Guardian blocked is not a touch: no person was needed for it.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core import store

#: Margin an offering should keep after the AI it takes, unless the profile sets limits.target_margin_pct.
DEFAULT_TARGET_MARGIN = 0.6


def _since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _hours(a: Optional[str], b: Optional[str]) -> Optional[float]:
    try:
        return round((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 3600, 2)
    except (TypeError, ValueError):
        return None


def _work(days: int) -> List[Dict[str, Any]]:
    """Each work item received in the window, with its runs, actions and the people who decided them."""
    since = _since(days)
    with store.connect() as c:
        items = [dict(r) for r in c.execute(
            "SELECT id, kind, title, status, received_at FROM work_items WHERE received_at >= ? ORDER BY received_at",
            (since,))]
        runs = [dict(r) for r in c.execute(
            "SELECT id, work_item_id, status, cost_usd, started_at, finished_at FROM runs WHERE started_at >= ?", (since,))]
        actions = [dict(r) for r in c.execute(
            "SELECT id, run_id, kind, status, autonomous, value_usd FROM actions WHERE created_at >= ?", (since,))]
        approvals = [dict(r) for r in c.execute(
            "SELECT action_id, decided_by, role, decision, at FROM approvals WHERE at >= ?", (since,))]
    by_item: Dict[str, List[dict]] = {}
    for r in runs:
        by_item.setdefault(r["work_item_id"], []).append(r)
    by_run: Dict[str, List[dict]] = {}
    for a in actions:
        by_run.setdefault(a["run_id"], []).append(a)
    decided: Dict[str, List[dict]] = {}
    for d in approvals:
        decided.setdefault(d["action_id"], []).append(d)
    out = []
    for it in items:
        its_runs = sorted(by_item.get(it["id"], []), key=lambda r: r["started_at"])
        its_actions = [a for r in its_runs for a in by_run.get(r["id"], [])]
        people = [d for a in its_actions for d in decided.get(a["id"], [])]
        out.append({**it, "runs": its_runs, "actions": its_actions, "decisions": people,
                    "retries": max(0, len(its_runs) - 1),
                    "stopped_runs": sum(1 for r in its_runs if r["status"] in ("partial", "held", "failed")),
                    "ai_usd": round(sum(float(r["cost_usd"] or 0) for r in its_runs), 4)})
    return out


def autonomy(days: int = 30) -> Dict[str, Any]:
    work = _work(days)
    finished = [w for w in work if w["status"] in ("done", "failed")]
    alone = [w for w in finished if w["status"] == "done" and not w["decisions"] and not w["retries"]]
    touches: Dict[str, int] = {}
    for w in work:
        for d in w["decisions"]:
            a = next((x for x in w["actions"] if x["id"] == d["action_id"]), {})
            kind = a.get("kind", "action").replace("_", " ")
            key = f"{d['decision']} {'an' if kind[0] in 'aeiou' else 'a'} {kind}"
            touches[key] = touches.get(key, 0) + 1
        if w["retries"]:
            touches["ran stopped work again"] = touches.get("ran stopped work again", 0) + w["retries"]
    actions = [a for w in work for a in w["actions"]]
    by_people = {d["action_id"] for w in work for d in w["decisions"]}
    went = [a for a in actions if a["status"] in ("sent", "approved")]
    blocked = [a for a in actions if a["status"] == "blocked"]
    waiting = [w for w in work if w["status"] in ("held", "running", "received")]
    return {
        "days": days,
        "work_items": len(work),
        "finished": len(finished),
        "done_alone": len(alone),
        "autonomy_pct": round(100 * len(alone) / len(finished), 1) if finished else None,
        "people_touches": sum(touches.values()),
        "touches": [{"what": k, "count": v} for k, v in sorted(touches.items(), key=lambda kv: -kv[1])],
        "actions_carried_out": len(went),
        "actions_carried_out_alone": sum(1 for a in went if a["id"] not in by_people),
        "stopped_by_guardian": len(blocked),
        "waiting": [{"id": w["id"], "title": w["title"], "status": w["status"]} for w in waiting],
        "by_kind": _by_kind(work),
    }


def _by_kind(work: List[dict]) -> List[Dict[str, Any]]:
    kinds: Dict[str, Dict[str, Any]] = {}
    for w in work:
        k = kinds.setdefault(w["kind"], {"kind": w["kind"], "items": 0, "done_alone": 0, "touched": 0, "open": 0})
        k["items"] += 1
        if w["status"] == "done" and not w["decisions"] and not w["retries"]:
            k["done_alone"] += 1
        elif w["status"] in ("done", "failed"):
            k["touched"] += 1
        else:
            k["open"] += 1
    return sorted(kinds.values(), key=lambda k: -k["items"])


def unit_economics(days: int = 30, target_margin: Optional[float] = None) -> Dict[str, Any]:
    from core import business
    profile = business.current()
    if target_margin is None:
        pct = (profile.get("limits") or {}).get("target_margin_pct")
        target_margin = float(pct) / 100 if isinstance(pct, (int, float)) and 0 < pct < 100 else DEFAULT_TARGET_MARGIN
    since = _since(days)
    work = {w["id"]: w for w in _work(days)}
    with store.connect() as c:
        orders = [dict(r) for r in c.execute(
            "SELECT id, offering, amount_usd, status, work_item_id, paid_tx, delivery, created_at, updated_at FROM orders"
            " WHERE created_at >= ? AND status != 'awaiting_payment' ORDER BY created_at", (since,))]
        pays = [dict(r) for r in c.execute(
            "SELECT direction, amount_usd, status, detail, counterparty FROM payments WHERE created_at >= ?", (since,))]
        # When the order went out: the deliver_order action that was carried out (orders.updated_at moves on
        # later writes, such as a transaction found afterwards, so it is not a delivery time).
        delivered_at = {o["id"]: (c.execute("SELECT MAX(created_at) FROM actions WHERE kind='deliver_order'"
                                            " AND status='sent' AND payload LIKE ?", (f'%"{o["id"]}"%',)).fetchone()[0])
                        for o in orders}
    refunds: Dict[str, float] = {}
    for p in pays:
        if p["direction"] == "refund" and p["status"] == "sent":
            oid = (json.loads(p["detail"] or "{}") or {}).get("order_id")
            if oid:
                refunds[oid] = refunds.get(oid, 0) + p["amount_usd"]
    rows = []
    for o in orders:
        w = work.get(o["work_item_id"] or "", {})
        revenue = o["amount_usd"] - refunds.get(o["id"], 0)
        ai = float(w.get("ai_usd") or 0)
        rows.append({
            "order": o["id"], "offering": o["offering"], "status": o["status"], "revenue_usd": round(revenue, 2),
            "ai_usd": round(ai, 4), "margin_usd": round(revenue - ai, 2),
            "margin_pct": round(100 * (revenue - ai) / revenue, 1) if revenue else None,
            "people_touches": len(w.get("decisions") or []) + int(w.get("retries") or 0),
            "hours_to_deliver": _hours(o["created_at"], delivered_at.get(o["id"])),
        })
    prices = {x.get("id"): float(x.get("price_usd") or 0) for x in profile.get("offerings", [])}
    offerings = []
    for oid in sorted({r["offering"] for r in rows} | set(prices)):
        mine = [r for r in rows if r["offering"] == oid]
        ai_each = statistics.mean(r["ai_usd"] for r in mine) if mine else None
        floor = round(ai_each / (1 - target_margin), 2) if ai_each is not None else None
        price = prices.get(oid)
        offerings.append({
            "offering": oid, "price_usd": price, "orders": len(mine),
            "ai_per_order_usd": round(ai_each, 4) if ai_each is not None else None,
            "floor_price_usd": floor,
            "below_target": bool(price is not None and floor is not None and price < floor),
        })
    order_items = {o["work_item_id"] for o in orders}
    overhead_ai = sum(w["ai_usd"] for wid, w in work.items() if wid not in order_items)
    vendors = sum(p["amount_usd"] for p in pays if p["direction"] == "out" and p["status"] == "sent")
    revenue = sum(r["revenue_usd"] for r in rows)
    direct = sum(r["ai_usd"] for r in rows)
    return {
        "days": days, "target_margin_pct": round(100 * target_margin, 1),
        "orders": rows, "offerings": offerings,
        "revenue_usd": round(revenue, 2), "direct_ai_usd": round(direct, 4),
        "gross_margin_pct": round(100 * (revenue - direct) / revenue, 1) if revenue else None,
        "overhead": {"vendors_usd": round(vendors, 2), "ai_usd": round(overhead_ai, 4),
                     "note": "AI for goals and requests that were not an order, and what the team bought"},
        "net_usd": round(revenue - direct - overhead_ai - vendors, 2),
    }


def growth(days: int = 30) -> Dict[str, Any]:
    """Each published sample: how often it was read, the orders it started, the orders paid."""
    since = _since(days)
    sources = store.order_sources()
    with store.connect() as c:
        orders = {r["id"]: dict(r) for r in c.execute("SELECT id, status, amount_usd FROM orders WHERE created_at >= ?", (since,))}
    rows = []
    for s in store.list_samples(include_unpublished=True):
        mine = [orders[o] for o, src in sources.items() if src == f"sample:{s['slug']}" and o in orders]
        paid = [o for o in mine if o["status"] != "awaiting_payment"]
        rows.append({"slug": s["slug"], "title": s["title"], "offering": s["offering"], "views": s["views"],
                     "published_at": s["published_at"], "live": s["unpublished_at"] is None,
                     "checkouts": len(mine), "paid": len(paid), "revenue_usd": round(sum(o["amount_usd"] for o in paid), 2)})
    views = sum(r["views"] for r in rows)
    paid = sum(r["paid"] for r in rows)
    return {"samples": rows, "views": views, "checkouts": sum(r["checkouts"] for r in rows), "paid": paid,
            "revenue_usd": round(sum(r["revenue_usd"] for r in rows), 2),
            "paid_per_100_views": round(100 * paid / views, 1) if views else None}


def overview(days: int = 30) -> Dict[str, Any]:
    return {"autonomy": autonomy(days), "economics": unit_economics(days), "growth": growth(days)}


def _usd(x: Optional[float], places: int = 2) -> str:
    return "—" if x is None else f"${x:,.{places}f}"


def markdown(o: Dict[str, Any], commentary: str = "", name: str = "") -> str:
    a, e = o["autonomy"], o["economics"]
    lines = [f"# Autonomy and unit economics{' — ' + name if name else ''}",
             f"Last {a['days']} days · filed {datetime.now(timezone.utc).date().isoformat()} · figures counted in code",
             "", "## How much ran without a person", "",
             f"- Work finished: **{a['finished']}** of {a['work_items']} received; "
             f"done with no person at all: **{a['done_alone']}**"
             + (f" (**{a['autonomy_pct']}%**)" if a["autonomy_pct"] is not None else ""),
             f"- Times a person stepped in: **{a['people_touches']}**"
             + ("".join(f"\n  - {t['what']}: {t['count']}" for t in a["touches"]) if a["touches"] else ""),
             f"- Actions carried out: {a['actions_carried_out']}, of which {a['actions_carried_out_alone']} without a person",
             f"- Stopped by the Guardian (no person needed): {a['stopped_by_guardian']}",
             "", "## Does each order pay for itself", "",
             "| Order | Offering | Revenue | AI | Margin | Touches | Hours to deliver |", "|---|---|---|---|---|---|---|"]
    for r in e["orders"]:
        lines.append(f"| {r['order']} | {r['offering']} | {_usd(r['revenue_usd'])} | {_usd(r['ai_usd'], 3)} | "
                     f"{'—' if r['margin_pct'] is None else str(r['margin_pct']) + '%'} | {r['people_touches']} | "
                     f"{'—' if r['hours_to_deliver'] is None else r['hours_to_deliver']} |")
    if not e["orders"]:
        lines.append("| (no paid orders in this window) | | | | | | |")
    lines += ["", f"Target margin after AI: {e['target_margin_pct']}%.", "",
              "| Offering | Price | Orders | AI per order | Floor price | |", "|---|---|---|---|---|---|"]
    for f in e["offerings"]:
        lines.append(f"| {f['offering']} | {_usd(f['price_usd'])} | {f['orders']} | {_usd(f['ai_per_order_usd'], 3)} | "
                     f"{_usd(f['floor_price_usd'])} | {'below target' if f['below_target'] else ''} |")
    g = o.get("growth") or {"samples": []}
    if g["samples"]:
        lines += ["", "## Customers the samples brought", "", "| Sample | Read | Checkouts | Paid | Revenue |", "|---|---|---|---|---|"]
        lines += [f"| {r['title']} | {r['views']} | {r['checkouts']} | {r['paid']} | {_usd(r['revenue_usd'])} |" for r in g["samples"]]
    oh = e["overhead"]
    lines += ["", f"Overhead: vendors {_usd(oh['vendors_usd'])}, AI outside orders {_usd(oh['ai_usd'], 3)}. "
              f"Revenue {_usd(e['revenue_usd'])} → net {_usd(e['net_usd'])}."]
    if commentary.strip():
        lines += ["", "## Commentary", "", commentary.strip()]
    return "\n".join(lines) + "\n"


def demo() -> None:
    from core import business
    store.save_profile(business.EXAMPLE, by="check")
    before = autonomy(30)
    seen = {t["what"]: t["count"] for t in before["touches"]}
    # an order the team handled alone
    store.create_order("ord_e1", "brief", 15.0, {}, customer="a.testnet")
    w1 = store.record_work_item("order", "Order ord_e1", "simulated", {"order_id": "ord_e1"})
    with store.connect() as c:
        c.execute("UPDATE orders SET status='delivered', work_item_id=? WHERE id='ord_e1'", (w1,))
    r1 = store.start_run(w1)
    store.close_run(r1, "done", {"status": "done"}, cost_usd=0.30)
    store.set_work_status(w1, "done")
    # a request that needed a person twice: one approval, one run again
    w2 = store.record_work_item("request", "Buy data", "api", {})
    r2a = store.start_run(w2)
    store.close_run(r2a, "partial", {"status": "partial"}, cost_usd=0.10)
    r2b = store.start_run(w2)
    from core import registry
    from core.actions import raise_action
    with registry.bind_run(r2b):
        act = raise_action("payment", {"receiver": f"v{w2[-6:]}.testnet", "amount_usd": 8}, {"verdict": "warn", "reasons": []},
                           value_usd=8, execute=False).value
    store.decide_action(act["id"], "owner@x", "owner", "approved")
    store.close_run(r2b, "done", {"status": "done"}, cost_usd=0.05)
    store.set_work_status(w2, "done")

    a = autonomy(30)
    assert a["finished"] - before["finished"] == 2 and a["done_alone"] - before["done_alone"] == 1, a
    mine = {t["what"]: t["count"] for t in a["touches"]}
    assert mine.get("approved a payment", 0) - seen.get("approved a payment", 0) == 1, mine
    assert mine.get("ran stopped work again", 0) - seen.get("ran stopped work again", 0) == 1, mine
    e = unit_economics(30, target_margin=0.6)
    row = next(r for r in e["orders"] if r["order"] == "ord_e1")
    assert row["revenue_usd"] == 15.0 and row["ai_usd"] == 0.3 and row["margin_pct"] == 98.0 and row["people_touches"] == 0
    brief = next(f for f in e["offerings"] if f["offering"] == "brief")
    assert brief["floor_price_usd"] == 0.75 and not brief["below_target"], brief
    assert e["overhead"]["ai_usd"] >= 0.15, "the request's AI is overhead, not an order's"
    store.publish_sample("vn-coffee", "fil_x", "VN coffee", "", "brief", "text", None)
    store.get_sample("vn-coffee", count_view=True)
    store.create_order("ord_g1", "brief", 15.0, {}, customer="b.testnet", status="paid")
    store.record_order_source("ord_g1", "sample:vn-coffee")
    g = growth(30)
    vn = next(r for r in g["samples"] if r["slug"] == "vn-coffee")
    assert vn["views"] == 1 and vn["checkouts"] == 1 and vn["paid"] == 1 and vn["revenue_usd"] == 15.0, vn
    md = markdown(overview(30), "Steady.")
    assert "Customers the samples brought" in md
    assert "ord_e1" in md and "approved a payment: " in md and "## Commentary" in md
    print(f"economics ok: autonomy {a['autonomy_pct']}% · touches named ✓ · margin and floor price in code ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_ECONOMICS_CHECK")
    demo()
