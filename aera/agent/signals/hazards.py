"""Natural hazards near the supply chain, from three public feeds.

BMKG answers one question, a quake in Indonesia, and the disruption this
system was built around (a typhoon closing Ningbo) is not one BMKG can see.
These feeds cover the rest of the map, free and without a key:

  GDACS       the UN/EC Global Disaster Alert and Coordination System. Cyclones,
              floods, quakes, eruptions, fires and droughts, each graded Green,
              Orange or Red for humanitarian impact. Read from its RSS file,
              which answers in seconds; its JSON API took 50 s to time-out in
              testing. Cyclone tracks come from JTWC, flood extents from
              satellite microwave (GFDS).
  NASA EONET  the Earth Observatory Natural Event Tracker: events NASA's
              satellite imagery shows, with the latest observed position. For a
              cyclone that is the JTWC fix every six hours, which is fresher than
              the GDACS episode, so a moving storm is placed where it is now.
  USGS        quakes of M5.5 and above worldwide, for the places BMKG does not
              cover (ports in China, Japan, Korea and the rest).

One storm shows up in two feeds under two names ("Tropical Cyclone CHAMPI-26",
"Super Typhoon Champi"). They are fused into one hazard before anything is
measured, so a typhoon raises one event, not two handlings that each spend a
model call deciding the same thing.

The positions are live. The list of places they are measured against comes
from the company profile and the open orders, so a hit is labelled derived:
computed from live data, against a list that is only as real as the records.
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from clients import feeds
from core.provenance import Origin, Result

GDACS_URL = "https://www.gdacs.org/xml/rss.xml"
EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=20"
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"

#: About 1 MB, a static file regenerated every few minutes.
GDACS_TIMEOUT, GDACS_TTL = 30, 30 * 60
EONET_TIMEOUT, EONET_TTL = 30, 30 * 60
USGS_TIMEOUT, USGS_TTL = 30, 15 * 60

#: How close a hazard has to be to a place before it is our problem. A judgement
#: call per kind, set by how far the damage reaches rather than by the point the
#: feed reports:
#:   cyclone  600 km  a typhoon's gale field and the port closures ahead of it
#:                    reach several hundred km; at 600 km there is a day or two
#:                    to act, which is the point of watching
#:   flood    150 km  river basins and the roads out of a plant
#:   quake    300 km  the same radius signals/bmkg.py uses
#:   volcano  100 km  ash fall and exclusion zones
#:   wildfire  50 km  smoke and closed roads
#:   drought  300 km  GDACS places a drought at the centroid of a large area, so
#:                    this is coarse by nature
RADIUS_KM = {"tropical_cyclone": 600, "flood": 150, "earthquake": 300,
             "volcano": 100, "wildfire": 50, "drought": 300}

GDACS_KIND = {"TC": "tropical_cyclone", "FL": "flood", "EQ": "earthquake",
              "VO": "volcano", "WF": "wildfire", "DR": "drought"}
#: The lowest GDACS grade worth reading, per type. The grade measures people
#: affected, not ports closed: a Green cyclone still stops a port, so every
#: cyclone, flood and eruption is read. A Green wildfire is small, a Green quake
#: is moderate (and USGS reports it anyway), and a drought is slow, so for those
#: only Orange and Red. GDACS lists some 250 Green wildfires on a normal day.
_GRADE = {"Green": 1, "Orange": 2, "Red": 3}
GDACS_MIN_GRADE = {"TC": 1, "FL": 1, "VO": 1, "EQ": 2, "WF": 2, "DR": 2}
_NS = {"gdacs": "http://www.gdacs.org", "georss": "http://www.georss.org/georss"}
EONET_KIND = {"severeStorms": "tropical_cyclone", "floods": "flood", "earthquakes": "earthquake",
              "volcanoes": "volcano", "wildfires": "wildfire", "drought": "drought"}

#: USGS lists every M4.5 in the world. Below M5.5 a quake far from a fault we
#: know about rarely closes a port; BMKG's own threshold is M5.0 inside Indonesia.
#: A quake near an Indonesian place is BMKG's to raise (signals/bmkg.py), from
#: whichever feed it comes, so it is never raised twice under two kinds.
USGS_MIN_MAGNITUDE = 5.5

#: A sighting older than this is history, not a hazard: GDACS keeps months of
#: events in the same list, and EONET keeps a wildfire open for weeks.
MAX_AGE_DAYS = 3

#: Which feed's id names a fused hazard, per kind: the feed that sees the most of
#: that kind, so the id does not change when a second feed starts reporting it.
#: EONET lists every cyclone from its first fix; GDACS only once it turns Orange.
ID_PREFERENCE = {"tropical_cyclone": ("EONET", "GDACS"), "earthquake": ("USGS", "GDACS", "EONET")}
DEFAULT_PREFERENCE = ("GDACS", "EONET", "USGS")

#: Two feeds' reports of one quake: the agencies' epicentres differ by tens of
#: km, their origin times by seconds.
QUAKE_SAME_KM, QUAKE_SAME_MINUTES = 100, 3

#: Words that say what a hazard is rather than which one it is.
_GENERIC = {"tropical", "cyclone", "typhoon", "super", "hurricane", "storm", "severe",
            "earthquake", "flood", "floods", "eruption", "forest", "fires", "fire",
            "wildfire", "drought", "volcano", "prescribed", "the", "and", "of", "in"}


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _when(raw: Any) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):                        # USGS: ms since epoch
        return datetime.fromtimestamp(raw / 1000, tz=timezone.utc)
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        try:
            t = parsedate_to_datetime(str(raw))             # GDACS RSS: RFC 822
        except (TypeError, ValueError):
            return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- the feeds
def _gdacs_name(kind: str, item: ET.Element) -> str:
    """'Tropical cyclone CHAMPI-26' when GDACS names the event, otherwise its
    own title cut before the date: 'Earthquake (Magnitude 5.9M, ...) in Vanuatu'."""
    named = (item.findtext("gdacs:eventname", "", _NS) or "").strip()
    if named:
        return f"{kind.replace('_', ' ').capitalize()} {named}"
    title = re.sub(r"^(Green|Orange|Red)\s+", "", (item.findtext("title") or "").strip())
    title = re.split(r"\s+\d{1,2}/\d{1,2}/\d{4}", title)[0].rstrip(" ,")
    return (title[:1].upper() + title[1:]) or kind


def parse_gdacs(body: str, now: datetime) -> List[dict]:
    out = []
    for it in ET.fromstring(body).iter("item"):
        code = it.findtext("gdacs:eventtype", "", _NS)
        kind = GDACS_KIND.get(code)
        alert = it.findtext("gdacs:alertlevel", "", _NS)
        point = (it.findtext("georss:point", "", _NS) or "").split()
        if not kind or len(point) != 2 or _GRADE.get(alert, 0) < GDACS_MIN_GRADE[code]:
            continue
        until = _when(it.findtext("gdacs:todate", "", _NS)) or _when(it.findtext("gdacs:fromdate", "", _NS))
        current = (it.findtext("gdacs:iscurrent", "", _NS) or "").lower() == "true"
        if not current and (until is None or now - until > timedelta(days=MAX_AGE_DAYS)):
            continue
        lat, lon = float(point[0]), float(point[1])           # georss is "lat lon"
        out.append({"feed": "GDACS", "id": f"GDACS {code}{it.findtext('gdacs:eventid', '', _NS)}",
                    "kind": kind, "name": _gdacs_name(kind, it), "alert": alert,
                    "severity": (it.findtext("gdacs:severity", "", _NS) or "").strip() or None,
                    "lat": lat, "lon": lon,
                    "observed_at": until.isoformat() if until else None,
                    "url": (it.findtext("link") or "").strip() or None})
    return out


def parse_eonet(body: dict, now: datetime) -> List[dict]:
    out = []
    for ev in body.get("events") or []:
        kind = next((EONET_KIND[c["id"]] for c in ev.get("categories") or []
                     if c.get("id") in EONET_KIND), None)
        points = [x for x in ev.get("geometry") or [] if x.get("coordinates")]
        if not kind or not points:
            continue
        last = points[-1]
        at = _when(last.get("date"))
        if at is None or now - at > timedelta(days=MAX_AGE_DAYS):
            continue
        c = last["coordinates"]
        if last.get("type") == "Polygon":                    # first ring's mean
            ring = c[0]
            c = [sum(x[0] for x in ring) / len(ring), sum(x[1] for x in ring) / len(ring)]
        mag = last.get("magnitudeValue")
        src = (ev.get("sources") or [{}])[0]
        out.append({"feed": "EONET", "id": f"EONET {ev.get('id')}", "kind": kind,
                    "name": ev.get("title") or kind, "alert": None,
                    "severity": f"{mag:g} {last.get('magnitudeUnit') or ''}".strip()
                    if isinstance(mag, (int, float)) else None,
                    "lat": float(c[1]), "lon": float(c[0]), "observed_at": at.isoformat(),
                    "url": src.get("url") or ev.get("link")})
    return out


def parse_usgs(body: dict, now: datetime) -> List[dict]:
    out = []
    for f in body.get("features") or []:
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        mag = p.get("mag")
        at = _when(p.get("time"))
        if not isinstance(mag, (int, float)) or mag < USGS_MIN_MAGNITUDE or at is None:
            continue
        if now - at > timedelta(days=MAX_AGE_DAYS):
            continue
        lon, lat = g["coordinates"][:2]
        out.append({"feed": "USGS", "id": f"USGS {f.get('id')}", "kind": "earthquake",
                    "name": f"M{mag:g} quake, {p.get('place') or 'unnamed location'}",
                    "alert": (p.get("alert") or "").capitalize() or None,
                    "severity": f"M{mag:g}", "lat": float(lat), "lon": float(lon),
                    "observed_at": at.isoformat(), "url": p.get("url")})
    return out


def _tokens(name: str) -> set:
    words = re.findall(r"[a-z]+", (name or "").lower())
    return {w for w in words if len(w) >= 4 and w not in _GENERIC}


def _same(a: dict, b: dict) -> bool:
    """Two feeds' sightings of one hazard. A cyclone is named, and the name is
    the identity (CHAMPI-26 and Super Typhoon Champi). Anything else is matched
    on place and time, tightly for quakes: a swarm of five Vanuatu quakes in an
    hour is five quakes, and a shared country name proves nothing."""
    if a["kind"] != b["kind"] or a["feed"] == b["feed"]:
        return False
    if a["kind"] == "tropical_cyclone":
        return bool(_tokens(a["name"]) & _tokens(b["name"]))
    ta, tb = _when(a["observed_at"]), _when(b["observed_at"])
    if not (ta and tb):
        return False
    quake = a["kind"] == "earthquake"
    window = timedelta(minutes=QUAKE_SAME_MINUTES) if quake else timedelta(days=2)
    reach = QUAKE_SAME_KM if quake else 150
    return abs(ta - tb) <= window and km(a["lat"], a["lon"], b["lat"], b["lon"]) <= reach


def fuse(sightings: List[dict]) -> List[dict]:
    """One hazard per real-world event. Position from the most recent sighting,
    alert grade from whichever feed grades, every feed kept in `sources`."""
    groups: List[List[dict]] = []
    for s in sightings:
        for g in groups:
            if any(_same(s, x) for x in g):
                g.append(s)
                break
        else:
            groups.append([s])
    hazards = []
    for g in groups:
        kind = g[0]["kind"]
        latest = max(g, key=lambda x: _when(x["observed_at"]) or datetime.min.replace(tzinfo=timezone.utc))
        order = ID_PREFERENCE.get(kind, DEFAULT_PREFERENCE)
        named = min(g, key=lambda x: order.index(x["feed"]) if x["feed"] in order else 9)
        hazards.append({
            "kind": kind, "id": named["id"], "name": named["name"],
            "alert": next((x["alert"] for x in g if x["alert"]), None),
            "severity": latest["severity"] or next((x["severity"] for x in g if x["severity"]), None),
            "lat": latest["lat"], "lon": latest["lon"], "observed_at": latest["observed_at"],
            "position_from": latest["feed"],
            "sources": [{"feed": x["feed"], "id": x["id"], "name": x["name"], "url": x["url"]}
                        for x in g],
        })
    return hazards


def near(hazards: List[dict], places: List[dict]) -> List[dict]:
    hits = []
    for h in hazards:
        radius = RADIUS_KM[h["kind"]]
        for p in places:
            if h["kind"] == "earthquake" and p.get("country") == "ID":
                continue                                     # BMKG's ground
            d = km(h["lat"], h["lon"], p["lat"], p["lon"])
            if d <= radius:
                hits.append({**h, "place": p["code"], "place_kind": p["kind"],
                             "place_name": p["name"], "place_why": p["why"],
                             "distance_km": round(d), "radius_km": radius})
    hits.sort(key=lambda x: (x["distance_km"] / x["radius_km"]))
    return hits


def _read(url: str, ttl: int, timeout: int, parse: Callable[[dict, datetime], List[dict]],
          now: datetime, as_json: bool = True) -> Tuple[List[dict], dict]:
    try:
        body, at = feeds.get(url, ttl=ttl, timeout=timeout, as_json=as_json)
        rows = parse(body, now)
        return rows, {"origin": Origin.LIVE.value, "fetched_at": at.isoformat(timespec="seconds"),
                      "sightings": len(rows)}
    except feeds.FeedError as e:
        return [], {"origin": Origin.MISSING.value, "note": str(e)}
    except Exception as e:                                           # noqa: BLE001
        # A reshaped feed is a missing feed, not a crash in the watcher.
        return [], {"origin": Origin.MISSING.value, "note": f"unreadable: {type(e).__name__}: {e}"}


def poll(places: Optional[List[dict]] = None, now: Optional[datetime] = None) -> Result:
    """Every current hazard within reach of a watched place.

    Value: {"hits": [...], "feeds": {feed: status}, "places": n}. Derived when
    at least one feed answered; missing when none did, because an empty list
    from three dead feeds would read as a quiet day.
    """
    from signals import places as _places
    now = now or datetime.now(timezone.utc)
    if places is None:
        places = _places.watched().value["places"]
    sightings: List[dict] = []
    status: Dict[str, dict] = {}
    for name, url, ttl, timeout, parse, as_json in (
            ("GDACS", GDACS_URL, GDACS_TTL, GDACS_TIMEOUT, parse_gdacs, False),
            ("EONET", EONET_URL, EONET_TTL, EONET_TIMEOUT, parse_eonet, True),
            ("USGS", USGS_URL, USGS_TTL, USGS_TIMEOUT, parse_usgs, True)):
        rows, st = _read(url, ttl, timeout, parse, now, as_json)
        sightings += rows
        status[name] = st
    down = [f"{k}: {v['note']}" for k, v in status.items() if v["origin"] == Origin.MISSING.value]
    if len(down) == len(status):
        return Result(None, Origin.MISSING, "GDACS + NASA EONET + USGS", note="; ".join(down))
    hits = near(fuse(sightings), places)
    note = "distances to places from the company profile and open orders"
    if down:
        note += "; not reached: " + "; ".join(down)
    return Result({"hits": hits, "feeds": status, "places": len(places)},
                  Origin.DERIVED, "GDACS + NASA EONET + USGS", note=note)


# ------------------------------------------------------------------- events
def _storm(hit: dict) -> str:
    """A cyclone's own name, the same whichever feed reported it: CHAMPI."""
    names = [_tokens(s["name"]) for s in hit["sources"]]
    common = set.intersection(*names) if names else set()
    return " ".join(sorted(common or names[0])).upper() if names else ""


