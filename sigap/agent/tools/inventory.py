"""Iris's tools (Stock Validity).

Stock that is recorded as present is not automatically stock you may use.
This file answers the 'may use' half: quality holds and safety stock.
"""
from __future__ import annotations

from clients import sap_s4
from core.provenance import Origin, Result
from core.registry import register
from tools.fetcher import as_of, read


@register("get_quality_holds", "inventory",
          "Stock that is on the books but blocked pending a quality inspection.",
          {"material": {"type": "string"}, "plant": {"type": "string"}},
          ["material", "plant"])
def get_quality_holds(material: str, plant: str) -> Result:
    if not sap_s4.available():
        return Result([], Origin.MODELLED, "API_INSPECTIONLOT_SRV",
                      note="the fixture carries no quality holds for this scenario")
    # SAP keeps held stock as its own stock type beside the unrestricted kind.
    stock = read("MaterialStock", material=material, plant=plant)
    if stock.value is None:
        return stock
    holds = [{"material": r["Material"], "plant": r["Plant"], "kind": kind, "qty": r[field],
              "unit": r.get("BaseUnit") or ""}
             for r in stock.value
             for kind, field in (("quality inspection", "QualityInspectionQty"),
                                 ("blocked", "BlockedQty"),
                                 ("special stock (promised elsewhere)", "SpecialStockQty"))
             if r.get(field)]
    return Result(holds, Origin.LIVE, stock.source,
                  note="stock types 02 (quality inspection) and 07 (blocked), and special "
                       "stock; none of it is in the usable figure")


@register("get_safety_stock_policy", "inventory",
          "The safety stock floor that normal production must not draw down.",
          {"material": {"type": "string"}, "plant": {"type": "string"}},
          ["material", "plant"])
def get_safety_stock_policy(material: str, plant: str) -> Result:
    if sap_s4.available():
        from clients import sap_map
        return sap_map.safety_stock(material, plant)
    return Result(None, Origin.MISSING, "API_PRODUCT_SRV (MARC)",
                  note="not in the fixture. It needs the customer's own master data")


@register("assess_transfer", "inventory",
          "Judge one proposed inter-plant transfer from both ends. The receiving plant "
          "is easy to model and the donor is the one that gets forgotten. Returns "
          "whether the donor keeps its own safety floor, and when it would empty if it "
          "does not. A transfer that breaks the sender is not a solution.",
          {"material": {"type": "string"}, "from_plant": {"type": "string"},
           "to_plant": {"type": "string"}, "qty": {"type": "number"},
           "floor_days": {"type": "integer", "description": "safety floor, default 14"}},
          ["material", "from_plant", "to_plant", "qty"])
def assess_transfer(material: str, from_plant: str, to_plant: str, qty: float,
                    floor_days: int = 14) -> Result:
    from engine.matching import assess

    stock = read("MaterialStock", material=material)
    if not stock.value:
        return Result(None, Origin.MISSING, stock.source, note="no stock records to judge")
    unknown = sorted(r["Plant"] for r in stock.value
                     if r.get("Plant") in (from_plant, to_plant) and r.get("DailyConsumption") is None)
    if unknown:
        # Unknown use would read as none, and the donor would look able to give everything.
        return Result(None, Origin.MISSING, stock.source,
                      note=f"daily consumption of {material} could not be read at "
                           f"{', '.join(unknown)} ({stock.note})")
    start = as_of()

    # Stock another open handling has already promised is not available to this
    # one. Both read the same on-hand figure, so without this each is right
    # alone and they are wrong together.
    from core import registry, store

    held = store.reserved_qty(material, from_plant, excluding_run=registry.current_run())
    rows = stock.value
    if held:
        rows = [dict(r) for r in rows]
        for r in rows:
            if r.get("Material") == material and r.get("Plant") == from_plant:
                on_hand = r.get("MatlWrhsStkQtyInMatlBaseUnit")
                if on_hand is not None:
                    r["MatlWrhsStkQtyInMatlBaseUnit"] = max(0.0, float(on_hand) - held)

    t = assess(rows, material, from_plant, to_plant, qty, start, floor_days)
    out = t.as_dict()
    out["reserved_elsewhere"] = held
    note = t.reason
    if held:
        note = f"{note} ({held:g} already held by another handling)"
    return Result(out, stock.origin, stock.source, note=note)


