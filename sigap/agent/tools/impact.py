"""Alat milik Ahli Dampak."""
from __future__ import annotations

from typing import Optional

from core.provenance import Hasil
from core.registry import daftarkan
from tools._sumber import tarik


@daftarkan("get_open_purchase_orders", "impact",
           "Pesanan pembelian yang masih terbuka, bisa disaring per pelabuhan muat atau material.",
           {"port": {"type": ["string", "null"], "description": "kode pelabuhan, mis. CNNGB"},
            "material": {"type": ["string", "null"]}})
def get_open_purchase_orders(port: Optional[str] = None, material: Optional[str] = None) -> Hasil:
    """Pesanan pembelian terbuka, bisa disaring per pelabuhan muat atau material."""
    def cocok(r: dict) -> bool:
        return ((port is None or r.get("LoadingPort") == port)
                and (material is None or r.get("Material") == material))

    params = {"$filter": f"LoadingPort eq '{port}'", "$top": "50"} if port else {"$top": "50"}
    return tarik("PurchaseOrder", "API_PURCHASEORDER_PROCESS_SRV", "A_PurchaseOrder", params, cocok)


@daftarkan("get_material_stock", "impact",
           "Stok material per plant berikut laju pemakaian hariannya.",
           {"material": {"type": ["string", "null"]}, "plant": {"type": ["string", "null"]}})
def get_material_stock(material: Optional[str] = None, plant: Optional[str] = None) -> Hasil:
    """Stok material per plant, berikut laju pemakaian hariannya."""
    def cocok(r: dict) -> bool:
        return ((material is None or r.get("Material") == material)
                and (plant is None or r.get("Plant") == plant))

    return tarik("MaterialStock", "API_MATERIAL_STOCK_SRV", "A_MatlStkInAcctMod", {"$top": "100"}, cocok)


@daftarkan("get_bom_explosion", "impact",
           "Produk jadi apa saja yang memakai material ini.",
           {"material": {"type": "string"}}, ["material"])
def get_bom_explosion(material: str) -> Hasil:
    """Produk jadi apa saja yang memakai material ini."""
    return tarik("BillOfMaterial", "API_BILL_OF_MATERIAL_SRV", "A_BillOfMaterial",
                 {"$top": "100"}, lambda r: r.get("Material") == material)


@daftarkan("get_sales_order_commitments", "impact",
           "Pesanan pelanggan untuk produk jadi tertentu, berikut nilainya.",
           {"finished_goods": {"type": "array", "items": {"type": "string"}}},
           ["finished_goods"])
def get_sales_order_commitments(finished_goods: list) -> Hasil:
    """Pesanan pelanggan untuk produk jadi tertentu."""
    fg = set(finished_goods)
    return tarik("SalesOrder", "API_SALES_ORDER_SRV", "A_SalesOrder",
                 {"$top": "100"}, lambda r: r.get("Material") in fg)
