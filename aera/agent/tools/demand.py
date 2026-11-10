"""Dara's tools (Demand).

The demand side. Daily consumption is treated as a variable that moves, not a
fixed number copied out of master data.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date
from typing import List, Optional, Tuple

from core.provenance import Origin, Result
from core.registry import register
from tools.fetcher import read

HISTORY = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "consumption_history.json"
_cache: Optional[list] = None


def _history(material: str, plant: str) -> List[Tuple[date, float]]:
    """Daily withdrawals, from their own file: thousands of rows only this reads."""
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
    return Result(None, Origin.MISSING, "demand plan",
                  note="a demand plan is not connected")


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

    series = _history(material, plant)
    if not series:
        return Result(None, Origin.MISSING,
                      "fixtures/consumption_history.json",
                      note=f"no withdrawal history for {material} at {plant}")

    row = next(iter(read("MaterialStock", material=material, plant=plant).value or []), None)
    planned = (float(row["DailyConsumption"])
               if row and row.get("DailyConsumption") is not None else None)
    unit = row.get("BaseUnit", "") if row else ""

    f = forecast(series, horizon_days, confidence, planned, material, plant, unit)
    if f.refused:
        return Result({"refused": True, "reason": f.reason}, Origin.MISSING,
                      "engine/forecast.py", note=f.reason)

    note = (f"planned {planned} {unit}/day, forecast mean "
            f"{f.mean_rate} {unit}/day over {horizon_days} days")
    if f.drift_pct is not None and abs(f.drift_pct) >= 5:
        note += (f". The last 28 days ran {f.observed_rate}, {f.drift_pct:+.1f}% against "
                 "plan, so every cover date computed from the planned rate is optimistic"
                 if f.drift_pct > 0 else
                 f". The last 28 days ran {f.observed_rate}, {f.drift_pct:+.1f}% against plan")
    # Derived from history the same way the calculator derives a cover date.
    return Result(f.as_dict(), Origin.DERIVED, "engine/forecast.py", note=note)


def demo() -> None:
    """Dara's point is that daily consumption moves. So the check is that a
    forecast is derived, says what it is against, and refuses when it cannot."""
    sched = get_production_schedule("M-4471", "SBY1")
    assert sched.value and sched.value["daily_consumption"] == 9.6, sched.brief()
    assert sched.value["unit"] == "TON" and not sched.trusted, sched.brief()

    # A material at a plant that holds none has no schedule, and says so
    # rather than reporting a rate of zero.
    assert get_production_schedule("M-4471", "CKR1").origin is Origin.MISSING

    # No demand plan is connected, and that is stated rather than filled in.
    signal = get_demand_signal("M-4471")
    assert signal.origin is Origin.MISSING and "not connected" in signal.note

    # 120 days of withdrawals on file. The forecast is DERIVED - computed from
    # history, not read anywhere - and names the planned rate it is judged
    # against, because that is the figure every cover date is divided by.
    f = forecast_demand("M-4471", "SBY1", horizon_days=30)
    assert f.origin is Origin.DERIVED and f.source == "engine/forecast.py", f.brief()
    v = f.value
    assert not v.get("refused"), v
    assert v["mean_rate"] > 0 and len(v["points"]) == 30, v["mean_rate"]
    assert all(p["lower"] <= p["point"] <= p["upper"] for p in v["points"]), v["points"][:2]
    assert "planned 9.6 TON/day" in f.note, f.note
    assert "forecast mean" in f.note, f.note

    # The sentence worth having: history is running 10.5% above the planned
    # rate, so every cover date in the system is divided by too small a number.
    assert v["planned_rate"] == 9.6 and v["observed_rate"] > v["planned_rate"], v
    assert v["drift_pct"] >= 5 and "optimistic" in f.note, f.note

    # A wider interval cannot be narrower. 95% must contain 80%, point for point.
    narrow = forecast_demand("M-4471", "SBY1", confidence=80).value
    wide = forecast_demand("M-4471", "SBY1", confidence=95).value
    assert narrow["confidence"] == 80 and wide["confidence"] == 95
    widths = [(w["upper"] - w["lower"], n["upper"] - n["lower"])
              for w, n in zip(wide["points"], narrow["points"])]
    assert all(w >= n for w, n in widths), widths[:3]
    assert any(w > n for w, n in widths), "95% that equals 80% everywhere is not an interval"

    # No history is a gap that names itself, not a flat line through zero.
    none = forecast_demand("M-4471", "NOWHERE")
    assert none.origin is Origin.MISSING and none.value is None, none.brief()
    assert "no withdrawal history" in none.note, none.note

    # Too little history refuses out loud instead of extrapolating from noise.
    short = _history("M-4471", "SBY1")[:3]
    was = globals()["_history"]
    globals()["_history"] = lambda m, p: short
    try:
        thin = forecast_demand("M-4471", "SBY1")
    finally:
        globals()["_history"] = was
    assert thin.value.get("refused") and thin.origin is Origin.MISSING, thin.brief()

    print(f"  schedule 9.6 TON/day ✓ · IBP absence stated ✓")
    print(f"  forecast derived, {v['mean_rate']} against planned 9.6, "
          f"drift {v['drift_pct']:+.1f}% called optimistic ✓ · 95% contains 80% ✓")
    print("  no history refuses ✓ · three days of history refuses ✓")
    print("demand ok")


if __name__ == "__main__":
    from core.config import fixtures_only

    fixtures_only(__file__, "AERA_DEMAND_CHECK")
    demo()
