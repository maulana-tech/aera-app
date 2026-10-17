"""Per-domain table views.

Each domain page needs its own table. This file arranges tools that already
exist into a shape that displays well, it adds no new data source, so origin
labels flow through untouched.

Views are keyed by agent code, so a page and the specialist who owns it can
never drift apart.
"""
from __future__ import annotations

import json
from datetime import date
from typing import List

from core.provenance import Origin, Result
from engine.simulate import project_cover
from tools.compliance import check_local_constraints
from tools.fetcher import fixture, profile
from tools.impact import (get_bom_explosion, get_material_stock,
                          get_open_purchase_orders, get_sales_order_commitments)
from tools.logistics import estimate_eta
from tools.procurement import (compare_quotations, get_quotations,
                               get_supplier_master, get_supplier_performance)
from tools.sourcing import find_alternate_sources

# Display constants. `floor_days` is documented as 14 in both tools that take it
# and is what the dashboard already draws its threshold at; a view that charted
# a different number would be arguing with the rest of the system.
SAFETY_FLOOR_DAYS = 14

# A view's table can carry fifty rows. A chart of fifty bars is a smear, so each
# chart draws the lines that answer its question and the caption says how many
# of the total were left out.
CHART_LINES = 12


def _wrap(rows: List[dict], columns: List[dict], r: Result, note: str = "") -> dict:
    return {
        "columns": columns,
        "rows": rows,
        "origin": r.origin.value,
        "source": r.source,
        "note": note or r.note,
    }


def inventory() -> dict:
    r = get_material_stock()
    p = profile()
    start = date.fromisoformat(p["AsOfDate"])
    rows = []
    for x in (r.value or []):
        qty = x.get("MatlWrhsStkQtyInMatlBaseUnit", 0)
        daily = x.get("DailyConsumption", 0)
        cover = project_cover(float(qty), float(daily), start)
        rows.append({
            "material": x.get("Material"),
            "description": x.get("Description"),
            "plant": x.get("Plant"),
            "qty": qty,
            "unit": x.get("BaseUnit"),
            "daily_consumption": daily,
            "depleted_on": cover.depleted_on.isoformat() if cover.depleted_on else None,
            "days_left": round(float(qty) / float(daily), 1) if daily else None,
        })
    rows.sort(key=lambda b: b["days_left"] if b["days_left"] is not None else 9999)
    out = _wrap(rows, [
        {"k": "material", "l": "Material"}, {"k": "description", "l": "Name"},
        {"k": "plant", "l": "Plant"}, {"k": "qty", "l": "Quantity", "n": True},
        {"k": "daily_consumption", "l": "Used/day", "n": True},
        {"k": "days_left", "l": "Days left", "n": True},
        {"k": "depleted_on", "l": "Depleted"},
    ], r)
    # Already sorted by cover ascending, so the first lines are the ones that
    # empty first and the chart needs no ordering of its own. A line with no
    # consumption has no cover to draw; it stays in the table where the blank
    # is meaningful.
    tightest = [x for x in rows if x["days_left"] is not None][:CHART_LINES]
    if tightest:
        out["chart"] = {
            "kind": "cover",
            "unit": "days",
            "total": len(rows),
            "threshold": SAFETY_FLOOR_DAYS,
            "threshold_label": f"{SAFETY_FLOOR_DAYS}-day safety floor",
            "items": [{
                "material": x["material"], "plant": x["plant"],
                "description": x["description"], "days": x["days_left"],
                "qty": x["qty"], "unit": x["unit"],
                "daily": x["daily_consumption"], "depleted_on": x["depleted_on"],
            } for x in tightest],
        }
    return out


