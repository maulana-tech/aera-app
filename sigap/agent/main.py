"""Jalankan satu skenario, keluarkan jejaknya.

    python3 main.py                      # skenario Ningbo
    python3 main.py --keluar ../../app/sigap/jejak.json

Tanpa kredensial Bedrock, program jalan dalam MODE RUNUT: urutan langkahnya
mengikuti rancangan, dan angkanya tetap dihitung kalkulator sungguhan.
Mode ini ditandai di jejak — tidak berpura-pura agent yang menalar.
"""
from __future__ import annotations

import argparse
import os
from datetime import date

from agents.definisi import SEMUA
from core.jejak import Jejak
from core.provenance import Asal, Hasil
from engine.simulate import Kedatangan, Putusan, simulate_scenario
from tools._sumber import profil
from tools.impact import (get_bom_explosion, get_material_stock,
                          get_open_purchase_orders, get_sales_order_commitments)
from tools.sourcing import find_alternate_sources

A = SEMUA


def jalankan_ningbo(anggap_langsung: bool = False) -> Jejak:
    mode = "otonom" if os.environ.get("AWS_REGION") and os.environ.get("BEDROCK_READY") else "runut"
    j = Jejak("Topan menutup Pelabuhan Ningbo",
              "Advisory maritim: Ningbo–Zhoushan tutup 8–13 Sep 2026", mode)
    p = profil()
    mulai = date.fromisoformat(p["TanggalAcuan"])

    j.catat("DETECT", A["supervisor"], "Mengenali Ningbo sebagai jalur yang dipakai perusahaan",
            ["detect_disruption"])

    po = get_open_purchase_orders(port="CNNGB")
    j.catat("SCOPE", A["impact"],
            f"{len(po.nilai or [])} pesanan pembelian lewat Ningbo terdampak",
            ["get_open_purchase_orders"], po,
            pesanan=[r["PurchaseOrder"] for r in (po.nilai or [])])

    stok = get_material_stock(material="M-4471", plant="KRW1")
    krw = (stok.nilai or [{}])[0]
    harian = krw.get("DailyConsumption", 9.2)
    awal = krw.get("MatlWrhsStkQtyInMatlBaseUnit", 0.0)
    j.catat("IMPACT", A["impact"],
            f"M-4471 di KRW1: {awal} ton, pemakaian {harian} ton/hari",
            ["get_material_stock", "get_bom_explosion"], stok,
            material="M-4471", stok_ton=awal, pemakaian_harian=harian)

    bom = get_bom_explosion("M-4471")
    fg = [r["FinishedGood"] for r in (bom.nilai or [])]
    so = get_sales_order_commitments(fg)
    nilai = sum(r["NetAmount"] for r in (so.nilai or []))
    j.catat("QUANTIFY", A["impact"],
            f"{len(so.nilai or [])} pesanan pelanggan senilai Rp {nilai:,} terancam",
            ["get_sales_order_commitments"], so, nilai_idr=nilai, produk=fg)

    opsi = find_alternate_sources("M-4471")
    j.catat("GENERATE", A["sourcing"],
            f"{len(opsi.nilai or [])} pilihan pasokan disusun",
            ["find_alternate_sources"], opsi,
            pilihan=[o["id"] for o in (opsi.nilai or [])])

    putusan = {
        "A": Putusan("A", "air freight", True),
        "B": Putusan("B", "supplier lokal Gresik", True),
        "C": Putusan("C", "realokasi SBY1", True),
        "D": Putusan("D", "Vietnam", False,
                     "LARTAS: negara asal baru menambah 10 hari kerja — tiba setelah lini berhenti"),
        "E": Putusan("E", "termurah Tiongkok", False,
                     f"TKDN turun ke 34,8%; ambang kontrak {p['TkdnAmbangKontrak']}%"),
    }
    tolak = [k for k, v in putusan.items() if not v.layak]
    j.catat("FILTER", A["compliance"],
            f"{len(tolak)} pilihan dicoret karena aturan, bukan karena harga",
            ["check_local_constraints"],
            Hasil(putusan, Asal.CONTOH, "references/ (rule pack)"),
            ditolak=tolak, alasan={k: putusan[k].alasan for k in tolak})

    if anggap_langsung:                      # simulasi seolah kunci SAP sudah ada
        stok = Hasil(stok.nilai, Asal.LANGSUNG, "API_MATERIAL_STOCK_SRV")
        opsi = Hasil(opsi.nilai, Asal.LANGSUNG, "A_PurchasingInfoRecord")

    po_terjadwal = [Kedatangan("4500018872", date(2026, 9, 22), 120.0)]
    sim = simulate_scenario(stok, opsi, putusan, p, mulai, harian, awal, po_terjadwal)

    if sim.ditolak:
        j.catat("SIMULATE", A["simulation"], sim.alasan_tolak, ["simulate_scenario"],
                Hasil(None, Asal.TIDAK_ADA, "engine/simulate.py"))
        j.keputusan = {"status": "ditahan", "alasan": sim.alasan_tolak}
        return j

    t = sim.terpilih
    j.catat("SIMULATE", A["simulation"],
            f"Kombinasi termurah yang aman: {t['kombinasi']} — Rp {t['biaya']:,}",
            ["simulate_scenario"],
            Hasil(sim.kombinasi, Asal.HITUNGAN, "engine/simulate.py"),
            kombinasi=sim.kombinasi[:6], habis_tanpa_tindakan=str(sim.habis_tanpa_tindakan))

    sendiri = [k for k in sim.kombinasi if len(k["anggota"]) == 1 and k["aman"]]
    banding = min(sendiri, key=lambda k: k["biaya"]) if sendiri else None
    hemat = (banding["biaya"] - t["biaya"]) if banding else 0

    j.catat("DECIDE", A["supervisor"],
            f"Rekomendasi {t['kombinasi']}, bukan {banding['kombinasi'] if banding else '—'} "
            f"— hemat Rp {hemat:,}",
            [], None,
            risiko_sisa="SBY1 tersisa 4 hari cover sampai PO 4500018901 mendarat 24 Sep")

    j.catat("ACT", A["execution"],
            "Pemindahan stok dijalankan sendiri; pesanan pembelian berhenti sebagai draf",
            ["create_stock_transfer", "create_draft_po", "notify"], None,
            otonom="create_stock_transfer (< Rp 50 juta)",
            butuh_persetujuan="create_draft_po")

    j.keputusan = {
        "status": "menunggu persetujuan",
        "kombinasi": t["kombinasi"],
        "biaya_idr": t["biaya"],
        "pembanding": banding["kombinasi"] if banding else None,
        "pembanding_biaya_idr": banding["biaya"] if banding else None,
        "hemat_idr": hemat,
        "hemat_pct": round(hemat / banding["biaya"] * 100) if banding else 0,
        "tkdn_sebelum": p["TkdnSaatIni"],
        "tkdn_sesudah": t["tkdn_sesudah"],
        "nilai_terlindungi_idr": nilai,
        "ditolak": tolak,
    }
    return j


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--keluar", default="../../app/sigap/jejak.json")
    ap.add_argument("--anggap-langsung", action="store_true",
                    help="perlakukan fixture seolah data langsung (untuk mencoba jalur penuh)")
    a = ap.parse_args()

    j = jalankan_ningbo(a.anggap_langsung)
    j.tulis(a.keluar)
    print(f"mode      : {j.mode}")
    print(f"langkah   : {len(j.langkah)}")
    print(f"agent     : {' → '.join(j.agent_terpakai)}")
    print(f"keputusan : {j.keputusan.get('status')}")
    if j.keputusan.get("kombinasi"):
        k = j.keputusan
        print(f"            {k['kombinasi']} Rp {k['biaya_idr']:,} "
              f"(hemat Rp {k['hemat_idr']:,} / {k['hemat_pct']}%)")
    print(f"jejak     : {a.keluar}")
