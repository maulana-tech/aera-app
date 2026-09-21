"""Alat milik Ahli Pencari Sumber."""
from __future__ import annotations

from core.provenance import Hasil
from tools._sumber import tarik


def find_alternate_sources(material: str) -> Hasil:
    """Pilihan pasokan pengganti: supplier lain, stok internal, atau kirim cepat."""
    return tarik("AlternateSource", "API_PURCHASING_INFO_RECORD_SRV", "A_PurchasingInfoRecord",
                 {"$top": "50"}, lambda r: r.get("Material") == material)
