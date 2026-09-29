"""Live seismic and weather signal from BMKG.

This is the only external source in the system that needs no credential and is
reachable right now: data.bmkg.go.id publishes JSON, free, no registration.
Everything else we read is either a fixture or waiting on an API key.

It matters for one reason. Every figure on every screen today is labelled
modelled, because it came from a fixture. A quake that BMKG published this
morning, landing 40 km from a plant, is labelled live, and the difference is
the whole point of the origin system.

BMKG covers Indonesian territory. It is not a source for the East China Sea,
which is where the Ningbo typhoon sits. See DATA-SOURCES.md section 5.

    python3 signals/bmkg.py           # show what the feed says right now
    python3 signals/bmkg.py --raise   # and POST anything worth handling
"""
from __future__ import annotations

import json
import math
import sys
import urllib.request
from typing import List, Optional

from core.provenance import Origin, Result
from tools.fetcher import profile

FEED = "https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.json"
TIMEOUT = 15

# BMKG returns 403 to urllib's default agent string. Identify the caller
# properly instead, which is what a public feed is entitled to ask for.
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SIGAP/0.1 (supply disruption response; +https://github.com/)",
}

# A quake far away, or a small one nearby, is not a supply disruption. These
# are the thresholds at which a planner would want to be told; they are a
# judgement call and belong in a config once someone has an opinion.
NEAR_KM = 300.0
MIN_MAGNITUDE = 5.0


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance. Earth is close enough to a sphere at this scale."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def recent_quakes() -> Result:
    """The last fifteen quakes of M5.0 and above, from BMKG."""
    try:
        req = urllib.request.Request(FEED, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = json.loads(r.read().decode())
    except Exception as e:                                           # noqa: BLE001
        # A feed we cannot reach is not a feed that says all is well.
        return Result(None, Origin.MISSING, FEED, note=f"{type(e).__name__}: {e}")

    rows = []
    for q in body.get("Infogempa", {}).get("gempa", []):
        try:
            lat, lon = (float(x) for x in q["Coordinates"].split(","))
        except (KeyError, ValueError):
            continue
        rows.append({
            "at": q.get("DateTime"),
            "magnitude": float(q.get("Magnitude", 0) or 0),
            "depth": q.get("Kedalaman"),
            "region": q.get("Wilayah"),
            "tsunami": q.get("Potensi"),
            "lat": lat, "lon": lon,
        })
    return Result(rows, Origin.LIVE, FEED)


def near_facilities(quakes: List[dict], radius_km: float = NEAR_KM,
                    min_magnitude: float = MIN_MAGNITUDE) -> List[dict]:
    """Which quakes landed close enough to a plant or port to matter."""
    facilities = profile().get("Facilities", [])
    hits = []
    for q in quakes:
        if q["magnitude"] < min_magnitude:
            continue
        for f in facilities:
            d = _km(q["lat"], q["lon"], f["lat"], f["lon"])
            if d <= radius_km:
                hits.append({**q, "facility": f["code"], "facility_kind": f["kind"],
                             "facility_name": f["name"], "distance_km": round(d)})
    hits.sort(key=lambda h: h["distance_km"])
    return hits


def as_event(hit: dict) -> dict:
    """The shape POST /events expects."""
    what = "plant" if hit["facility_kind"] == "plant" else "port"
    return {
        "kind": "seismic",
        "title": (f"M{hit['magnitude']} quake {hit['distance_km']} km from "
                  f"{hit['facility_name']} {what}"),
        "trigger": f"BMKG: {hit['region']}, {hit['at']}",
        "payload": {
            "facility": hit["facility"], "magnitude": hit["magnitude"],
            "distance_km": hit["distance_km"], "depth": hit["depth"],
            "region": hit["region"], "tsunami": hit["tsunami"],
        },
        "source": FEED,
    }


def poll(raise_events: bool = False, api: str = "http://127.0.0.1:8787") -> dict:
    r = recent_quakes()
    if r.value is None:
        return {"origin": r.origin.value, "note": r.note, "quakes": 0, "hits": []}

    hits = near_facilities(r.value)
    raised: List[str] = []
    if raise_events:
        for h in hits:
            body = json.dumps(as_event(h)).encode()
            req = urllib.request.Request(f"{api}/events", data=body, method="POST",
                                         headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raised.append(json.loads(resp.read().decode())["run_id"])

    return {"origin": r.origin.value, "note": r.note, "quakes": len(r.value),
            "hits": hits, "raised": raised}


def demo() -> None:
    out = poll()
    if out["origin"] == "missing":
        # Offline is a legitimate outcome, not a failed check. The point of the
        # origin label is that we say which one we got.
        print(f"bmkg unreachable, {out['note']}")
        print("  the feed is live data, so a check that needs the network can miss it")
        return

    assert out["quakes"] > 0, "BMKG returned an empty list, which it never does"
    facilities = {f["code"] for f in profile().get("Facilities", [])}
    assert facilities, "the profile carries no facilities to measure against"
    for h in out["hits"]:
        assert h["facility"] in facilities, h
        assert h["distance_km"] <= NEAR_KM, h
        assert h["magnitude"] >= MIN_MAGNITUDE, h

    # The distance maths has to be right or the whole filter is noise.
    assert 600 < _km(-6.3227, 107.3376, -7.2575, 112.7521) < 615, "Karawang to Surabaya"
    assert 50 < _km(-6.3227, 107.3376, -6.1045, 106.8816) < 62, "Karawang to Priok"

    print(f"bmkg ok, {out['quakes']} quakes live from BMKG, "
          f"{len(out['hits'])} within {NEAR_KM:.0f} km of a facility")
    for h in out["hits"][:3]:
        print(f"  M{h['magnitude']} {h['distance_km']} km from {h['facility']}, {h['region']}")
    if not out["hits"]:
        print("  nothing near a facility today, which is the usual answer")


if __name__ == "__main__":
    if "--raise" in sys.argv:
        out = poll(raise_events=True)
        print(f"{len(out['raised'])} events raised: {', '.join(out['raised']) or 'none'}")
    else:
        demo()
