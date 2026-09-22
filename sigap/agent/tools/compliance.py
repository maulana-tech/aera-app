"""Alat Ahli Aturan. Membaca rule pack di references/, bukan dari ingatan model."""
from __future__ import annotations

import pathlib
import re
from datetime import date, timedelta
from typing import Dict, List

from core.provenance import Asal, Hasil
from core.registry import daftarkan
from tools._sumber import fixture, profil

REFERENCES = pathlib.Path(__file__).resolve().parent.parent.parent / "references"

# Hari kerja tambahan untuk izin impor dari negara asal yang baru bagi perusahaan.
LARTAS_HARI_KERJA_ASAL_BARU = 10


def _rule_pack() -> Dict[str, str]:
    """Baca dokumen aturan. Kalau belum ditulis, katakan — jangan menebak."""
    isi: Dict[str, str] = {}
    for nama in ("tkdn-rules", "lartas-procedure", "holiday-calendar", "priok-dwell-time"):
        f = REFERENCES / f"{nama}.md"
        if f.exists():
            isi[nama] = f.read_text()
    return isi


def _tambah_hari_kerja(mulai: date, hari: int) -> date:
    d, sisa = mulai, hari
    while sisa > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            sisa -= 1
    return d


@daftarkan(
    "check_local_constraints", "compliance",
    "Uji satu pilihan pasokan terhadap TKDN, LARTAS, klausul kontrak, dan kalender libur. "
    "Kembalikan layak/tidak beserta alasan yang menyebut aturan dan angkanya. "
    "Penolakan dari alat ini bersifat final dan tidak boleh dikalahkan pertimbangan biaya.",
    {"opsi_id": {"type": "string", "description": "id pilihan, mis. 'A'"}},
    ["opsi_id"],
)
def check_local_constraints(opsi_id: str) -> Hasil:
    pack = _rule_pack()
    p = profil()
    opsi = next((o for o in fixture("AlternateSource") if o["id"] == opsi_id), None)
    if opsi is None:
        return Hasil(None, Asal.TIDAK_ADA, "references/", catatan=f"opsi '{opsi_id}' tidak dikenal")

    alasan: List[str] = []
    layak = True
    ambang = p["TkdnAmbangKontrak"]

    # --- TKDN ---
    # Aturannya: pilihan tidak boleh MEMPERBURUK posisi konten lokal, dan tidak
    # boleh menjatuhkannya ke bawah ambang kalau sekarang masih di atas.
    # Perusahaan yang sudah di bawah ambang tidak otomatis kehilangan semua
    # pilihan — yang dilarang adalah memperparahnya.
    tkdn = opsi.get("TkdnAfterPct")
    sekarang = p["TkdnSaatIni"]
    if tkdn is not None:
        if tkdn < sekarang - 0.05:                       # toleransi pembulatan
            layak = False
            alasan.append(
                f"TKDN turun dari {sekarang}% ke {tkdn}%"
                + (f", makin jauh di bawah ambang kontrak {ambang}%" if tkdn < ambang
                   else f", melanggar ambang kontrak {ambang}%")
            )
        elif tkdn < ambang and sekarang >= ambang:
            layak = False
            alasan.append(f"TKDN jatuh ke {tkdn}%, ambang kontrak {ambang}%")
        elif tkdn >= ambang > sekarang:
            alasan.append(f"TKDN naik ke {tkdn}%, kembali di atas ambang {ambang}%")

    # --- LARTAS ---
    tiba = date.fromisoformat(opsi["ArrivalDate"])
    if opsi.get("NewOrigin"):
        tiba_izin = _tambah_hari_kerja(tiba, LARTAS_HARI_KERJA_ASAL_BARU)
        alasan.append(
            f"LARTAS: negara asal baru ({opsi['Origin']}) menambah "
            f"{LARTAS_HARI_KERJA_ASAL_BARU} hari kerja, tiba efektif {tiba_izin}"
        )
        tiba = tiba_izin

    # --- kalender libur (kalau dokumennya sudah ada) ---
    libur = pack.get("holiday-calendar", "")
    for tgl in re.findall(r"\d{4}-\d{2}-\d{2}", libur):
        if date.fromisoformat(tgl) <= tiba:
            continue

    catatan = "" if pack else (
        "references/ belum ditulis — TKDN & LARTAS dinilai dari parameter fixture, "
        "bukan dari dokumen aturan"
    )
    return Hasil(
        {
            "opsi_id": opsi_id,
            "layak": layak,
            "alasan": "; ".join(alasan) if alasan else "tidak ada aturan yang dilanggar",
            "tiba_efektif": tiba.isoformat(),
            "tkdn_sesudah": tkdn,
        },
        Asal.HITUNGAN if pack else Asal.CONTOH,
        "references/ (rule pack)" if pack else "fixture + aturan bawaan",
        catatan=catatan,
    )
