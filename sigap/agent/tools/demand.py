"""Dara's tools (Demand).

The demand side. Daily consumption is treated as a variable that moves, not a
fixed number copied out of master data.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date
from typing import List, Optional, Tuple

from clients import sap_s4
from core.provenance import Origin, Result
from core.registry import register
from tools.fetcher import read

HISTORY = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "consumption_history.json"
_cache: Optional[list] = None


def _history(material: str, plant: str) -> List[Tuple[date, float]]:
    """Daily withdrawals. With SAP, the goods issues of the last 90 days; without
    it, its own file: thousands of rows only this reads."""
    if sap_s4.available():
        from clients import sap_map
        return sap_map.consumption_series(material, plant)
    global _cache
    if _cache is None:
        _cache = json.loads(HISTORY.read_text()) if HISTORY.exists() else []
    return [(date.fromisoformat(h["Date"]), float(h["Quantity"])) for h in _cache
            if h["Material"] == material and h["Plant"] == plant]


@register("get_production_schedule", "demand",
          "Production schedule and daily consumption rate for one material at one plant.",
          {"material": {"type": "string"}, "plant": {"type": "string"}},
          ["material", "plant"])
def get_production_schedule(material: str, plant: str) -> Result:
    stock = read("MaterialStock", material=material, plant=plant)
    r = next(iter(stock.value or []), None)
    if r is None or r.get("DailyConsumption") is None:
        return Result(None, Origin.MISSING, "API_PRODUCTION_ORDER_2_SRV",
                      note=stock.note if r is not None else "")
    return Result({"material": material, "plant": plant,
                   "daily_consumption": r["DailyConsumption"], "unit": r["BaseUnit"]},
                  stock.origin, stock.source, note=stock.note)


@register("get_demand_signal", "demand",
          "Customer demand changes not yet reflected in the production schedule.",
          {"material": {"type": "string"}}, ["material"])
def get_demand_signal(material: str) -> Result:
    return Result(None, Origin.MISSING, "SAP IBP demand plan",
                  note="not connected. The SAP sandbox exposes no demand plan")


@register("forecast_demand", "demand",
          "Forecast daily consumption for a material at a plant from its withdrawal "
          "history, with a prediction interval. Compares the result against the planned "
          "rate in master data, which is the figure every cover date in the system is "
          "currently divided by. Deterministic: Holt's linear trend over a deseasonalised "
          "series, no model. Refuses when the history is too short to say anything.",
          {"material": {"type": "string"}, "plant": {"type": "string"},
           "horizon_days": {"type": "integer", "description": "days ahead, default 30"},
           "confidence": {"type": "integer", "description": "80, 90 or 95. Default 90"}},
          ["material", "plant"])
def forecast_demand(material: str, plant: str, horizon_days: int = 30,
                    confidence: int = 90) -> Result:
    from engine.forecast import forecast

    live = sap_s4.available()
    series = _history(material, plant)
    if not series:
        return Result(None, Origin.MISSING,
                      "API_MATERIAL_DOCUMENT_SRV" if live else "fixtures/consumption_history.json",
                      note=f"no withdrawal history for {material} at {plant}")

    row = next(iter(read("MaterialStock", material=material, plant=plant).value or []), None)
    planned = (float(row["DailyConsumption"])
               if row and row.get("DailyConsumption") is not None else None)
    unit = row.get("BaseUnit", "") if row else ""

    f = forecast(series, horizon_days, confidence, planned, material, plant, unit)
    if f.refused:
        return Result({"refused": True, "reason": f.reason}, Origin.MISSING,
                      "engine/forecast.py", note=f.reason)

    # SAP holds no planned rate; the one beside the forecast is the 90-day average.
    note = (f"{'90-day average' if live else 'planned'} {planned} {unit}/day, forecast mean "
            f"{f.mean_rate} {unit}/day over {horizon_days} days")
    if f.drift_pct is not None and abs(f.drift_pct) >= 5:
        note += (f". The last 28 days ran {f.observed_rate}, {f.drift_pct:+.1f}% against "
                 "plan, so every cover date computed from the planned rate is optimistic"
                 if f.drift_pct > 0 else
                 f". The last 28 days ran {f.observed_rate}, {f.drift_pct:+.1f}% against plan")
    # Derived from history the same way the calculator derives a cover date.
    return Result(f.as_dict(), Origin.DERIVED, "engine/forecast.py", note=note)
