"""Clint's tools (Sourcing).

Finds and qualifies replacement supply: other suppliers, internal stock,
expedited shipping.
"""
from __future__ import annotations

from core.provenance import Result
from core.registry import register
from tools.fetcher import pull


@register("find_alternate_sources", "sourcing",
          "Replacement supply options: another supplier, internal stock, or expedited freight.",
          {"material": {"type": "string"}}, ["material"])
def find_alternate_sources(material: str) -> Result:
    return pull("AlternateSource", "API_PURCHASING_INFO_RECORD_SRV", "A_PurchasingInfoRecord",
                {"$top": "50"}, lambda r: r.get("Material") == material)
