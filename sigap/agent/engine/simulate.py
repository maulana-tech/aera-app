"""Kalkulator. Tidak ada AI di sini, dan tidak boleh ada.

Kalau angka rupiah keluar dari model bahasa, satu pertanyaan juri
merobohkan seluruh klaim penghematan. Model yang memutuskan,
berkas ini yang menghitung.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence

from core.provenance import Asal, Hasil


@dataclass
class Kedatangan:
    id: str
    tanggal: date
    jumlah: float


@dataclass
class Cover:
    habis: Optional[date]          # hari pertama pemakaian tidak tercukupi
    tercakup_sampai: Optional[date]
    sisa_akhir: float


def hitung_cover(
    stok_awal: float,
    pemakaian_harian: float,
    mulai: date,
    kedatangan: Sequence[Kedatangan] = (),
    horizon_hari: int = 120,
) -> Cover:
    """Jalankan saldo harian ke depan. Kedatangan masuk di awal harinya."""
    if pemakaian_harian <= 0:
        return Cover(None, None, stok_awal)

    masuk: Dict[date, float] = {}
    for k in kedatangan:
        masuk[k.tanggal] = masuk.get(k.tanggal, 0.0) + k.jumlah

    saldo = stok_awal
    hari = mulai
    for _ in range(horizon_hari):
        saldo += masuk.get(hari, 0.0)
        if saldo < pemakaian_harian:
            return Cover(hari, hari - timedelta(days=1), round(saldo, 2))
        saldo -= pemakaian_harian
        hari += timedelta(days=1)
    return Cover(None, hari - timedelta(days=1), round(saldo, 2))


@dataclass
class Putusan:
    id: str
    label: str
    layak: bool
    alasan: str = ""


@dataclass
class HasilSimulasi:
    ditolak: bool
    alasan_tolak: str = ""
    habis_tanpa_tindakan: Optional[date] = None
    opsi: List[dict] = field(default_factory=list)
    kombinasi: List[dict] = field(default_factory=list)
    terpilih: Optional[dict] = None


def simulate_scenario(
    stok: Hasil,
    opsi: Hasil,
    putusan_kepatuhan: Dict[str, Putusan],
    profil: dict,
    mulai: date,
    pemakaian_harian: float,
    stok_awal: float,
    kedatangan_terjadwal: Sequence[Kedatangan] = (),
) -> HasilSimulasi:
    """Hitung biaya tiap opsi yang lolos aturan, plus kombinasinya.

    Sebuah rencana disebut AMAN kalau tidak ada kekurangan stok sampai
    pasokan terjadwal terakhir mendarat — bukan sampai selamanya. Tugasnya
    menambal celah, bukan memasok pabrik tanpa batas waktu.

    Menolak mengeluarkan angka kalau masukan penting tidak tepercaya.
    """
    for nama, h in (("stok", stok), ("opsi pasokan", opsi)):
        if not h.tepercaya:
            return HasilSimulasi(
                ditolak=True,
                alasan_tolak=(
                    f"Masukan '{nama}' berasal dari {h.asal.value} ({h.sumber}). "
                    "Angka penghematan tidak dikeluarkan sampai datanya langsung."
                ),
            )

    dasar = hitung_cover(stok_awal, pemakaian_harian, mulai, kedatangan_terjadwal)

    # celah yang harus ditambal berakhir saat pasokan terjadwal terakhir tiba
    tambal_sampai = max((k.tanggal for k in kedatangan_terjadwal), default=None)

    hidup: List[dict] = []
    keluar: List[dict] = []
    for o in opsi.nilai:
        p = putusan_kepatuhan.get(o["id"])
        baris = {
            "id": o["id"], "label": o["label"], "supplier": o["Supplier"],
            "jumlah": o["Quantity"], "tiba": o["ArrivalDate"],
            "biaya_tambahan": o["ExtraCostIDR"], "tkdn_sesudah": o["TkdnAfterPct"],
            "layak": bool(p and p.layak), "alasan": p.alasan if p else "belum dinilai",
        }
        (hidup if baris["layak"] else keluar).append(baris)

    # kombinasi: setiap opsi sendiri, lalu tiap pasangan
    kandidat: List[dict] = []
    for i, a in enumerate(hidup):
        kandidat.append({"anggota": [a], "biaya": a["biaya_tambahan"]})
        for b in hidup[i + 1:]:
            kandidat.append({"anggota": [a, b], "biaya": a["biaya_tambahan"] + b["biaya_tambahan"]})

    dinilai: List[dict] = []
    for k in kandidat:
        tiba = [Kedatangan(x["id"], date.fromisoformat(x["tiba"]), x["jumlah"]) for x in k["anggota"]]
        c = hitung_cover(stok_awal, pemakaian_harian, mulai, list(kedatangan_terjadwal) + tiba)
        tkdn = [x["tkdn_sesudah"] for x in k["anggota"] if x["tkdn_sesudah"] is not None]
        aman_sampai_tambal = (
            c.habis is None or (tambal_sampai is not None and c.habis > tambal_sampai)
        )
        dinilai.append({
            "kombinasi": "+".join(x["id"] for x in k["anggota"]),
            "anggota": [x["id"] for x in k["anggota"]],
            "biaya": k["biaya"],
            "aman": aman_sampai_tambal,
            "habis": c.habis.isoformat() if c.habis else None,
            "tkdn_sesudah": max(tkdn) if tkdn else profil["TkdnSaatIni"],
        })

    aman = [d for d in dinilai if d["aman"]]
    terpilih = min(aman, key=lambda d: d["biaya"]) if aman else None

    return HasilSimulasi(
        ditolak=False,
        habis_tanpa_tindakan=dasar.habis,
        opsi=hidup + keluar,
        kombinasi=sorted(dinilai, key=lambda d: d["biaya"]),
        terpilih=terpilih,
    )


# --------------------------------------------------------------------------- #
def demo() -> None:
    import json, pathlib
    from tools._sumber import fixture, profil

    fx = json.loads((pathlib.Path(__file__).resolve().parent.parent
                     / "fixtures" / "skenario_ningbo.json").read_text())
    mulai = date.fromisoformat(fx["Profil"]["TanggalAcuan"])

    # 1. tanpa tindakan apa pun
    dasar = hitung_cover(84.0, 9.2, mulai)
    assert dasar.habis == date(2026, 9, 13), dasar.habis
    print(f"  tanpa tindakan  → habis {dasar.habis}")

    # 2. penolakan saat data tidak tepercaya
    tolak = simulate_scenario(
        Hasil([], Asal.CONTOH, "fixture"), Hasil([], Asal.CONTOH, "fixture"),
        {}, fx["Profil"], mulai, 9.2, 84.0,
    )
    assert tolak.ditolak and "tidak dikeluarkan" in tolak.alasan_tolak
    print("  data contoh     → kalkulator menolak memberi angka ✓")

    # 3. jalur penuh, anggap datanya langsung
    stok = Hasil(fx["MaterialStock"], Asal.LANGSUNG, "API_MATERIAL_STOCK_SRV")
    opsi = Hasil(fx["AlternateSource"], Asal.LANGSUNG, "A_PurchasingInfoRecord")
    putusan = {
        "A": Putusan("A", "air freight", True),
        "B": Putusan("B", "supplier lokal", True),
        "C": Putusan("C", "realokasi SBY1", True),
        "D": Putusan("D", "Vietnam", False, "LARTAS asal baru +10 hari kerja"),
        "E": Putusan("E", "termurah", False, "TKDN jatuh ke 34,8% — ambang kontrak 40%"),
    }
    po = [Kedatangan("4500018872", date(2026, 9, 22), 120.0)]
    h = simulate_scenario(stok, opsi, putusan, fx["Profil"], mulai, 9.2, 84.0, po)

    assert not h.ditolak
    assert h.terpilih is not None, "harus ada kombinasi yang aman"
    ditolak = sorted(o["id"] for o in h.opsi if not o["layak"])
    assert ditolak == ["D", "E"], ditolak
    print(f"  ditolak aturan  → {ditolak}")
    print(f"  terpilih        → {h.terpilih['kombinasi']} "
          f"Rp {h.terpilih['biaya']:,} · TKDN {h.terpilih['tkdn_sesudah']}%")

    # yang termurah dan aman harus C+B, bukan air freight
    assert h.terpilih["kombinasi"] == "B+C", h.terpilih["kombinasi"]
    assert h.terpilih["biaya"] == 116_000_000
    a = next(d for d in h.kombinasi if d["kombinasi"] == "A")
    assert a["aman"], "air freight sendiri seharusnya menutup gap"
    assert a["biaya"] > h.terpilih["biaya"], "kombinasi harus lebih murah dari air freight"
    hemat = a["biaya"] - h.terpilih["biaya"]
    print(f"  pembanding A    → Rp {a['biaya']:,} · hemat Rp {hemat:,} "
          f"({hemat / a['biaya'] * 100:.0f}%)")
    print("simulate ok")


if __name__ == "__main__":
    demo()
