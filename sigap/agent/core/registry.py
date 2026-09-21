"""Daftar alat: nama → skema + fungsi.

Skema di sini dikirim apa adanya ke model sebagai definisi tool.
Satu sumber, supaya definisi yang dilihat model dan fungsi yang
benar-benar jalan tidak pernah berbeda.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from core.provenance import Hasil


@dataclass
class Alat:
    nama: str
    milik: str                  # kode agent pemilik
    deskripsi: str
    skema: Dict[str, Any]
    fungsi: Callable[..., Hasil]


_DAFTAR: Dict[str, Alat] = {}


def daftarkan(nama: str, milik: str, deskripsi: str,
              properties: Optional[Dict[str, Any]] = None,
              wajib: Optional[List[str]] = None) -> Callable:
    def bungkus(fn: Callable[..., Hasil]) -> Callable[..., Hasil]:
        _DAFTAR[nama] = Alat(
            nama=nama, milik=milik, deskripsi=deskripsi,
            skema={
                "type": "object",
                "properties": properties or {},
                "required": wajib or [],
                "additionalProperties": False,
            },
            fungsi=fn,
        )
        return fn
    return bungkus


def ambil(nama: str) -> Alat:
    if nama not in _DAFTAR:
        raise KeyError(f"alat '{nama}' belum terdaftar")
    return _DAFTAR[nama]


def milik(kode_agent: str) -> List[Alat]:
    return [a for a in _DAFTAR.values() if a.milik == kode_agent]


def definisi_untuk_model(kode_agent: str) -> List[dict]:
    """Bentuk yang dikirim ke Claude sebagai parameter `tools`."""
    return [
        {"name": a.nama, "description": a.deskripsi, "input_schema": a.skema, "strict": True}
        for a in milik(kode_agent)
    ]


def semua() -> Dict[str, Alat]:
    return dict(_DAFTAR)


def jalankan(nama: str, argumen: Dict[str, Any]) -> Hasil:
    return ambil(nama).fungsi(**argumen)
