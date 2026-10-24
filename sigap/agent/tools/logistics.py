"""Milo's tools (Logistics).

Arrival dates that survive contact with reality: port dwell and customs
clearance are computed, not guessed by the model.

Dwell is measured, not typed in. Every import declaration released at a port
says how long the goods sat there, and the median of those is a dwell anyone
can recompute. Customs data is not in S/4HANA (CEISA holds it in Indonesia),
so it comes from an uploaded CustomsDeclaration file, or the fixture offline.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from core.provenance import Origin, Result, weakest
from core.registry import register
from tools.fetcher import as_of, read, read_extra

#: Fewer releases than this and a median says more about the sample than the port.
MIN_DWELL_SAMPLES = 5


def _day(v) -> Optional[date]:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def observed_dwell(port: Optional[str] = None) -> Tuple[Optional[dict], Result]:
    """Days from discharge to release on the declarations released at `port`
    (every port when None): the median, the 80th percentile, and per lane."""
    r = read_extra("CustomsDeclaration", (lambda x: x.get("Port") == port) if port else None)
    spans: List[Tuple[str, int]] = []
    for x in r.value or []:
        arrived, released = _day(x.get("ArrivalDate")), _day(x.get("ReleasedDate"))
        if arrived and released and released >= arrived:
            spans.append((str(x.get("Lane") or "unknown"), (released - arrived).days))
    if len(spans) < MIN_DWELL_SAMPLES:
        return None, r
    days = sorted(d for _, d in spans)
    lanes: Dict[str, List[int]] = {}
    for lane, d in spans:
        lanes.setdefault(lane, []).append(d)
    return {
        "port": port or "every port on record",
        "samples": len(days),
        "median_days": math.ceil(_median(days)),
        "p80_days": days[math.ceil(0.8 * len(days)) - 1],
        "by_lane": {k: {"samples": len(v), "median_days": math.ceil(_median(sorted(v)))}
                    for k, v in sorted(lanes.items())},
    }, r


def _median(xs: List[int]) -> float:
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


@register("estimate_eta", "logistics",
          "Estimate a realistic arrival date for a supply option: its booked arrival plus "
          "port dwell and customs clearance when it is imported. The dwell is the median "
          "measured on the customs declarations released at the port, with the 80th "
          "percentile as the slow case; pass dwell_days only to override it. With no "
          "customs history it falls back to the rule pack's default and says the date "
          "rests on that assumption. Deterministic, not a model guess.",
          {"option_id": {"type": "string"},
           "dwell_days": {"type": ["integer", "null"],
                          "description": "override the measured dwell, in days"},
           "port": {"type": ["string", "null"],
                    "description": "discharge port to measure dwell at, e.g. IDTPP; "
                                   "default every port on record"}},
          ["option_id"])
def estimate_eta(option_id: str, dwell_days: Optional[int] = None,
                 port: Optional[str] = None) -> Result:
    options = read("AlternateSource", ids=[option_id])
    o = next(iter(options.value or []), None)
    if o is None:
        return Result(None, Origin.MISSING, "dwell time model",
                      note=f"unknown option '{option_id}'")
    if not o.get("ArrivalDate"):
        return Result(None, Origin.MISSING, "dwell time model",
                      note=f"option {option_id} has no booked arrival date to add dwell to")
    booked = date.fromisoformat(o["ArrivalDate"])
    out = {"option_id": option_id, "arrival_booked": booked.isoformat()}

    if (o.get("Origin") or "ID") == "ID":
        return Result(out | {"arrival_effective": booked.isoformat(), "dwell_days": 0,
                             "basis": "domestic, no port dwell or customs"},
                      weakest(options.origin, Origin.DERIVED), "dwell time engine")

    if dwell_days is not None:
        days, slow, origin = int(dwell_days), None, weakest(options.origin, Origin.DERIVED)
        basis = f"{days} days of dwell given by the caller"
        source = "dwell time engine"
    else:
        measured, history = observed_dwell(port)
        if measured:
            days, slow = measured["median_days"], measured["p80_days"]
            origin = weakest(options.origin, history.origin, Origin.DERIVED)
            basis = (f"median of {measured['samples']} customs releases at "
                     f"{measured['port']}; 1 in 5 took {slow} days or more")
            source = f"dwell time engine over {history.source}"
        else:
            from tools.compliance import load_pack, rule
            assumed = rule("default_port_dwell_days", load_pack())
            days, slow = int(assumed.value), None
            origin = weakest(options.origin, assumed.origin, Origin.DERIVED)
            basis = (f"{days} days assumed ({assumed.source}): "
                     + (f"fewer than {MIN_DWELL_SAMPLES} customs releases on record"
                        if history.value is not None else f"no customs history ({history.note})"))
            source = "dwell time engine"
    effective = booked + timedelta(days=days)
    out |= {"arrival_effective": effective.isoformat(), "dwell_days": days, "basis": basis}
    if slow is not None and slow > days:
        out["arrival_if_slow"] = (booked + timedelta(days=slow)).isoformat()
    return Result(out, origin, source)


@register("get_customs_status", "logistics",
          "Where an import stands in customs: its declaration, the lane it was given (green, "
          "yellow, red, MITA), whether it is released, under inspection or held, why, and "
          "how many days it has sat at the port, beside how long releases on that lane "
          "usually take. Pass a purchase order, or a port to list every declaration still "
          "open there. Customs data is not in SAP S/4HANA: it comes from an uploaded "
          "CustomsDeclaration file, and is missing when none is on record.",
          {"purchase_order": {"type": ["string", "null"]},
           "port": {"type": ["string", "null"], "description": "UN/LOCODE, e.g. IDTPP"}})
def get_customs_status(purchase_order: Optional[str] = None,
                       port: Optional[str] = None) -> Result:
    if not purchase_order and not port:
        return Result(None, Origin.MISSING, "customs declarations",
                      note="name a purchase order, or a port to list what is open there")
    number = str(purchase_order).split("-")[0] if purchase_order else None

    def keep(x: dict) -> bool:
        if number:
            return str(x.get("PurchaseOrder") or "").split("-")[0] == number
        return x.get("Port") == port and x.get("Status") != "released"

    r = read_extra("CustomsDeclaration", keep)
    if r.value is None:
        return r
    measured, _ = observed_dwell(port or next((x.get("Port") for x in r.value), None))
    lanes = (measured or {}).get("by_lane", {})
    today = as_of()
    out = []
    for x in r.value:
        arrived, released = _day(x.get("ArrivalDate")), _day(x.get("ReleasedDate"))
        lane = str(x.get("Lane") or "unknown")
        row = {
            "declaration": x.get("DeclarationNumber"), "purchase_order": x.get("PurchaseOrder"),
            "material": x.get("Material"), "supplier": x.get("Supplier"),
            "origin_country": x.get("OriginCountry"), "port": x.get("Port"),
            "lane": lane, "status": x.get("Status"), "hold_reason": x.get("HoldReason"),
            "arrived": arrived.isoformat() if arrived else None,
            "released": released.isoformat() if released else None,
            "days_at_port": ((released or today) - arrived).days if arrived else None,
        }
        typical = lanes.get(lane, {}).get("median_days")
        if typical is not None:
            row["lane_median_days"] = typical
            if arrived and not released:
                # A floor, not a forecast: a hold is a dispute, not a queue.
                row["release_if_typical"] = (arrived + timedelta(days=typical)).isoformat()
        out.append(row)

    if number and not out:
        return Result([], r.origin, r.source,
                      note=f"no customs declaration for {purchase_order} on record: not yet "
                           "discharged, domestic, or not in the file uploaded")
    held = [o for o in out if o["status"] == "held"]
    note = r.note
    if held:
        note = "; ".join(x for x in (note, "a held declaration is a dispute, not a queue: "
                                     "release_if_typical is the earliest it could clear, "
                                     "not when it will") if x)
    return Result(out if not number or len(out) > 1 else out[0], r.origin, r.source, note=note)


@register("get_shipment_status", "logistics",
          "Position and status of a shipment in transit.",
          {"purchase_order": {"type": "string"}}, ["purchase_order"])
def get_shipment_status(purchase_order: str) -> Result:
    orders = read("PurchaseOrder", numbers=[purchase_order], open_only=False)
    lines = orders.value or []
    if not lines:
        return Result(None, Origin.MISSING, "SAP Business Network",
                      note=orders.note if orders.value is None
                      else f"no purchase order {purchase_order} on record")
    # SAP has no vessel position; the order's own dates are what it does hold.
    out = [{"purchase_order": r["PurchaseOrder"], "status": r["Status"],
            "arrival_original": r["DeliveryDate"],
            "arrival_revised": r["RevisedDeliveryDate"]} for r in lines]
    return Result(out[0] if len(out) == 1 else out, orders.origin, orders.source,
                  note="order dates only, no vessel position" + (f"; {orders.note}" if orders.note else ""))


# ------------------------------------------------------------ the outside world
# Live, keyless public sources: what the weather, the news and the calendar say
# about a lane, which no SAP record does. The work is in signals/weather.py and
# clients/web_data.py; these are the doors to it.

@register("get_port_conditions", "logistics",
          "Live conditions at a port or plant: the next three days of forecast wind gusts, "
          "rain and (for ports) wave height from Open-Meteo, each day flagged where it "
          "crosses a named threshold (gale gusts 62 km/h, waves 4 m, rain 100 mm), plus any "
          "current cyclone, flood, quake, eruption, fire or drought within reach from GDACS, "
          "NASA EONET and USGS. Takes a UN/LOCODE such as CNNGB or a facility code such as KRW1.",
          {"port": {"type": "string", "description": "UN/LOCODE (CNNGB) or facility code (KRW1)"}},
          ["port"])
def get_port_conditions(port: str) -> Result:
    from signals.weather import port_conditions
    return port_conditions(port)


@register("search_news", "logistics",
          "Recent news headlines from Google News for a query, newest first: headline, "
          "publisher, time and link. Headlines only, the articles are not read. Use it to "
          "find out whether a port closure, strike or storm is being reported. A headline "
          "is someone else's claim: cite it as reported, never as fact.",
          {"query": {"type": "string", "description": "e.g. 'Ningbo port typhoon'"},
           "days": {"type": "integer", "description": "how far back, 1 to 30, default 7"}},
          ["query"])
def search_news(query: str, days: int = 7) -> Result:
    from clients.web_data import search_news as _news
    return _news(query, days)


@register("get_public_holidays", "logistics",
          "National public holidays in one country between two dates, from Nager.Date: when "
          "a supplier, a port's customs office or a trucking market closes. Covers ID, CN, "
          "JP, KR, VN, SG, HK and most others; not MY, TH or TW. Indonesia's list leaves out "
          "cuti bersama (collective leave).",
          {"country": {"type": "string", "description": "ISO 3166 two-letter code, e.g. CN"},
           "start": {"type": "string", "description": "YYYY-MM-DD, default today"},
           "end": {"type": "string", "description": "YYYY-MM-DD, default 30 days after start"}},
          ["country"])
def get_public_holidays(country: str, start: str = "", end: str = "") -> Result:
    from clients.web_data import public_holidays
    return public_holidays(country, start or None, end or None)


@register("web_brief", "logistics",
          "Ask a web-search model one question about the outside world (is a port open, "
          "has a carrier suspended a service) and get a short answer with the pages it "
          "read. Model-written: use it to find where to look and cite its links; take no "
          "number or date from it that a cited page does not state. Costs a model call.",
          {"question": {"type": "string"}}, ["question"])
def web_brief(question: str) -> Result:
    from clients.web_data import web_brief as _brief
    return _brief(question)


def demo() -> None:
    # The fixture's history: four months of releases at Tanjung Priok.
    measured, history = observed_dwell("IDTPP")
    assert measured and measured["samples"] >= 20, measured
    assert measured["p80_days"] >= measured["median_days"] >= 1, measured
    assert history.origin is Origin.MODELLED

    # An imported option takes the measured dwell, labelled no better than the
    # history it was measured on; a domestic one takes none.
    e = estimate_eta("D", port="IDTPP")
    assert e.value["dwell_days"] == measured["median_days"], e.value
    assert "median of" in e.value["basis"] and e.origin is Origin.MODELLED, e.value
    assert estimate_eta("B").value["dwell_days"] == 0
    given = estimate_eta("D", dwell_days=9)
    assert given.value["dwell_days"] == 9 and "given by the caller" in given.value["basis"]

    # No history at all: the default is an assumption and the basis says so.
    global read_extra
    real = read_extra
    read_extra = lambda entity, keep=None: Result(           # noqa: E731
        None, Origin.MISSING, "upload:CustomsDeclaration", note="none uploaded")
    try:
        bare = estimate_eta("D")
        assert "assumed" in bare.value["basis"] and bare.origin is Origin.MODELLED, bare.value
        assert get_customs_status("4500018876").origin is Origin.MISSING
    finally:
        read_extra = real

    # The customs hold the seed event describes, and how long it has sat.
    held = get_customs_status("4500018876")
    assert held.value["status"] == "held" and held.value["lane"] == "red", held.value
    assert held.value["days_at_port"] == 3 and held.value["release_if_typical"], held.value
    assert "dispute, not a queue" in held.note
    open_at_port = get_customs_status(port="IDTPP")
    assert {o["status"] for o in open_at_port.value} == {"held", "inspection"}, open_at_port.value
    none = get_customs_status("4500018872")
    assert none.value == [] and "no customs declaration" in none.note
    print(f"logistics ok, dwell at IDTPP median {measured['median_days']} days over "
          f"{measured['samples']} releases (80th percentile {measured['p80_days']})")
    print("  measured dwell, not a typed-in default ✓ · no history → assumption, named ✓ · "
          "customs hold read with its days at port ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_LOGISTICS_CHECK")
    demo()
