"""Alat sisanya. Yang datanya ada diimplementasikan; sisanya jujur mengembalikan TIDAK_ADA."""
from __future__ import annotations

import hashlib

from datetime import date, datetime, timedelta
from typing import List, Optional

from core.provenance import Asal, Hasil
from core.registry import daftarkan
from tools._sumber import fixture

# --------------------------------------------------------------- Ahli Permintaan
@daftarkan("get_production_schedule", "demand",
           "Jadwal produksi dan laju pemakaian harian untuk satu material di satu plant.",
           {"material": {"type": "string"}, "plant": {"type": "string"}},
           ["material", "plant"])
def get_production_schedule(material: str, plant: str) -> Hasil:
    r = next((x for x in fixture("MaterialStock")
              if x["Material"] == material and x["Plant"] == plant), None)
    if r is None:
        return Hasil(None, Asal.TIDAK_ADA, "API_PRODUCTION_ORDER_2_SRV")
    return Hasil({"material": material, "plant": plant,
                  "pemakaian_harian": r["DailyConsumption"], "satuan": r["BaseUnit"]},
                 Asal.CONTOH, "fixture:MaterialStock")


@daftarkan("get_demand_signal", "demand",
           "Perubahan permintaan pelanggan yang belum tercermin di jadwal produksi.",
           {"material": {"type": "string"}}, ["material"])
def get_demand_signal(material: str) -> Hasil:
    return Hasil(None, Asal.TIDAK_ADA, "SAP IBP demand plan",
                 catatan="belum tersambung — sandbox SAP tidak menyediakan rencana permintaan")


# ------------------------------------------------------- Ahli Keabsahan Stok
@daftarkan("get_quality_holds", "inventory",
           "Stok yang tercatat ada tapi sedang ditahan karena hasil inspeksi mutu.",
           {"material": {"type": "string"}, "plant": {"type": "string"}},
           ["material", "plant"])
def get_quality_holds(material: str, plant: str) -> Hasil:
    return Hasil([], Asal.CONTOH, "API_INSPECTIONLOT_SRV",
                 catatan="fixture tidak memuat tahanan mutu untuk skenario ini")


@daftarkan("get_safety_stock_policy", "inventory",
           "Kebijakan stok cadangan minimum yang tidak boleh dipakai untuk produksi normal.",
           {"material": {"type": "string"}, "plant": {"type": "string"}},
           ["material", "plant"])
def get_safety_stock_policy(material: str, plant: str) -> Hasil:
    return Hasil(None, Asal.TIDAK_ADA, "API_PRODUCT_SRV (MARC)",
                 catatan="belum diisi di fixture — perlu data master pelanggan")


# ------------------------------------------------------------- Ahli Logistik
@daftarkan("estimate_eta", "logistics",
           "Perkirakan tanggal tiba yang realistis, memperhitungkan waktu bongkar pelabuhan "
           "dan pengurusan bea cukai. Deterministik — bukan tebakan model.",
           {"opsi_id": {"type": "string"},
            "dwell_hari": {"type": "integer", "description": "waktu bongkar, default 4"}},
           ["opsi_id"])
def estimate_eta(opsi_id: str, dwell_hari: int = 4) -> Hasil:
    o = next((x for x in fixture("AlternateSource") if x["id"] == opsi_id), None)
    if o is None:
        return Hasil(None, Asal.TIDAK_ADA, "model dwell time")
    dasar = date.fromisoformat(o["ArrivalDate"])
    impor = o["Origin"] != "ID"
    efektif = dasar + timedelta(days=dwell_hari if impor else 0)
    return Hasil({"opsi_id": opsi_id, "tiba_tercatat": dasar.isoformat(),
                  "tiba_efektif": efektif.isoformat(),
                  "dwell_hari": dwell_hari if impor else 0,
                  "dasar": "impor lewat pelabuhan" if impor else "domestik, tanpa dwell"},
                 Asal.HITUNGAN, "engine dwell time")


@daftarkan("get_shipment_status", "logistics",
           "Posisi dan status kiriman yang sedang berjalan.",
           {"purchase_order": {"type": "string"}}, ["purchase_order"])
def get_shipment_status(purchase_order: str) -> Hasil:
    r = next((x for x in fixture("PurchaseOrder") if x["PurchaseOrder"] == purchase_order), None)
    if r is None:
        return Hasil(None, Asal.TIDAK_ADA, "SAP Business Network")
    return Hasil({"purchase_order": purchase_order, "status": r["Status"],
                  "tiba_semula": r["DeliveryDate"], "tiba_revisi": r["RevisedDeliveryDate"]},
                 Asal.CONTOH, "fixture:PurchaseOrder")


# ------------------------------------------------------------ Ahli Preseden
@daftarkan("search_past_incidents", "precedent",
           "Cari kejadian serupa di masa lalu beserta bagaimana penanganannya berakhir.",
           {"kata_kunci": {"type": "string"}}, ["kata_kunci"])
