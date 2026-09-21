"""Penanda asal data.

Aturan main: setiap alat mengembalikan Hasil, bukan nilai telanjang.
Kalau masukan di jalur penting bukan LANGSUNG/SIMPANAN/HITUNGAN,
kalkulator tidak boleh mengeluarkan angka penghematan (lihat engine/simulate.py).
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class Asal(str, Enum):
    LANGSUNG = "live"       # dari SAP / API resmi
    SIMPANAN = "cached"     # pernah langsung, ada waktunya
    HITUNGAN = "derived"    # dihitung dari yang langsung
    CONTOH = "modelled"     # profil perusahaan / fixture — ditandai terbuka
    TIDAK_ADA = "missing"   # ketua berhenti, tidak menebak


#: Asal yang boleh dipakai untuk mengeluarkan angka rupiah ke pengguna.
TEPERCAYA = frozenset({Asal.LANGSUNG, Asal.SIMPANAN, Asal.HITUNGAN})


@dataclass
class Hasil:
    nilai: Any
    asal: Asal
    sumber: str                      # "API_MATERIAL_STOCK_SRV" / "register TKDN"
    diambil: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    catatan: str = ""

    @property
    def tepercaya(self) -> bool:
        return self.asal in TEPERCAYA

    def ringkas(self) -> dict:
        return {
            "asal": self.asal.value,
            "sumber": self.sumber,
            "diambil": self.diambil.isoformat(timespec="seconds"),
            "catatan": self.catatan,
        }


def alat(sumber: str, asal_default: Asal = Asal.LANGSUNG) -> Callable:
    """Bungkus fungsi alat supaya nilainya selalu berlabel asal.

    Fungsi yang dibungkus boleh mengembalikan Hasil sendiri (kalau ia tahu
    asalnya berbeda, misalnya jatuh ke fixture), atau nilai biasa yang akan
    dilabeli asal_default. Kegagalan jadi TIDAK_ADA, bukan lemparan error —
    ketua yang memutuskan apakah itu menghentikan investigasi.
    """
    def bungkus(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def jalan(*args, **kwargs) -> Hasil:
            try:
                keluaran = fn(*args, **kwargs)
            except Exception as e:                       # noqa: BLE001
                return Hasil(None, Asal.TIDAK_ADA, sumber, catatan=f"{type(e).__name__}: {e}")
            if isinstance(keluaran, Hasil):
                return keluaran
            if keluaran is None:
                return Hasil(None, Asal.TIDAK_ADA, sumber, catatan="tidak ada data")
            return Hasil(keluaran, asal_default, sumber)
        jalan._sumber = sumber                           # type: ignore[attr-defined]
        return jalan
    return bungkus


def demo() -> None:
    @alat("API_MATERIAL_STOCK_SRV")
    def ambil_stok(kode: str) -> dict:
        return {"material": kode, "jumlah": 84.0}

    @alat("API_MATERIAL_STOCK_SRV")
    def gagal(kode: str) -> dict:
        raise ConnectionError("tidak ada kunci API")

    baik = ambil_stok("M-4471")
    assert baik.asal is Asal.LANGSUNG and baik.tepercaya
    assert baik.nilai["jumlah"] == 84.0

    buruk = gagal("M-4471")
    assert buruk.asal is Asal.TIDAK_ADA and not buruk.tepercaya
    assert buruk.nilai is None, "kegagalan tidak boleh mengarang nilai"
    assert "ConnectionError" in buruk.catatan

    contoh = Hasil({"jumlah": 84.0}, Asal.CONTOH, "fixture")
    assert not contoh.tepercaya, "data contoh tidak boleh dianggap tepercaya"
    print("provenance ok")


if __name__ == "__main__":
    demo()
