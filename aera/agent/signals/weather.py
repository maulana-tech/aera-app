"""Severe weather in the forecast, at the ports and plants we depend on.

A typhoon is the extreme case and signals/hazards.py watches for it. Most lost
port days come from weather that never gets a name: a gale that stops the
quay cranes, a sea too rough to put a pilot aboard, a day of rain that floods
the road out of a plant. None of that reaches GDACS. It is all in a weather
forecast, three days before it happens, which is the head start worth having.

Open-Meteo serves the national weather models (ECMWF, GFS, ICON, CMA, JMA and
others) through one free API without a key, and a marine model for wave
height. Every watched place is asked in one request, three days ahead.

The thresholds are judgement calls, named so they can be argued with:

  gusts    62 km/h  the bottom of Beaufort force 8, a gale. Quay cranes are
                    commonly stopped at about 72 km/h of sustained wind, and a
                    gale gusts past that, so this gives warning before the stop.
  waves     4 m     the start of "very rough" on the Douglas sea scale, around
                    where pilot boarding and berthing are suspended.
  rain    100 mm    a day's total. BMKG's "hujan sangat lebat" (very heavy
                    rain) starts here, and it is the band in which Karawang and
                    Bekasi have flooded before.

Ports are judged on all three. Plants are judged on rain only: wind and sea
state do not stop a production line, a flooded access road does.

The forecast figures are live. The places come from the company profile and the
open orders (signals/places.py), and the breach flags are a comparison with the
fixed thresholds above.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional

from clients import feeds
from core.provenance import Origin, Result

FORECAST_URL = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                "&daily=wind_gusts_10m_max,precipitation_sum&forecast_days={days}"
                "&timezone=UTC&wind_speed_unit=kmh")
MARINE_URL = ("https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}"
              "&daily=wave_height_max&forecast_days={days}&timezone=UTC")
FORECAST_DAYS = 3
#: The models behind Open-Meteo update every one to six hours.
TTL, TIMEOUT = 60 * 60, 20

GUST_KMH = 62.0
WAVE_M = 4.0
RAIN_MM = 100.0

#: (field, threshold, what it means, unit, the kinds of place it applies to)
THRESHOLDS = (
    ("gust_kmh", GUST_KMH, "gale-force gusts", "km/h", ("port",)),
    ("wave_m", WAVE_M, "very rough sea", "m", ("port",)),
    ("rain_mm", RAIN_MM, "very heavy rain", "mm", ("port", "plant")),
)


def _url(template: str, places: List[dict]) -> str:
    return template.format(lat=",".join(f"{p['lat']:.4f}" for p in places),
                           lon=",".join(f"{p['lon']:.4f}" for p in places), days=FORECAST_DAYS)


def _rows(body) -> List[dict]:
    """Open-Meteo answers one location with an object and several with a list."""
    return body if isinstance(body, list) else [body]


def _series(daily: dict, field: str) -> Dict[str, Optional[float]]:
    return dict(zip(daily.get("time") or [], daily.get(field) or []))


def breaches(kind: str, day: dict) -> List[dict]:
    out = []
    for field, limit, label, unit, applies in THRESHOLDS:
        v = day.get(field)
        if kind in applies and isinstance(v, (int, float)) and v >= limit:
            out.append({"measure": field, "value": v, "threshold": limit, "unit": unit,
                        "label": label})
    return out


def outlook(places: List[dict]) -> Result:
    """Three days of forecast for each place, with any threshold it crosses.

    Value: {code: {"place": {...}, "days": [{date, gust_kmh, rain_mm, wave_m,
    breaches}]}}. Missing when the forecast cannot be read; a missing marine
    forecast only blanks the wave column and says so.
    """
    if not places:
        return Result({}, Origin.LIVE, "Open-Meteo", note="no places to forecast")
    try:
        body, at = feeds.get(_url(FORECAST_URL, places), ttl=TTL, timeout=TIMEOUT)
        rows = _rows(body)
        if len(rows) != len(places) or not all(isinstance(r, dict) and r.get("daily") for r in rows):
            raise feeds.FeedError(f"asked for {len(places)} places, got {len(rows)} without a "
                                  f"daily forecast: {str(body)[:120]}")
        forecast = [r["daily"] for r in rows]
    except feeds.FeedError as e:
        return Result(None, Origin.MISSING, "Open-Meteo forecast", note=str(e))
    except Exception as e:                                           # noqa: BLE001
        return Result(None, Origin.MISSING, "Open-Meteo forecast",
                      note=f"unreadable: {type(e).__name__}: {e}")

    notes, waves = [], {}
    ports = [p for p in places if p["kind"] == "port"]
    if ports:
        try:
            mbody, _ = feeds.get(_url(MARINE_URL, ports), ttl=TTL, timeout=TIMEOUT)
            mrows = _rows(mbody)
            if len(mrows) != len(ports):
                raise feeds.FeedError(f"asked for {len(ports)} ports, got {len(mrows)}")
            waves = {p["code"]: _series(r.get("daily") or {}, "wave_height_max")
                     for p, r in zip(ports, mrows)}
        except Exception as e:                                       # noqa: BLE001
            notes.append(f"wave heights not read ({e})")

    out, no_sea = {}, []
    for p, daily in zip(places, forecast):
        gust, rain = _series(daily, "wind_gusts_10m_max"), _series(daily, "precipitation_sum")
        sea = waves.get(p["code"], {})
        days = []
        for d in daily.get("time") or []:
            row = {"date": d, "gust_kmh": gust.get(d), "rain_mm": rain.get(d),
                   "wave_m": sea.get(d) if p["kind"] == "port" else None}
            row["breaches"] = breaches(p["kind"], row)
            days.append(row)
        if p["kind"] == "port" and waves and not any(x["wave_m"] is not None for x in days):
            no_sea.append(p["code"])
        out[p["code"]] = {"place": p, "days": days}
    if no_sea:
        notes.append(f"the marine model has no sea state for {', '.join(no_sea)} "
                     "(river or sheltered port)")
    age = feeds.age_note(at)
    if age:
        notes.append(age)
    return Result(out, Origin.LIVE, "Open-Meteo forecast" + (" + marine" if ports else ""),
                  fetched_at=at, note="; ".join(notes))


def _resolve(code: str) -> Optional[dict]:
    from signals import places
    code = (code or "").strip().upper()
    for p in places.watched().value["places"]:
        if p["code"] == code:
            return p
    known = places.port(code)
    return asdict(known) if known else None


def port_conditions(code: str) -> Result:
    """Everything the outside world says about one port or plant right now: the
    three-day forecast against the thresholds, and any current hazard within
    reach of it."""
    from signals import hazards
    place = _resolve(code)
    if place is None:
        return Result(None, Origin.MISSING, "signals/places.py",
                      note=f"{code!r} is not a watched place or a port with known coordinates")
    wx = outlook([place])
    hz = hazards.poll(places=[place])
    if wx.value is None and hz.value is None:
        return Result(None, Origin.MISSING, "Open-Meteo + GDACS + NASA EONET + USGS",
                      note=f"{wx.note}; {hz.note}")
    days = wx.value[place["code"]]["days"] if wx.value else None
    near = [{k: h[k] for k in ("kind", "name", "alert", "severity", "distance_km", "radius_km",
                               "observed_at", "position_from")}
            | {"reported_by": [s["feed"] for s in h["sources"]],
               "url": next((s["url"] for s in h["sources"] if s["url"]), None)}
            for h in (hz.value or {}).get("hits", [])]
    value = {
        "place": {k: place[k] for k in ("code", "kind", "name", "country", "lat", "lon", "why")},
        "forecast": days,
        "thresholds": {f: f"{limit:g} {unit} ({label})" for f, limit, label, unit, applies
                       in THRESHOLDS if place["kind"] in applies},
        "hazards_nearby": near if hz.value is not None else None,
    }
    notes = [n for n in (wx.note, hz.note) if n]
    if wx.value is None:
        # Only the hazard distances survived, and those are computed.
        return Result(value, Origin.DERIVED, "GDACS + NASA EONET + USGS",
                      note="forecast not read: " + "; ".join(notes))
    if hz.value is None:
        notes.append("hazard feeds not reached, so no hazard is not the same as none")
    return Result(value, Origin.LIVE, wx.source + " · GDACS + NASA EONET + USGS",
                  fetched_at=wx.fetched_at, note="; ".join(notes))


# ------------------------------------------------------------------- events
def _title(place: dict) -> str:
    what = "plant" if place["kind"] == "plant" else "port"
    return f"Severe weather forecast at {place['name']} {what} ({place['code']})"[:120]


def _trigger(code: str, first_day: str) -> str:
    return f"Open-Meteo · {code} · from {first_day}"


def as_event(entry: dict) -> dict:
    place = entry["place"]
    bad = [d for d in entry["days"] if d["breaches"]]
    return {
        "kind": "port_weather" if place["kind"] == "port" else "plant_weather",
        "title": _title(place),
        "trigger": _trigger(place["code"], bad[0]["date"]),
        "payload": {"place": place["code"], "place_kind": place["kind"],
                    "place_name": place["name"], "place_why": place["why"],
                    "first_day": bad[0]["date"],
                    "breaches": [{"date": d["date"], **b} for d in bad for b in d["breaches"]],
                    "forecast": entry["days"]},
        "source": "Open-Meteo",
    }


def sweep(raise_event: Callable[[dict], str],
          seen: Optional[Callable[[str, str], bool]] = None,
          places: Optional[List[dict]] = None) -> List[str]:
    """One pass, same contract as signals/watch.sweep.

    One event per place per spell of bad weather. A spell is keyed by its first
    bad day, and a place already raised for any of the days before it inside the
    forecast window is the same spell carrying on, not a new one: a gale forecast
    on Monday for Tuesday to Thursday is still the same gale on Wednesday.
    """
    if seen is None:
        from core import store
        seen = store.event_exists
    if places is None:
        from signals import places as _places
        places = _places.watched().value["places"]
    r = outlook(places)
    if r.value is None:
        return []
    raised = []
    for entry in r.value.values():
        bad = [d for d in entry["days"] if d["breaches"]]
        if not bad:
            continue
        place, first = entry["place"], date.fromisoformat(bad[0]["date"])
        earlier = (first - timedelta(days=k) for k in range(FORECAST_DAYS))
        if any(seen(_title(place), _trigger(place["code"], d.isoformat())) for d in earlier):
            continue
        raised.append(raise_event(as_event(entry)))
    return raised


# --------------------------------------------------------------- self-check
#: Recorded 24 Oct 2026 for CNNGB, KRPUS, VNSGN and the Karawang plant: Champi's
#: outer gale over Ningbo, a front's rain over Busan, a river port the marine
#: model cannot see.
SAMPLE_FORECAST = [
    {"daily": {"time": ["2026-10-24", "2026-10-25", "2026-10-26"],
               "wind_gusts_10m_max": [79.2, 79.6, 45.0], "precipitation_sum": [42.9, 2.8, 0.0]}},
    {"daily": {"time": ["2026-10-24", "2026-10-25", "2026-10-26"],
               "wind_gusts_10m_max": [45.4, 67.3, 71.3], "precipitation_sum": [117.0, 113.4, 5.0]}},
    {"daily": {"time": ["2026-10-24", "2026-10-25", "2026-10-26"],
               "wind_gusts_10m_max": [25.2, 23.4, 26.3], "precipitation_sum": [0.0, 0.1, 0.0]}},
    {"daily": {"time": ["2026-10-24", "2026-10-25", "2026-10-26"],
               "wind_gusts_10m_max": [70.0, 30.1, 28.0], "precipitation_sum": [12.0, 3.4, 0.0]}},
]
SAMPLE_MARINE = [
    {"daily": {"time": ["2026-10-24", "2026-10-25", "2026-10-26"], "wave_height_max": [1.3, 1.28, 0.64]}},
    {"daily": {"time": ["2026-10-24", "2026-10-25", "2026-10-26"], "wave_height_max": [1.08, 1.54, 1.5]}},
    {"daily": {"time": ["2026-10-24", "2026-10-25", "2026-10-26"], "wave_height_max": [None, None, None]}},
]


def demo() -> None:
    from signals.places import port
    ports = [asdict(port(c)) for c in ("CNNGB", "KRPUS", "VNSGN")]
    plant = {"code": "KRW1", "kind": "plant", "name": "Karawang", "lat": -6.3227,
             "lon": 107.3376, "country": "ID", "why": "company plant"}
    places = ports + [plant]
    feeds.prime(_url(FORECAST_URL, places), SAMPLE_FORECAST)
    feeds.prime(_url(MARINE_URL, ports), SAMPLE_MARINE)
    try:
        r = outlook(places)
        assert r.origin is Origin.LIVE, r
        ngb, pus, sgn, krw = (r.value[c] for c in ("CNNGB", "KRPUS", "VNSGN", "KRW1"))
        assert [b["measure"] for b in ngb["days"][0]["breaches"]] == ["gust_kmh"]
        assert {b["measure"] for b in pus["days"][0]["breaches"]} == {"rain_mm"}
        assert {b["measure"] for b in pus["days"][1]["breaches"]} == {"gust_kmh", "rain_mm"}
        assert not any(d["breaches"] for d in sgn["days"])
        assert not any(d["breaches"] for d in krw["days"]), "wind does not stop a plant"
        assert "VNSGN" in r.note, "a port with no sea state says so"

        raised: List[dict] = []
        recorded: set = set()

        def fake_raise(body: dict) -> str:
            raised.append(body)
            recorded.add((body["title"], body["trigger"]))
            return f"evt_{len(raised)}"

        def seen(title: str, trigger: str) -> bool:
            return (title, trigger) in recorded

        first = sweep(fake_raise, seen=seen, places=places)
        assert first == ["evt_1", "evt_2"], first
        assert raised[0]["kind"] == "port_weather" and "CNNGB" in raised[0]["title"]
        assert raised[0]["payload"]["first_day"] == "2026-10-24"
        assert sweep(fake_raise, seen=seen, places=places) == [], "one event per spell"

        # A day later the gale is still forecast, now starting on the 25th: the
        # same spell, already raised on the 24th.
        later = [dict(x, daily=dict(x["daily"], time=["2026-10-25", "2026-10-26", "2026-10-27"]))
                 for x in SAMPLE_FORECAST]
        feeds.prime(_url(FORECAST_URL, places), later)
        feeds.forget(_url(MARINE_URL, ports))
        feeds.prime(_url(MARINE_URL, ports), [])                 # marine down
        assert sweep(fake_raise, seen=seen, places=places) == [], "a continuing spell is not new"
        r2 = outlook(places)
        assert r2.origin is Origin.LIVE and all(d["wave_m"] is None for d in r2.value["CNNGB"]["days"])
        assert "wave heights not read" in r2.note, r2.note

        feeds.forget(_url(FORECAST_URL, places))
        feeds.prime(_url(FORECAST_URL, places), {"error": True})
        assert outlook(places).origin is Origin.MISSING, "a reshaped answer is a missing forecast"
        assert sweep(fake_raise, seen=seen, places=places) == []
    finally:
        feeds.forget(_url(FORECAST_URL, places))
        feeds.forget(_url(MARINE_URL, ports))
    print("weather ok: gale at CNNGB and rain at KRPUS flagged ✓ · plant judged on rain only ✓ "
          "· no sea state said, not zeroed ✓ · one event per spell ✓ · bad answer is missing ✓")


if __name__ == "__main__":
    demo()
