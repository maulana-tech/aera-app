"""Clint's tools (Sourcing).

Finds and qualifies replacement supply: other suppliers, internal stock,
expedited shipping.
"""
from __future__ import annotations

from datetime import date

from core.provenance import Origin, Result
from core.registry import register
from tools.fetcher import profile, pull


@register("find_alternate_sources", "sourcing",
          "Replacement supply options: another supplier, internal stock, or expedited freight.",
          {"material": {"type": "string"}}, ["material"])
def find_alternate_sources(material: str) -> Result:
    return pull("AlternateSource", "API_PURCHASING_INFO_RECORD_SRV", "A_PurchasingInfoRecord",
                {"$top": "50"}, lambda r: r.get("Material") == material)


@register("find_internal_transfers", "sourcing",
          "Plants that could send a material to one that is short, with what each "
          "transfer would cost the plant sending it. Returns the ones that break the "
          "donor as well as the ones that do not, because an option removed silently "
          "cannot be argued with.",
          {"material": {"type": "string"}, "to_plant": {"type": "string"},
           "need_qty": {"type": "number"},
           "floor_days": {"type": "integer", "description": "donor safety floor, default 14"}},
          ["material", "to_plant", "need_qty"])
def find_internal_transfers(material: str, to_plant: str, need_qty: float,
                            floor_days: int = 14) -> Result:
    from engine.matching import find

    stock = pull("MaterialStock", "API_MATERIAL_STOCK_SRV", "A_MatlStkInAcctMod",
                 {"$top": "500"})
    if not stock.value:
        return Result(None, Origin.MISSING, stock.source, note="no stock to transfer from")
    start = date.fromisoformat(profile()["AsOfDate"])
    found = find(stock.value, material, to_plant, need_qty, start, floor_days)
    return Result([t.as_dict() for t in found], stock.origin, stock.source,
                  note=f"{sum(1 for t in found if t.verdict == 'available')} of "
                       f"{len(found)} donor plants can afford it")