def search_past_incidents(kata_kunci: str) -> Hasil:
    return Hasil([], Asal.TIDAK_ADA, "Bedrock Knowledge Bases",
                 catatan="basis pengetahuan insiden belum diisi — ini kejadian pertama")


# ------------------------------------------------------------ Ahli Eksekusi
_CATATAN_AKSI: List[dict] = []


def aksi_tercatat() -> List[dict]:
    return list(_CATATAN_AKSI)


def kunci_idempoten(jenis: str, **rinci) -> str:
    """Kunci stabil dari isi aksi. Aksi yang sama tidak pernah dikirim dua kali."""
    sidik = "|".join(f"{k}={rinci[k]}" for k in sorted(rinci))
    return f"{jenis}:{hashlib.sha256(sidik.encode()).hexdigest()[:16]}"


def _catat(jenis: str, otonom: bool, **rinci) -> Hasil:
    from clients import sap_s4
    from core import simpan
    from core.konfigurasi import KONF

    kunci = kunci_idempoten(jenis, **rinci)
    jalan_id = rinci.pop("_jalan_id", None) or "run_lepas"
    aksi = simpan.catat_aksi(jalan_id, kunci, jenis, otonom, rinci)

    if aksi.get("diulang"):
        return Hasil(aksi, Asal.HITUNGAN, "catatan aksi",
                     catatan="aksi identik sudah pernah diajukan — tidak dikirim ulang")

    # Hanya aksi otonom yang langsung menyentuh SAP. Sisanya menunggu persetujuan.
    if otonom and sap_s4.tersedia() and jenis == "stock_transfer":
        try:
            r = sap_s4.kirim("API_STOCK_TRANSFER_SRV", "A_StockTransfer",
                             rinci, kunci_idempoten=kunci)
            return Hasil(aksi | {"referensi_sap": r.get("d", {}).get("MaterialDocument")},
                         Asal.LANGSUNG, "API_STOCK_TRANSFER_SRV")
        except Exception as e:                                       # noqa: BLE001
            return Hasil(aksi, Asal.TIDAK_ADA, "API_STOCK_TRANSFER_SRV",
                         catatan=f"gagal menulis ke SAP: {type(e).__name__}: {e}")

    sumber = "catatan aksi" if sap_s4.tersedia() else "catatan aksi (SAP belum tersambung)"
    return Hasil(aksi, Asal.HITUNGAN, sumber)


BATAS_OTONOM_IDR = 50_000_000


@daftarkan("create_stock_transfer", "execution",
           "Pindahkan stok antar plant. Otonom kalau dampak biayanya di bawah Rp 50 juta.",
           {"material": {"type": "string"}, "dari_plant": {"type": "string"},
            "ke_plant": {"type": "string"}, "jumlah": {"type": "number"},
            "biaya_idr": {"type": "integer"}},
           ["material", "dari_plant", "ke_plant", "jumlah", "biaya_idr"])
def create_stock_transfer(material: str, dari_plant: str, ke_plant: str,
                          jumlah: float, biaya_idr: int) -> Hasil:
    return _catat("stock_transfer", biaya_idr < BATAS_OTONOM_IDR,
                  material=material, dari=dari_plant, ke=ke_plant,
                  jumlah=jumlah, biaya_idr=biaya_idr)


@daftarkan("create_draft_po", "execution",
           "Buat DRAF pesanan pembelian. Selalu menunggu persetujuan buyer — tidak pernah otonom.",
           {"supplier": {"type": "string"}, "material": {"type": "string"},
            "jumlah": {"type": "number"}, "butuh_tanggal": {"type": "string"},
            "biaya_idr": {"type": "integer"}},
           ["supplier", "material", "jumlah", "butuh_tanggal", "biaya_idr"])
def create_draft_po(supplier: str, material: str, jumlah: float,
                    butuh_tanggal: str, biaya_idr: int) -> Hasil:
    return _catat("draft_po", False, supplier=supplier, material=material,
                  jumlah=jumlah, butuh_tanggal=butuh_tanggal, biaya_idr=biaya_idr)


@daftarkan("notify", "execution",
           "Beri tahu peran yang terdampak, sertakan bukti yang mendasari.",
           {"peran": {"type": "string"}, "pesan": {"type": "string"}},
           ["peran", "pesan"])
def notify(peran: str, pesan: str) -> Hasil:
    return _catat("notify", True, peran=peran, pesan=pesan)


@daftarkan("monitor_shipment", "execution",
           "Pantau kiriman sampai diterima, lalu catat hasilnya ke memori.",
           {"referensi": {"type": "string"}}, ["referensi"])
def monitor_shipment(referensi: str) -> Hasil:
    return _catat("monitor", True, referensi=referensi)
