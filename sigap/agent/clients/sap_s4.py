"""Connector to SAP S/4HANA Cloud.

One client, two destinations: the sandbox today, a customer tenant tomorrow.
Only SAP_BASE_URL and SAP_API_KEY change, the code does not.

When there is no API key this client does NOT invent data. It raises
MissingApiKey, and the caller turns that into Origin.MISSING.
"""
from __future__ import annotations

import gzip
import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

from core.config import CFG

# Read through CFG, not os.environ. core.config is what loads .env, so reading
# the environment directly here made the connector work or not depending on
# whether something else had imported config first. It did work through api.py,
# by luck of import order, and failed the moment anything imported this module
# on its own.
TIMEOUT = int(os.environ.get("SAP_TIMEOUT", "30"))


def base_url() -> str:
    return CFG.sap_base_url


def api_key() -> str:
    return CFG.sap_api_key


class MissingApiKey(RuntimeError):
    pass


class SapError(RuntimeError):
    pass


def _body(resp) -> str:
    """The response text, decompressed if the gateway sent it compressed.

    SAP's sandbox gzips even when nothing asked it to, and urllib hands back
    the raw bytes. Without this, the first live call of the product's life dies
    on a UnicodeDecodeError at byte 0x8b, which says nothing about gzip.
    """
    raw = resp.read()
    if (resp.headers.get("Content-Encoding") or "").lower() == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def available() -> bool:
    return bool(api_key())


def get(service: str, entity: str, params: Optional[Dict[str, Any]] = None) -> dict:
    """Call one OData entity.

    service , e.g. "API_PURCHASEORDER_PROCESS_SRV"
    entity  , e.g. "A_PurchaseOrder"
    params  , OData parameters: $filter, $top, $select, $expand
    """
    if not api_key():
        raise MissingApiKey(
            "SAP_API_KEY is not set. Get one free at https://api.sap.com "
            "(sign in with an SAP ID, open the API page, click Show API Key)."
        )

    q = dict(params or {})
    q.setdefault("$format", "json")
    url = (f"{base_url()}/s4hanacloud/sap/opu/odata/sap/{service}/{entity}"
           f"?{urllib.parse.urlencode(q)}")

    req = urllib.request.Request(url, headers={"APIKey": api_key(),
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(_body(r))
    except urllib.error.HTTPError as e:
        raise SapError(f"HTTP {e.code} from {service}/{entity}: "
                       f"{e.read()[:200].decode(errors='replace')}") from e


def rows(response: dict) -> list:
    """Pull the record list out of either an OData v2 or v4 response shape."""
    if "d" in response:                                 # OData v2
        d = response["d"]
        return d.get("results", [d]) if isinstance(d, dict) else d
    return response.get("value", [])                    # OData v4


# --------------------------------------------------------------------- writes
class CsrfFailed(SapError):
    pass


def _csrf_token(service: str) -> Tuple[str, str]:
    """SAP OData v2 refuses writes without a CSRF token. Fetch it, keep the cookie."""
    url = f"{base_url()}/s4hanacloud/sap/opu/odata/sap/{service}/"
    req = urllib.request.Request(url, headers={
        "APIKey": api_key(), "X-CSRF-Token": "Fetch", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            token = r.headers.get("X-CSRF-Token", "")
            cookie = "; ".join(v.split(";", 1)[0]
                               for v in r.headers.get_all("Set-Cookie") or [])
        if not token:
            raise CsrfFailed(f"{service} returned no X-CSRF-Token")
        return token, cookie
    except urllib.error.HTTPError as e:
        raise CsrfFailed(f"could not fetch a CSRF token from {service}: HTTP {e.code}") from e


def post(service: str, entity: str, payload: dict,
         idempotency_key: Optional[str] = None) -> dict:
    """Write one entity to SAP.

    idempotency_key goes out as a header so the SAP side can reject a repeat.
    Our side also guards it in the actions table, two layers, because a
    duplicate purchase order is expensive.
    """
    if not api_key():
        raise MissingApiKey("SAP_API_KEY is not set. The write to SAP is refused")

    token, cookie = _csrf_token(service)
    url = f"{base_url()}/s4hanacloud/sap/opu/odata/sap/{service}/{entity}"
    headers = {
        "APIKey": api_key(),
        "X-CSRF-Token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if cookie:
        headers["Cookie"] = cookie
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(_body(r) or "{}")
    except urllib.error.HTTPError as e:
        raise SapError(
            f"HTTP {e.code} writing to {service}/{entity}: "
            f"{e.read()[:300].decode(errors='replace')}"
        ) from e