def demand() -> dict:
    """Planned rate against forecast rate, which is the gap Demand exists to find."""
    from tools.demand import forecast_demand

    r = get_material_stock()
    rows = []
    for x in (r.value or []):
        f = forecast_demand(x["Material"], x["Plant"]).value or {}
        drift = f.get("drift_pct")
        rows.append({
            "material": x.get("Material"), "plant": x.get("Plant"),
            "planned": x.get("DailyConsumption"),
            "observed": f.get("observed_rate"),
            "forecast": f.get("mean_rate"),
            "drift_pct": drift,
            "unit": x.get("BaseUnit"),
            "stale": drift is not None and abs(drift) >= 5,
        })
    rows.sort(key=lambda b: -(abs(b["drift_pct"]) if b["drift_pct"] is not None else -1))

    drifting = [b for b in rows if b["stale"]]
    note = ("Every cover date in this system divides stock by the planned rate. "
            f"{len(drifting)} of {len(rows)} material and plant pairs ran at least 5% "
            "away from it over the last 28 days, so those cover dates are wrong. Drift "
            "compares what was actually withdrawn against the plan; the last column is "
            "where the forecast expects it to go next.")

    # The flagship material carries the chart, because its drift moves the answer.
    lead = forecast_demand("M-4471", "KRW1").value or {}
    # Daily withdrawals swing between a full shift and a Sunday, and that swing
    # buries the question the chart is asked: is the rate above plan. A trailing
    # weekly mean answers it, and the daily series stays as context behind it.
    raw = _recent_history("M-4471", "KRW1", 35)
    points = lead.get("points", [])

    def trailing(values, i, n=7):
        window = values[max(0, i - n + 1):i + 1]
        return round(sum(window) / len(window), 2)

    # One window across both halves. Smoothing only the left side would put a
    # weekly mean and a daily figure on the same axis, which is two quantities
    # wearing one scale.
    daily = [q for _, q in raw] + [p["point"] for p in points]
    lows = [q for _, q in raw] + [p["lower"] for p in points]
    highs = [q for _, q in raw] + [p["upper"] for p in points]

    history = [{"on": day.isoformat(), "qty": round(q, 2),
                "mean": trailing(daily, i)}
               for i, (day, q) in enumerate(raw)][-28:]
    smoothed = [{**p,
                 "point": trailing(daily, len(raw) + i),
                 "lower": trailing(lows, len(raw) + i),
                 "upper": trailing(highs, len(raw) + i)}
                for i, p in enumerate(points)]
    out = _wrap(rows, [
        {"k": "material", "l": "Material"}, {"k": "plant", "l": "Plant"},
        {"k": "planned", "l": "Planned/day", "n": True},
        {"k": "observed", "l": "Last 28d", "n": True},
        {"k": "drift_pct", "l": "Drift %", "n": True},
        {"k": "forecast", "l": "Next 30d", "n": True},
    ], r, note)
    if lead.get("points"):
        out["chart"] = {
            "kind": "demand",
            "material": "M-4471", "plant": "KRW1",
            "unit": lead.get("unit", ""), "confidence": lead.get("confidence", 90),
            "planned_rate": lead.get("planned_rate"),
            "observed": history, "points": smoothed,
            "window_days": 7,
            "mape_pct": lead.get("mape_pct"),
        }
    return out


def _recent_history(material: str, plant: str, days: int):
    from tools.demand import _history
    return _history(material, plant)[-days:]


def sourcing() -> dict:
    from datetime import date as _date

    from engine.matching import assess
    from tools.impact import get_material_stock

    r = find_alternate_sources("M-4471")
    stock = get_material_stock()
    start = _date.fromisoformat(profile()["AsOfDate"])
    rows = []
    for o in (r.value or []):
        v = (check_local_constraints(o["id"]).value or {})
        donor = None
        # An internal option moves stock out of a plant that is also using it.
        # Compliance does not look at that, so it has to be checked here.
        if o.get("Supplier") == "INTERNAL" and stock.value:
            source_plant = next((p for p in {x["Plant"] for x in stock.value}
                                 if p in o["label"]), None)
            if source_plant:
                t = assess(stock.value, o["Material"], source_plant, "KRW1",
                           float(o["Quantity"]), start)
                donor = t.verdict if t.verdict != "available" else None
        rows.append({
            "id": o["id"], "label": o["label"], "supplier": o["Supplier"],
            "qty": o["Quantity"], "arrives": o["ArrivalDate"],
            "cost_idr": o["ExtraCostIDR"], "tkdn": o.get("TkdnAfterPct"),
            "origin_country": o["Origin"],
            "allowed": v.get("allowed"), "reason": v.get("reason"),
            "donor_impact": donor,
        })
    return _wrap(rows, [
        {"k": "id", "l": "#"}, {"k": "label", "l": "Option"},
        {"k": "arrives", "l": "Arrives"}, {"k": "cost_idr", "l": "Extra cost", "rp": True},
        {"k": "tkdn", "l": "TKDN", "n": True}, {"k": "allowed", "l": "Clears rules"},
        {"k": "donor_impact", "l": "Donor plant"},
    ], r, "Clearing the rules is not the same as being available. An internal transfer "
          "also has to leave the plant it came from above its own floor.")


