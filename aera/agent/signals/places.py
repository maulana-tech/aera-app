"""The places a disruption can land on: our plants, and the ports our goods
pass through.

Every outside signal (a cyclone, a flood, a gale forecast) only matters if it
is near somewhere the supply chain touches. Two lists say where that is:

  - the facilities in the company profile: plants, and the port they import
    through;
  - the loading port of every purchase order still open. A typhoon over
    Ningbo is our problem because seventeen open orders load there, not
    because Ningbo is big.

Port coordinates are a fixed table keyed by UN/LOCODE. They are the container
terminals' positions to about 0.05 degrees (a few km), which is far finer than
the 100 to 600 km radii the watchers use. A port code that is not in the table
is reported as unknown rather than placed somewhere plausible.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

from core.provenance import Origin, Result

#: UN/LOCODE -> (name, lat, lon, ISO country). The loading ports in the data,
#: plus the ones a Tier-1 supplier in Indonesia is likely to add next.
PORTS: Dict[str, Tuple[str, float, float, str]] = {
    "CNNGB": ("Ningbo-Zhoushan (Beilun)", 29.93, 121.85, "CN"),
    "CNSHA": ("Shanghai (Yangshan)", 30.63, 122.07, "CN"),
    "CNSZX": ("Shenzhen (Shekou)", 22.48, 113.91, "CN"),
    "CNTAO": ("Qingdao (Qianwan)", 36.03, 120.21, "CN"),
    "HKHKG": ("Hong Kong (Kwai Tsing)", 22.34, 114.12, "HK"),
    "TWKHH": ("Kaohsiung", 22.61, 120.28, "TW"),
    "JPYOK": ("Yokohama", 35.45, 139.66, "JP"),
    "KRPUS": ("Busan", 35.10, 129.04, "KR"),
    "MYPKG": ("Port Klang", 3.00, 101.39, "MY"),
    "THLCH": ("Laem Chabang", 13.08, 100.88, "TH"),
    "VNSGN": ("Ho Chi Minh City (Cat Lai)", 10.76, 106.79, "VN"),
    "SGSIN": ("Singapore (Pasir Panjang)", 1.27, 103.77, "SG"),
    "IDTPP": ("Tanjung Priok, Jakarta", -6.10, 106.88, "ID"),
    "IDSUB": ("Tanjung Perak, Surabaya", -7.20, 112.73, "ID"),
    "IDSRG": ("Tanjung Emas, Semarang", -6.95, 110.42, "ID"),
}

#: Purchase order statuses that mean the goods have arrived and the lane no
#: longer matters. Anything else is still on its way, or not yet shipped.
CLOSED_STATUSES = {"received", "delivered", "closed", "cancelled", "completed"}

#: A coarse box around Indonesian territory. Used only to say which plants BMKG
#: already covers; a plant's country is not in the profile, so this is the one
#: inference made here, and it is about coverage, not about the map.
_INDONESIA = (-11.5, 6.5, 94.5, 141.5)


@dataclass(frozen=True)
class Place:
    code: str
    kind: str                       # plant | port
    name: str
    lat: float
    lon: float
    country: Optional[str]          # ISO 3166 alpha-2, None when unknown
    why: str                        # what ties it to the supply chain


def in_indonesia(lat: float, lon: float) -> bool:
    s, n, w, e = _INDONESIA
    return s <= lat <= n and w <= lon <= e


#: Words an incoterms location uses for a port in the table. An order may hold
#: no loading port; "FOB Ningbo" holds one in its location, which is where a
#: buyer writes it.
_ALIASES: Dict[str, str] = {
    "ningbo": "CNNGB", "beilun": "CNNGB", "zhoushan": "CNNGB",
    "shanghai": "CNSHA", "yangshan": "CNSHA",
    "shenzhen": "CNSZX", "shekou": "CNSZX", "yantian": "CNSZX",
    "qingdao": "CNTAO", "hong kong": "HKHKG", "kaohsiung": "TWKHH",
    "yokohama": "JPYOK", "busan": "KRPUS", "pusan": "KRPUS",
    "port klang": "MYPKG", "klang": "MYPKG", "laem chabang": "THLCH",
    "ho chi minh": "VNSGN", "saigon": "VNSGN", "cat lai": "VNSGN",
    "singapore": "SGSIN", "tanjung priok": "IDTPP", "priok": "IDTPP", "jakarta": "IDTPP",
    "tanjung perak": "IDSUB", "surabaya": "IDSUB", "tanjung emas": "IDSRG", "semarang": "IDSRG",
}


def port_for_location(text: Optional[str]) -> Optional[str]:
    """The UN/LOCODE an incoterms location names, or None. 'CNNGB', 'Ningbo',
    'NINGBO PORT' and 'FOB Beilun' all give CNNGB; 'VENDOR' and 'Palo Alto'
    give None, because they name no port."""
    t = " ".join((text or "").lower().replace(",", " ").replace("-", " ").split())
    if not t:
        return None
    code = t.replace(" ", "").upper()
    if code in PORTS:
        return code
    for alias in sorted(_ALIASES, key=len, reverse=True):
        if f" {alias} " in f" {t} ":
            return _ALIASES[alias]
    return None


def port(code: str) -> Optional[Place]:
    p = PORTS.get((code or "").strip().upper())
    if p is None:
        return None
    name, lat, lon, country = p
    return Place(code.strip().upper(), "port", name, lat, lon, country, "known port")


def _open_lanes() -> Tuple[Dict[str, int], Result]:
    """Loading port -> open order count, and the Result it was read from."""
    from tools.fetcher import read
    r = read("PurchaseOrder")
    lanes: Dict[str, int] = {}
    for po in r.value or []:
        code = str(po.get("LoadingPort") or "").strip().upper()
        if code and str(po.get("Status") or "").lower() not in CLOSED_STATUSES:
            lanes[code] = lanes.get(code, 0) + 1
    return lanes, r


def watched() -> Result:
    """Every place worth watching, with the reason it is watched.

    The value is {"places": [...], "unknown_ports": [...]}. It is labelled
    modelled, because the list is only as real as the profile it starts from.
    """
    from tools.fetcher import profile
    places: Dict[str, Place] = {}
    for f in profile().get("Facilities", []):
        try:
            lat, lon = float(f["lat"]), float(f["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        known = PORTS.get(f["code"])
        country = known[3] if known else ("ID" if in_indonesia(lat, lon) else None)
        places[f["code"]] = Place(f["code"], f.get("kind", "plant"), f.get("name", f["code"]),
                                  lat, lon, country, f"company {f.get('kind', 'facility')}")

    lanes, orders = _open_lanes()
    unknown = []
    for code, n in sorted(lanes.items(), key=lambda kv: -kv[1]):
        why = f"loading port of {n} open purchase order{'s' if n != 1 else ''}"
        if code in places:
            places[code] = Place(**{**asdict(places[code]), "why": places[code].why + "; " + why})
            continue
        p = port(code)
        if p is None:
            unknown.append({"code": code, "open_orders": n})
            continue
        places[code] = Place(**{**asdict(p), "why": why})

    # The profile is modelled in every installation so far, so the list is too,
    # whatever the order book's own origin.
    origin = Origin.MODELLED
    note = "the company profile is modelled"
    if orders.origin == Origin.MISSING:
        note += f"; the order book could not be read ({orders.note}), so no loading ports"
    elif orders.value and not lanes:
        note += (f"; none of the {len(orders.value)} open order lines names a loading port "
                 "this table knows, so only the company's own facilities are watched")
    if unknown:
        note += f"; no coordinates for port(s) {', '.join(u['code'] for u in unknown)}, not watched"
    return Result({"places": [asdict(p) for p in places.values()], "unknown_ports": unknown},
                  origin, f"profile + {orders.source}", note=note)


def demo() -> None:
    r = watched()
    codes = {p["code"]: p for p in r.value["places"]}
    assert {"KRW1", "SBY1", "IDTPP"} <= set(codes), sorted(codes)
    assert "CNNGB" in codes and "open purchase order" in codes["CNNGB"]["why"]
    assert codes["IDTPP"]["why"].startswith("company port; loading port of"), codes["IDTPP"]["why"]
    assert codes["KRW1"]["country"] == "ID" and codes["CNNGB"]["country"] == "CN"
    assert r.origin == Origin.MODELLED, "a list read from the fixture is only modelled"
    assert port("XXFOO") is None, "an unknown port is not placed anywhere"
    assert port("cnngb") and port("cnngb").lat == 29.93
    print(f"places ok: {len(codes)} watched ({', '.join(sorted(codes))}) · "
          f"unknown ports reported, not guessed ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_PLACES_CHECK")
    demo()
