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
