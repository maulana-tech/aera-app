"""Tara's tools (Costing).

A thin wrapper over engine/simulate.py. The model calls this tool; plain Python
still does the arithmetic. The model decides, the arithmetic computes.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

from core.provenance import Origin, Result, weakest
from core.registry import register
from engine.simulate import Arrival, Ruling, simulate_scenario
from tools.compliance import check_local_constraints
from tools.fetcher import as_of, bom, profile, read
from tools.impact import get_material_stock
from tools.sourcing import find_alternate_sources


@register(
    "simulate_scenario", "simulation",
    "Compute cost, stockout date, OTIF, and TKDN impact for every supply option that "
    "cleared the rules, plus their combinations. Also returns compliance_cost: what "
    "obeying the rules cost, when an option that was struck out would have been "
    "cheaper, and which rule struck it. Deterministic, the same inputs always give the "
    "same answer. Refuses to emit figures when the inputs are not trustworthy.",
    {"material": {"type": "string"},
     "plant": {"type": "string"},
     "allowed_options": {"type": "array", "items": {"type": "string"},
                         "description": "option ids Kira cleared, e.g. ['A','B','C']. It can only "
                                        "narrow the rules: an option the rule pack strikes out "
                                        "stays out whatever is listed"}},
    ["material", "plant"],
)
def simulate_scenario_tool(material: str, plant: str,
                           allowed_options: Optional[List[str]] = None) -> Result:
    p = profile()
    start = as_of()

    stock = get_material_stock(material=material, plant=plant)
    row = (stock.value or [{}])[0]
    opening = row.get("MatlWrhsStkQtyInMatlBaseUnit")
    daily = row.get("DailyConsumption")
    if opening is None or daily is None:
        return Result(None, Origin.MISSING, "engine/simulate.py",
                      note=f"no stock found for {material} at {plant}")

    options = find_alternate_sources(material)

    # An option with no quantity, cost or date cannot be costed. Leaving it out
    # would let the calculator recommend from the rest as if it were complete.
    gaps = sorted({f for o in (options.value or [])
                   for f in ("Quantity", "ExtraCostIDR", "ArrivalDate") if o.get(f) is None})
    if gaps:
        return Result(None, Origin.MISSING, "engine/simulate.py",
                      note=f"the supply options for {material} have no {', '.join(gaps)} "
                           f"({options.source}); upload AlternateSource with those columns "
                           "to cost them")

    rulings, overruled = rulings_for(options.value or [], allowed_options)

    # supply already booked and in transit
    scheduled = [
        Arrival(r["PurchaseOrder"],
                date.fromisoformat(r["RevisedDeliveryDate"]),
                float(r["OrderQuantity"]))
        for r in read("PurchaseOrder", material=material, plant=plant).value or []
        if r.get("RevisedDeliveryDate")
    ]

    # The same pack Kira rules from prices the options: duty is set per HS
    # heading, so the tariff table and the restricted headings live together.
    from tools.compliance import load_pack
    sim = simulate_scenario(stock, options, rulings, p, start,
                            float(daily), float(opening), scheduled,
                            pack=load_pack())

    if sim.refused:
        return Result({"refused": True, "reason": sim.refusal_reason},
                      Origin.MISSING, "engine/simulate.py", note=sim.refusal_reason)

    return Result({
        "depleted_without_action": str(sim.depleted_without_action),
        "options": sim.options,
        "combinations": sim.combinations[:8],
        "chosen": sim.chosen,
        # What the rules cost on this scenario, or None when nothing that was
        # struck out would have been cheaper anyway.
        "compliance_cost": sim.compliance_cost,
    }, Origin.DERIVED, "engine/simulate.py",
        note=("listed as cleared but struck out by the rules, so not costed as an option: "
              + "; ".join(overruled)) if overruled else "")


def rulings_for(options: List[dict],
                allowed_options: Optional[List[str]]) -> Tuple[Dict[str, Ruling], List[str]]:
    """Each option's ruling, and the listed ones the rules struck out.

    The rulings come from the rule pack Kira rules with, run here again rather
    than taken on the caller's word: the caller is a model, and a list it hands
    in must not be able to clear what the rules struck out. The list can only
    narrow them.
    """
    rulings, overruled = {}, []
    for o in options:
        v = check_local_constraints(o["id"]).value or {}
        allowed, reason = bool(v.get("allowed")), v.get("reason", "")
        if allowed_options is not None and o["id"] not in allowed_options and allowed:
            allowed, reason = False, "the rules allow it, but it was not among the options cleared"
        elif allowed_options is not None and o["id"] in allowed_options and not allowed:
            overruled.append(f"{o['id']} ({reason})")
        rulings[o["id"]] = Ruling(o["id"], o["label"], allowed, reason)
    return rulings, overruled


@register(
    "allocate_short_supply", "simulation",
    "When a material cannot cover every customer order before supply returns, decide "
    "which orders get what is left. The orders whose lateness costs the most contract "
    "penalty per unit of material are served first and the rest wait for the new supply. "
    "Returns the orders to serve, in the order to build them, the ones deferred with "
    "their days late and penalty, and the penalty total set against serving them in "
    "due-date order. Deterministic, engine/allocate.py. Without penalty terms on the "
    "orders it ranks on order value and states no rupiah total.",
    {"material": {"type": "string"},
     "plant": {"type": ["string", "null"],
               "description": "the plant that is short; its on-hand is the default quantity"},
     "available_qty": {"type": ["number", "null"],
                       "description": "material left to allocate, in its base unit"},
     "supply_returns": {"type": ["string", "null"],
                        "description": "YYYY-MM-DD, the day the material is available again"},
     "days_to_ship": {"type": ["integer", "null"],
                      "description": "days from the material arriving to the order shipping, "
                                     "default 0"}},
    ["material"],
)
def allocate_short_supply(material: str, plant: Optional[str] = None,
                          available_qty: Optional[float] = None,
                          supply_returns: Optional[str] = None,
                          days_to_ship: Optional[int] = None) -> Result:
    from engine.allocate import Claim, allocate

    try:
        returns = date.fromisoformat(supply_returns) if supply_returns else None
    except ValueError:
        return Result(None, Origin.MISSING, "engine/allocate.py",
                      note=f"supply_returns '{supply_returns}' is not a YYYY-MM-DD date")

    structure = bom()
    if structure.value is None:
        return Result(None, Origin.MISSING, structure.source, note=structure.note)
    per_piece = {}
    for b in structure.value:
        if b.get("Material") == material and (not plant or not b.get("Plant") or b["Plant"] == plant):
            per_piece.setdefault(b["FinishedGood"], b.get("ComponentQuantity"))
    if not per_piece:
        return Result({"serve": [], "defer": []}, structure.origin, structure.source,
                      note=f"no finished good consumes {material}, so no customer order "
                           "competes for it")

    sales = read("SalesOrder", materials=list(per_piece))
    if sales.value is None:
        return Result(None, Origin.MISSING, sales.source, note=sales.note)
    claims, undated = [], []
    for o in sales.value:
        due = o.get("RequestedDeliveryDate")
        if not due:
            undated.append(str(o.get("SalesOrder")))
            continue
        pieces, qty = o.get("Quantity"), per_piece.get(o.get("Material"))
        claims.append(Claim(
            str(o.get("SalesOrder")), str(o.get("CustomerName") or o.get("Customer") or ""),
            str(o.get("Material")), date.fromisoformat(str(due)[:10]),
            round(float(pieces) * float(qty), 6) if pieces and qty else None,
            o.get("NetAmount"), o.get("LatePenaltyPctPerDay"), o.get("LatePenaltyCapPct")))

    origins = [structure.origin, sales.origin, Origin.DERIVED]
    if available_qty is None:
        stock = read("MaterialStock", material=material, plant=plant)
        held = [r.get("MatlWrhsStkQtyInMatlBaseUnit") for r in stock.value or []]
        if not held or any(h is None for h in held):
            return Result(None, Origin.MISSING, stock.source,
                          note=f"no on-hand figure for {material}"
                               + (f" at {plant}" if plant else "") + "; pass available_qty")
        available_qty = float(sum(held))
        origins.append(stock.origin)

    plan = allocate(claims, float(available_qty), returns, int(days_to_ship or 0))
    notes = [f"material per order is its pieces times the bill of materials quantity per "
             f"piece; {plan.available:g} to allocate"]
    if plan.basis == "value":
        notes.append("no contract penalty terms on these orders, so they are ranked on order "
                     "value and no penalty total is stated")
    if returns is None:
        notes.append("the date supply returns was not given, so every order competes and "
                     "no lateness can be counted")
    if plan.unknown_need:
        notes.append(f"{len(plan.unknown_need)} order(s) carry no quantity, so what they need "
                     "is unknown and they were not allocated")
    if undated:
        notes.append(f"{len(undated)} order(s) have no requested date: {', '.join(undated)}")
    return Result(plan.as_dict(), weakest(*origins), "engine/allocate.py", note="; ".join(notes))


def demo() -> None:
    # The scenario: three FG-1120 orders due 30 Sep, with too little ADC12 left
    # for all of them and the Ningbo supply not back until 2 Oct. All three
    # carry the same terms and price per piece, so they weigh the same per
    # tonne: the tie goes by order number, and the smallest still fits after.
    r = allocate_short_supply("M-4471", plant="KRW1", available_qty=5.0,
                              supply_returns="2026-10-02")
    plan = r.value
    assert r.origin is Origin.MODELLED and plan["basis"] == "penalty", (r.origin, plan["basis"])
    assert [s["order"] for s in plan["serve"]] == ["0000104411", "0000104455"], plan["serve"]
    assert [d["order"] for d in plan["defer"]] == ["0000104427"], plan["defer"]
    late = plan["defer"][0]
    assert late["days_late"] == 2 and late["penalty_idr"] == 7_150_000, late
    assert plan["saved_idr"] is not None and plan["saved_idr"] >= 0, plan

    # Everything fits: nothing deferred, no penalty.
    roomy = allocate_short_supply("M-4471", available_qty=100.0, supply_returns="2026-10-02").value
    assert not roomy["defer"] and roomy["penalty_plan_idr"] == 0.0, roomy

    # A material no product consumes leaves nothing to allocate, and says so.
    assert "no finished good" in allocate_short_supply("M-1202").note
    assert allocate_short_supply("M-4471", supply_returns="2 Oct").origin is Origin.MISSING

    # The veto is the rules', not the caller's. A model that lists every option
    # as cleared still gets the struck-out ones struck out, and is told so.
    from tools import compliance
    real = compliance._public_holidays
    compliance._public_holidays = lambda first, last: Result(        # noqa: E731
        {"country": "ID", "holidays": []}, Origin.LIVE, "Nager.Date")
    try:
        options = find_alternate_sources("M-4471").value
        ids = [o["id"] for o in options]
        by_rules, _ = rulings_for(options, None)
        blocked = sorted(i for i in ids if not by_rules[i].allowed)
        cleared = sorted(i for i in ids if by_rules[i].allowed)
        assert "E" in blocked and cleared, (blocked, cleared)

        everything, overruled = rulings_for(options, ids)
        assert sorted(i for i in ids if not everything[i].allowed) == blocked, everything
        assert [o.split(" ")[0] for o in overruled] == blocked, overruled
        assert everything["E"].reason == by_rules["E"].reason, "the rule's own reason is kept"

        # Narrowing still works: what the caller leaves out is not costed.
        one, overruled = rulings_for(options, cleared[:1])
        assert [i for i in ids if one[i].allowed] == cleared[:1] and not overruled, one
        assert "not among the options cleared" in one[cleared[-1]].reason or len(cleared) == 1
    finally:
        compliance._public_holidays = real
    print("simulation ok, allocation serves the costliest lateness first on the scenario ✓")
    print(f"  a list of options cannot clear what the rules struck out ({', '.join(blocked)}) ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_SIMULATION_CHECK")
    demo()
