"""Pengambil data: coba SAP dulu, jatuh ke fixture kalau kunci belum ada.

Yang penting: jatuh ke fixture TIDAK disembunyikan. Asal-nya jadi CONTOH,
dan itu terlihat di UI maupun di pengecekan kalkulator.
"""
from __future__ import annotations

import json
import pathlib
from typing import Callable, Dict, List, Optional

from core.provenance import Asal, Hasil
from clients import sap_s4

_FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "skenario_ningbo.json"
_cache: Optional[dict] = None


def fixture(entitas: str) -> List[dict]:
    global _cache
    if _cache is None:
        _cache = json.loads(_FIX.read_text())
    return _cache[entitas]


def profil() -> dict:
    return fixture("Profil")  # type: ignore[return-value]


def tarik(
    entitas_fixture: str,
    layanan_sap: str,
    entitas_sap: str,
    params: Optional[Dict] = None,
    saring: Optional[Callable[[dict], bool]] = None,
) -> Hasil:
    """Satu jalur pengambilan untuk semua alat baca."""
    if sap_s4.tersedia():
        try:
            data = sap_s4.baris(sap_s4.ambil(layanan_sap, entitas_sap, params))
            if saring:
                data = [r for r in data if saring(r)]
            return Hasil(data, Asal.LANGSUNG, layanan_sap)
        except Exception as e:                                   # noqa: BLE001
            return Hasil(None, Asal.TIDAK_ADA, layanan_sap, catatan=f"{type(e).__name__}: {e}")

    data = fixture(entitas_fixture)
    if saring:
        data = [r for r in data if saring(r)]
    return Hasil(
        data, Asal.CONTOH, f"fixture:{entitas_fixture}",
        catatan="SAP_API_KEY belum diisi — memakai data contoh",
    )
