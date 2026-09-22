"""Elsa's tools (Impact).

Traces a disruption through orders, stock, and the bill of materials to the
customer commitments that are genuinely at risk.
"""
from __future__ import annotations

from typing import Optional

from core.provenance import Result
from core.registry import register
from tools.fetcher import pull


@register("get_open_purchase_orders", "impact",
          "Open purchase orders, filterable by loading port or material.",
          {"port": {"type": ["string", "null"], "description": "port code, e.g. CNNGB"},
           "material": {"type": ["string", "null"]}})
def get_open_purchase_orders(port: Optional[str] = None,
                             material: Optional[str] = None) -> Result:
    def keep(r: dict) -> bool:
        return ((port is None or r.get("LoadingPort") == port)
                and (material is None or r.get("Material") == material))

    params = {"$filter": f"LoadingPort eq '{port}'", "$top": "50"} if port else {"$top": "50"}
    return pull("PurchaseOrder", "API_PURCHASEORDER_PROCESS_SRV", "A_PurchaseOrder", params, keep)


@register("get_material_stock", "impact",
          "Material stock per plant together with its daily consumption rate.",
          {"material": {"type": ["string", "null"]}, "plant": {"type": ["string", "null"]}})
def get_material_stock(material: Optional[str] = None, plant: Optional[str] = None) -> Result:
    def keep(r: dict) -> bool:
        return ((material is None or r.get("Material") == material)
                and (plant is None or r.get("Plant") == plant))

    return pull("MaterialStock", "API_MATERIAL_STOCK_SRV", "A_MatlStkInAcctMod",
                {"$top": "100"}, keep)


@register("get_bom_explosion", "impact",
          "Which finished goods consume this material.",
          {"material": {"type": "string"}}, ["material"])
def get_bom_explosion(material: str) -> Result:
    return pull("BillOfMaterial", "API_BILL_OF_MATERIAL_SRV", "A_BillOfMaterial",
                {"$top": "100"}, lambda r: r.get("Material") == material)


@register("get_sales_order_commitments", "impact",
          "Customer orders for given finished goods, with their value.",
          {"finished_goods": {"type": "array", "items": {"type": "string"}}},
          ["finished_goods"])
def get_sales_order_commitments(finished_goods: list) -> Result:
    fg = set(finished_goods)
    return pull("SalesOrder", "API_SALES_ORDER_SRV", "A_SalesOrder",
                {"$top": "100"}, lambda r: r.get("Material") in fg)
