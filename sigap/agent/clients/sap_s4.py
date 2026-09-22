"""Connector to SAP S/4HANA Cloud.

One client, two destinations: the sandbox today, a customer tenant tomorrow.
Only SAP_BASE_URL and SAP_API_KEY change — the code does not.

When there is no API key this client does NOT invent data. It raises
MissingApiKey, and the caller turns that into Origin.MISSING.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

BASE_URL = os.environ.get("SAP_BASE_URL", "https://sandbox.api.sap.com")
API_KEY = os.environ.get("SAP_API_KEY", "")
TIMEOUT = int(os.environ.get("SAP_TIMEOUT", "30"))


class MissingApiKey(RuntimeError):
    pass


class SapError(RuntimeError):
    pass


def available() -> bool:
    return bool(API_KEY)


def get(service: str, entity: str, params: Optional[Dict[str, Any]] = None) -> dict:
    """Call one OData entity.

    service  — e.g. "API_PURCHASEORDER_PROCESS_SRV"
    entity   — e.g. "A_PurchaseOrder"
    params   — OData parameters: $filter, $top, $select, $expand
    """
    if not API_KEY:
        raise MissingApiKey(
            "SAP_API_KEY is not set. Get one free at https://api.sap.com "
            "(sign in with an SAP ID, open the API page, click Show API Key)."
        )

    q = dict(params or {})
    q.setdefault("$format", "json")
    url = (f"{BASE_URL}/s4hanacloud/sap/opu/odata/sap/{service}/{entity}"
           f"?{urllib.parse.urlencode(q)}")

    req = urllib.request.Request(url, headers={"APIKey": API_KEY,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
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
    url = f"{BASE_URL}/s4hanacloud/sap/opu/odata/sap/{service}/"
    req = urllib.request.Request(url, headers={
        "APIKey": API_KEY, "X-CSRF-Token": "Fetch", "Accept": "application/json"})
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
    Our side also guards it in the actions table — two layers, because a
    duplicate purchase order is expensive.
    """
    if not API_KEY:
        raise MissingApiKey("SAP_API_KEY is not set — the write to SAP is refused")

    token, cookie = _csrf_token(service)
    url = f"{BASE_URL}/s4hanacloud/sap/opu/odata/sap/{service}/{entity}"
    headers = {
        "APIKey": API_KEY,
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
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise SapError(
            f"HTTP {e.code} writing to {service}/{entity}: "
            f"{e.read()[:300].decode(errors='replace')}"
        ) from e