def _identities(hit: dict) -> List[Tuple[str, str]]:
    """Every (title, trigger) this hazard at this place could have been raised
    under; the first is the one it is raised under now. None carries a distance
    or a grade, so a storm that moves or strengthens stays one event.

    A cyclone is keyed on its name and year, so it is the same event whether
    EONET, GDACS or both reported it on a given pass. Anything else is keyed on
    each feed's own id, and a hazard seen under any of them is not new."""
    what = "plant" if hit["place_kind"] == "plant" else "port"
    where = f"{hit['place_name']} {what} ({hit['place']})"
    storm = _storm(hit) if hit["kind"] == "tropical_cyclone" else ""
    if storm:
        year = (hit["observed_at"] or "")[:4]
        return [(f"Tropical cyclone {storm} near {where}"[:120],
                 f"cyclone {storm} {year} · {hit['place']}"[:200])]
    return [(f"{s['name']} near {where}"[:120], f"{s['id']} · {hit['place']}"[:200])
            for s in sorted(hit["sources"], key=lambda s: s["id"] != hit["id"])]


def as_event(hit: dict) -> dict:
    title, trigger = _identities(hit)[0]
    return {
        "kind": hit["kind"],
        "title": title,
        "trigger": trigger,
        "payload": {k: hit[k] for k in (
            "place", "place_kind", "place_name", "place_why", "distance_km", "radius_km",
            "name", "alert", "severity", "lat", "lon", "observed_at", "position_from", "sources")},
        "source": " + ".join(sorted({s["feed"] for s in hit["sources"]})),
    }


