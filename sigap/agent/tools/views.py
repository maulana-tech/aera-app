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
from tools.sourcing import find_alternate_sources


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
    return _wrap(rows, [
        {"k": "material", "l": "Material"}, {"k": "description", "l": "Name"},
        {"k": "plant", "l": "Plant"}, {"k": "qty", "l": "Quantity", "n": True},
        {"k": "daily_consumption", "l": "Used/day", "n": True},
        {"k": "days_left", "l": "Days left", "n": True},
        {"k": "depleted_on", "l": "Depleted"},
    ], r)


def demand() -> dict:
    r = get_material_stock()
    rows = [{
        "material": x.get("Material"), "plant": x.get("Plant"),
        "daily_consumption": x.get("DailyConsumption"),
        "unit": x.get("BaseUnit"),
        "signal": "not connected",
    } for x in (r.value or [])]
    return _wrap(rows, [
        {"k": "material", "l": "Material"}, {"k": "plant", "l": "Plant"},
        {"k": "daily_consumption", "l": "Used/day", "n": True},
        {"k": "signal", "l": "Demand signal"},
    ], r, "A demand-change signal needs SAP IBP, which is not connected. What is shown "
          "is the consumption rate from the production schedule.")


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
    rows = [{
        "reference": x["PurchaseOrder"], "material": x["Material"],
        "plant": x["Plant"], "qty": x["OrderQuantity"],
        "port": x.get("LoadingPort"), "status": x["Status"],
        "arrival_original": x["DeliveryDate"], "arrival_revised": x["RevisedDeliveryDate"],
        "delay_days": (date.fromisoformat(x["RevisedDeliveryDate"])
                       - date.fromisoformat(x["DeliveryDate"])).days,
    } for x in (po.value or [])]
    for o in (find_alternate_sources("M-4471").value or []):
        e = (estimate_eta(o["id"]).value or {})
        if e:
            rows.append({
                "reference": f"option {o['id']}", "material": o["Material"],
                "plant": "-", "qty": o["Quantity"], "port": o["Origin"],
                "status": "planned", "arrival_original": e["arrival_booked"],
                "arrival_revised": e["arrival_effective"], "delay_days": e["dwell_days"],
            })
    return _wrap(rows, [
        {"k": "reference", "l": "Reference"}, {"k": "material", "l": "Material"},
        {"k": "port", "l": "Origin"}, {"k": "status", "l": "Status"},
        {"k": "arrival_original", "l": "Arrival booked"},
        {"k": "arrival_revised", "l": "Arrival actual"},
        {"k": "delay_days", "l": "Delay (days)", "n": True},
    ], po)


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
    "sourcing": sourcing, "logistics": logistics, "compliance": compliance,
    "simulation": simulation, "execution": execution, "exposure": exposure,
}
