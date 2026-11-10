"""Vega's tools (Risk Scanner).

Prevent mode. Every other specialist is called because something broke. These
are called on a schedule, when nothing has broken, to find what is about to.

The scan is arithmetic over the same records everyone else reads. It invents no
risk: a material is single-sourced because the records show one supplier and no
alternate, not because a model thought it looked fragile.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date
from typing import Dict, List

from core.config import CFG
from core.provenance import Origin, Result, weakest
from core.registry import register
from tools.fetcher import as_of, bom, fixture, read



def _weakest(*results: Result) -> Origin:
    """A finding is never more trustworthy than the weakest thing it rests on."""
    return weakest(*(r.origin for r in results))


@register(
    "scan_supply_exposure", "exposure",
    "Scan for risk that has not happened yet: materials with a single source, lanes "
    "concentrated on one port, and cover falling below policy inside the horizon. "
    "Ranked by the committed customer value behind each material. Deterministic.",
    {"horizon_weeks": {"type": "integer", "description": "how far ahead to look, default 8"},
     "cover_floor_days": {"type": "integer", "description": "policy floor in days, default 14"}},
    [],
)
def scan_supply_exposure(horizon_weeks: int = 8, cover_floor_days: int = 14) -> Result:
    stock = read("MaterialStock")
    orders = read("PurchaseOrder")
    if stock.value is None or orders.value is None:
        return Result(None, Origin.MISSING, "scan", note="could not read stock or purchase orders")

    structure, sales_r, alternates_r = bom(), read("SalesOrder"), read("AlternateSource")
    bom_rows = structure.value or []
    sales = sales_r.value or []
    alternates = alternates_r.value or []
    horizon_days = horizon_weeks * 7
    start = as_of()

    # committed customer value that depends on each material, through the BOM
    finished_for: Dict[str, set] = {}
    for b in bom_rows:
        finished_for.setdefault(b["Material"], set()).add(b["FinishedGood"])
    def committed(materials) -> float | None:
        """Value behind a set of materials, counted once.

        Two materials can feed the same finished good, so summing their
        individual exposures double counts the customer orders behind it. Take
        the union of finished goods first, then price that once.
        """
        goods: set = set()
        for m in materials:
            goods |= finished_for.get(m, set())
        if not goods:
            return None
        # An amount that could not be converted to rupiah is left out, not zero.
        matched = [s["NetAmount"] for s in sales
                   if s["Material"] in goods and s.get("NetAmount") is not None]
        # No order on record is not the same as an order worth nothing. Zero
        # tells a planner this exposure does not matter; None tells them the
        # records do not say, which is the true answer.
        return sum(matched) if matched else None

    value_of: Dict[str, float] = {m: committed([m]) for m in finished_for}

    suppliers_of: Dict[str, set] = {}
    for o in orders.value:
        suppliers_of.setdefault(o["Material"], set()).add(o["Supplier"])
    for a in alternates:
        suppliers_of.setdefault(a["Material"], set()).add(a["Supplier"])

    lane_of: Dict[str, set] = {}
    for o in orders.value:
        if o.get("LoadingPort"):
            lane_of.setdefault(o["LoadingPort"], set()).add(o["Material"])

    findings: List[dict] = []
    for row in stock.value:
        material, plant = row["Material"], row["Plant"]
        qty = float(row.get("MatlWrhsStkQtyInMatlBaseUnit") or 0)
        daily = float(row.get("DailyConsumption") or 0)
        cover = round(qty / daily, 1) if daily else None
        sources = suppliers_of.get(material, set())
        exposed = value_of.get(material)

        if len(sources) == 1:
            findings.append({
                "pattern": "single source",
                "material": material, "plant": plant,
                "detail": f"{next(iter(sources))} is the only supplier on record, "
                          "and no alternate source exists",
                "cover_days": cover,
                "value_idr": exposed,
                "action": "qualify a second supplier",
                "authority": "draft for procurement",
            })

        if cover is not None and cover < cover_floor_days:
            findings.append({
                "pattern": "cover below policy",
                "material": material, "plant": plant,
                "detail": f"{cover} days of cover against a {cover_floor_days} day floor",
                "cover_days": cover,
                "value_idr": exposed,
                "action": "pre-position stock or bring supply forward",
                "authority": f"autonomous under {CFG.autonomous_limit_text}, when every "
                             "figure under it is trusted",
            })
        elif cover is not None and cover < horizon_days:
            findings.append({
                "pattern": "cover runs out inside the horizon",
                "material": material, "plant": plant,
                "detail": f"{cover} days of cover, horizon is {horizon_days} days",
                "cover_days": cover,
                "value_idr": exposed,
                "action": "confirm inbound supply covers the gap",
                "authority": "autonomous",
            })

    for port, materials in lane_of.items():
        if len(materials) > 1:
            findings.append({
                "pattern": "lane concentration",
                "material": ", ".join(sorted(materials)), "plant": "-",
                "detail": f"{len(materials)} materials route through {port}. "
                          "One closure takes out all of them at once",
                "cover_days": None,
                "value_idr": committed(materials),
                "action": "split the lane or hold buffer at the far side",
                "authority": "draft for procurement",
            })

    # Ranked by what it would cost. Unknown value sorts last rather than as zero,
    # because "we do not know" is not "it does not matter".
    findings.sort(key=lambda f: (f["value_idr"] is None, -(f["value_idr"] or 0)))

    # No finding can be worth more than every customer order put together.
    # This is the guard that catches double counting, which is exactly the
    # mistake a per-material sum makes when two materials share a product.
    total_committed = sum(s["NetAmount"] for s in sales if s.get("NetAmount") is not None)
    for f in findings:
        if f["value_idr"] is not None and f["value_idr"] > total_committed:
            raise AssertionError(
                f"{f['pattern']} on {f['material']} priced at {f['value_idr']:,}, "
                f"above the {total_committed:,} committed in total"
            )

    unpriced = [f for f in findings if f["value_idr"] is None]
    note = f"{len(findings)} exposures across {len(stock.value)} material and plant pairs."
    if unpriced:
        note += (f" {len(unpriced)} could not be priced: no bill of materials links them to a "
                 "customer order, so the ranking puts them last rather than at zero.")

    if not finished_for:
        note += f" No bill of materials could be read ({structure.note or structure.source})."
    return Result(findings, _weakest(stock, orders), "scan over stock and purchase orders",
                  note=note)


@register(
    "get_supplier_certifications", "exposure",
    "A supplier's TKDN certificates from the rule pack: the certified percentage, the "
    "validity dates and the days left before each lapses. A certificate that lapses "
    "drops the local-content ratio with no physical event at all.",
    {"supplier": {"type": "string"}}, ["supplier"],
)
def get_supplier_certifications(supplier: str) -> Result:
    # The certificates belong in the rule pack beside the TKDN rules, because
    # that is the thing a person can audit. There is no API to read them from:
    # see DATA-SOURCES.md section 2.
    from tools.compliance import load_pack, pack_source

    pack = load_pack()
    if pack is None:
        return Result(
            None, Origin.MISSING, "rule pack",
            note="no rule pack is installed, so no certificate can be checked. Its "
                 "certificates list carries each supplier's TKDN certificate and validity "
                 "dates (aera/references/README.md)",
        )
    held = [c for c in pack.get("certificates") or [] if str(c.get("supplier")) == supplier]
    if not held:
        return Result(None, Origin.MISSING, pack_source(),
                      note=f"{supplier} has no certificate in the rule pack")
    today = as_of()
    out, sourced = [], True
    for c in held:
        until = c.get("valid_until")
        try:
            left = (date.fromisoformat(str(until)) - today).days if until else None
        except ValueError:
            left = None
        sourced &= bool(c.get("verified")) and bool(str(c.get("source") or "").strip())
        out.append({"supplier": supplier, "certificate": c.get("certificate"),
                    "tkdn_pct": c.get("tkdn_pct"), "valid_from": c.get("valid_from"),
                    "valid_until": until, "days_left": left,
                    "lapsed": left is not None and left < 0,
                    "source": c.get("source"), "verified": bool(c.get("verified"))})
    return Result(out, Origin.DERIVED if sourced else Origin.MODELLED, pack_source(),
                  note="" if sourced else "a certificate entry is not verified against its source")


@register(
    "scan_live_hazards", "exposure",
    "Every natural hazard happening now within reach of a place the supply chain "
    "touches: our plants, and the loading port of every open purchase order. Cyclones, "
    "floods, quakes, eruptions, wildfires and droughts from GDACS (graded Green, Orange "
    "or Red), NASA EONET and USGS, one storm reported by two feeds counted once, each "
    "with its distance to the place and the radius it is judged by. Live positions, "
    "measured against the profile and order book.",
    {}, [],
)
def scan_live_hazards() -> Result:
    from signals import hazards
    r = hazards.poll()
    if r.value is None:
        return r
    hits = [{k: h[k] for k in ("place", "place_kind", "place_name", "place_why", "kind", "name",
                               "alert", "severity", "distance_km", "radius_km", "observed_at",
                               "position_from")}
            | {"reported_by": [s["feed"] for s in h["sources"]],
               "url": next((s["url"] for s in h["sources"] if s["url"]), None)}
            for h in r.value["hits"]]
    return Result({"hits": hits, "places_watched": r.value["places"],
                   "feeds": {k: v["origin"] for k, v in r.value["feeds"].items()}},
                  r.origin, r.source, fetched_at=r.fetched_at, note=r.note)


def demo() -> None:
    r = scan_supply_exposure()
    assert r.value, "the scan found nothing, which cannot be right for this fixture"

    single = [f for f in r.value if f["pattern"] == "single source"]
    assert single, "M-3308 and M-5512 have one supplier and no alternate"
    assert all(f["material"] != "M-4471" for f in single), \
        "M-4471 has four alternate sources and must not read as single sourced"

    # Priced findings sort ahead of unpriced ones.
    priced = [f["value_idr"] for f in r.value if f["value_idr"] is not None]
    assert priced == sorted(priced, reverse=True), priced
    assert r.value[0]["value_idr"] is not None, "an unpriced finding cannot rank first"
    assert 0 not in priced, "a finding with no order on record must be unpriced, not zero"

    # Whatever the dataset, an unpriced finding sorts behind every priced one.
    # Unpriced means the records do not say, which is not the same as zero.
    seen_unpriced = False
    for f in r.value:
        if f["value_idr"] is None:
            seen_unpriced = True
        else:
            assert not seen_unpriced, "a priced finding ranked behind an unpriced one"

    # A scan over modelled stock is modelled, never derived.
    assert r.origin is Origin.MODELLED, r.origin

    # Materials sharing a finished good must be priced through it once. The
    # bound that catches double counting is the whole order book: no finding
    # can be worth more than every customer order put together.
    total = sum(s["NetAmount"] for s in fixture("SalesOrder"))
    for f in r.value:
        if f["value_idr"] is not None:
            assert f["value_idr"] <= total, (f["pattern"], f["value_idr"], total)
    lane = next(f for f in r.value if f["pattern"] == "lane concentration")
    assert lane["value_idr"] is not None and lane["value_idr"] > 0, lane

    # Certificates come from the rule pack; with none installed there is nothing
    # to check, and the answer says that rather than reporting no certificate.
    import tempfile
    from tools import compliance
    with tempfile.TemporaryDirectory() as tmp:
        compliance._pack_file = pathlib.Path(tmp) / "rule-pack.json"
        try:
            c = get_supplier_certifications("SUP-4417")
            assert c.origin is Origin.MISSING and "rule pack" in c.note, c.note
            compliance._pack_file.write_text(json.dumps({"certificates": [
                {"supplier": "SUP-4417", "certificate": "T-1", "tkdn_pct": 41.6,
                 "valid_until": "2026-09-20", "source": "certificate scan", "verified": True}]}))
            c = get_supplier_certifications("SUP-4417")
            assert c.origin is Origin.DERIVED and c.value[0]["days_left"] == 16, c.value
            assert get_supplier_certifications("SUP-2201").origin is Origin.MISSING
        finally:
            compliance._pack_file = None

    print(f"exposure ok, {len(r.value)} exposures, {len(single)} single sourced")
    for f in r.value[:4]:
        money = f"Rp {f['value_idr']:,}" if f["value_idr"] else "unpriced"
        print(f"  {f['pattern']:<32} {f['material']:<22} {money}")


if __name__ == "__main__":
    # demo() asserts figures computed from fixtures/, so it has to read them
    # rather than whatever the live service happens to return today.
    from core.config import fixtures_only

    fixtures_only(__file__, "AERA_EXPOSURE_CHECK")
    demo()
