"""Who gets the material when there is not enough of it. No AI in here.

When a material runs short, what is left has to go to some customer orders
before others. Which ones is a commercial choice, but its cost can be worked
out: an order delivered late pays its contract penalty for every day it waits,
up to the cap. This file serves first the orders whose lateness costs the most
per unit of material, defers the rest to when supply returns, and sets that
against serving them in due-date order, which is what a plant does when nobody
decides. The two totals side by side are what the choice is worth.

It is a sequence of customer orders, not a production schedule: no production
order, routing or capacity is read, so the material an order needs is its
pieces times the bill of materials, and an order is served whole or deferred
whole.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional


@dataclass
class Claim:
    order: str
    customer: str
    finished_good: str
    due: date
    need: Optional[float]                  # the material it takes, in its base unit
    value_idr: Optional[float]
    penalty_pct_per_day: Optional[float]
    penalty_cap_pct: Optional[float]

    def penalty(self, days_late: int) -> Optional[float]:
        """Rupiah owed for `days_late` days, or None when the terms are not known."""
        if days_late <= 0:
            return 0.0
        if self.value_idr is None or self.penalty_pct_per_day is None:
            return None
        pct = self.penalty_pct_per_day * days_late
        if self.penalty_cap_pct is not None:
            pct = min(pct, self.penalty_cap_pct)
        return round(self.value_idr * pct / 100)

    def as_dict(self) -> dict:
        return {"order": self.order, "customer": self.customer,
                "finished_good": self.finished_good, "due": self.due.isoformat(),
                "need": self.need, "value_idr": self.value_idr}


@dataclass
class Plan:
    basis: str                             # "penalty" | "value"
    available: float
    serve: List[dict] = field(default_factory=list)
    defer: List[dict] = field(default_factory=list)
    not_competing: List[dict] = field(default_factory=list)
    unknown_need: List[dict] = field(default_factory=list)
    left: float = 0.0
    penalty_plan_idr: Optional[float] = None
    penalty_due_date_order_idr: Optional[float] = None
    saved_idr: Optional[float] = None

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _greedy(claims: List[Claim], available: float, key) -> tuple:
    served, deferred, left = [], [], available
    for c in sorted(claims, key=key):
        if c.need is not None and c.need <= left + 1e-9:
            served.append(c)
            left -= c.need
        else:
            deferred.append(c)
    return served, deferred, round(left, 6)


def allocate(claims: List[Claim], available: float, supply_returns: Optional[date],
             days_to_ship: int = 0) -> Plan:
    """Serve the orders whose lateness costs most per unit of material first.

    supply_returns  the day the material is available again; an order due on
                    or after it (plus days_to_ship) can be made from the new
                    supply and does not compete for what is left. Unknown, and
                    every order competes and no penalty total can be stated.
    days_to_ship    from the material arriving to the order leaving, added to
                    the lateness of every deferred order.
    """
    known = [c for c in claims if c.need is not None and c.need > 0]
    unknown = [c for c in claims if c.need is None]
    ready = supply_returns + timedelta(days=days_to_ship) if supply_returns else None
    competing = [c for c in known if ready is None or c.due < ready]
    later = [c for c in known if ready is not None and c.due >= ready]

    def late(c: Claim) -> Optional[int]:
        return max(0, (ready - c.due).days) if ready else None

    terms = all(c.value_idr is not None and c.penalty_pct_per_day is not None for c in competing)
    basis = "penalty" if terms else "value"

    def weight(c: Claim) -> float:
        # Rounded, so two orders that cost the same per unit tie exactly rather
        # than by floating-point noise. A tie goes to the earlier due date, then
        # the lower order number: the order a planner would read them in.
        rate = (c.value_idr or 0) * ((c.penalty_pct_per_day or 0) if terms else 1)
        return round(rate / c.need, 2)

    served, deferred, left = _greedy(competing, available, lambda c: (-weight(c), c.due, c.order))
    _, fifo_deferred, _ = _greedy(competing, available, lambda c: (c.due, c.order))

    def total(cs: List[Claim]) -> Optional[float]:
        if ready is None:
            return None
        owed = [c.penalty(late(c)) for c in cs]
        return None if any(o is None for o in owed) else float(sum(owed))

    plan = Plan(basis=basis, available=available, left=left,
                not_competing=[c.as_dict() for c in later],
                unknown_need=[c.as_dict() for c in unknown])
    plan.serve = [c.as_dict() for c in sorted(served, key=lambda c: (c.due, c.order))]
    for c in deferred:
        days = late(c)
        plan.defer.append(c.as_dict() | {"days_late": days,
                                         "penalty_idr": c.penalty(days) if days is not None else None})
    plan.penalty_plan_idr = total(deferred)
    plan.penalty_due_date_order_idr = total(fifo_deferred)
    if plan.penalty_plan_idr is not None and plan.penalty_due_date_order_idr is not None:
        plan.saved_idr = plan.penalty_due_date_order_idr - plan.penalty_plan_idr
    return plan


def demo() -> None:
    d = date(2026, 9, 20)
    claims = [
        Claim("SO-1", "C1", "FG", d, 3.0, 1_000_000_000, 0.5, 10.0),
        Claim("SO-2", "C2", "FG", d - timedelta(days=2), 3.0, 200_000_000, 0.5, 10.0),
        Claim("SO-3", "C3", "FG", d, 1.0, 600_000_000, 0.5, 10.0),
        Claim("SO-4", "C4", "FG", d + timedelta(days=30), 2.0, 900_000_000, 0.5, 10.0),
        Claim("SO-5", "C5", "FG", d, None, 50_000_000, 0.5, 10.0),
    ]
    p = allocate(claims, 4.0, d + timedelta(days=6))
    # Penalty per unit: SO-3 600M/1, SO-1 1000M/3, SO-2 200M/3. Four units take SO-3 and SO-1.
    assert [s["order"] for s in p.serve] == ["SO-1", "SO-3"], p.serve
    assert [x["order"] for x in p.defer] == ["SO-2"], p.defer
    # SO-2 waits 8 days: 0.5% a day of Rp 200M is Rp 8M.
    assert p.defer[0]["days_late"] == 8 and p.penalty_plan_idr == 8_000_000, p.defer
    # Due-date order serves SO-2 (earliest) and SO-3, deferring SO-1: 6 days, Rp 30M.
    assert p.penalty_due_date_order_idr == 30_000_000 and p.saved_idr == 22_000_000, p
    assert [x["order"] for x in p.not_competing] == ["SO-4"], "due after supply returns"
    assert [x["order"] for x in p.unknown_need] == ["SO-5"]
    assert p.basis == "penalty" and p.left == 0.0

    # The cap binds: 0.5% for 30 days is 15%, capped at 10%.
    assert claims[0].penalty(30) == 100_000_000

    # No penalty terms: ranked on value, and no rupiah total is claimed.
    bare = [Claim(c.order, c.customer, c.finished_good, c.due, c.need, c.value_idr, None, None)
            for c in claims[:3]]
    v = allocate(bare, 4.0, d + timedelta(days=6))
    assert v.basis == "value" and v.penalty_plan_idr is None and v.saved_idr is None, v

    # Supply return unknown: every order competes, and no lateness can be counted.
    u = allocate(claims, 4.0, None)
    assert "SO-4" in [x["order"] for x in u.serve + u.defer] and u.penalty_plan_idr is None
    print("allocate ok, scarce material to the costliest lateness first ✓ · cap binds ✓ · "
          "no terms → no rupiah claimed ✓ · beats due-date order by Rp 22,000,000 in the check ✓")


if __name__ == "__main__":
    demo()
