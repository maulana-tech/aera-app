"""Layanan HTTP SIGAP.

# ponytail: http.server stdlib — cukup untuk belasan peristiwa/hari, nol dependensi.
#           Pindah ke FastAPI + uvicorn kalau butuh async, websocket, atau >10 rps.

    python3 api.py                 # dengarkan di :8787

Endpoint
    GET  /sehat
    POST /peristiwa                {jenis, judul, pemicu, muatan, sumber}  → jalankan
    GET  /jalan                    daftar penanganan terakhir
    GET  /jalan/{id}               satu penanganan: langkah, aksi, persetujuan
    POST /aksi/{id}/putusan        {oleh, peran, putusan, catatan}
"""
from __future__ import annotations

import json
import re
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

import tools.impact, tools.sourcing, tools.compliance, tools.lainnya  # noqa: F401  (daftarkan alat)
from core import identitas, simpan
from core.identitas import Pengguna, TidakBerwenang
from core.konfigurasi import KONF

PORT = 8787


# --------------------------------------------------------------- penanganan
def _tangani(jalan_id: str, peristiwa: dict) -> None:
    """Jalankan tim agent di latar. Kegagalan ditulis, bukan ditelan."""
    urut = {"n": 0}

    def lapor(jenis: str, d: dict) -> None:
        urut["n"] += 1
        nama = d.get("nama") or d.get("agent", "-")
        simpan.simpan_langkah(jalan_id, {
            "urutan": urut["n"],
            "tahap": {"ahli_mulai": "DELEGASI", "ahli_selesai": "TEMUAN",
                      "alat": "ALAT"}.get(jenis, jenis.upper()),
            "agent": d.get("agent", "supervisor"),
            "agent_nama": nama,
            "ringkas": d.get("ringkas") or d.get("tugas") or d.get("nama", ""),
            "alat": [d["nama"]] if jenis == "alat" else [],
            "detail": d,
            "waktu": simpan._sekarang(),
        })

    try:
        import graph
        hasil = graph.jalankan(peristiwa, lapor)
        simpan.tutup_jalan(jalan_id, "selesai", hasil, biaya_idr=hasil.get("biaya_idr", 0))
    except Exception as e:                                           # noqa: BLE001
        simpan.tutup_jalan(jalan_id, "gagal", galat=f"{type(e).__name__}: {e}")
        traceback.print_exc()


# ------------------------------------------------------------------- routing
RUTE: list = []


def _pengguna(headers) -> Pengguna:
    """Identitas HANYA dari token. Tidak pernah dari badan permintaan."""
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise TidakBerwenang("perlu token sesi")
    return identitas.dari_token(auth[7:])


def rute(metode: str, pola: str) -> Callable:
    r = re.compile("^" + pola + "$")

    def bungkus(fn: Callable) -> Callable:
        RUTE.append((metode, r, fn))
        return fn
    return bungkus


@rute("GET", r"/sehat")
def sehat(_m, _b, _h) -> Tuple[int, dict]:
    return 200, {
        "lingkungan": KONF.lingkungan,
        "sap_siap": KONF.sap_siap,
        "model_siap": KONF.model_siap,
        "boleh_pakai_contoh": KONF.boleh_pakai_contoh,
        "model": KONF.model,
    }


@rute("POST", r"/peristiwa")
def terima_peristiwa(_m, b: dict, _h) -> Tuple[int, dict]:
    for w in ("jenis", "judul", "pemicu"):
        if not b.get(w):
            return 400, {"galat": f"'{w}' wajib diisi"}

    if KONF.produksi and not (KONF.sap_siap and KONF.model_siap):
        return 503, {"galat": "produksi belum siap: SAP atau model belum tersambung"}

    pid = simpan.catat_peristiwa(b["jenis"], b["judul"], b["pemicu"],
                                 b.get("muatan", {}), b.get("sumber", "api"))
    mode = "otonom" if KONF.model_siap else "runut"
    jid = simpan.mulai_jalan(pid, mode)

    peristiwa = {"id": pid, "jenis": b["jenis"], "judul": b["judul"],
                 "pemicu": b["pemicu"], **b.get("muatan", {})}

    if KONF.model_siap:
        threading.Thread(target=_tangani, args=(jid, peristiwa), daemon=True).start()
    else:
        simpan.tutup_jalan(jalan_id=jid, status="ditahan", keputusan={
            "status": "ditahan",
            "alasan": "AWS_REGION belum diisi — tim agent tidak bisa menalar. "
                      "Tidak ada keputusan yang dibuat.",
        })

    return 202, {"peristiwa_id": pid, "jalan_id": jid, "mode": mode}


