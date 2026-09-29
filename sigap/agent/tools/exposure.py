"""Vega's tools (Risk Scanner).

Prevent mode. Every other specialist is called because something broke. These
are called on a schedule, when nothing has broken, to find what is about to.

The scan is arithmetic over the same records everyone else reads. It invents no
risk: a material is single-sourced because the records show one supplier and no
alternate, not because a model thought it looked fragile.
"""
from __future__ import annotations

import pathlib
from datetime import date
from typing import Dict, List

from core.provenance import Origin, Result
from core.registry import register
from tools.fetcher import fixture, profile, pull

REFERENCES = pathlib.Path(__file__).resolve().parent.parent.parent / "references"


def _weakest(*results: Result) -> Origin:
    """A finding is never more trustworthy than the weakest thing it rests on."""
    order = [Origin.MISSING, Origin.MODELLED, Origin.CACHED, Origin.DERIVED, Origin.LIVE]
    return min((r.origin for r in results), key=order.index)


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
    stock = pull("MaterialStock", "API_MATERIAL_STOCK_SRV", "A_MatlStkInAcctMod", {"$top": "100"})
    orders = pull("PurchaseOrder", "API_PURCHASEORDER_PROCESS_SRV", "A_PurchaseOrder", {"$top": "100"})
    if stock.value is None or orders.value is None:
        return Result(None, Origin.MISSING, "scan", note="could not read stock or purchase orders")

    bom = fixture("BillOfMaterial")
    sales = fixture("SalesOrder")
    alternates = fixture("AlternateSource")
    horizon_days = horizon_weeks * 7
    start = date.fromisoformat(profile()["AsOfDate"])

    # committed customer value that depends on each material, through the BOM
    finished_for: Dict[str, set] = {}
    for b in bom:
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
        matched = [s["NetAmount"] for s in sales if s["Material"] in goods]
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
                "authority": "autonomous under Rp 50 million",
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
    total_committed = sum(s["NetAmount"] for s in sales)
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

    return Result(findings, _weakest(stock, orders), "scan over stock and purchase orders",
                  note=note)


@register(
    "get_supplier_certifications", "exposure",
    "A supplier's TKDN certificate and its validity dates. A certificate that lapses "
    "drops the local-content ratio with no physical event at all.",
    {"supplier": {"type": "string"}}, ["supplier"],
)
def get_supplier_certifications(supplier: str) -> Result:
    # The certificates belong in the rule pack beside the TKDN rules, because
    # that is the thing a person can audit. There is no API to read them from:
    # see DATA-SOURCES.md section 2.
    pack = REFERENCES / "tkdn-rules.md"
    if not pack.exists():
        return Result(
            None, Origin.MISSING, "references/tkdn-rules.md",
            note="the rule pack is not written yet, so no certificate can be checked. "
                 "It should carry each scenario supplier and its validity dates.",
        )

    text = pack.read_text()
    if supplier not in text:
        return Result(None, Origin.MISSING, "references/tkdn-rules.md",
                      note=f"{supplier} is not in the rule pack")
    lines = [ln.strip() for ln in text.splitlines() if supplier in ln]
    return Result({"supplier": supplier, "entries": lines},
                  Origin.DERIVED, "references/tkdn-rules.md")


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

    # M-5512 feeds FG-2040 and no customer order references it.
    m5512 = [f for f in r.value if f["material"] == "M-5512"]
    assert m5512 and all(f["value_idr"] is None for f in m5512), m5512

    # A scan over modelled stock is modelled, never derived.
    assert r.origin is Origin.MODELLED, r.origin

    # M-4471 and M-3308 both feed FG-1120, so a lane carrying both is exposed
    # to those orders once, not twice.
    lane = next(f for f in r.value if f["pattern"] == "lane concentration")
    total = sum(s["NetAmount"] for s in fixture("SalesOrder"))
    assert lane["value_idr"] == total, (lane["value_idr"], total)

    c = get_supplier_certifications("SUP-4417")
    assert c.origin is Origin.MISSING and "rule pack" in c.note, c.note

    print(f"exposure ok, {len(r.value)} exposures, {len(single)} single sourced")
    for f in r.value[:4]:
        money = f"Rp {f['value_idr']:,}" if f["value_idr"] else "unpriced"
        print(f"  {f['pattern']:<32} {f['material']:<22} {money}")


if __name__ == "__main__":
    demo()
