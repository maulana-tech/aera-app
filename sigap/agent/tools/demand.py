"""Dara's tools (Demand).

The demand side. Daily consumption is treated as a variable that moves, not a
fixed number copied out of master data.
"""
from __future__ import annotations

from core.provenance import Origin, Result
from core.registry import register
from tools.fetcher import fixture


@register("get_production_schedule", "demand",
          "Production schedule and daily consumption rate for one material at one plant.",
          {"material": {"type": "string"}, "plant": {"type": "string"}},
          ["material", "plant"])
def get_production_schedule(material: str, plant: str) -> Result:
    r = next((x for x in fixture("MaterialStock")
              if x["Material"] == material and x["Plant"] == plant), None)
    if r is None:
        return Result(None, Origin.MISSING, "API_PRODUCTION_ORDER_2_SRV")
    return Result({"material": material, "plant": plant,
                   "daily_consumption": r["DailyConsumption"], "unit": r["BaseUnit"]},
                  Origin.MODELLED, "fixture:MaterialStock")


@register("get_demand_signal", "demand",
          "Customer demand changes not yet reflected in the production schedule.",
          {"material": {"type": "string"}}, ["material"])
def get_demand_signal(material: str) -> Result:
    return Result(None, Origin.MISSING, "SAP IBP demand plan",
                  note="not connected — the SAP sandbox exposes no demand plan")