def demo() -> None:
    """Iris answers "may I use it", and the half that gets forgotten is the
    plant being asked to give. So that is what this checks: the donor."""
    import contextlib

    # Without SAP there are no inspection lots to read, and the answer says so
    # rather than returning an empty list that reads as "nothing is held".
    holds = get_quality_holds("M-4471", "SBY1")
    assert holds.value == [] and holds.origin is Origin.MODELLED, holds.brief()
    assert "carries no quality holds" in holds.note, holds.note

    # A safety floor is customer master data. Inventing one would set the
    # threshold every later transfer is judged against.
    floor = get_safety_stock_policy("M-4471", "SBY1")
    assert floor.origin is Origin.MISSING and floor.value is None, floor.brief()
    assert "own master data" in floor.note, floor.note

    # SBY1 holds 172.8 t of M-4471 at 9.6/day, KRW1 84.0 at 9.2/day.
    small = assess_transfer("M-4471", "SBY1", "KRW1", 20.0)
    t = small.value
    assert t and t["verdict"] == "available", small.brief()
    assert t["donor_cover_before"] > t["donor_cover_after"], t
    assert t["recipient_cover_after"] > t["recipient_cover_before"], t
    assert not t["donor_breaches_floor"] and t["cost_idr"] > 0, t
    assert t["reserved_elsewhere"] == 0

    # Emptying the donor to fix the recipient is not a solution, and the
    # verdict says which end it is refusing for.
    greedy = assess_transfer("M-4471", "SBY1", "KRW1", 170.0)
    assert greedy.value["donor_breaches_floor"] is True, greedy.value
    assert greedy.value["verdict"] != "available", greedy.value
    assert greedy.value["donor_cover_after"] < greedy.value["donor_floor_days"], greedy.value

    # A plant with no record of the material is said, not assumed empty.
    nowhere = assess_transfer("M-4471", "SBY1", "CKR1", 5.0)
    assert nowhere.value["verdict"] == "no stock record", nowhere.value
    assert "CKR1" in nowhere.value["reason"], nowhere.value

    # The one that makes two handlings see each other: stock another run has
    # promised is gone from this one's donor. Each is right alone and they are
    # wrong together.
    from core import store
    other = store.start_run(
        store.record_event("port_closure", "Another handling", "check", {}, "check"), "guided")
    store.reserve(other, "M-4471", "SBY1", 140.0)
    try:
        after = assess_transfer("M-4471", "SBY1", "KRW1", 20.0)
        assert after.value["reserved_elsewhere"] == 140.0, after.value
        assert "already held by another handling" in after.note, after.note
        assert after.value["donor_cover_after"] < t["donor_cover_after"], \
            "held stock must shrink the donor, not sit beside it"
    finally:
        store.release_reservations("self-check", run_id=other)
    assert assess_transfer("M-4471", "SBY1", "KRW1", 20.0).value["reserved_elsewhere"] == 0

    # Consumption that could not be read must refuse. Read as zero, the donor
    # looks able to give everything it has forever.
    @contextlib.contextmanager
    def blind():
        was = globals()["read"]
        def patched(entity, **kw):
            r = was(entity, **kw)
            if entity == "MaterialStock" and r.value:
                r.value = [{**x, "DailyConsumption": None} if x.get("Plant") == "SBY1" else x
                           for x in r.value]
            return r
        globals()["read"] = patched
        try:
            yield
        finally:
            globals()["read"] = was

    with blind():
        refused = assess_transfer("M-4471", "SBY1", "KRW1", 20.0)
    assert refused.origin is Origin.MISSING and refused.value is None, refused.brief()
    assert "daily consumption" in refused.note and "SBY1" in refused.note, refused.note

    print("  no inspection lots is said, not implied ✓ · no invented safety floor ✓")
    print(f"  20 t moves ({t['verdict']}) ✓ · 170 t breaks the donor and is refused ✓")
    print("  stock another handling holds is gone from this donor ✓ · unknown use refuses ✓")
    print("inventory ok")


if __name__ == "__main__":
    # Reservations are written, so this must not touch the operator's database.
    from core.config import fixtures_only

    fixtures_only(__file__, "SIGAP_INVENTORY_CHECK")
    demo()
