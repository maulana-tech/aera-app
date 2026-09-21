"""Identitas dan wewenang.

Lubang yang diperbaiki: sebelumnya 'siapa yang menyetujui' datang dari badan
permintaan, artinya siapa pun bisa mengaku siapa saja. Sekarang identitas
HANYA datang dari token sesi yang ditandatangani server.

# ponytail: auth lokal berbasis token HMAC. Di perusahaan sungguhan ini
#           diganti SSO — `dari_token()` jadi satu-satunya titik yang berubah.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.simpan import buka, _sekarang

RAHASIA = os.environ.get("SIGAP_SECRET", "")
UMUR_SESI_JAM = 12

SKEMA = """
CREATE TABLE IF NOT EXISTS pengguna (
  id       TEXT PRIMARY KEY,
  email    TEXT NOT NULL UNIQUE,
  nama     TEXT NOT NULL,
  peran    TEXT NOT NULL,
  sandi    TEXT NOT NULL,          -- pbkdf2$iterasi$garam$turunan
  aktif    INTEGER NOT NULL DEFAULT 1,
  dibuat   TEXT NOT NULL
);
"""

# Batas nilai aksi yang boleh disetujui tiap peran (rupiah).
BATAS_PERAN = {
    "planner": 0,                    # hanya membaca
    "buyer": 500_000_000,
    "procurement_lead": 10_000_000_000,
    "admin": 10_000_000_000,
}


class TidakBerwenang(PermissionError):
    pass


@dataclass(frozen=True)
class Pengguna:
    id: str
    email: str
    nama: str
    peran: str

    @property
    def batas_idr(self) -> int:
        return BATAS_PERAN.get(self.peran, 0)

    def boleh_menyetujui(self, nilai_idr: int) -> bool:
        return self.batas_idr > 0 and nilai_idr <= self.batas_idr


# ------------------------------------------------------------------ kata sandi
def _acak_sandi(sandi: str, garam: Optional[bytes] = None, iterasi: int = 200_000) -> str:
    g = garam or secrets.token_bytes(16)
    turun = hashlib.pbkdf2_hmac("sha256", sandi.encode(), g, iterasi)
    return f"pbkdf2${iterasi}${base64.b64encode(g).decode()}${base64.b64encode(turun).decode()}"


def _cocok_sandi(sandi: str, tersimpan: str) -> bool:
    try:
        _, it, g, t = tersimpan.split("$")
        ulang = hashlib.pbkdf2_hmac("sha256", sandi.encode(),
                                    base64.b64decode(g), int(it))
        return hmac.compare_digest(ulang, base64.b64decode(t))
    except Exception:                                                # noqa: BLE001
        return False


# --------------------------------------------------------------------- token
def _rahasia() -> bytes:
    if not RAHASIA:
        raise RuntimeError(
            "SIGAP_SECRET belum diisi. Tanpa itu token sesi bisa dipalsukan. "
            "Buat dengan: python3 -c \"import secrets;print(secrets.token_hex(32))\""
        )
    return RAHASIA.encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _debase(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def terbitkan_token(p: Pengguna) -> str:
    isi = {"sub": p.id, "email": p.email, "nama": p.nama, "peran": p.peran,
           "exp": (datetime.now(timezone.utc) + timedelta(hours=UMUR_SESI_JAM)).timestamp()}
    muatan = _b64(json.dumps(isi, separators=(",", ":")).encode())
    tanda = _b64(hmac.new(_rahasia(), muatan.encode(), hashlib.sha256).digest())
    return f"{muatan}.{tanda}"


def dari_token(token: str) -> Pengguna:
    """Satu-satunya jalan masuk identitas. Ganti isinya kalau pindah ke SSO."""
    try:
        muatan, tanda = token.split(".")
    except ValueError:
        raise TidakBerwenang("token tidak berbentuk sah")

    harap = _b64(hmac.new(_rahasia(), muatan.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(harap, tanda):
        raise TidakBerwenang("tanda tangan token tidak cocok")

    isi = json.loads(_debase(muatan))
    if isi["exp"] < datetime.now(timezone.utc).timestamp():
        raise TidakBerwenang("sesi kedaluwarsa")
    return Pengguna(isi["sub"], isi["email"], isi["nama"], isi["peran"])


# ------------------------------------------------------------------- pengguna
def siapkan() -> None:
    with buka() as c:
        c.executescript(SKEMA)


def tambah_pengguna(email: str, nama: str, peran: str, sandi: str) -> Pengguna:
    if peran not in BATAS_PERAN:
        raise ValueError(f"peran tidak dikenal: {peran}")
    siapkan()
    uid = "usr_" + secrets.token_hex(6)
    with buka() as c:
        c.execute("INSERT INTO pengguna (id,email,nama,peran,sandi,dibuat) VALUES (?,?,?,?,?,?)",
                  (uid, email.lower(), nama, peran, _acak_sandi(sandi), _sekarang()))
    return Pengguna(uid, email.lower(), nama, peran)


def masuk(email: str, sandi: str) -> Pengguna:
    siapkan()
    with buka() as c:
        r = c.execute("SELECT * FROM pengguna WHERE email=? AND aktif=1",
                      (email.lower(),)).fetchone()
    # bandingkan tetap walau pengguna tidak ada, supaya waktunya seragam
    tersimpan = r["sandi"] if r else _acak_sandi("x")
    if not _cocok_sandi(sandi, tersimpan) or not r:
        raise TidakBerwenang("email atau kata sandi salah")
    return Pengguna(r["id"], r["email"], r["nama"], r["peran"])


def demo() -> None:
    os.environ.setdefault("SIGAP_SECRET", secrets.token_hex(16))
    global RAHASIA
    RAHASIA = os.environ["SIGAP_SECRET"]

    p = Pengguna("usr_1", "budi@kpn.co.id", "Budi", "buyer")
    t = terbitkan_token(p)
    assert dari_token(t).email == p.email

    muatan, tanda = t.split(".")
    palsu = json.loads(_debase(muatan)); palsu["peran"] = "admin"
    t_palsu = f"{_b64(json.dumps(palsu).encode())}.{tanda}"
    try:
        dari_token(t_palsu)
        raise AssertionError("token palsu seharusnya ditolak")
    except TidakBerwenang:
        pass
    print("  token: sah ✓ · dipalsukan → ditolak ✓")

    assert Pengguna("u", "e", "n", "planner").boleh_menyetujui(1) is False
    assert Pengguna("u", "e", "n", "buyer").boleh_menyetujui(94_000_000) is True
    assert Pengguna("u", "e", "n", "buyer").boleh_menyetujui(900_000_000) is False
    assert Pengguna("u", "e", "n", "procurement_lead").boleh_menyetujui(900_000_000) is True
    print("  wewenang: planner tidak boleh · buyer sampai Rp 500 jt · lead di atasnya ✓")

    h = _acak_sandi("rahasia123")
    assert _cocok_sandi("rahasia123", h) and not _cocok_sandi("salah", h)
    print("  kata sandi: pbkdf2 ✓")
    print("identitas ok")


if __name__ == "__main__":
    demo()
