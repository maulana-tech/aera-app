"""The calculator. No AI in here, and none allowed.

If a rupiah figure comes out of a language model, one sceptical question brings
the whole savings claim down. The model decides; this file does the arithmetic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence

from core.provenance import Origin, Result


@dataclass
class Arrival:
    id: str
    on: date
    qty: float


@dataclass
class Cover:
    depleted_on: Optional[date]       # first day consumption cannot be met
    covered_through: Optional[date]
    closing_qty: float


def project_cover(
    opening_qty: float,
    daily_consumption: float,
    start: date,
    arrivals: Sequence[Arrival] = (),
    horizon_days: int = 120,
) -> Cover:
    """Roll the daily balance forward. Arrivals land at the start of their day."""
    if daily_consumption <= 0:
        return Cover(None, None, opening_qty)

    incoming: Dict[date, float] = {}
    for a in arrivals:
        incoming[a.on] = incoming.get(a.on, 0.0) + a.qty

    balance = opening_qty
    day = start
    for _ in range(horizon_days):
        balance += incoming.get(day, 0.0)
        if balance < daily_consumption:
            return Cover(day, day - timedelta(days=1), round(balance, 2))
        balance -= daily_consumption
        day += timedelta(days=1)
    return Cover(None, day - timedelta(days=1), round(balance, 2))


@dataclass
class Ruling:
    id: str
    label: str
    allowed: bool
    reason: str = ""


@dataclass
class Simulation:
    refused: bool
    refusal_reason: str = ""
    depleted_without_action: Optional[date] = None
    options: List[dict] = field(default_factory=list)
    combinations: List[dict] = field(default_factory=list)
    chosen: Optional[dict] = None


def simulate_scenario(
    stock: Result,
    options: Result,
    compliance_rulings: Dict[str, Ruling],
    profile: dict,
    start: date,
    daily_consumption: float,
    opening_qty: float,
    scheduled_arrivals: Sequence[Arrival] = (),
) -> Simulation:
    """Cost every option that cleared the rules, plus their combinations.

    A plan counts as SAFE when there is no shortfall before the last scheduled
    delivery lands — not forever. The job is to bridge the gap, not to supply
    the plant indefinitely.

    Refuses to emit figures when a critical input is not trustworthy.
    """
    for label, r in (("stock", stock), ("supply options", options)):
        if not r.trusted:
            return Simulation(
                refused=True,
                refusal_reason=(
                    f"Input '{label}' came from {r.origin.value} ({r.source}). "
                    "No savings figure is emitted until that data is live."
                ),
            )

    baseline = project_cover(opening_qty, daily_consumption, start, scheduled_arrivals)

    # the gap to bridge ends when the last scheduled delivery arrives
    bridge_until = max((a.on for a in scheduled_arrivals), default=None)

    viable: List[dict] = []
    blocked: List[dict] = []
    for o in options.value:
        ruling = compliance_rulings.get(o["id"])
        row = {
            "id": o["id"], "label": o["label"], "supplier": o["Supplier"],
            "qty": o["Quantity"], "arrives": o["ArrivalDate"],
            "extra_cost_idr": o["ExtraCostIDR"], "tkdn_after": o["TkdnAfterPct"],
            "allowed": bool(ruling and ruling.allowed),
            "reason": ruling.reason if ruling else "not yet assessed",
        }
        (viable if row["allowed"] else blocked).append(row)

    # combinations: each option alone, then every pair
    candidates: List[dict] = []
    for i, a in enumerate(viable):
        candidates.append({"members": [a], "cost": a["extra_cost_idr"]})
        for b in viable[i + 1:]:
            candidates.append({"members": [a, b],
                               "cost": a["extra_cost_idr"] + b["extra_cost_idr"]})

    scored: List[dict] = []
    for c in candidates:
        arrivals = [Arrival(m["id"], date.fromisoformat(m["arrives"]), m["qty"])
                    for m in c["members"]]
        cover = project_cover(opening_qty, daily_consumption, start,
                              list(scheduled_arrivals) + arrivals)
        tkdn = [m["tkdn_after"] for m in c["members"] if m["tkdn_after"] is not None]
        safe = (cover.depleted_on is None
                or (bridge_until is not None and cover.depleted_on > bridge_until))
        scored.append({
            "combination": "+".join(m["id"] for m in c["members"]),
            "members": [m["id"] for m in c["members"]],
            "cost_idr": c["cost"],
            "safe": safe,
            "depleted_on": cover.depleted_on.isoformat() if cover.depleted_on else None,
            "tkdn_after": max(tkdn) if tkdn else profile["TkdnCurrentPct"],
        })

    safe_plans = [s for s in scored if s["safe"]]
    chosen = min(safe_plans, key=lambda s: s["cost_idr"]) if safe_plans else None

    return Simulation(
        refused=False,
        depleted_without_action=baseline.depleted_on,
        options=viable + blocked,
        combinations=sorted(scored, key=lambda s: s["cost_idr"]),
        chosen=chosen,
    )


# --------------------------------------------------------------------------- #
def demo() -> None:
    import json
    import pathlib

    fx = json.loads((pathlib.Path(__file__).resolve().parent.parent
                     / "fixtures" / "ningbo_scenario.json").read_text())
    start = date.fromisoformat(fx["Profile"]["AsOfDate"])

    # 1. do nothing at all
    baseline = project_cover(84.0, 9.2, start)
    assert baseline.depleted_on == date(2026, 9, 13), baseline.depleted_on
    print(f"  no action        → depleted {baseline.depleted_on}")

    # 2. refusal when the data is not trustworthy
    refused = simulate_scenario(
        Result([], Origin.MODELLED, "fixture"), Result([], Origin.MODELLED, "fixture"),
        {}, fx["Profile"], start, 9.2, 84.0,
    )
    assert refused.refused
    assert "until that data is live" in refused.refusal_reason
    print("  modelled data    → calculator refuses to give a figure ✓")

    # 3. full path, treating the data as live
    stock = Result(fx["MaterialStock"], Origin.LIVE, "API_MATERIAL_STOCK_SRV")
    options = Result(fx["AlternateSource"], Origin.LIVE, "A_PurchasingInfoRecord")
    rulings = {
        "A": Ruling("A", "air freight", True),
        "B": Ruling("B", "local supplier", True),
        "C": Ruling("C", "SBY1 reallocation", True),
        "D": Ruling("D", "Vietnam", False, "LARTAS new origin +10 working days"),
        "E": Ruling("E", "cheapest", False, "TKDN drops to 34.8% — contract floor 40%"),
    }
    po = [Arrival("4500018872", date(2026, 9, 22), 120.0)]
    sim = simulate_scenario(stock, options, rulings, fx["Profile"], start, 9.2, 84.0, po)

    assert not sim.refused
    assert sim.chosen is not None, "there must be a safe combination"
    blocked = sorted(o["id"] for o in sim.options if not o["allowed"])
    assert blocked == ["D", "E"], blocked
    print(f"  blocked by rules → {blocked}")
    print(f"  chosen           → {sim.chosen['combination']} "
          f"Rp {sim.chosen['cost_idr']:,} · TKDN {sim.chosen['tkdn_after']}%")

    # the cheapest safe plan must be C+B, not air freight
    assert sim.chosen["combination"] == "B+C", sim.chosen["combination"]
    assert sim.chosen["cost_idr"] == 116_000_000
    a = next(s for s in sim.combinations if s["combination"] == "A")
    assert a["safe"], "air freight alone should bridge the gap"
    assert a["cost_idr"] > sim.chosen["cost_idr"], "the pair must beat air freight"
    saved = a["cost_idr"] - sim.chosen["cost_idr"]
    print(f"  vs option A      → Rp {a['cost_idr']:,} · saves Rp {saved:,} "
          f"({saved / a['cost_idr'] * 100:.0f}%)")
    print("simulate ok")


if __name__ == "__main__":
    demo()
