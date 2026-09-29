"""Demand forecasting. Arithmetic, like everything else that produces a number.

Every cover date in this system divides stock by a single figure taken from
master data. Nobody checks whether that figure is still true. For M-4471 at
KRW1 it is not: the plan says 9.2 tonnes a day and the last month averaged
10.1, which moves the stockout date and changes which options bridge the gap.

Holt's linear trend over a deseasonalised series, with weekly seasonal indices
and prediction intervals from in-sample one-step errors. Textbook, pure Python,
no model. The point of a forecast here is not a prettier number; it is a range,
because a plan built on a point estimate is a plan that has not admitted what
it does not know.

Refuses rather than guesses when the history is too short to say anything.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional, Sequence, Tuple

WEEK = 7
MIN_DAYS = 28                    # under four weeks there is no weekly shape to find
ALPHA, BETA = 0.25, 0.08         # level and trend smoothing
Z = {80: 1.282, 90: 1.645, 95: 1.960}


@dataclass
class Point:
    on: str
    point: float
    lower: float
    upper: float


@dataclass
class Forecast:
    refused: bool
    reason: str = ""
    material: str = ""
    plant: str = ""
    unit: str = ""
    planned_rate: Optional[float] = None
    observed_rate: Optional[float] = None
    drift_pct: Optional[float] = None
    confidence: int = 90
    horizon_days: int = 0
    points: List[Point] = field(default_factory=list)
    mape_pct: Optional[float] = None
    weekly_shape: List[float] = field(default_factory=list)

    def as_dict(self) -> dict:
        # mean_rate is a property, so it has to be added explicitly. It is the
        # figure anyone comparing against the planned rate actually wants.
        return {**self.__dict__, "points": [p.__dict__ for p in self.points],
                "mean_rate": self.mean_rate}

    @property
    def mean_rate(self) -> Optional[float]:
        if not self.points:
            return None
        return round(sum(p.point for p in self.points) / len(self.points), 2)

    def band_at(self, day: int) -> Tuple[float, float]:
        p = self.points[min(day, len(self.points) - 1)]
        return p.lower, p.upper


def _seasonal_indices(series: Sequence[Tuple[date, float]]) -> List[float]:
    """Average ratio of each weekday to the overall mean."""
    overall = sum(v for _, v in series) / len(series)
    if overall <= 0:
        return [1.0] * WEEK
    buckets: List[List[float]] = [[] for _ in range(WEEK)]
    for d, v in series:
        buckets[d.weekday()].append(v / overall)
    idx = [sum(b) / len(b) if b else 1.0 for b in buckets]
    # Normalise so the week averages to one and the level carries the scale.
    mean = sum(idx) / WEEK
    return [i / mean if mean else 1.0 for i in idx]


def forecast(
    series: Sequence[Tuple[date, float]],
    horizon_days: int = 30,
    confidence: int = 90,
    planned_rate: Optional[float] = None,
    material: str = "",
    plant: str = "",
    unit: str = "",
) -> Forecast:
    series = sorted(series, key=lambda t: t[0])
    if len(series) < MIN_DAYS:
        return Forecast(True,
                        f"{len(series)} days of history, at least {MIN_DAYS} are needed "
                        "before a weekly pattern can be separated from noise",
                        material, plant, unit, planned_rate)
    if confidence not in Z:
        confidence = 90

    idx = _seasonal_indices(series)
    deseasonalised = [v / idx[d.weekday()] if idx[d.weekday()] else v for d, v in series]

    # Holt's linear trend, with one-step errors kept for the interval.
    level = deseasonalised[0]
    trend = (deseasonalised[min(WEEK, len(deseasonalised) - 1)] - deseasonalised[0]) / WEEK
    errors: List[float] = []
    actuals: List[float] = []
    for i in range(1, len(deseasonalised)):
        predicted = level + trend
        errors.append(deseasonalised[i] - predicted)
        actuals.append(series[i][1])
        prev_level = level
        level = ALPHA * deseasonalised[i] + (1 - ALPHA) * (level + trend)
        trend = BETA * (level - prev_level) + (1 - BETA) * trend

    n = len(errors)
    sigma = math.sqrt(sum(e * e for e in errors) / n) if n else 0.0
    absolute = [abs(e) for e in errors]
    mape = (sum(a / v for a, v in zip(absolute, actuals) if v > 0)
            / max(sum(1 for v in actuals if v > 0), 1) * 100)

    last = series[-1][0]
    z = Z[confidence]
    points: List[Point] = []
    for h in range(1, horizon_days + 1):
        day = last + timedelta(days=h)
        base = max(level + h * trend, 0.0)
        value = base * idx[day.weekday()]
        # Uncertainty compounds with the horizon, which is why a thirty day
        # band is wider than a three day one.
        spread = z * sigma * math.sqrt(h) * idx[day.weekday()]
        points.append(Point(day.isoformat(), round(value, 2),
                            round(max(value - spread, 0.0), 2),
                            round(value + spread, 2)))

    recent = [v for _, v in series[-28:]]
    observed = round(sum(recent) / len(recent), 2)
    drift = round((observed / planned_rate - 1) * 100, 1) if planned_rate else None

    return Forecast(False, "", material, plant, unit, planned_rate, observed, drift,
                    confidence, horizon_days, points, round(mape, 1),
                    [round(i, 3) for i in idx])


def demo() -> None:
    import json
    import pathlib

    here = pathlib.Path(__file__).resolve().parent.parent
    history = json.loads((here / "fixtures" / "consumption_history.json").read_text())
    fx = json.loads((here / "fixtures" / "ningbo_scenario.json").read_text())

    rows = [(date.fromisoformat(h["Date"]), h["Quantity"]) for h in history
            if h["Material"] == "M-4471" and h["Plant"] == "KRW1"]
    planned = next(r["DailyConsumption"] for r in fx["MaterialStock"]
                   if r["Material"] == "M-4471" and r["Plant"] == "KRW1")

    f = forecast(rows, 30, 90, planned, "M-4471", "KRW1", "TON")
    assert not f.refused, f.reason
    assert f.observed_rate > planned, (f.observed_rate, planned)
    assert f.drift_pct and f.drift_pct > 5, f.drift_pct
    assert f.mape_pct is not None and f.mape_pct < 25, f.mape_pct
    assert len(f.points) == 30

    # The band has to widen with the horizon or it is not an interval.
    first, last = f.points[0], f.points[-1]
    assert (last.upper - last.lower) > (first.upper - first.lower)
    for p in f.points:
        assert p.lower <= p.point <= p.upper, p
        assert p.lower >= 0, p

    # Sunday is a rest day, so the weekly shape has to show it.
    assert min(f.weekly_shape) == f.weekly_shape[6], f.weekly_shape
    assert f.as_dict()["mean_rate"] == f.mean_rate, "mean_rate missing from the dict"

    # Too little history is refused, not smoothed over.
    short = forecast(rows[-10:], 30, 90, planned)
    assert short.refused and "at least" in short.reason

    print("forecast ok")
    print(f"  planned   {planned}/day from master data")
    print(f"  observed  {f.observed_rate}/day over the last 28 days, "
          f"{f.drift_pct:+.1f}%")
    print(f"  next 30d  mean {f.mean_rate}/day, in-sample MAPE {f.mape_pct}%")
    lo, hi = f.band_at(6)
    print(f"  day 7     {f.points[6].point} ({lo} to {hi}) at {f.confidence}%")
    print(f"  week      {' '.join(f'{i:.2f}' for i in f.weekly_shape)}")


if __name__ == "__main__":
    demo()
