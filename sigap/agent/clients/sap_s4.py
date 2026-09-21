"""Penghubung ke SAP S/4HANA Cloud.

Satu klien, dua tujuan: sandbox hari ini, tenant pelanggan besok.
Yang berubah cuma SAP_BASE_URL dan SAP_API_KEY — kodenya tidak.

Kalau kunci API belum ada, klien ini TIDAK mengarang data. Ia melempar
KunciBelumAda, dan pembungkus @alat mengubahnya jadi Asal.TIDAK_ADA.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

BASE_URL = os.environ.get("SAP_BASE_URL", "https://sandbox.api.sap.com")
API_KEY = os.environ.get("SAP_API_KEY", "")
TIMEOUT = int(os.environ.get("SAP_TIMEOUT", "30"))


class KunciBelumAda(RuntimeError):
    pass


class SapError(RuntimeError):
    pass


def tersedia() -> bool:
    return bool(API_KEY)


def ambil(layanan: str, entitas: str, params: Optional[Dict[str, Any]] = None) -> dict:
    """Panggil satu entitas OData.

    layanan  — mis. "API_PURCHASEORDER_PROCESS_SRV"
    entitas  — mis. "A_PurchaseOrder"
    params   — parameter OData: $filter, $top, $select, $expand
    """
    if not API_KEY:
        raise KunciBelumAda(
            "SAP_API_KEY belum diisi. Ambil gratis di https://api.sap.com "
            "(login akun SAP ID, buka halaman API, klik Show API Key)."
        )

    q = dict(params or {})
    q.setdefault("$format", "json")
    url = f"{BASE_URL}/s4hanacloud/sap/opu/odata/sap/{layanan}/{entitas}?{urllib.parse.urlencode(q)}"

    req = urllib.request.Request(url, headers={"APIKey": API_KEY, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SapError(f"HTTP {e.code} dari {layanan}/{entitas}: {e.read()[:200].decode(errors='replace')}") from e


def baris(respons: dict) -> list:
    """Ambil daftar record dari bentuk respons OData v2 maupun v4."""
    if "d" in respons:                                  # OData v2
        d = respons["d"]
        return d.get("results", [d]) if isinstance(d, dict) else d
    return respons.get("value", [])                     # OData v4
