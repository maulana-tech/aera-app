"""Iris's tools (Stock Validity).

Stock that is recorded as present is not automatically stock you may use.
This file answers the 'may use' half: quality holds and safety stock.
"""
from __future__ import annotations

from datetime import date

from core.provenance import Origin, Result
from core.registry import register
from tools.fetcher import profile, pull


@register("get_quality_holds", "inventory",
          "Stock that is on the books but blocked pending a quality inspection.",
          {"material": {"type": "string"}, "plant": {"type": "string"}},
          ["material", "plant"])
def get_quality_holds(material: str, plant: str) -> Result:
    return Result([], Origin.MODELLED, "API_INSPECTIONLOT_SRV",
                  note="the fixture carries no quality holds for this scenario")


@register("get_safety_stock_policy", "inventory",
          "The safety stock floor that normal production must not draw down.",
          {"material": {"type": "string"}, "plant": {"type": "string"}},
          ["material", "plant"])
def get_safety_stock_policy(material: str, plant: str) -> Result:
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

    stock = pull("MaterialStock", "API_MATERIAL_STOCK_SRV", "A_MatlStkInAcctMod",
                 {"$top": "500"})
    if not stock.value:
        return Result(None, Origin.MISSING, stock.source, note="no stock records to judge")
    start = date.fromisoformat(profile()["AsOfDate"])
    t = assess(stock.value, material, from_plant, to_plant, qty, start, floor_days)
    return Result(t.as_dict(), stock.origin, stock.source, note=t.reason)
