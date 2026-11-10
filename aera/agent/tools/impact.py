"""Elsa's tools (Impact).

Traces a disruption through orders, stock, and the bill of materials to the
customer commitments that are genuinely at risk.
"""
from __future__ import annotations

from typing import Optional

from core.provenance import Origin, Result
from core.registry import register
from tools.fetcher import bom, read


@register("get_open_purchase_orders", "impact",
          "Open purchase orders, filterable by loading port, material or supplier. When a "
          "supplier is what failed, filter by supplier: its orders are the ones at risk, "
          "whichever port they load at.",
          {"port": {"type": ["string", "null"], "description": "port code, e.g. CNNGB"},
           "material": {"type": ["string", "null"]},
           "supplier": {"type": ["string", "null"], "description": "supplier id, e.g. SUP-2201"}})
def get_open_purchase_orders(port: Optional[str] = None, material: Optional[str] = None,
                             supplier: Optional[str] = None) -> Result:
    r = read("PurchaseOrder", port=port, material=material, supplier=supplier)
    if supplier and r.value == []:
        # No orders for a supplier nobody has heard of reads exactly like "no
        # exposure". Ask the supplier master which of the two it is.
        known = read("Supplier", ids=[supplier])
        if known.value == []:
            return Result(None, Origin.MISSING, known.source,
                          note=f"no supplier {supplier} on record; pass a supplier id as the "
                               "supplier master writes it")
        r.note = "; ".join(x for x in (r.note, f"{supplier} has no open purchase order"
                                       + (f" loading at {port}" if port else "")
                                       + (f" for {material}" if material else "")) if x)
    return r


@register("get_material_stock", "impact",
          "Material stock per plant together with its daily consumption rate.",
          {"material": {"type": ["string", "null"]}, "plant": {"type": ["string", "null"]}})
def get_material_stock(material: Optional[str] = None, plant: Optional[str] = None) -> Result:
    return read("MaterialStock", material=material, plant=plant)


@register("get_bom_explosion", "impact",
          "Which finished goods consume this material.",
          {"material": {"type": "string"}}, ["material"])
def get_bom_explosion(material: str) -> Result:
    r = bom()
    if r.value is not None:
        r.value = [row for row in r.value if row.get("Material") == material]
    return r


@register("get_sales_order_commitments", "impact",
          "Customer orders for given finished goods, with their value.",
          {"finished_goods": {"type": "array", "items": {"type": "string"}}},
          ["finished_goods"])
def get_sales_order_commitments(finished_goods: list) -> Result:
    return read("SalesOrder", materials=finished_goods)


def demo() -> None:
    """Elsa's reads are thin over fetcher. What is hers is the distinction
    between "this supplier has no exposure" and "nobody has heard of it" -
    which came back as the same empty list until it was separated."""
    stock = get_material_stock()
    assert stock.value, stock.brief()
    material = stock.value[0]["Material"]
    assert all(r["Material"] == material
               for r in get_material_stock(material=material).value)

    pos = get_open_purchase_orders()
    assert pos.value is not None, pos.brief()
    known_supplier = next((str(r["Supplier"]) for r in pos.value if r.get("Supplier")), None)
    assert known_supplier, "the fixture must have a supplier on an order"
    mine = get_open_purchase_orders(supplier=known_supplier)
    assert mine.value and all(str(r["Supplier"]) == known_supplier for r in mine.value)

    # A supplier nobody has heard of is a gap, not a clean bill of health.
    unheard = get_open_purchase_orders(supplier="SUP-NOBODY")
    assert unheard.origin is Origin.MISSING and unheard.value is None, unheard.brief()
    assert "no supplier SUP-NOBODY on record" in unheard.note, unheard.note

    # A real supplier with nothing open says so in words, and stays readable.
    port = next((r["LoadingPort"] for r in pos.value if r.get("LoadingPort")), None)
    quiet = get_open_purchase_orders(supplier=known_supplier, port="XXXXX")
    assert quiet.value == [] and quiet.origin is not Origin.MISSING, quiet.brief()
    assert f"{known_supplier} has no open purchase order" in quiet.note, quiet.note

    # The structure, and the commitments it leads to.
    rows = bom().value or []
    assert rows, "the product structure must be readable"
    component = rows[0]["Material"]
    blast = get_bom_explosion(component)
    assert blast.value and all(r["Material"] == component for r in blast.value)
    goods = sorted({r["FinishedGood"] for r in blast.value})
    orders = get_sales_order_commitments(goods)
    assert orders.value is not None, orders.brief()
    assert get_bom_explosion("M-NOT-A-PART").value == []

    print(f"  stock, orders, structure read ✓ · {port or 'no port'} filter ✓")
    print("  an unknown supplier is a gap, not 'no exposure' ✓ · a quiet one says so ✓")
    print("impact ok")


if __name__ == "__main__":
    from core.config import fixtures_only

    fixtures_only(__file__, "AERA_IMPACT_CHECK")
    demo()
