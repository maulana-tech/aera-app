"""Per-domain table views.

Each domain page needs its own table. This file arranges tools that already
exist into a shape that displays well — it adds no new data source, so origin
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
from tools.impact import get_material_stock, get_open_purchase_orders
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
    r = find_alternate_sources("M-4471")
    rows = []
    for o in (r.value or []):
        v = (check_local_constraints(o["id"]).value or {})
        rows.append({
            "id": o["id"], "label": o["label"], "supplier": o["Supplier"],
            "qty": o["Quantity"], "arrives": o["ArrivalDate"],
            "cost_idr": o["ExtraCostIDR"], "tkdn": o.get("TkdnAfterPct"),
            "origin_country": o["Origin"],
            "allowed": v.get("allowed"), "reason": v.get("reason"),
        })
    return _wrap(rows, [
        {"k": "id", "l": "#"}, {"k": "label", "l": "Option"},
        {"k": "arrives", "l": "Arrives"}, {"k": "cost_idr", "l": "Extra cost", "rp": True},
        {"k": "tkdn", "l": "TKDN", "n": True}, {"k": "allowed", "l": "Clears rules"},
    ], r)


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
                "plant": "—", "qty": o["Quantity"], "port": o["Origin"],
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
    "inventory": inventory, "demand": demand, "sourcing": sourcing,
    "logistics": logistics, "simulation": simulation, "execution": execution,
}
