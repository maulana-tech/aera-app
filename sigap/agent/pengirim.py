"""Pengirim aksi yang sudah disetujui ke SAP.

Dipisah dari agent: agent mengajukan, manusia menyetujui, berkas ini yang
mengirim. Jalankan berkala.

    python3 pengirim.py              # sekali jalan
"""
from __future__ import annotations

import json
import sys

from clients import sap_s4
from core import simpan

PETA = {
    "draft_po": ("API_PURCHASEREQ_PROCESS_SRV", "A_PurchaseRequisitionHeader"),
    "stock_transfer": ("API_STOCK_TRANSFER_SRV", "A_StockTransfer"),
    "create_sourcing_event": ("API_SOURCING_PROJECT_SRV", "A_SourcingProject"),
}


def kirim_yang_disetujui() -> int:
    if not sap_s4.tersedia():
        print("SAP_API_KEY belum diisi — tidak ada yang dikirim.")
        return 0

    with simpan.buka() as c:
        antre = c.execute("SELECT * FROM aksi WHERE status='disetujui'").fetchall()

    terkirim = 0
    for a in antre:
        jenis = a["jenis"]
        if jenis not in PETA:
            print(f"  lewati {a['id']}: jenis '{jenis}' belum dipetakan ke SAP")
            continue
        layanan, entitas = PETA[jenis]
        try:
            r = sap_s4.kirim(layanan, entitas, json.loads(a["muatan"]),
                             kunci_idempoten=a["kunci_idempoten"])
            ref = (r.get("d") or {}).get("PurchaseRequisition") or \
                  (r.get("d") or {}).get("MaterialDocument") or "terkirim"
            simpan.tandai_terkirim(a["id"], str(ref))
            print(f"  ✓ {a['id']} → {layanan} · {ref}")
            terkirim += 1
        except Exception as e:                                       # noqa: BLE001
            # Gagal TIDAK mengubah status. Aksi tetap 'disetujui' dan dicoba lagi
            # nanti — kunci idempoten mencegah pesanan ganda.
            print(f"  ✗ {a['id']}: {type(e).__name__}: {e}", file=sys.stderr)
    return terkirim


if __name__ == "__main__":
    n = kirim_yang_disetujui()
    print(f"{n} aksi terkirim.")