@rute("GET", r"/agent")
def daftar_agent(_m, _b, _h) -> Tuple[int, dict]:
    """Anatomi tim: siapa saja, punya alat apa, mana yang sudah tersambung."""
    from agents.definisi import SEMUA
    from core import registry

    terdaftar = registry.semua()
    keluar = []
    for kode, a in SEMUA.items():
        alat = []
        for nama in a.alat:
            ada = nama in terdaftar
            alat.append({
                "nama": nama,
                "terpasang": ada,
                "deskripsi": terdaftar[nama].deskripsi if ada else None,
            })
        keluar.append({
            "kode": kode, "nama": a.nama, "peran": a.peran,
            "effort": a.effort, "veto": a.veto,
            "ketua": kode == "supervisor",
            "alat": alat,
            "terpasang": sum(1 for x in alat if x["terpasang"]),
            "total_alat": len(alat),
        })

    # hitung berapa peristiwa yang benar-benar memanggil tiap agent
    with simpan.buka() as c:
        pakai = dict(c.execute(
            "SELECT agent, COUNT(DISTINCT jalan_id) FROM langkah GROUP BY agent").fetchall())
    for a in keluar:
        a["dipakai_di"] = pakai.get(a["kode"], 0)

    return 200, {
        "agent": keluar,
        "ringkas": {
            "jumlah_agent": len(keluar),
            "alat_terpasang": sum(a["terpasang"] for a in keluar),
            "alat_total": sum(a["total_alat"] for a in keluar),
            "model_siap": KONF.model_siap,
            "sap_siap": KONF.sap_siap,
        },
    }


@rute("POST", r"/agent/([a-z_]+)/tanya")
def tanya_agent(m, b: dict, h) -> Tuple[int, dict]:
    """Percakapan langsung dengan satu ahli."""
    _pengguna(h)                                    # harus masuk dulu
    kode, tanya = m.group(1), (b.get("tanya") or "").strip()
    if not tanya:
        return 400, {"galat": "'tanya' wajib diisi"}

    from agents.definisi import SEMUA
    if kode not in SEMUA:
        return 404, {"galat": f"agent '{kode}' tidak dikenal"}

    if not KONF.model_siap:
        return 503, {
            "galat": "AWS_REGION belum diisi — agent tidak bisa menalar.",
            "petunjuk": "Isi AWS_REGION di sigap/agent/.env dengan wilayah "
                        "yang menyediakan Claude di Bedrock, lalu jalankan ulang layanan.",
        }
    try:
        import graph
        return 200, graph.tanya_ahli(kode, tanya)
    except Exception as e:                                          # noqa: BLE001
        traceback.print_exc()
        return 500, {"galat": f"{type(e).__name__}: {e}"}


@rute("GET", r"/log")
def log_mentah(_m, b: dict, _h) -> Tuple[int, dict]:
    """Seluruh langkah dari semua penanganan, terbaru dulu."""
    with simpan.buka() as c:
        rows = c.execute(
            "SELECT l.*, p.judul, p.jenis AS jenis_peristiwa FROM langkah l"
            " JOIN jalan j ON j.id = l.jalan_id"
            " JOIN peristiwa p ON p.id = j.peristiwa_id"
            " ORDER BY l.id DESC LIMIT 300").fetchall()
        aksi = c.execute(
            "SELECT a.*, p.judul FROM aksi a"
            " JOIN jalan j ON j.id = a.jalan_id"
            " JOIN peristiwa p ON p.id = j.peristiwa_id"
            " ORDER BY a.dibuat DESC LIMIT 100").fetchall()
        setuju = c.execute(
            "SELECT s.*, a.jenis AS jenis_aksi, a.jalan_id FROM persetujuan s"
            " JOIN aksi a ON a.id = s.aksi_id ORDER BY s.id DESC LIMIT 100").fetchall()
    return 200, {
        "langkah": [dict(r) | {"alat": json.loads(r["alat"]),
                               "detail": json.loads(r["detail"])} for r in rows],
        "aksi": [dict(r) | {"muatan": json.loads(r["muatan"])} for r in aksi],
        "persetujuan": [dict(r) for r in setuju],
    }