def _procurement_book() -> dict:
    """The supplier book, and what its shape says.

    Concentration is the question no other domain asks. Sourcing reads the
    options for one material, Impact traces lines through a bill of materials,
    Vega counts single sources — none of them will tell you how few suppliers
    carry most of what is bought, which is the fact a portfolio exists to show.
    """
    master = get_supplier_master()
    if not master.value:
        out = _wrap([], [], master, master.note or "no supplier master to read")
        out["title"] = "The supplier book, and who carries it"
        return out

    # Both tools read the same master, so the join cannot disagree with itself
    # about which code belongs to which company.
    perf = {r["supplier"]: r for r in (get_supplier_performance().value or [])}
    floor = profile().get("TkdnContractFloorPct")

    rows = [{
        "name": s.get("name"), "country": s.get("country"),
        "orders": s.get("orders", 0), "share": s.get("share_pct"),
        "late": (perf.get(s["supplier"]) or {}).get("late"),
        "slip": (perf.get(s["supplier"]) or {}).get("avg_slip_days"),
        "tkdn": s.get("tkdn_certified_pct"),
        # Shaded because it is worth noticing, not because it is at fault: a
        # certified supplier with no orders is capacity the book is not using.
        "flagged": not s.get("orders"),
    } for s in master.value]

    def certified(r, at_or_above: bool) -> bool:
        if r["tkdn"] is None or floor is None:
            return False
        return r["tkdn"] >= floor if at_or_above else r["tkdn"] < floor

    unused = [r for r in rows if r["flagged"]]
    below_used = [r for r in rows if r["orders"] and certified(r, False)]
    dups = [s for s in master.value if s.get("duplicate_of")]

    if not unused:
        note = f"{len(rows)} suppliers on the approved list, all of them holding orders"
    else:
        note = (f"{len(rows)} suppliers on the approved list, {len(unused)} of them "
                f"holding no orders")
        names = ", ".join(str(r["name"]) for r in unused)
        if all(certified(r, True) for r in unused):
            note += (f". All {len(unused)} — {names} — are certified at or above the "
                     f"{floor:g}% contract floor")
            if below_used:
                note += (f", while the {len(below_used)} certified below it carry "
                         f"{sum(r['share'] for r in below_used):.0f}% of the book")
            note += "."
        else:
            note += f": {names}."
    if dups:
        note += (" " + "; ".join(
            f"{d['name']} appears twice, as {d['supplier']} and {d['duplicate_of']}"
            for d in dups) + ".")

    out = _wrap(rows, [
        {"k": "name", "l": "Supplier"}, {"k": "country", "l": "Origin"},
        {"k": "orders", "l": "Orders", "n": True},
        {"k": "share", "l": "Share %", "n": True},
        {"k": "late", "l": "Late", "n": True},
        {"k": "slip", "l": "Avg slip (d)", "n": True},
        {"k": "tkdn", "l": "TKDN cert %", "n": True},
    ], master, note)
    out["title"] = "The supplier book, and who carries it"

    # The chart carries the suppliers that hold orders. One with none is a bar
    # of zero and a cumulative line it does not move, which is the table's job.
    active = [s for s in master.value if s.get("orders")]
    if not active:
        return out

    rule_pct = 80
    marks, running = [], 0.0
    for s in active:
        running += float(s.get("share_pct") or 0)
        p = perf.get(s["supplier"]) or {}
        marks.append({
            "supplier": s["supplier"], "name": s.get("name"),
            "country": s.get("country"),
            "share": s.get("share_pct") or 0,
            "cumulative": round(running, 2),
            "volume": s.get("volume"), "unit": s.get("unit"),
            "orders": s.get("orders"), "late": p.get("late", 0),
            "slip": p.get("avg_slip_days"),
            "tkdn": s.get("tkdn_certified_pct"),
        })

    # How many suppliers it takes to make four fifths of the book. That count
    # is the whole question a concentration chart is asked.
    cover_n = next((i + 1 for i, m in enumerate(marks)
                    if m["cumulative"] >= rule_pct), len(marks))
    out["chart"] = {
        "kind": "portfolio",
        "total": len(rows),
        "active": len(active),
        "rule_pct": rule_pct,
        "cover_n": cover_n,
        "items": marks[:CHART_LINES],
    }
    return out


