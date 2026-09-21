"""Penyimpanan. SQLite — cukup untuk belasan peristiwa per hari, nol dependensi.

# ponytail: SQLite; pindah ke Postgres kalau sudah multi-perusahaan atau butuh tulis serentak

Yang disimpan bersifat catatan resmi: apa yang diputuskan agent, atas bukti apa,
siapa yang menyetujui, dan apa yang benar-benar dikirim ke SAP. Baris di tabel
aksi dan persetujuan TIDAK pernah diubah — koreksi ditulis sebagai baris baru.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from core.konfigurasi import KONF

SKEMA = """
CREATE TABLE IF NOT EXISTS peristiwa (
  id            TEXT PRIMARY KEY,
  jenis         TEXT NOT NULL,           -- port_closure | supplier_failure | demand_spike | ...
  judul         TEXT NOT NULL,
  pemicu        TEXT NOT NULL,
  muatan        TEXT NOT NULL,           -- JSON mentah dari sumber sinyal
  diterima      TEXT NOT NULL,
  sumber        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jalan (
  id            TEXT PRIMARY KEY,
  peristiwa_id  TEXT NOT NULL REFERENCES peristiwa(id),
  mode          TEXT NOT NULL,           -- otonom | runut
  status        TEXT NOT NULL,           -- berjalan | selesai | ditahan | gagal
  mulai         TEXT NOT NULL,
  selesai       TEXT,
  biaya_token_idr INTEGER DEFAULT 0,
  keputusan     TEXT,                    -- JSON
  galat         TEXT
);

CREATE TABLE IF NOT EXISTS langkah (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  jalan_id      TEXT NOT NULL REFERENCES jalan(id),
  urutan        INTEGER NOT NULL,
  tahap         TEXT NOT NULL,
  agent         TEXT NOT NULL,
  agent_nama    TEXT NOT NULL,
  ringkas       TEXT NOT NULL,
  alat          TEXT NOT NULL,           -- JSON array
  asal          TEXT,
  sumber        TEXT,
  detail        TEXT NOT NULL,           -- JSON
  waktu         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_langkah_jalan ON langkah(jalan_id, urutan);

-- Catatan resmi. Tidak pernah di-UPDATE.
CREATE TABLE IF NOT EXISTS aksi (
  id            TEXT PRIMARY KEY,
  jalan_id      TEXT NOT NULL REFERENCES jalan(id),
  kunci_idempoten TEXT NOT NULL UNIQUE,  -- mencegah PO ganda saat diulang
  jenis         TEXT NOT NULL,
  otonom        INTEGER NOT NULL,
  muatan        TEXT NOT NULL,
  status        TEXT NOT NULL,           -- menunggu | disetujui | ditolak | terkirim | gagal
  referensi_sap TEXT,
  dibuat        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS persetujuan (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  aksi_id       TEXT NOT NULL REFERENCES aksi(id),
  oleh          TEXT NOT NULL,
  peran         TEXT NOT NULL,
  putusan       TEXT NOT NULL,           -- disetujui | ditolak | dinaikkan
  catatan       TEXT,
  waktu         TEXT NOT NULL
);
"""


def _sekarang() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def id_baru(awalan: str) -> str:
    return f"{awalan}_{uuid.uuid4().hex[:12]}"


@contextmanager
def buka() -> Iterator[sqlite3.Connection]:
    p = pathlib.Path(KONF.basis_data)
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA journal_mode = WAL")
    try:
        c.executescript(SKEMA)
        yield c
        c.commit()
    finally:
        c.close()


# ------------------------------------------------------------------ peristiwa
def catat_peristiwa(jenis: str, judul: str, pemicu: str, muatan: dict, sumber: str) -> str:
    pid = id_baru("evt")
    with buka() as c:
        c.execute(
            "INSERT INTO peristiwa (id, jenis, judul, pemicu, muatan, diterima, sumber)"
            " VALUES (?,?,?,?,?,?,?)",
            (pid, jenis, judul, pemicu, json.dumps(muatan, ensure_ascii=False), _sekarang(), sumber),
        )
    return pid


# ----------------------------------------------------------------------- jalan
def mulai_jalan(peristiwa_id: str, mode: str) -> str:
    jid = id_baru("run")
    with buka() as c:
        c.execute("INSERT INTO jalan (id, peristiwa_id, mode, status, mulai) VALUES (?,?,?,?,?)",
                  (jid, peristiwa_id, mode, "berjalan", _sekarang()))
    return jid


def tutup_jalan(jalan_id: str, status: str, keputusan: Optional[dict] = None,
                galat: Optional[str] = None, biaya_idr: int = 0) -> None:
    with buka() as c:
        c.execute(
            "UPDATE jalan SET status=?, selesai=?, keputusan=?, galat=?, biaya_token_idr=?"
            " WHERE id=?",
            (status, _sekarang(),
             json.dumps(keputusan, ensure_ascii=False) if keputusan else None,
             galat, biaya_idr, jalan_id),
        )


def simpan_langkah(jalan_id: str, l: dict) -> None:
    with buka() as c:
        c.execute(
            "INSERT INTO langkah (jalan_id, urutan, tahap, agent, agent_nama, ringkas,"
            " alat, asal, sumber, detail, waktu) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (jalan_id, l["urutan"], l["tahap"], l["agent"], l["agent_nama"], l["ringkas"],
             json.dumps(l["alat"], ensure_ascii=False), l.get("asal"), l.get("sumber"),
             json.dumps(l.get("detail", {}), ensure_ascii=False), l["waktu"]),
        )


# ------------------------------------------------------------------------ aksi
def catat_aksi(jalan_id: str, kunci_idempoten: str, jenis: str,
               otonom: bool, muatan: dict) -> Dict[str, Any]:
    """Idempoten: kunci yang sama tidak pernah membuat aksi kedua."""
    with buka() as c:
        ada = c.execute("SELECT * FROM aksi WHERE kunci_idempoten=?",
                        (kunci_idempoten,)).fetchone()
        if ada:
            return dict(ada) | {"diulang": True}
        aid = id_baru("act")
        c.execute(
            "INSERT INTO aksi (id, jalan_id, kunci_idempoten, jenis, otonom, muatan,"
            " status, dibuat) VALUES (?,?,?,?,?,?,?,?)",
            (aid, jalan_id, kunci_idempoten, jenis, int(otonom),
             json.dumps(muatan, ensure_ascii=False),
             "terkirim" if otonom else "menunggu", _sekarang()),
        )
        return dict(c.execute("SELECT * FROM aksi WHERE id=?", (aid,)).fetchone()) | {"diulang": False}


def putuskan_aksi(aksi_id: str, oleh: str, peran: str, putusan: str,
                  catatan: str = "") -> Dict[str, Any]:
    peta = {"disetujui": "disetujui", "ditolak": "ditolak", "dinaikkan": "menunggu"}
    if putusan not in peta:
        raise ValueError(f"putusan tidak dikenal: {putusan}")
    with buka() as c:
        a = c.execute("SELECT * FROM aksi WHERE id=?", (aksi_id,)).fetchone()
        if not a:
            raise KeyError(aksi_id)
        if a["status"] not in ("menunggu",):
            return dict(a) | {"tidak_berubah": True}
        c.execute("INSERT INTO persetujuan (aksi_id, oleh, peran, putusan, catatan, waktu)"
                  " VALUES (?,?,?,?,?,?)", (aksi_id, oleh, peran, putusan, catatan, _sekarang()))
        c.execute("UPDATE aksi SET status=? WHERE id=?", (peta[putusan], aksi_id))
        return dict(c.execute("SELECT * FROM aksi WHERE id=?", (aksi_id,)).fetchone())


# ------------------------------------------------------------------- pembacaan
def daftar_jalan(batas: int = 50) -> List[dict]:
    with buka() as c:
        rows = c.execute(
            "SELECT j.*, p.judul, p.jenis, p.pemicu FROM jalan j"
            " JOIN peristiwa p ON p.id = j.peristiwa_id"
            " ORDER BY j.mulai DESC LIMIT ?", (batas,)).fetchall()
    return [dict(r) | {"keputusan": json.loads(r["keputusan"]) if r["keputusan"] else None}
            for r in rows]


def ambil_jalan(jalan_id: str) -> Optional[dict]:
    with buka() as c:
        j = c.execute(
            "SELECT j.*, p.judul, p.jenis, p.pemicu, p.sumber AS sumber_sinyal"
            " FROM jalan j JOIN peristiwa p ON p.id = j.peristiwa_id WHERE j.id=?",
            (jalan_id,)).fetchone()
        if not j:
            return None
        langkah = c.execute("SELECT * FROM langkah WHERE jalan_id=? ORDER BY urutan",
                            (jalan_id,)).fetchall()
        aksi = c.execute("SELECT * FROM aksi WHERE jalan_id=? ORDER BY dibuat",
                         (jalan_id,)).fetchall()
        setuju = c.execute(
            "SELECT s.* FROM persetujuan s JOIN aksi a ON a.id = s.aksi_id"
            " WHERE a.jalan_id=? ORDER BY s.waktu", (jalan_id,)).fetchall()
    return {
        **dict(j),
        "keputusan": json.loads(j["keputusan"]) if j["keputusan"] else None,
        "langkah": [dict(l) | {"alat": json.loads(l["alat"]),
                               "detail": json.loads(l["detail"])} for l in langkah],
        "aksi": [dict(a) | {"muatan": json.loads(a["muatan"])} for a in aksi],
        "persetujuan": [dict(s) for s in setuju],
    }
