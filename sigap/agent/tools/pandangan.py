"""Pandangan data per domain.

Tiap halaman domain butuh tabelnya sendiri. Berkas ini merangkai alat yang
sudah ada jadi bentuk yang enak ditampilkan — tidak menambah sumber data baru,
jadi label asalnya tetap mengalir apa adanya.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from core.provenance import Asal, Hasil
from engine.simulate import Kedatangan, Putusan, hitung_cover, simulate_scenario
from tools._sumber import fixture, profil
from tools.compliance import check_local_constraints
from tools.impact import get_material_stock, get_open_purchase_orders
from tools.lainnya import estimate_eta
from tools.sourcing import find_alternate_sources

DOMAIN = {
    "permintaan": "demand",
    "stok": "inventory",
    "sumber": "sourcing",
    "logistik": "logistics",
    "perhitungan": "simulation",
    "eksekusi": "execution",
}


def _bungkus(baris: List[dict], kolom: List[dict], h: Hasil, catatan: str = "") -> dict:
    return {
        "kolom": kolom,
        "baris": baris,
        "asal": h.asal.value,
        "sumber": h.sumber,
        "catatan": catatan or h.catatan,
    }


def stok() -> dict:
    h = get_material_stock()
    baris = []
    p = profil()
    mulai = date.fromisoformat(p["TanggalAcuan"])
    for r in (h.nilai or []):
        jml = r.get("MatlWrhsStkQtyInMatlBaseUnit", 0)
        harian = r.get("DailyConsumption", 0)
        c = hitung_cover(float(jml), float(harian), mulai)
        baris.append({
            "material": r.get("Material"),
            "deskripsi": r.get("Description"),
            "plant": r.get("Plant"),
            "jumlah": jml,
            "satuan": r.get("BaseUnit"),
            "pemakaian_harian": harian,
            "habis": c.habis.isoformat() if c.habis else None,
            "hari_tersisa": round(float(jml) / float(harian), 1) if harian else None,
        })
    baris.sort(key=lambda b: b["hari_tersisa"] or 9999)
    return _bungkus(baris, [
        {"k": "material", "l": "Material"}, {"k": "deskripsi", "l": "Nama"},
        {"k": "plant", "l": "Plant"}, {"k": "jumlah", "l": "Jumlah", "n": True},
        {"k": "pemakaian_harian", "l": "Pemakaian/hari", "n": True},
        {"k": "hari_tersisa", "l": "Hari tersisa", "n": True},
        {"k": "habis", "l": "Habis"},
    ], h)


def permintaan() -> dict:
    h = get_material_stock()
    baris = [{
        "material": r.get("Material"), "plant": r.get("Plant"),
        "pemakaian_harian": r.get("DailyConsumption"),
        "satuan": r.get("BaseUnit"),
        "sinyal": "belum tersambung",
    } for r in (h.nilai or [])]
    return _bungkus(baris, [
        {"k": "material", "l": "Material"}, {"k": "plant", "l": "Plant"},
        {"k": "pemakaian_harian", "l": "Pemakaian/hari", "n": True},
        {"k": "sinyal", "l": "Sinyal permintaan"},
    ], h, "Sinyal perubahan permintaan butuh SAP IBP — belum tersambung. "
          "Yang ditampilkan baru laju pemakaian dari jadwal produksi.")


def sumber() -> dict:
    h = find_alternate_sources("M-4471")
    baris = []
    for o in (h.nilai or []):
        v = (check_local_constraints(o["id"]).nilai or {})
        baris.append({
            "id": o["id"], "label": o["label"], "supplier": o["Supplier"],
            "jumlah": o["Quantity"], "tiba": o["ArrivalDate"],
            "biaya_idr": o["ExtraCostIDR"], "tkdn": o.get("TkdnAfterPct"),
            "asal_negara": o["Origin"],
            "layak": v.get("layak"), "alasan": v.get("alasan"),
        })
    return _bungkus(baris, [
        {"k": "id", "l": "#"}, {"k": "label", "l": "Pilihan"},
        {"k": "tiba", "l": "Tiba"}, {"k": "biaya_idr", "l": "Biaya tambahan", "rp": True},
        {"k": "tkdn", "l": "TKDN", "n": True}, {"k": "layak", "l": "Lolos aturan"},
    ], h)


def logistik() -> dict:
    po = get_open_purchase_orders()
    baris = [{
        "purchase_order": r["PurchaseOrder"], "material": r["Material"],
        "plant": r["Plant"], "jumlah": r["OrderQuantity"],
        "pelabuhan": r.get("LoadingPort"), "status": r["Status"],
        "tiba_semula": r["DeliveryDate"], "tiba_revisi": r["RevisedDeliveryDate"],
        "mundur_hari": (date.fromisoformat(r["RevisedDeliveryDate"])
                        - date.fromisoformat(r["DeliveryDate"])).days,
    } for r in (po.nilai or [])]
    for o in (find_alternate_sources("M-4471").nilai or []):
        e = (estimate_eta(o["id"]).nilai or {})
        if e:
            baris.append({
                "purchase_order": f"opsi {o['id']}", "material": o["Material"],
                "plant": "—", "jumlah": o["Quantity"], "pelabuhan": o["Origin"],
                "status": "rencana", "tiba_semula": e["tiba_tercatat"],
                "tiba_revisi": e["tiba_efektif"], "mundur_hari": e["dwell_hari"],
            })
    return _bungkus(baris, [
        {"k": "purchase_order", "l": "Referensi"}, {"k": "material", "l": "Material"},
        {"k": "pelabuhan", "l": "Asal"}, {"k": "status", "l": "Status"},
        {"k": "tiba_semula", "l": "Tiba semula"}, {"k": "tiba_revisi", "l": "Tiba nyata"},
        {"k": "mundur_hari", "l": "Mundur (hari)", "n": True},
    ], po)


def perhitungan() -> dict:
    from tools.simulasi import simulate_scenario_tool
    h = simulate_scenario_tool("M-4471", "KRW1")
    v = h.nilai or {}
    if v.get("ditolak") or not v.get("kombinasi"):
        return _bungkus([], [], h, v.get("alasan") or h.catatan)
    baris = [{
        "kombinasi": k["kombinasi"], "biaya_idr": k["biaya"],
        "aman": k["aman"], "habis": k["habis"], "tkdn": k["tkdn_sesudah"],
        "terpilih": k["kombinasi"] == (v.get("terpilih") or {}).get("kombinasi"),
    } for k in v["kombinasi"]]
    return _bungkus(baris, [
        {"k": "kombinasi", "l": "Kombinasi"}, {"k": "biaya_idr", "l": "Biaya", "rp": True},
        {"k": "aman", "l": "Menutup celah"}, {"k": "habis", "l": "Habis kalau dipakai"},
        {"k": "tkdn", "l": "TKDN", "n": True},
    ], h, f"Tanpa tindakan, stok habis {v.get('habis_tanpa_tindakan')}.")


def eksekusi() -> dict:
    from core import simpan
    with simpan.buka() as c:
        rows = c.execute(
            "SELECT a.*, p.judul FROM aksi a JOIN jalan j ON j.id=a.jalan_id"
            " JOIN peristiwa p ON p.id=j.peristiwa_id ORDER BY a.dibuat DESC LIMIT 100"
        ).fetchall()
    import json as _json
    baris = []
    for r in rows:
        m = _json.loads(r["muatan"])
        baris.append({
            "id": r["id"], "jenis": r["jenis"], "status": r["status"],
            "otonom": bool(r["otonom"]), "biaya_idr": m.get("biaya_idr"),
            "gangguan": r["judul"], "jalan_id": r["jalan_id"],
            "referensi_sap": r["referensi_sap"], "dibuat": r["dibuat"],
        })
    return _bungkus(baris, [
        {"k": "jenis", "l": "Aksi"}, {"k": "status", "l": "Status"},
        {"k": "biaya_idr", "l": "Nilai", "rp": True},
        {"k": "gangguan", "l": "Gangguan"}, {"k": "referensi_sap", "l": "Referensi SAP"},
    ], Hasil(baris, Asal.LANGSUNG, "tabel aksi"))


PANDANGAN = {
    "stok": stok, "permintaan": permintaan, "sumber": sumber,
    "logistik": logistik, "perhitungan": perhitungan, "eksekusi": eksekusi,
}