@rute("POST", r"/masuk")
def login(_m, b: dict, _h) -> Tuple[int, dict]:
    try:
        p = identitas.masuk(b.get("email", ""), b.get("sandi", ""))
    except TidakBerwenang as e:
        return 401, {"galat": str(e)}
    return 200, {"token": identitas.terbitkan_token(p),
                 "pengguna": {"nama": p.nama, "email": p.email,
                              "peran": p.peran, "batas_idr": p.batas_idr}}


@rute("GET", r"/saya")
def saya(_m, _b, h) -> Tuple[int, dict]:
    p = _pengguna(h)
    return 200, {"nama": p.nama, "email": p.email, "peran": p.peran,
                 "batas_idr": p.batas_idr}


@rute("GET", r"/jalan")
def daftar(_m, _b, _h) -> Tuple[int, dict]:
    return 200, {"jalan": simpan.daftar_jalan()}


@rute("GET", r"/jalan/([A-Za-z0-9_]+)")
def satu(m, _b, _h) -> Tuple[int, dict]:
    d = simpan.ambil_jalan(m.group(1))
    return (200, d) if d else (404, {"galat": "tidak ditemukan"})


@rute("POST", r"/aksi/([A-Za-z0-9_]+)/putusan")
def putuskan(m, b: dict, h) -> Tuple[int, dict]:
    p = _pengguna(h)                       # identitas dari token, bukan dari badan
    if not b.get("putusan"):
        return 400, {"galat": "'putusan' wajib diisi"}

    aksi_id = m.group(1)
    d = simpan.ambil_aksi(aksi_id)
    if not d:
        return 404, {"galat": "aksi tidak ditemukan"}

    nilai = int(d["muatan"].get("biaya_idr", 0))
    if b["putusan"] == "disetujui" and not p.boleh_menyetujui(nilai):
        return 403, {
            "galat": f"peran '{p.peran}' tidak berwenang menyetujui Rp {nilai:,}",
            "batas_idr": p.batas_idr,
            "saran": "naikkan ke procurement_lead",
        }
    try:
        return 200, simpan.putuskan_aksi(aksi_id, p.email, p.peran,
                                         b["putusan"], b.get("catatan", ""))
    except ValueError as e:
        return 400, {"galat": str(e)}


# -------------------------------------------------------------------- server
class Penangan(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _kirim(self, kode: int, data: Any) -> None:
        isi = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(kode)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(isi)

    def do_OPTIONS(self) -> None:          # noqa: N802
        self._kirim(204, {})

    def _jalankan(self, metode: str) -> None:
        jalur = urlparse(self.path).path.rstrip("/") or "/sehat"
        badan: Dict[str, Any] = {}
        if metode == "POST":
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                try:
                    badan = json.loads(self.rfile.read(n))
                except json.JSONDecodeError:
                    return self._kirim(400, {"galat": "badan bukan JSON yang sah"})
        for m, pola, fn in RUTE:
            if m != metode:
                continue
            cocok = pola.match(jalur)
            if cocok:
                try:
                    kode, data = fn(cocok, badan, self.headers)
                except TidakBerwenang as e:
                    return self._kirim(401, {"galat": str(e)})
                except Exception as e:                               # noqa: BLE001
                    traceback.print_exc()
                    return self._kirim(500, {"galat": f"{type(e).__name__}: {e}"})
                return self._kirim(kode, data)
        self._kirim(404, {"galat": f"rute tidak dikenal: {metode} {jalur}"})

    def do_GET(self) -> None:              # noqa: N802
        self._jalankan("GET")

    def do_POST(self) -> None:             # noqa: N802
        self._jalankan("POST")

    def log_message(self, fmt: str, *a) -> None:
        print(f"  {self.command} {self.path} → {a[1] if len(a) > 1 else ''}")


if __name__ == "__main__":
    print(f"SIGAP API · lingkungan={KONF.lingkungan} · sap={'siap' if KONF.sap_siap else 'belum'} "
          f"· model={'siap' if KONF.model_siap else 'belum'}")
    print(f"dengarkan http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Penangan).serve_forever()