def sweep(raise_event: Callable[[dict], str],
          seen: Optional[Callable[[str, str], bool]] = None,
          places: Optional[List[dict]] = None, now: Optional[datetime] = None) -> List[str]:
    """One pass, same contract as signals/watch.sweep: the ids of the events
    actually raised. A hazard already raised under any of its identities is
    skipped, so a storm first seen by EONET is not raised again once GDACS
    grades it, nor when one of the two feeds misses a pass."""
    if seen is None:
        from core import store
        seen = store.event_exists
    r = poll(places=places, now=now)
    if r.value is None:
        return []
    raised = []
    for hit in r.value["hits"]:
        if any(seen(title, trigger) for title, trigger in _identities(hit)):
            continue
        raised.append(raise_event(as_event(hit)))
    return raised


# --------------------------------------------------------------- self-check
#: Recorded 24 Oct 2026, trimmed to the fields read. Champi as both feeds saw
#: it, a cyclone GDACS still lists from August, a Florida wildfire, and a
#: Vanuatu quake from USGS.
_RSS_ITEM = """<item><title>{title}</title><link>{link}</link>
<gdacs:iscurrent>{current}</gdacs:iscurrent><gdacs:fromdate>{start}</gdacs:fromdate>
<gdacs:todate>{until}</gdacs:todate><georss:point>{lat} {lon}</georss:point>
<gdacs:eventtype>{code}</gdacs:eventtype><gdacs:alertlevel>{alert}</gdacs:alertlevel>
<gdacs:eventname>{name}</gdacs:eventname><gdacs:eventid>{eid}</gdacs:eventid>
<gdacs:severity unit="km/h" value="296">{severity}</gdacs:severity></item>"""
SAMPLE_GDACS = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:gdacs="http://www.gdacs.org" '
                'xmlns:georss="http://www.georss.org/georss"><channel>' + "".join(_RSS_ITEM.format(**x) for x in (
    dict(title="Red notification for tropical cyclone CHAMPI-26.", code="TC", alert="Red", eid=1001338,
         name="CHAMPI-26", current="true", start="Wed, 14 Oct 2026 12:00:00 GMT",
         until="Fri, 23 Oct 2026 00:00:00 GMT", lat=22.7, lon=123.8,
         severity="Hurricane/Typhoon &gt; 74 mph (maximum wind speed of 167 km/h)",
         link="http://www.gdacs.org/report.aspx?eventtype=TC&amp;eventid=1001338"),
    dict(title="Orange notification for tropical cyclone SAUDEL-26.", code="TC", alert="Orange", eid=1001305,
         name="SAUDEL-26", current="false", start="Tue, 18 Aug 2026 12:00:00 GMT",
         until="Thu, 03 Sep 2026 00:00:00 GMT", lat=23.8, lon=117.4, severity="",
         link="http://www.gdacs.org/report.aspx?eventtype=TC&amp;eventid=1001305"),
    dict(title="Green forest fire alert in Thailand 23/10/2026", code="WF", alert="Green", eid=1029001,
         name="", current="true", start="Thu, 22 Oct 2026 00:00:00 GMT",
         until="Fri, 23 Oct 2026 00:00:00 GMT", lat=13.10, lon=100.90, severity="",
         link="http://www.gdacs.org/report.aspx?eventtype=WF&amp;eventid=1029001"),
    dict(title="Orange earthquake (Magnitude 5.9M, Depth:10km) in Vanuatu 24/10/2026 08:56 UTC, Few people",
         code="EQ", alert="Orange", eid=1530001, name="", current="true",
         start="Sat, 24 Oct 2026 08:56:28 GMT", until="Sat, 24 Oct 2026 08:56:28 GMT",
         lat=-13.9418, lon=165.6471, severity="Magnitude 5.9M, Depth:10km",
         link="http://www.gdacs.org/report.aspx?eventtype=EQ&amp;eventid=1530001"),
)) + "</channel></rss>")
SAMPLE_EONET = {"events": [
    {"id": "EONET_25339", "title": "Super Typhoon Champi", "link": "https://eonet.gsfc.nasa.gov/api/v3/events/EONET_25339",
     "categories": [{"id": "severeStorms"}],
     "sources": [{"id": "JTWC", "url": "https://www.metoc.navy.mil/jtwc/products/wp2926.tcw"}],
     "geometry": [
         {"date": "2026-10-23T00:00:00Z", "type": "Point", "coordinates": [123.8, 22.7],
          "magnitudeValue": 90.0, "magnitudeUnit": "kts"},
         {"date": "2026-10-24T00:00:00Z", "type": "Point", "coordinates": [123.3, 24.8],
          "magnitudeValue": 65.0, "magnitudeUnit": "kts"}]},
    {"id": "EONET_25590", "title": "Wildfire BEE HAVEN (2) (24-06), Hamilton, Florida",
     "categories": [{"id": "wildfires"}], "sources": [{"id": "IRWIN", "url": "https://irwin.doi.gov/observer/"}],
     "geometry": [{"date": "2026-10-22T21:45:00Z", "type": "Point",
                   "coordinates": [-82.8577778, 30.4952778], "magnitudeValue": 2060.0, "magnitudeUnit": "acres"}]},
]}
SAMPLE_USGS = {"features": [
    {"id": "us6000u4lm", "geometry": {"coordinates": [165.6471, -13.9418, 10]},
     "properties": {"mag": 5.9, "place": "196 km NW of Port-Olry, Vanuatu", "time": 1792832188815,
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us6000u4lm", "alert": "green"}},
    {"id": "us6000u4kx", "geometry": {"coordinates": [165.8666, -14.0424, 10]},
     "properties": {"mag": 6.3, "place": "180 km NW of Port-Olry, Vanuatu", "time": 1792809357000,
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us6000u4kx", "alert": "green"}},
]}


def demo() -> None:
    now = datetime(2026, 10, 24, 3, 0, tzinfo=timezone.utc)
    g, e, u = parse_gdacs(SAMPLE_GDACS, now), parse_eonet(SAMPLE_EONET, now), parse_usgs(SAMPLE_USGS, now)
    assert [x["name"] for x in g] == ["Tropical cyclone CHAMPI-26", "Earthquake (Magnitude 5.9M, "
                                      "Depth:10km) in Vanuatu"], [x["name"] for x in g]
    # An August cyclone is history, and a Green wildfire is below the grade read.
    assert g[0]["lat"] == 22.7 and g[0]["lon"] == 123.8, "georss gives lat first"
    assert len(e) == 2 and len(u) == 2

    hazards = fuse(g + e + u)
    quakes = [h for h in hazards if h["kind"] == "earthquake"]
    assert len(quakes) == 2, "two Vanuatu quakes stay two; GDACS's report of one joins USGS's"
    assert sorted(len(q["sources"]) for q in quakes) == [1, 2], quakes
    champi = next(h for h in hazards if "CHAMPI" in h["name"].upper())
    assert len(champi["sources"]) == 2, "one storm in two feeds is one hazard"
    assert champi["alert"] == "Red", "the grade comes from GDACS"
    assert (champi["lat"], champi["lon"]) == (24.8, 123.3) and champi["position_from"] == "EONET", \
        "the position is the newest fix, not GDACS's older episode"
    assert champi["id"] == "EONET EONET_25339", "named by the feed that tracks it from the start"

    from signals.places import port
    places = [vars(port(c)) | {"why": "test"} for c in ("CNNGB", "JPYOK", "IDTPP")]
    hits = near(hazards, places)
    assert [(h["place"], h["kind"]) for h in hits] == [("CNNGB", "tropical_cyclone")], hits
    assert 580 <= hits[0]["distance_km"] <= 595, hits[0]["distance_km"]
    # On GDACS's position alone (23 Oct) Champi was ~820 km out, beyond the radius.
    alone = near(fuse(g), places)
    assert not alone, "the older episode position would have missed it"

    # A quake is only matched where BMKG cannot see, from whichever feed.
    jakarta_quake = {**u[0], "lat": -6.2, "lon": 106.9, "id": "USGS test"}
    assert not near(fuse([jakarta_quake, {**jakarta_quake, "feed": "GDACS", "id": "GDACS EQ1"}]),
                    places), "an Indonesian quake is BMKG's"

    ev = as_event(hits[0])
    assert ev["kind"] == "tropical_cyclone" and ev["source"] == "EONET + GDACS"
    assert "km" not in ev["title"], "a moving storm must keep one title"

    raised: List[dict] = []
    recorded: set = set()

    def fake_raise(body: dict) -> str:
        raised.append(body)
        recorded.add((body["title"], body["trigger"]))
        return f"evt_{len(raised)}"

    def seen(title: str, trigger: str) -> bool:
        return (title, trigger) in recorded

    feeds.prime(GDACS_URL, SAMPLE_GDACS)
    feeds.prime(EONET_URL, SAMPLE_EONET)
    feeds.prime(USGS_URL, SAMPLE_USGS)
    try:
        first = sweep(fake_raise, seen, places=places, now=now)
        again = sweep(fake_raise, seen, places=places, now=now)
        # EONET misses a pass: GDACS alone still names the same storm.
        feeds.prime(EONET_URL, {"events": []})
        alone_pass = sweep(fake_raise, seen, places=places, now=now)
        # Every feed down: nothing raised, and the poll says missing, not quiet.
        for url in (GDACS_URL, EONET_URL, USGS_URL):
            feeds.prime(url, "not json" if url != GDACS_URL else "<not-rss")
        dead = poll(places=places, now=now)
    finally:
        for url in (GDACS_URL, EONET_URL, USGS_URL):
            feeds.forget(url)
    assert first == ["evt_1"] and again == [] and alone_pass == [], (first, again, alone_pass)
    assert raised[0]["title"] == "Tropical cyclone CHAMPI near Ningbo-Zhoushan (Beilun) port (CNNGB)", \
        raised[0]["title"]
    assert raised[0]["trigger"] == "cyclone CHAMPI 2026 · CNNGB", raised[0]["trigger"]
    assert dead.origin is Origin.MISSING and dead.value is None, dead
    print(f"hazards ok: Champi fused from GDACS + EONET ✓ · {hits[0]['distance_km']} km from CNNGB "
          f"on the newest fix ✓ · stale and low-grade events dropped ✓ · a quake swarm stays "
          f"apart ✓ · quakes kept off BMKG's ground ✓ · one event per hazard per place ✓")


if __name__ == "__main__":
    demo()
