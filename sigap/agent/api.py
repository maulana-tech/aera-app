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
from core import simpan
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


def rute(metode: str, pola: str) -> Callable:
    r = re.compile("^" + pola + "$")

    def bungkus(fn: Callable) -> Callable:
        RUTE.append((metode, r, fn))
        return fn
    return bungkus


@rute("GET", r"/sehat")
def sehat(_m, _b) -> Tuple[int, dict]:
    return 200, {
        "lingkungan": KONF.lingkungan,
        "sap_siap": KONF.sap_siap,
        "model_siap": KONF.model_siap,
        "boleh_pakai_contoh": KONF.boleh_pakai_contoh,
        "model": KONF.model,
    }


@rute("POST", r"/peristiwa")
def terima_peristiwa(_m, b: dict) -> Tuple[int, dict]:
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


@rute("GET", r"/jalan")
def daftar(_m, _b) -> Tuple[int, dict]:
    return 200, {"jalan": simpan.daftar_jalan()}


@rute("GET", r"/jalan/([A-Za-z0-9_]+)")
def satu(m, _b) -> Tuple[int, dict]:
    d = simpan.ambil_jalan(m.group(1))
    return (200, d) if d else (404, {"galat": "tidak ditemukan"})


@rute("POST", r"/aksi/([A-Za-z0-9_]+)/putusan")
def putuskan(m, b: dict) -> Tuple[int, dict]:
    for w in ("oleh", "peran", "putusan"):
        if not b.get(w):
            return 400, {"galat": f"'{w}' wajib diisi"}
    try:
        return 200, simpan.putuskan_aksi(m.group(1), b["oleh"], b["peran"],
                                         b["putusan"], b.get("catatan", ""))
    except KeyError:
        return 404, {"galat": "aksi tidak ditemukan"}
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
                    kode, data = fn(cocok, badan)
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
