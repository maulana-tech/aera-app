"""Internal stock transfers, judged from both ends.

Moving stock between plants is the cheapest way out of a shortage, which is
why it is the first thing anyone reaches for and the last thing anyone checks.
The receiving plant is easy to model. The donor is the one that gets forgotten.

This exists because the recommendation SIGAP has been making since the first
scenario, move 55 tonnes from SBY1 to KRW1, pushes SBY1 from eighteen days of
cover to twelve, under its own fourteen day floor, and empties it eight days
before its own replenishment lands. Nothing in the system noticed, because
compliance checks regulation and the calculator only ever modelled the plant
that receives.

No model here. Daily balances forward, both ends, same arithmetic as
engine/simulate.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence

from engine.simulate import Arrival, project_cover

#: Road transit between plants, in days. A real installation reads this from
#: its own lane master; until then it is a declared assumption, not a fact.
TRANSIT_DAYS = 2

#: Rupiah per unit moved. Same status as the transit time.
COST_PER_UNIT_IDR = 400_000


@dataclass
class Transfer:
    material: str
    from_plant: str
    to_plant: str
    qty: float
    unit: str
    arrives: str

    donor_cover_before: float
    donor_cover_after: float
    donor_depleted_before: Optional[str]
    donor_depleted_after: Optional[str]
    donor_floor_days: int
    donor_breaches_floor: bool

    recipient_cover_before: float
    recipient_cover_after: float

    cost_idr: int
    verdict: str          # "available" | "breaches donor floor" | "donor has no surplus"
    reason: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _cover(qty: float, daily: float) -> float:
    return round(qty / daily, 1) if daily else float("inf")


def assess(
    stock: Sequence[dict],
    material: str,
    from_plant: str,
    to_plant: str,
    qty: float,
    start: date,
    floor_days: int = 14,
    arrivals: Optional[Dict[str, List[Arrival]]] = None,
) -> Transfer:
    """Judge one proposed transfer from both ends."""
    arrivals = arrivals or {}

    def row(plant: str) -> Optional[dict]:
        return next((r for r in stock
                     if r["Material"] == material and r["Plant"] == plant), None)

    donor, recipient = row(from_plant), row(to_plant)
    if donor is None or recipient is None:
        missing = from_plant if donor is None else to_plant
        return Transfer(material, from_plant, to_plant, qty, "", "",
                        0, 0, None, None, floor_days, False, 0, 0, 0,
                        "no stock record",
                        f"{material} has no stock record at {missing}")

    d_qty = float(donor["MatlWrhsStkQtyInMatlBaseUnit"])
    d_daily = float(donor["DailyConsumption"] or 0)
    r_qty = float(recipient["MatlWrhsStkQtyInMatlBaseUnit"])
    r_daily = float(recipient["DailyConsumption"] or 0)

    d_before = _cover(d_qty, d_daily)
    d_after = _cover(d_qty - qty, d_daily)
    r_before = _cover(r_qty, r_daily)
    # The recipient does not get it the day it is asked for.
    r_after = _cover(r_qty + qty, r_daily)

    d_in = arrivals.get(from_plant, [])
    depleted_before = project_cover(d_qty, d_daily, start, d_in).depleted_on
    depleted_after = project_cover(d_qty - qty, d_daily, start, d_in).depleted_on

    breaches = d_after < floor_days
    if d_qty - qty < 0:
        verdict = "donor has no surplus"
        reason = (f"{from_plant} holds {d_qty:g} and cannot give {qty:g}")
    elif breaches:
        verdict = "breaches donor floor"
        reason = (f"{from_plant} falls from {d_before} to {d_after} days of cover, "
                  f"under its own {floor_days} day floor"
                  + (f", and empties on {depleted_after}" if depleted_after else ""))
    else:
        verdict = "available"
        reason = (f"{from_plant} keeps {d_after} days of cover, above its "
                  f"{floor_days} day floor")

    return Transfer(
        material, from_plant, to_plant, qty, donor.get("BaseUnit", ""),
        (start + timedelta(days=TRANSIT_DAYS)).isoformat(),
        d_before, d_after,
        depleted_before.isoformat() if depleted_before else None,
        depleted_after.isoformat() if depleted_after else None,
        floor_days, breaches,
        r_before, r_after,
        int(qty * COST_PER_UNIT_IDR),
        verdict, reason,
    )


def find(
    stock: Sequence[dict],
    material: str,
    to_plant: str,
    need_qty: float,
    start: date,
    floor_days: int = 14,
    arrivals: Optional[Dict[str, List[Arrival]]] = None,
) -> List[Transfer]:
    """Every plant that could send, with what it costs each of them.

    Returns the ones that break the donor as well as the ones that do not. An
    option removed silently cannot be argued with, and the lead may decide a
    donor breach is acceptable. That is a decision, not a default.
    """
    donors = sorted({r["Plant"] for r in stock
                     if r["Material"] == material and r["Plant"] != to_plant})
    out = []
    for plant in donors:
        # Offer what the donor can spare down to its floor, capped at the need.
        row = next(r for r in stock
                   if r["Material"] == material and r["Plant"] == plant)
        daily = float(row["DailyConsumption"] or 0)
        spare = float(row["MatlWrhsStkQtyInMatlBaseUnit"]) - daily * floor_days
        offer = round(min(need_qty, max(spare, 0)), 1) or need_qty
        out.append(assess(stock, material, plant, to_plant, offer, start,
                          floor_days, arrivals))
    order = {"available": 0, "breaches donor floor": 1,
             "donor has no surplus": 2, "no stock record": 3}
    out.sort(key=lambda t: (order.get(t.verdict, 9), -t.qty))
    return out


def demo() -> None:
    import json
    import pathlib

    fx = json.loads((pathlib.Path(__file__).resolve().parent.parent
                     / "fixtures" / "ningbo_scenario.json").read_text())
    stock = fx["MaterialStock"]
    start = date.fromisoformat(fx["Profile"]["AsOfDate"])
    inbound = {"SBY1": [Arrival("4500018901", date(2026, 9, 24), 90.0)]}

    # The transfer the system has been recommending all along.
    t = assess(stock, "M-4471", "SBY1", "KRW1", 55.0, start, 14, inbound)
    assert t.donor_breaches_floor, "the SBY1 transfer must be flagged"
    assert t.verdict == "breaches donor floor", t.verdict
    assert t.donor_cover_before > 14 > t.donor_cover_after, (t.donor_cover_before,
                                                             t.donor_cover_after)
    assert t.donor_depleted_after < t.donor_depleted_before, t
    assert "under its own 14 day floor" in t.reason

    # A smaller transfer the donor can genuinely afford.
    small = assess(stock, "M-4471", "SBY1", "KRW1", 20.0, start, 14, inbound)
    assert small.verdict == "available", small.reason
    assert small.donor_cover_after >= 14, small.donor_cover_after

    # The search offers what the donor can spare rather than what was asked for.
    found = find(stock, "M-4471", "KRW1", 55.0, start, 14, inbound)
    assert found, "no donor plant found for a material held at two plants"
    best = found[0]
    assert best.verdict == "available", best.reason
    assert best.qty < 55.0, "the full 55 t was never affordable"

    print("matching ok")
    print(f"  asked for 55.0 t from SBY1  -> {t.verdict}")
    print(f"    cover {t.donor_cover_before} to {t.donor_cover_after} days, "
          f"floor {t.donor_floor_days}")
    print(f"    SBY1 empties {t.donor_depleted_before} -> {t.donor_depleted_after}")
    print(f"  affordable instead          -> {best.qty:g} {best.unit} "
          f"leaves {best.donor_cover_after} days")


if __name__ == "__main__":
    demo()
