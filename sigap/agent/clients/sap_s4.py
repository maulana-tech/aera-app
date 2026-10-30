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
import threading
import time
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

#: Seconds to stop calling SAP after it says the rate quota is spent. The
#: sandbox answers every call with the same 500 until the quota resets, and
#: each one still counts against it, so asking again only delays the reset.
QUOTA_COOLDOWN = int(os.environ.get("SAP_QUOTA_COOLDOWN", "300"))
_quota = {"until": 0.0, "since": ""}
_quota_lock = threading.Lock()


#: A key and a base URL set from the Settings page beat the environment, so a
#: deployment can be pointed at a customer's own tenant without a redeploy.
#: Cached like the mode: api_key() is called on every single SAP request.
_CRED_TTL = 2.0
_cred = {"at": 0.0, "key": None, "url": None}


def _stored() -> Dict[str, Optional[str]]:
    now = time.monotonic()
    if now - _cred["at"] >= _CRED_TTL:
        try:
            from core import store
            _cred["key"] = store.get_setting("sap.api_key")
            _cred["url"] = store.get_setting("sap.base_url")
        except Exception:                                           # noqa: BLE001
            _cred["key"] = _cred["url"] = None                      # no DB yet
        _cred["at"] = now
    return _cred


def clear_quota_cooldown() -> None:
    """Forget that the quota was spent.

    The cooldown exists so a spent quota is not hammered, and it is right for
    ordinary traffic. It is wrong for two cases: a NEW key has its own quota,
    and an admin pressing "test" has asked for one real call and deserves an
    answer about their key rather than about the previous one.
    """
    with _quota_lock:
        _quota.update(until=0.0, since="")


def forget_credentials() -> None:
    """Drop the cache so the next call re-reads. Called after a settings write."""
    _cred["at"] = 0.0
    _mode["at"] = 0.0
    clear_quota_cooldown()


def base_url() -> str:
    return (_stored()["url"] or CFG.sap_base_url or "").rstrip("/")


def api_key() -> str:
    return _stored()["key"] or CFG.sap_api_key or ""


def key_hint() -> str:
    """The last four characters, for a settings page to show which key is in
    use without ever sending the key itself to a browser."""
    k = api_key()
    return f"…{k[-4:]}" if len(k) >= 4 else ("set" if k else "")


def key_source() -> str:
    """'settings', 'environment' or 'none' - so an admin can see which one wins."""
    if _stored()["key"]:
        return "settings"
    return "environment" if CFG.sap_api_key else "none"


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


#: data_mode() reads SQLite, and available() is called on nearly every tool
#: call, so the answer is held briefly. Two seconds is short enough that a
#: switch in the sidebar is felt immediately and long enough that one handling
#: does not open the database a hundred times.
_MODE_TTL = 2.0
_mode = {"at": 0.0, "value": "live"}


def data_mode() -> str:
    """'live' or 'demo', from the settings table. Falls back to live."""
    now = time.monotonic()
    if now - _mode["at"] >= _MODE_TTL:
        try:
            from core import store
            _mode["value"] = store.data_mode()
        except Exception:                                           # noqa: BLE001
            _mode["value"] = "live"                                 # no DB yet
        _mode["at"] = now
    return _mode["value"]


def available() -> bool:
    """Whether the tools should call SAP at all.

    One gate for the whole product: ten callers ask this before reaching for
    S/4HANA, and when it is False every one of them already falls through to
    uploaded data and the modelled fixtures. Demo mode is therefore not a
    second code path - it is this gate answering no.
    """
    return data_mode() == "live" and bool(api_key())


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

    with _quota_lock:
        if time.monotonic() < _quota["until"]:
            left = round(_quota["until"] - time.monotonic())
            raise SapError(f"SAP rate quota exceeded at {_quota['since']}; not calling "
                           f"{service}/{entity} again for {left}s")

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
        body = e.read()[:200].decode(errors="replace")
        if e.code == 429 or "QuotaViolation" in body or "Rate limit" in body:
            with _quota_lock:
                _quota.update(until=time.monotonic() + QUOTA_COOLDOWN,
                              since=time.strftime("%H:%M:%S"))
        raise SapError(f"HTTP {e.code} from {service}/{entity}: {body}") from e


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
