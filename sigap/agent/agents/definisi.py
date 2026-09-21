"""Definisi 11 agent. Instruksinya di prompts/, bukan di sini."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import List

PROMPTS = pathlib.Path(__file__).resolve().parent.parent / "prompts"


@dataclass
class Agent:
    kode: str
    nama: str
    peran: str
    alat: List[str] = field(default_factory=list)
    effort: str = "medium"       # supervisor & kepatuhan "high" — lihat TEKNIS.md
    veto: bool = False

    @property
    def instruksi(self) -> str:
        f = PROMPTS / f"{self.kode}.txt"
        return f.read_text() if f.exists() else f"[belum ditulis: prompts/{self.kode}.txt]"


SUPERVISOR = Agent(
    "supervisor", "SIGAP Core",
    "Memasukkan ahli ke dalam tim sesuai temuan terakhir, menilai kapan bukti cukup, "
    "menulis rekomendasi beserta trade-off dan risiko sisa.",
    ["detect_disruption"], effort="high",
)

AHLI = [
    Agent("impact", "Ahli Dampak",
          "Menelusuri gangguan lewat pesanan, stok, dan struktur produk ke komitmen pelanggan yang benar-benar terancam.",
          ["get_open_purchase_orders", "get_material_stock", "get_bom_explosion", "get_sales_order_commitments"]),
    Agent("demand", "Ahli Permintaan",
          "Memiliki sisi permintaan. Pemakaian harian adalah variabel yang bisa bergerak, bukan angka tetap.",
          ["get_demand_signal", "get_production_schedule"]),
    Agent("inventory", "Ahli Keabsahan Stok",
          "Stok mana yang benar-benar bisa dipakai — tahanan mutu, batch ditolak, cadangan minimum.",
          ["get_quality_holds", "get_safety_stock_policy"]),
    Agent("sourcing", "Ahli Pencari Sumber",
          "Mencari dan mengkualifikasi pasokan pengganti: supplier lain, stok internal, kirim cepat.",
          ["find_alternate_sources"]),
    Agent("logistics", "Ahli Logistik",
          "Memodelkan tanggal tiba yang tahan uji: waktu bongkar pelabuhan, pindah kapal, bea cukai, moda angkut.",
          ["get_shipment_status", "estimate_eta"]),
    Agent("compliance", "Ahli Aturan",
          "Menguji tiap kandidat terhadap TKDN, LARTAS, klausul kontrak, dan kalender libur. "
          "Penolakannya tidak bisa dikalahkan biaya.",
          ["check_local_constraints"], effort="high", veto=True),
    Agent("simulation", "Ahli Hitungan",
          "Menghitung opsi yang lolos beserta kombinasinya. Deterministik — memanggil engine/simulate.py, bukan menalar sendiri.",
          ["simulate_scenario"]),
    Agent("precedent", "Ahli Preseden",
          "Memori institusional: apa yang pernah dilakukan pada kejadian serupa, dan bagaimana hasilnya.",
          ["search_past_incidents"]),
    Agent("execution", "Ahli Eksekusi",
          "Menulis balik ke SAP dalam batas wewenang, memberi tahu peran terkait, memantau sampai barang diterima.",
          ["create_stock_transfer", "create_draft_po", "notify", "monitor_shipment",
           "create_sourcing_event", "propose_safety_stock_change"]),   # dua terakhir: mode Cegah
    Agent("exposure", "Ahli Pemindai Risiko",
          "Mode Cegah: mencari risiko yang belum terjadi — sumber tunggal, jalur terkonsentrasi, sertifikat mau habis.",
          ["scan_supply_exposure", "get_supplier_certifications"]),
]

SEMUA = {a.kode: a for a in [SUPERVISOR, *AHLI]}


def demo() -> None:
    assert len(SEMUA) == 11, len(SEMUA)
    alat = [n for a in SEMUA.values() for n in a.alat]
    assert len(alat) == len(set(alat)), "ada alat terdaftar di dua agent"
    assert len(alat) == 23, len(alat)
    veto = [a.kode for a in SEMUA.values() if a.veto]
    assert veto == ["compliance"], veto
    print(f"definisi ok — {len(SEMUA)} agent, {len(alat)} alat, veto: {veto[0]}")


if __name__ == "__main__":
    demo()
