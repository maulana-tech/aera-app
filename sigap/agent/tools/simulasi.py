"""Alat Ahli Hitungan.

Pembungkus tipis di atas engine/simulate.py. Model memanggil alat ini;
yang menghitung tetap Python biasa. Model memutuskan, aritmetika menghitung.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from core.provenance import Asal, Hasil
from core.registry import daftarkan
from engine.simulate import Kedatangan, Putusan, simulate_scenario
from tools._sumber import fixture, profil
from tools.compliance import check_local_constraints
from tools.impact import get_material_stock
from tools.sourcing import find_alternate_sources


@daftarkan(
    "simulate_scenario", "simulation",
    "Hitung biaya, tanggal habis stok, OTIF, dan dampak TKDN untuk tiap pilihan pasokan "
    "yang lolos aturan, beserta kombinasinya. Deterministik — hasilnya selalu sama untuk "
    "masukan yang sama. Menolak mengeluarkan angka kalau data masukannya belum tepercaya.",
    {"material": {"type": "string"},
     "plant": {"type": "string"},
     "opsi_layak": {"type": "array", "items": {"type": "string"},
                    "description": "id pilihan yang sudah lolos Ahli Aturan, mis. ['A','B','C']"}},
    ["material", "plant"],
)
def simulate_scenario_tool(material: str, plant: str,
                           opsi_layak: Optional[List[str]] = None) -> Hasil:
    p = profil()
    mulai = date.fromisoformat(p["TanggalAcuan"])

    stok = get_material_stock(material=material, plant=plant)
    baris = (stok.nilai or [{}])[0]
    awal = baris.get("MatlWrhsStkQtyInMatlBaseUnit")
    harian = baris.get("DailyConsumption")
    if awal is None or harian is None:
        return Hasil(None, Asal.TIDAK_ADA, "engine/simulate.py",
                     catatan=f"stok {material} di {plant} tidak ditemukan")

    opsi = find_alternate_sources(material)

    # Putusan kepatuhan diambil dari Ahli Aturan, bukan ditebak di sini.
    putusan = {}
    for o in (opsi.nilai or []):
        if opsi_layak is not None:
            putusan[o["id"]] = Putusan(o["id"], o["label"], o["id"] in opsi_layak)
            continue
        h = check_local_constraints(o["id"])
        v = h.nilai or {}
        putusan[o["id"]] = Putusan(o["id"], o["label"],
                                   bool(v.get("layak")), v.get("alasan", ""))

    # pasokan terjadwal yang sudah dalam perjalanan
    terjadwal = [
        Kedatangan(r["PurchaseOrder"],
                   date.fromisoformat(r["RevisedDeliveryDate"]),
                   float(r["OrderQuantity"]))
        for r in fixture("PurchaseOrder")
        if r["Material"] == material and r["Plant"] == plant
    ]

    h = simulate_scenario(stok, opsi, putusan, p, mulai,
                          float(harian), float(awal), terjadwal)

    if h.ditolak:
        return Hasil({"ditolak": True, "alasan": h.alasan_tolak},
                     Asal.TIDAK_ADA, "engine/simulate.py", catatan=h.alasan_tolak)

    return Hasil({
        "habis_tanpa_tindakan": str(h.habis_tanpa_tindakan),
        "opsi": h.opsi,
        "kombinasi": h.kombinasi[:8],
        "terpilih": h.terpilih,
    }, Asal.HITUNGAN, "engine/simulate.py")