def _procurement_offers() -> dict:
    """What the quotations say on the material carrying the most committed value.

    The material is not chosen by hand. It is the one with the most money
    already committed against open purchase orders, priced off the very
    quotations the comparison then ranks, so the desk leads with a live
    decision rather than with whichever material sorts first. Every figure
    here comes from two tools: the purchase-order lines for the volume, the
    quotation book for the price.
    """
    title = "Vendor offers, price against lead time"

    def empty(r, why) -> dict:
        out = _wrap([], [], r, why)
        out["title"] = title
        return out

    orders = get_open_purchase_orders()
    quotes = get_quotations()
    if not orders.value:
        return empty(orders, orders.note or
                     "no open purchase orders, so there is no volume to price an offer against")
    if not quotes.value:
        return empty(quotes, quotes.note or "no quotations on file to compare")

    # The incumbent's own quote when it is still valid, the cheapest live one
    # when it is not. Committed value is what the company would pay today, not
    # what it paid on the order it placed.
    live_cheapest: dict = {}
    for q in quotes.value:
        if q["live"]:
            m = q["material"]
            live_cheapest[m] = min(live_cheapest.get(m, q["unit_price"]), q["unit_price"])
    own_quote = {(q["material"], q["supplier"]): q for q in quotes.value if q["live"]}

    committed, volume, unit_of = {}, {}, {}
    for o in orders.value:
        m = o.get("Material")
        if m not in live_cheapest:
            continue                       # nothing live to rank, so nothing to show
        hit = own_quote.get((m, o.get("Supplier")))
        price = hit["unit_price"] if hit else live_cheapest[m]
        qty = float(o.get("OrderQuantity") or 0)
        committed[m] = committed.get(m, 0.0) + price * qty
        volume[m] = volume.get(m, 0.0) + qty
        unit_of[m] = o.get("BaseUnit")

    if not committed:
        return empty(quotes, "no material still has a live offer, so there is nothing to rank")

    material = max(committed, key=lambda m: committed[m])
    qty = volume[material]
    unit = unit_of.get(material) or ""
    r = compare_quotations(material, qty)
    rows = r.value or []
    note = (f"Rp {committed[material]:,.0f} committed on {material}, the largest value on "
            f"the book, priced at the {qty:g} {unit} already on order. " + (r.note or ""))

    out = _wrap(rows, [
        {"k": "rank", "l": "Rank", "n": True},
        {"k": "name", "l": "Supplier"},
        {"k": "country", "l": "Origin"},
        {"k": "unit_price", "l": f"Rp per {unit}", "rp": True},
        {"k": "lead_days", "l": "Lead (d)", "n": True},
        {"k": "total", "l": f"Total for {qty:g} {unit}", "rp": True},
        {"k": "tkdn", "l": "TKDN cert %", "n": True},
        {"k": "valid_to", "l": "Valid to"},
        {"k": "live", "l": "Live"},
        {"k": "on_line", "l": "Trade-off line"},
    ], r, note)
    out["title"] = title
    out["chart"] = {
        "kind": "offers",
        "material": material,
        "unit": unit,
        "qty": qty,
        "live": sum(1 for x in rows if x["live"]),
        "total": len(rows),
        "points": [{
            "supplier": x["supplier"], "name": x["name"], "country": x["country"],
            "price": x["unit_price"], "lead": x["lead_days"],
            "live": x["live"], "on_line": x["on_line"],
            "tkdn": x["tkdn"],
        } for x in rows],
    }
    return out


def procurement() -> dict:
    """Prita's desk, in the order her work runs: what the quotes say, then the book.

    Her brief is to receive a signal, compare the vendors on price against lead
    time, and raise the draft that follows. So the comparison leads — it is the
    live decision — and the portfolio sits behind it, because how concentrated
    the book is decides how much freedom there is to choose at all.

    A view may return a list of these as `sections`, each one chart and table
    under its own heading. Domains with a single question still return one flat
    view, and the page renders both shapes.
    """
    return {"sections": [_procurement_offers(), _procurement_book()]}


