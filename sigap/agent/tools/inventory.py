"""Iris's tools (Stock Validity).

Stock that is recorded as present is not automatically stock you may use.
This file answers the 'may use' half: quality holds and safety stock.
"""
from __future__ import annotations

from core.provenance import Origin, Result
from core.registry import register


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
                  note="not in the fixture — needs the customer's own master data")
