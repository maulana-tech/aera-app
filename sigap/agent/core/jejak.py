"""Perekam jejak. Keluarannya dibaca dashboard."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.provenance import Hasil


@dataclass
class Langkah:
    urutan: int
    tahap: str                 # DETECT · SCOPE · IMPACT · ...
    agent: str                 # kode agent
    agent_nama: str
    ringkas: str
    alat: List[str] = field(default_factory=list)
    asal: Optional[str] = None      # provenance gabungan langkah ini
    sumber: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)
    waktu: str = ""


class Jejak:
    def __init__(self, judul: str, pemicu: str, mode: str = "otonom"):
        self.judul = judul
        self.pemicu = pemicu
        self.mode = mode                  # "otonom" | "runut"
        self.mulai = datetime.now(timezone.utc)
        self.langkah: List[Langkah] = []
        self.keputusan: Dict[str, Any] = {}

    def catat(self, tahap: str, agent, ringkas: str, alat=None,
              hasil: Optional[Hasil] = None, **detail) -> None:
        self.langkah.append(Langkah(
            urutan=len(self.langkah) + 1,
            tahap=tahap,
            agent=agent.kode, agent_nama=agent.nama,
            ringkas=ringkas,
            alat=list(alat or []),
            asal=hasil.asal.value if hasil else None,
            sumber=hasil.sumber if hasil else None,
            detail=detail,
            waktu=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ))

    @property
    def agent_terpakai(self) -> List[str]:
        keluar, lihat = [], set()
        for l in self.langkah:
            if l.agent not in lihat:
                lihat.add(l.agent); keluar.append(l.agent)
        return keluar

    def sebagai_dict(self) -> dict:
        return {
            "judul": self.judul,
            "pemicu": self.pemicu,
            "mode": self.mode,
            "mulai": self.mulai.isoformat(timespec="seconds"),
            "agent_terpakai": self.agent_terpakai,
            "jumlah_langkah": len(self.langkah),
            "langkah": [asdict(l) for l in self.langkah],
            "keputusan": self.keputusan,
        }

    def tulis(self, path) -> None:
        import pathlib
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.sebagai_dict(), indent=2, ensure_ascii=False) + "\n")