def compliance() -> dict:
    """Kira's rulings. The one view where the reason matters more than the number."""
    r = find_alternate_sources("M-4471")
    p = profile()
    rows = []
    for o in (r.value or []):
        v = check_local_constraints(o["id"]).value or {}
        tkdn = o.get("TkdnAfterPct")
        rows.append({
            "id": o["id"], "option": o["label"],
            "allowed": v.get("allowed"),
            "reason": v.get("reason"),
            "tkdn_before": p["TkdnCurrentPct"],
            "tkdn_after": tkdn,
            "tkdn_floor": p["TkdnContractFloorPct"],
            "cost_idr": o["ExtraCostIDR"],
            "arrival_booked": o["ArrivalDate"],
            "arrival_effective": v.get("arrival_effective"),
            "origin_country": o["Origin"],
            "new_origin": bool(o.get("NewOrigin")),
        })
    blocked = [x for x in rows if x["allowed"] is False]
    allowed = [x for x in rows if x["allowed"]]
    note = f"{len(blocked)} of {len(rows)} options blocked on the rules, not on price."
    # The line worth making is when a blocked option undercuts an allowed one,
    # because that is exactly the trade a pure cost model would take.
    if blocked and allowed:
        cheapest_blocked = min(blocked, key=lambda x: x["cost_idr"])
        dearest_beaten = [a for a in allowed if a["cost_idr"] > cheapest_blocked["cost_idr"]]
        if dearest_beaten:
            note += (f" {cheapest_blocked['option']} costs Rp {cheapest_blocked['cost_idr']:,}"
                     f" and is still out, while {min(dearest_beaten, key=lambda x: x['cost_idr'])['option']}"
                     f" at Rp {min(dearest_beaten, key=lambda x: x['cost_idr'])['cost_idr']:,} is allowed."
                     " Cost does not overturn a rule.")
    return _wrap(rows, [
        {"k": "id", "l": "#"}, {"k": "option", "l": "Option"},
        {"k": "tkdn_after", "l": "TKDN after", "n": True},
        {"k": "cost_idr", "l": "Cost", "rp": True},
        {"k": "allowed", "l": "Allowed"}, {"k": "reason", "l": "Reason"},
    ], r, note)


def impact() -> dict:
    """Elsa's trace: a disruption followed through to the money at risk."""
    po = get_open_purchase_orders(port="CNNGB")
    stock = get_material_stock()
    bom = get_bom_explosion("M-4471")
    finished = [x["FinishedGood"] for x in (bom.value or [])]
    orders = get_sales_order_commitments(finished)
    exposed = sum(x["NetAmount"] for x in (orders.value or []))

    rows = [{
        "stage": "Purchase orders through Ningbo",
        "count": len(po.value or []),
        "detail": ", ".join(x["PurchaseOrder"] for x in (po.value or [])[:4]),
        "value_idr": None,
    }, {
        "stage": "Materials affected",
        "count": len({x["Material"] for x in (stock.value or [])}),
        "detail": ", ".join(sorted({x["Material"] for x in (stock.value or [])})),
        "value_idr": None,
    }, {
        "stage": "Finished goods that consume M-4471",
        "count": len(finished),
        "detail": ", ".join(finished) or "none",
        "value_idr": None,
    }, {
        "stage": "Customer orders at risk",
        "count": len(orders.value or []),
        "detail": ", ".join(x["SalesOrder"] for x in (orders.value or [])),
        "value_idr": exposed,
    }]
    return _wrap(rows, [
        {"k": "stage", "l": "Stage"}, {"k": "count", "l": "Count", "n": True},
        {"k": "detail", "l": "Which"}, {"k": "value_idr", "l": "At risk", "rp": True},
    ], orders, "Each stage is read from SAP, not inferred. The chain stops where the "
               "evidence stops.")


def exposure() -> dict:
    """Vega's scan. The only view that exists without a disruption to trigger it."""
    from tools.exposure import scan_supply_exposure
    r = scan_supply_exposure()
    rows = []
    for f in (r.value or []):
        rows.append({
            "pattern": f["pattern"], "material": f["material"], "plant": f["plant"],
            "detail": f["detail"], "cover_days": f["cover_days"],
            "value_idr": f["value_idr"], "action": f["action"], "authority": f["authority"],
        })
    return _wrap(rows, [
        {"k": "pattern", "l": "Exposure"}, {"k": "material", "l": "Material"},
        {"k": "detail", "l": "Why"},
        {"k": "value_idr", "l": "At risk", "rp": True},
        {"k": "action", "l": "Recommended"}, {"k": "authority", "l": "Needs"},
    ], r, r.note)


