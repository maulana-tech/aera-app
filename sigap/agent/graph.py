"""Tim agent. Ketua memanggil ahli; tiap ahli punya putaran alatnya sendiri.

Pola: ahli dijadikan alat milik ketua. Ketua memutuskan siapa dipanggil
berdasarkan hasil terakhir — tidak ada urutan baku. Tiap ahli menjalankan
putaran tool-use sendiri sampai selesai, lalu menyerahkan ringkasannya
beserta label asal data ke papan bersama.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agents.definisi import AHLI, SEMUA, SUPERVISOR, Agent
from core import registry
from core.konfigurasi import KONF
from core.provenance import Asal, Hasil

# Tarif acuan untuk pembatas biaya. Bedrock punya tarif sendiri —
# ganti dari aws.amazon.com/bedrock/pricing sebelum dipakai produksi.
TARIF_MASUK_IDR_PER_JUTA = 82_000
TARIF_KELUAR_IDR_PER_JUTA = 410_000
MAKS_PUTARAN_AHLI = 8
MAKS_PUTARAN_KETUA = 14


class AnggaranHabis(RuntimeError):
    pass


class ModelTidakSiap(RuntimeError):
    pass


@dataclass
class Papan:
    """Papan bersama. Semua ahli menulis dan membaca di sini."""
    temuan: Dict[str, Any] = field(default_factory=dict)
    asal: Dict[str, str] = field(default_factory=dict)
    sumber: Dict[str, str] = field(default_factory=dict)

    def tulis(self, kunci: str, h: Hasil) -> None:
        self.temuan[kunci] = h.nilai
        self.asal[kunci] = h.asal.value
        self.sumber[kunci] = h.sumber

    def ada_yang_tidak_tepercaya(self) -> List[str]:
        return [k for k, v in self.asal.items()
                if v not in ("live", "cached", "derived")]

    def ringkas(self) -> str:
        baris = [f"- {k}: {self.asal[k]} ({self.sumber[k]})" for k in self.temuan]
        return "\n".join(baris) or "(papan masih kosong)"


@dataclass
class Biaya:
    masuk: int = 0
    keluar: int = 0

    @property
    def idr(self) -> int:
        return round(self.masuk / 1e6 * TARIF_MASUK_IDR_PER_JUTA
                     + self.keluar / 1e6 * TARIF_KELUAR_IDR_PER_JUTA)

    def tambah(self, usage) -> None:
        self.masuk += getattr(usage, "input_tokens", 0) or 0
        self.masuk += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.keluar += getattr(usage, "output_tokens", 0) or 0


def klien():
    if not KONF.model_siap:
        raise ModelTidakSiap(
            "AWS_REGION belum diisi. Tim agent tidak bisa jalan tanpa akses model. "
            "Pastikan wilayahnya menyediakan Claude di konsol Bedrock."
        )
    from anthropic import AnthropicBedrockMantle       # impor di sini supaya dev tanpa SDK tetap jalan
    return AnthropicBedrockMantle(aws_region=KONF.aws_region)


# --------------------------------------------------------------------------- #
def _putaran_alat(cl, agent: Agent, tugas: str, papan: Papan,
                  biaya: Biaya, lapor: Callable[[str, dict], None]) -> str:
    """Satu ahli bekerja sampai selesai. Mengembalikan ringkasan tertulisnya."""
    alat = registry.definisi_untuk_model(agent.kode)
    pesan: List[dict] = [{
        "role": "user",
        "content": (
            f"{tugas}\n\n"
            f"Isi papan bersama saat ini:\n{papan.ringkas()}\n\n"
            "Pakai alatmu seperlunya, lalu tulis ringkasan temuanmu. "
            "Kalau data yang kamu butuhkan tidak tersedia, katakan apa yang kurang — "
            "jangan menebak."
        ),
    }]

    for _ in range(MAKS_PUTARAN_AHLI):
        if biaya.idr > KONF.batas_biaya_per_peristiwa_idr:
            raise AnggaranHabis(f"melewati Rp {KONF.batas_biaya_per_peristiwa_idr:,} per peristiwa")

        r = cl.messages.create(
            model=KONF.model,
            max_tokens=8000,
            system=agent.instruksi,
            thinking={"type": "adaptive"},
            output_config={"effort": agent.effort},
            tools=alat,
            messages=pesan,
        )
        biaya.tambah(r.usage)
        pesan.append({"role": "assistant", "content": r.content})

        if r.stop_reason != "tool_use":
            teks = "".join(b.text for b in r.content if b.type == "text")
            lapor("ahli_selesai", {"agent": agent.kode, "ringkas": teks[:400]})
            return teks

        # semua tool_result WAJIB dikirim dalam SATU pesan user
        hasil_blok: List[dict] = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            lapor("alat", {"agent": agent.kode, "nama": b.name, "argumen": b.input})
            try:
                h = registry.jalankan(b.name, dict(b.input))
                papan.tulis(f"{agent.kode}.{b.name}", h)
                isi = json.dumps({"nilai": h.nilai, **h.ringkas()},
                                 ensure_ascii=False, default=str)
                hasil_blok.append({"type": "tool_result", "tool_use_id": b.id, "content": isi})
            except Exception as e:                                   # noqa: BLE001
                hasil_blok.append({"type": "tool_result", "tool_use_id": b.id,
                                   "content": f"{type(e).__name__}: {e}", "is_error": True})
        pesan.append({"role": "user", "content": hasil_blok})

    return f"[{agent.nama} berhenti: melewati {MAKS_PUTARAN_AHLI} putaran alat]"


def _alat_ahli() -> List[dict]:
    """Tiap ahli tampil sebagai satu alat milik ketua."""
    return [{
        "name": f"panggil_{a.kode}",
        "description": f"{a.panggilan} ({a.nama}) — {a.peran}" + (" PUNYA VETO." if a.veto else ""),
        "input_schema": {
            "type": "object",
            "properties": {"tugas": {
                "type": "string",
                "description": "pertanyaan spesifik untuk ahli ini, sertakan konteks yang perlu",
            }},
            "required": ["tugas"],
            "additionalProperties": False,
        },
        "strict": True,
    } for a in AHLI]


def jalankan(peristiwa: dict, lapor: Callable[[str, dict], None]) -> dict:
    """Tangani satu peristiwa. `lapor` dipanggil tiap ada kemajuan."""
    cl = klien()
    papan = Papan()
    biaya = Biaya()
    dipanggil: List[str] = []

    alat_ketua = _alat_ahli() + registry.definisi_untuk_model("supervisor")
    pesan: List[dict] = [{
        "role": "user",
        "content": (
            f"Peristiwa masuk:\n{json.dumps(peristiwa, ensure_ascii=False, indent=2)}\n\n"
            "Tangani. Panggil ahli yang relevan saja, satu per satu, berdasarkan temuan "
            "sebelumnya. Berhenti begitu buktimu cukup untuk memutuskan."
        ),
    }]

    for _ in range(MAKS_PUTARAN_KETUA):
        if biaya.idr > KONF.batas_biaya_per_peristiwa_idr:
            raise AnggaranHabis(f"melewati Rp {KONF.batas_biaya_per_peristiwa_idr:,}")

        r = cl.messages.create(
            model=KONF.model,
            max_tokens=16000,
            system=SUPERVISOR.instruksi,
            thinking={"type": "adaptive"},
            output_config={"effort": SUPERVISOR.effort},
            tools=alat_ketua,
            messages=pesan,
        )
        biaya.tambah(r.usage)
        pesan.append({"role": "assistant", "content": r.content})

        if r.stop_reason != "tool_use":
            teks = "".join(b.text for b in r.content if b.type == "text")
            return {
                "status": "selesai",
                "rekomendasi": teks,
                "agent_dipanggil": dipanggil,
                "biaya_idr": biaya.idr,
                "papan_tidak_tepercaya": papan.ada_yang_tidak_tepercaya(),
            }

        hasil_blok: List[dict] = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            if b.name.startswith("panggil_"):
                kode = b.name[len("panggil_"):]
                ahli = SEMUA[kode]
                dipanggil.append(kode)
                lapor("ahli_mulai", {"agent": kode, "nama": ahli.panggilan,
                                     "tugas": b.input.get("tugas", "")})
                ringkas = _putaran_alat(cl, ahli, b.input["tugas"], papan, biaya, lapor)
                hasil_blok.append({"type": "tool_result", "tool_use_id": b.id, "content": ringkas})
            else:
                try:
                    h = registry.jalankan(b.name, dict(b.input))
                    papan.tulis(f"supervisor.{b.name}", h)
                    hasil_blok.append({"type": "tool_result", "tool_use_id": b.id,
                                       "content": json.dumps({"nilai": h.nilai, **h.ringkas()},
                                                             ensure_ascii=False, default=str)})
                except Exception as e:                               # noqa: BLE001
                    hasil_blok.append({"type": "tool_result", "tool_use_id": b.id,
                                       "content": f"{type(e).__name__}: {e}", "is_error": True})
        pesan.append({"role": "user", "content": hasil_blok})

    return {"status": "berhenti", "alasan": f"melewati {MAKS_PUTARAN_KETUA} putaran ketua",
            "agent_dipanggil": dipanggil, "biaya_idr": biaya.idr}


def tanya_ahli(kode: str, pertanyaan: str,
               lapor: Optional[Callable[[str, dict], None]] = None) -> dict:
    """Tanya satu ahli secara langsung, di luar penanganan gangguan.

    Dipakai halaman percakapan per agent. Ahli yang sama, alat yang sama —
    bedanya cuma tidak ada ketua yang mengatur giliran.
    """
    if kode not in SEMUA:
        raise KeyError(kode)
    agent = SEMUA[kode]
    papan, biaya = Papan(), Biaya()
    jejak: List[dict] = []

    def rekam(jenis: str, d: dict) -> None:
        jejak.append({"jenis": jenis, **d})
        if lapor:
            lapor(jenis, d)

    cl = klien()
    jawab = _putaran_alat(cl, agent, pertanyaan, papan, biaya, rekam)
    return {
        "agent": kode,
        "nama": agent.panggilan,
        "peran": agent.nama,
        "jawab": jawab,
        "alat_dipakai": [j["nama"] for j in jejak if j["jenis"] == "alat"],
        "papan": {k: {"asal": papan.asal[k], "sumber": papan.sumber[k]} for k in papan.temuan},
        "tidak_tepercaya": papan.ada_yang_tidak_tepercaya(),
        "biaya_idr": biaya.idr,
    }
