"""Tara's tools (Costing).

A thin wrapper over engine/simulate.py. The model calls this tool; plain Python
still does the arithmetic. The model decides, the arithmetic computes.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from core.provenance import Origin, Result
from core.registry import register
from engine.simulate import Arrival, Ruling, simulate_scenario
from tools.compliance import check_local_constraints
from tools.fetcher import fixture, profile
from tools.impact import get_material_stock
from tools.sourcing import find_alternate_sources


@register(
    "simulate_scenario", "simulation",
    "Compute cost, stockout date, OTIF, and TKDN impact for every supply option that "
    "cleared the rules, plus their combinations. Deterministic — the same inputs always "
    "give the same answer. Refuses to emit figures when the inputs are not trustworthy.",
    {"material": {"type": "string"},
     "plant": {"type": "string"},
     "allowed_options": {"type": "array", "items": {"type": "string"},
                         "description": "option ids already cleared by Rules, e.g. ['A','B','C']"}},
    ["material", "plant"],
)
def simulate_scenario_tool(material: str, plant: str,
                           allowed_options: Optional[List[str]] = None) -> Result:
    p = profile()
    start = date.fromisoformat(p["AsOfDate"])

    stock = get_material_stock(material=material, plant=plant)
    row = (stock.value or [{}])[0]
    opening = row.get("MatlWrhsStkQtyInMatlBaseUnit")
    daily = row.get("DailyConsumption")
    if opening is None or daily is None:
        return Result(None, Origin.MISSING, "engine/simulate.py",
                      note=f"no stock found for {material} at {plant}")

    options = find_alternate_sources(material)

    # Compliance rulings come from Kira, never guessed here.
    rulings = {}
    for o in (options.value or []):
        if allowed_options is not None:
            rulings[o["id"]] = Ruling(o["id"], o["label"], o["id"] in allowed_options)
            continue
        v = check_local_constraints(o["id"]).value or {}
        rulings[o["id"]] = Ruling(o["id"], o["label"],
                                  bool(v.get("allowed")), v.get("reason", ""))

    # supply already booked and in transit
    scheduled = [
        Arrival(r["PurchaseOrder"],
                date.fromisoformat(r["RevisedDeliveryDate"]),
                float(r["OrderQuantity"]))
        for r in fixture("PurchaseOrder")
        if r["Material"] == material and r["Plant"] == plant
    ]

    sim = simulate_scenario(stock, options, rulings, p, start,
                            float(daily), float(opening), scheduled)

    if sim.refused:
        return Result({"refused": True, "reason": sim.refusal_reason},
                      Origin.MISSING, "engine/simulate.py", note=sim.refusal_reason)

    return Result({
        "depleted_without_action": str(sim.depleted_without_action),
        "options": sim.options,
        "combinations": sim.combinations[:8],
        "chosen": sim.chosen,
    }, Origin.DERIVED, "engine/simulate.py")