def logistics() -> dict:
    po = get_open_purchase_orders()
    rows = []
    for x in (po.value or []):
        d_orig = x.get("DeliveryDate") or x.get("delivery_date")
        d_rev = x.get("RevisedDeliveryDate") or x.get("revised_delivery_date")
        delay = 0
        if d_orig and d_rev:
            try:
                delay = (date.fromisoformat(str(d_rev)) - date.fromisoformat(str(d_orig))).days
            except ValueError:
                delay = 0
        rows.append({
            "reference": x.get("PurchaseOrder") or x.get("purchase_order") or "-",
            "material": x.get("Material") or x.get("material") or "-",
            "plant": x.get("Plant") or x.get("plant") or "-",
            "qty": x.get("OrderQuantity") or x.get("order_quantity") or 0,
            "port": x.get("LoadingPort") or x.get("loading_port"),
            "status": x.get("Status") or x.get("status") or "open",
            "arrival_original": d_orig or "",
            "arrival_revised": d_rev or "",
            "delay_days": delay,
        })
    for o in (find_alternate_sources("M-4471").value or []):
        e = (estimate_eta(o["id"]).value or {})
        if e:
            rows.append({
                "reference": f"option {o['id']}", "material": o.get("Material") or o.get("material") or "-",
                "plant": "-", "qty": o.get("Quantity") or o.get("quantity") or 0,
                "port": o.get("Origin") or o.get("origin"),
                "status": "planned", "arrival_original": e.get("arrival_booked"),
                "arrival_revised": e.get("arrival_effective"), "delay_days": e.get("dwell_days", 0),
            })
    out = _wrap(rows, [
        {"k": "reference", "l": "Reference"}, {"k": "material", "l": "Material"},
        {"k": "port", "l": "Origin"}, {"k": "status", "l": "Status"},
        {"k": "arrival_original", "l": "Arrival booked"},
        {"k": "arrival_revised", "l": "Arrival actual"},
        {"k": "delay_days", "l": "Delay (days)", "n": True},
    ], po)
    # Sort on the slip the table reports, then on when it lands, so the eight
    # shipments that share a delay still read in arrival order rather than
    # whatever order the fixture happened to list them in.
    worst = sorted(rows, key=lambda x: (-x["delay_days"], x["arrival_revised"]))[:CHART_LINES]
    if worst:
        out["chart"] = {
            "kind": "arrival",
            "total": len(rows),
            "today": profile()["AsOfDate"],
            "items": [{
                "reference": x["reference"], "material": x["material"],
                "port": x["port"] or "-", "status": x["status"],
                "booked": x["arrival_original"], "revised": x["arrival_revised"],
                "slip": x["delay_days"],
            } for x in worst],
        }
    return out


def simulation() -> dict:
    from tools.simulation import simulate_scenario_tool
    r = simulate_scenario_tool("M-4471", "KRW1")
    v = r.value or {}
    if v.get("refused") or not v.get("combinations"):
        return _wrap([], [], r, v.get("reason") or r.note)
    chosen = (v.get("chosen") or {}).get("combination")
    rows = [{
        "combination": c["combination"], "cost_idr": c["cost_idr"],
        "safe": c["safe"], "depleted_on": c["depleted_on"], "tkdn": c["tkdn_after"],
        "chosen": c["combination"] == chosen,
    } for c in v["combinations"]]
    return _wrap(rows, [
        {"k": "combination", "l": "Combination"}, {"k": "cost_idr", "l": "Cost", "rp": True},
        {"k": "safe", "l": "Bridges the gap"}, {"k": "depleted_on", "l": "Depleted if used"},
        {"k": "tkdn", "l": "TKDN", "n": True},
    ], r, f"With no action, stock runs out {v.get('depleted_without_action')}.")


def execution() -> dict:
    from core import store
    with store.connect() as c:
        found = c.execute(
            "SELECT a.*, e.title FROM actions a JOIN runs r ON r.id=a.run_id"
            " JOIN events e ON e.id=r.event_id ORDER BY a.created_at DESC LIMIT 100"
        ).fetchall()
    rows = []
    for x in found:
        payload = json.loads(x["payload"])
        rows.append({
            "id": x["id"], "kind": x["kind"], "status": x["status"],
            "autonomous": bool(x["autonomous"]), "cost_idr": payload.get("cost_idr"),
            "disruption": x["title"], "run_id": x["run_id"],
            "sap_reference": x["sap_reference"], "created_at": x["created_at"],
        })
    return _wrap(rows, [
        {"k": "kind", "l": "Action"}, {"k": "status", "l": "Status"},
        {"k": "cost_idr", "l": "Value", "rp": True},
        {"k": "disruption", "l": "Disruption"}, {"k": "sap_reference", "l": "SAP reference"},
    ], Result(rows, Origin.LIVE, "actions table"))


#: domain name == the agent code that owns it
VIEWS = {
    "impact": impact, "demand": demand, "inventory": inventory,
    "sourcing": sourcing, "procurement": procurement, "logistics": logistics,
    "compliance": compliance, "simulation": simulation, "execution": execution,
    "exposure": exposure,
}
