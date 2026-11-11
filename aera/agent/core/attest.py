"""NEAR AI Cloud TEE attestation and signed-response verification (stdlib only).

Two questions, answered with checks a user can re-run:

1. *Is this model really running in a TEE we can name?*  ``fetch_report`` asks
   ``GET /v1/attestation/report`` with a fresh 32-byte nonce; ``check_report``
   confirms the TDX quote's report_data binds the enclave signing address and
   our nonce, and that the attested docker-compose hashes to the measured
   compose hash (mr_config_id = 0x01 || sha256(app_compose)).
2. *Did that enclave produce this exact response?*  ``verify_response`` fetches
   ``GET /v1/signature/{chat_id}``, checks the signed text carries
   sha256(request bytes) and sha256(response bytes), recovers the EIP-191
   signer and requires it to be one of the attested signing addresses.

What is verified locally vs. what is not (reported honestly as ``skipped``):

* The TDX quote's Intel signature chain needs ``dcap-qvl`` (``tdx_quote_dcap``);
  without it report_data / mr_config_id are read from the quote body *unverified*.
* NVIDIA GPU evidence is posted to NRAS only when ``AERA_ATTEST_NRAS=1``.

Report shape confirmed against a live report (fixtures/near/attestation-sample.json)
and github.com/nearai/nearai-cloud-verifier (py/model_verifier.py, chat_verifier.py).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

if __package__ in (None, ""):  # allow `python3 core/attest.py` from aera/agent
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.crypto import eth_address_from_public, recover_eth_address  # noqa: E402

BASE_URL = os.environ.get("NEARAI_BASE_URL", "https://cloud-api.near.ai/v1").rstrip("/")
NRAS_URL = "https://nras.attestation.nvidia.com/v3/attest/gpu"
USER_AGENT = "AERA-agent/0.1 (+attest)"
TIMEOUT = 45.0
CACHE_SECONDS = 600

PASS, FAIL, SKIPPED = "pass", "fail", "skipped"
#: Checks that must pass for the verdict "attested".
REQUIRED = ("nonce_bound", "compose_hash", "signing_key_present", "signature_text",
            "signer_recovered", "signer_attested")

Check = Dict[str, Any]


class AttestError(RuntimeError):
    def __init__(self, message: str, status: int = 0, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _check(name: str, status: str, detail: str, scope: str = "") -> Check:
    c: Check = {"name": name, "status": status, "detail": detail}
    if scope:
        c["scope"] = scope
    return c


def _http(method: str, url: str, headers: Optional[Dict[str, str]] = None,
          body: Optional[bytes] = None, retries: int = 3) -> Any:
    last: Optional[AttestError] = None
    for attempt in range(retries):
        h = {"Accept": "application/json", "User-Agent": USER_AGENT}
        h.update(headers or {})
        req = urllib.request.Request(url, data=body, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            err = AttestError("%s %s -> HTTP %d: %s" % (method, url.split("?")[0], e.code, raw[:300]),
                              e.code, raw)
            if e.code == 429 or e.code >= 500:
                last = err
                time.sleep(1.0 * 2 ** attempt)
                continue
            raise err
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last = AttestError("%s %s failed: %s" % (method, url.split("?")[0], e))
            time.sleep(1.0 * 2 ** attempt)
    raise last or AttestError("request failed")


def _auth() -> Dict[str, str]:
    key = os.environ.get("NEARAI_API_KEY", "").strip()
    return {"Authorization": "Bearer " + key} if key else {}


# --------------------------------------------------------------------------- report

def new_nonce() -> str:
    return secrets.token_hex(32)


_CACHE: Dict[str, Tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()


def fetch_report(model: Optional[str] = None, nonce: Optional[str] = None,
                 signing_address: Optional[str] = None, use_cache: bool = True) -> dict:
    """GET /attestation/report. The returned dict carries ``_aera.nonce``.

    Cached per model for 10 minutes unless a nonce or signing address is given.
    """
    cache_key = model or ""
    cacheable = use_cache and nonce is None and signing_address is None
    if cacheable:
        with _CACHE_LOCK:
            hit = _CACHE.get(cache_key)
            if hit and time.time() - hit[0] < CACHE_SECONDS:
                return hit[1]
    nonce = nonce or new_nonce()
    q = {"signing_algo": "ecdsa", "nonce": nonce}
    if model:
        q["model"] = model
    if signing_address:
        q["signing_address"] = signing_address
    url = BASE_URL + "/attestation/report?" + urllib.parse.urlencode(q)
    headers = {"x-no-aliasing": "true"}
    headers.update(_auth())
    report = _http("GET", url, headers)
    if not isinstance(report, dict):
        raise AttestError("attestation report is not an object", body=report)
    report["_aera"] = {"nonce": nonce, "model": model,
                       "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if cacheable:
        with _CACHE_LOCK:
            _CACHE[cache_key] = (time.time(), report)
    return report


def fetch_model_list() -> List[dict]:
    res = _http("GET", BASE_URL + "/model/list?limit=500", _auth())
    return res.get("models", []) if isinstance(res, dict) else list(res or [])


def parse_tdx_quote(quote_hex: str) -> dict:
    """Fields of a TDX v4 quote body (header 48 B + TD report). Signature NOT verified."""
    q = bytes.fromhex(quote_hex[2:] if quote_hex.startswith("0x") else quote_hex)
    if len(q) < 632:
        raise ValueError("TDX quote too short (%d bytes)" % len(q))
    body = 48
    return {
        "version": int.from_bytes(q[0:2], "little"),
        "tee_type": int.from_bytes(q[4:8], "little"),
        "mr_td": q[body + 136:body + 184].hex(),
        "mr_config_id": q[body + 184:body + 232].hex(),
        "rtmr": [q[body + 328 + 48 * i:body + 376 + 48 * i].hex() for i in range(4)],
        "report_data": q[body + 520:body + 584].hex(),
    }


def _entries(report: dict, model: Optional[str]) -> List[Tuple[str, dict]]:
    out: List[Tuple[str, dict]] = []
    if isinstance(report.get("gateway_attestation"), dict):
        out.append(("gateway", report["gateway_attestation"]))
    for i, m in enumerate(report.get("model_attestations") or []):
        name = m.get("model_name") or m.get("model")
        if model and name and name != model:
            continue
        out.append(("model:%s#%d" % (name or model or "?", i), m))
    if not out and report.get("signing_address"):  # flat single-attestation shape
        out.append(("model:%s" % (model or "?"), report))
    return out


def _tcb_info(att: dict) -> dict:
    info = att.get("info") or {}
    tcb = info.get("tcb_info") if isinstance(info, dict) else None
    if isinstance(tcb, str):
        try:
            tcb = json.loads(tcb)
        except ValueError:
            tcb = None
    return tcb if isinstance(tcb, dict) else {}


def _check_nonce(att: dict, nonce: str, scope: str) -> Tuple[Check, Optional[dict]]:
    quote = None
    try:
        if att.get("intel_quote"):
            quote = parse_tdx_quote(att["intel_quote"])
            rd = bytes.fromhex(quote["report_data"])
            where = "intel_quote (unverified body)"
        else:
            rd = bytes.fromhex(att.get("report_data", ""))
            where = "report_data field"
    except ValueError as e:
        return _check("nonce_bound", FAIL, "cannot read report_data: %s" % e, scope), None
    addr = (att.get("signing_address") or "").lower()
    try:
        addr_raw = bytes.fromhex(addr[2:] if addr.startswith("0x") else addr)
        nonce_raw = bytes.fromhex(nonce)
    except ValueError:
        return _check("nonce_bound", FAIL, "signing address or nonce is not hex", scope), quote
    if len(rd) < 64 or len(nonce_raw) != 32:
        return _check("nonce_bound", FAIL, "report_data or nonce has wrong length", scope), quote
    fp = att.get("tls_cert_fingerprint")
    first = hashlib.sha256(addr_raw + bytes.fromhex(fp)).digest() if fp else addr_raw.ljust(32, b"\0")
    problems = []
    if rd[:32] != first:
        problems.append("report_data[0:32] does not bind signing address %s" % addr)
    if rd[32:64] != nonce_raw:
        problems.append("report_data[32:64] %s != our nonce" % rd[32:64].hex()[:16])
    if att.get("request_nonce") and att["request_nonce"].lower() != nonce.lower():
        problems.append("request_nonce echoed by server differs")
    if att.get("report_data") and quote and att["report_data"].lower() != quote["report_data"]:
        problems.append("report_data field differs from quote")
    if problems:
        return _check("nonce_bound", FAIL, "; ".join(problems), scope), quote
    return _check("nonce_bound", PASS, "address||nonce bound in %s" % where, scope), quote


def _check_compose(att: dict, quote: Optional[dict], scope: str) -> Check:
    tcb = _tcb_info(att)
    compose = tcb.get("app_compose")
    claimed = tcb.get("compose_hash") or (att.get("info") or {}).get("compose_hash")
    if not compose or not claimed:
        return _check("compose_hash", FAIL, "app_compose or compose_hash missing", scope)
    got = hashlib.sha256(compose.encode()).hexdigest()
    if got != claimed.lower():
        return _check("compose_hash", FAIL, "sha256(app_compose)=%s != %s" % (got[:16], claimed[:16]), scope)
    info_hash = (att.get("info") or {}).get("compose_hash")
    if info_hash and info_hash.lower() != got:
        return _check("compose_hash", FAIL, "info.compose_hash differs from tcb_info", scope)
    if quote is not None:
        if not quote["mr_config_id"].startswith("01" + got):
            return _check("compose_hash", FAIL, "mr_config_id does not measure this compose", scope)
        return _check("compose_hash", PASS, "sha256(app_compose)=%s… = mr_config_id" % got[:16], scope)
    return _check("compose_hash", PASS, "sha256(app_compose)=%s… (no quote to cross-check)" % got[:16], scope)


def _check_signing_key(att: dict, scope: str) -> Check:
    addr = att.get("signing_address") or ""
    if (att.get("signing_algo") or "ecdsa").lower() != "ecdsa":
        return _check("signing_key_present", FAIL, "signing_algo %r is not ecdsa" % att.get("signing_algo"), scope)
    if not (addr.startswith("0x") and len(addr) == 42):
        return _check("signing_key_present", FAIL, "no 20-byte ecdsa signing_address", scope)
    pub = att.get("signing_public_key")
    if pub:
        try:
            derived = eth_address_from_public(bytes.fromhex(pub[2:] if pub.startswith("0x") else pub))
        except ValueError as e:
            return _check("signing_key_present", FAIL, "bad signing_public_key: %s" % e, scope)
        if derived.lower() != addr.lower():
            return _check("signing_key_present", FAIL, "signing_public_key -> %s != %s" % (derived, addr), scope)
        return _check("signing_key_present", PASS, "%s (= keccak(signing_public_key))" % addr.lower(), scope)
    return _check("signing_key_present", PASS, addr.lower(), scope)


def _check_dcap(att: dict, scope: str) -> Check:
    try:
        import dcap_qvl  # type: ignore
    except ImportError:
        return _check("tdx_quote_dcap", SKIPPED, "dcap-qvl not installed", scope)
    try:
        import asyncio
        res = asyncio.run(dcap_qvl.get_collateral_and_verify(bytes.fromhex(att["intel_quote"])))
        st = getattr(res, "status", None)
        if st in ("UpToDate", "OutOfDate"):
            return _check("tdx_quote_dcap", PASS, "Intel TDX quote verified: %s" % st, scope)
        return _check("tdx_quote_dcap", FAIL, "TDX status %s" % st, scope)
    except Exception as e:  # best-effort optional path
        return _check("tdx_quote_dcap", FAIL, "dcap-qvl: %s" % e, scope)


def _b64url_json(seg: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)).decode())


def _check_gpu(att: dict, nonce: str, scope: str) -> Check:
    if os.environ.get("AERA_ATTEST_NRAS") != "1":
        return _check("gpu_nras", SKIPPED, "set AERA_ATTEST_NRAS=1 to post GPU evidence to NVIDIA NRAS", scope)
    try:
        payload = json.loads(att["nvidia_payload"])
        if str(payload.get("nonce", "")).lower() != nonce.lower():
            return _check("gpu_nras", FAIL, "GPU evidence nonce differs from ours", scope)
        body = _http("POST", NRAS_URL, {"Content-Type": "application/json"},
                     json.dumps(payload).encode(), retries=2)
        verdict = _b64url_json(body[0][1].split(".")[1]).get("x-nvidia-overall-att-result")
        if verdict is True:
            return _check("gpu_nras", PASS, "NVIDIA NRAS overall attestation result: true", scope)
        return _check("gpu_nras", FAIL, "NVIDIA NRAS verdict %r" % verdict, scope)
    except Exception as e:  # best-effort optional path
        return _check("gpu_nras", FAIL, "NRAS: %s" % e, scope)


def _check_chutes(att: dict, nonce: str, scope: str) -> List[Check]:
    """A model served through a provider that attests in its own shape (Chutes today):
    ``{provider, verified, tcb_status, gpu_verdict, nonce, e2e_pubkey, quote_b64, ...}``.

    The TDX quote's report_data[0:32] is sha256(nonce_hex + e2e_pubkey): the quote was made for
    OUR nonce and binds the instance's end-to-end key. There is no dstack app_compose and no
    per-model ECDSA key; the response is signed by the NEAR AI gateway enclave, whose own
    attestation and signature are checked separately. Checks that do not apply are SKIPPED,
    never passed."""
    checks: List[Check] = []
    prov = att.get("provider") or "provider"
    quote_hex = ""
    try:
        quote_hex = base64.b64decode(att.get("quote_b64") or "").hex()
        quote = parse_tdx_quote(quote_hex)
        rd = bytes.fromhex(quote["report_data"])
        bound = hashlib.sha256((nonce.lower() + (att.get("e2e_pubkey") or "")).encode()).digest()
        if (att.get("nonce") or "").lower() != nonce.lower():
            checks.append(_check("nonce_bound", FAIL, "%s echoed a different nonce" % prov, scope))
        elif rd[:32] != bound:
            checks.append(_check("nonce_bound", FAIL, "report_data[0:32] != sha256(nonce || e2e_pubkey)", scope))
        else:
            checks.append(_check("nonce_bound", PASS, "sha256(nonce || e2e_pubkey) bound in the %s TDX quote "
                                 "(unverified body)" % prov, scope))
    except (ValueError, KeyError) as e:
        checks.append(_check("nonce_bound", FAIL, "cannot read the %s quote: %s" % (prov, e), scope))
    checks.append(_check("compose_hash", SKIPPED, "%s attests the VM by its measurements (%s), not a dstack "
                         "app_compose" % (prov, att.get("measurement_config") or "?"), scope))
    checks.append(_check("signing_key_present", SKIPPED, "no per-model key: the response is signed by the "
                         "gateway enclave, checked below", scope))
    claims = {"verified": att.get("verified"), "tcb_status": att.get("tcb_status"),
              "gpu_verdict": att.get("gpu_verdict")}
    good = claims["verified"] is True and claims["tcb_status"] == "UpToDate" and claims["gpu_verdict"] == "PASS"
    checks.append(_check("provider_claims", PASS if good else FAIL,
                         "%s says %s (provider-asserted)" % (prov, claims), scope))
    checks.append(_check_dcap({"intel_quote": quote_hex}, scope) if quote_hex
                  else _check("tdx_quote_dcap", SKIPPED, "no quote", scope))
    return checks


def _check_router_attested(att: dict, scope: str) -> List[Check]:
    """A model behind a provider's attested router (Tinfoil today): AMD SEV-SNP, the enclave's
    measurement pinned through sigstore, ``trust: router_attested``. The report carries no nonce
    of ours, so freshness is NOT proven per request: nonce_bound is SKIPPED, never passed. The
    response is still signed by the NEAR AI gateway enclave, checked separately."""
    prov = att.get("provider") or "provider"
    router = att.get("router") or {}
    checks = [
        _check("nonce_bound", SKIPPED, "%s attests its router by a pinned measurement (%s, rekor #%s), "
               "not a per-request nonce: freshness is not proven" % (prov, (router.get("measurement") or "?")[:16],
                                                                      router.get("rekor_log_index") or "?"), scope),
        _check("compose_hash", SKIPPED, "%s pins the image by measurement (%s), not a dstack app_compose"
               % (prov, router.get("format") or "?"), scope),
        _check("signing_key_present", SKIPPED, "no per-model key: the response is signed by the gateway "
               "enclave, checked below", scope),
    ]
    good = att.get("verified") is True and att.get("trust") == "router_attested" and bool(router.get("measurement"))
    checks.append(_check("provider_claims", PASS if good else FAIL,
                         "%s says verified=%s trust=%s (provider-asserted)" % (prov, att.get("verified"), att.get("trust")),
                         scope))
    return checks


def check_report(report: dict, nonce: str, model: Optional[str] = None,
                 model_list: Optional[List[dict]] = None) -> List[Check]:
    checks: List[Check] = []
    entries = _entries(report, model)
    if model and not any(s.startswith("model:") for s, _ in entries):
        checks.append(_check("signing_key_present", FAIL, "report has no attestation for %s" % model,
                             "model:%s" % model))
    for scope, att in entries:
        if att.get("quote_b64") and not att.get("intel_quote"):
            checks.extend(_check_chutes(att, nonce, scope))
            continue
        if att.get("trust") == "router_attested" and not att.get("intel_quote"):
            checks.extend(_check_router_attested(att, scope))
            continue
        nc, quote = _check_nonce(att, nonce, scope)
        checks.append(nc)
        checks.append(_check_compose(att, quote, scope))
        checks.append(_check_signing_key(att, scope))
        checks.append(_check_dcap(att, scope) if att.get("intel_quote")
                      else _check("tdx_quote_dcap", SKIPPED, "no intel_quote", scope))
        if scope.startswith("model:") and att.get("nvidia_payload"):
            checks.append(_check_gpu(att, nonce, scope))
    if model:
        checks.append(_check_model_verifiable(model, model_list))
    return checks


def _check_model_verifiable(model: str, model_list: Optional[List[dict]]) -> Check:
    if model_list is None:
        try:
            model_list = fetch_model_list()
        except AttestError as e:
            return _check("model_verifiable", SKIPPED, "model list unavailable: %s" % e)
    for m in model_list:
        if m.get("modelId") == model or model in ((m.get("metadata") or {}).get("aliases") or []):
            meta = m.get("metadata") or {}
            flags = {k: meta.get(k) for k in ("verifiable", "attestationSupported") if k in meta}
            if any(v is True for v in flags.values()) and not any(v is False for v in flags.values()):
                return _check("model_verifiable", PASS, "model list: %s" % flags)
            return _check("model_verifiable", FAIL, "model list: %s (proxied, not TEE)" % flags)
    return _check("model_verifiable", SKIPPED, "%s not in model list" % model)


def attested_addresses(checks: Iterable[Check], report: dict, model: Optional[str] = None) -> Set[str]:
    """Signing addresses whose nonce binding and compose hash both passed."""
    ok: Dict[str, Set[str]] = {}
    for c in checks:
        if c.get("scope") and c["name"] in ("nonce_bound", "compose_hash") and c["status"] == PASS:
            ok.setdefault(c["scope"], set()).add(c["name"])
    out: Set[str] = set()
    for scope, att in _entries(report, model):
        if ok.get(scope) == {"nonce_bound", "compose_hash"} and att.get("signing_address"):
            out.add(att["signing_address"].lower())
    return out


# --------------------------------------------------------------------------- responses

def fetch_signature(chat_id: str, model: str) -> dict:
    url = "%s/signature/%s?%s" % (BASE_URL, urllib.parse.quote(chat_id, safe=""),
                                  urllib.parse.urlencode({"model": model, "signing_algo": "ecdsa"}))
    return _http("GET", url, _auth())


def verify_response(chat_id: str, model: str, request_body: bytes, response_body: bytes,
                    attested_addresses: Set[str],
                    signature_payload: Optional[dict] = None) -> List[Check]:
    """Checks ``signature_text``, ``signer_recovered``, ``signer_attested``.

    Signed text is ``"<model>:<sha256(req)>:<sha256(resp)>"`` (3 parts) or
    ``"<sha256(req)>:<sha256(resp)>"`` (2 parts); hashes are over the exact bytes.
    """
    if signature_payload is None:
        try:
            signature_payload = fetch_signature(chat_id, model)
        except AttestError as e:
            return [_check(n, SKIPPED, "signature unavailable: %s" % e)
                    for n in ("signature_text", "signer_recovered", "signer_attested")]
    text = signature_payload.get("text") or ""
    sig = signature_payload.get("signature") or ""
    claimed = (signature_payload.get("signing_address") or "").lower()
    req_h = hashlib.sha256(request_body).hexdigest()
    resp_h = hashlib.sha256(response_body).hexdigest()
    parts = text.split(":")
    checks: List[Check] = []
    if len(parts) == 3:
        got_req, got_resp, prefix = parts[1], parts[2], parts[0]
    elif len(parts) == 2:
        got_req, got_resp, prefix = parts[0], parts[1], ""
    else:
        got_req = got_resp = prefix = ""
    if not got_req:
        checks.append(_check("signature_text", FAIL, "unexpected signed text format %r" % text[:80]))
    elif got_req.lower() != req_h or got_resp.lower() != resp_h:
        which = [n for n, a, b in (("request", got_req, req_h), ("response", got_resp, resp_h))
                 if a.lower() != b]
        checks.append(_check("signature_text", FAIL, "%s hash mismatch (body tampered or re-encoded)"
                             % " and ".join(which)))
    else:
        checks.append(_check("signature_text", PASS, "sha256(req)=%s… sha256(resp)=%s…%s"
                             % (req_h[:12], resp_h[:12], " model=%s" % prefix if prefix else "")))
    recovered = recover_eth_address(text, sig) if text and sig else None
    if recovered is None:
        checks.append(_check("signer_recovered", FAIL, "signature does not recover"))
    elif recovered.lower() != claimed:
        checks.append(_check("signer_recovered", FAIL, "recovered %s != claimed %s" % (recovered, claimed)))
    else:
        checks.append(_check("signer_recovered", PASS, recovered.lower()))
    signer = (recovered or claimed).lower()
    if signer and signer in {a.lower() for a in attested_addresses}:
        checks.append(_check("signer_attested", PASS, "%s is an attested enclave key" % signer))
    else:
        checks.append(_check("signer_attested", FAIL, "%s not among attested %s"
                             % (signer or "?", sorted(attested_addresses))))
    return checks


def verdict(checks: Iterable[Check]) -> str:
    checks = list(checks)
    if any(c["status"] == FAIL for c in checks):
        return "failed"
    passed = {c["name"] for c in checks if c["status"] == PASS}
    # A model leg whose freshness is unproven (no nonce of ours in its attestation) is at most partial,
    # however well the gateway checks out.
    if any(c["name"] == "nonce_bound" and c["status"] == SKIPPED and str(c.get("scope") or "").startswith("model:")
           for c in checks):
        return "partial"
    return "attested" if all(r in passed for r in REQUIRED) else "partial"


def proof(model: str, chat_id: str, req_bytes: bytes, resp_bytes: bytes,
          signature_payload: Optional[dict] = None, report: Optional[dict] = None,
          model_list: Optional[List[dict]] = None) -> dict:
    """One record for the ``tee_proofs`` table / Proofs panel."""
    checks: List[Check] = []
    signing_address = None
    if signature_payload is None:
        try:
            signature_payload = fetch_signature(chat_id, model)
        except AttestError as e:
            checks.append(_check("signature_text", SKIPPED, "signature unavailable: %s" % e))
    if signature_payload:
        signing_address = (signature_payload.get("signing_address") or "").lower() or None
    try:
        rep = report if report is not None else fetch_report(model)
        rchecks = check_report(rep, rep.get("_aera", {}).get("nonce", ""), model, model_list)
        addrs = attested_addresses(rchecks, rep, model)
        if signing_address and signing_address not in addrs and report is None:
            # another replica signed: ask for that signer's attestation with a fresh nonce
            rep = fetch_report(model, signing_address=signing_address)
            rchecks = check_report(rep, rep["_aera"]["nonce"], model, model_list)
            addrs = attested_addresses(rchecks, rep, model)
        checks.extend(rchecks)
    except AttestError as e:
        addrs = set()
        checks.append(_check("nonce_bound", SKIPPED, "attestation report unavailable: %s" % e))
    if signature_payload:
        checks.extend(verify_response(chat_id, model, req_bytes, resp_bytes, addrs, signature_payload))
    return {
        "model": model, "chat_id": chat_id, "signing_address": signing_address,
        "checks": checks, "verdict": verdict(checks),
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------- self-check

_FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "fixtures", "near", "attestation-sample.json")


def _synthetic_report(priv: bytes, nonce: str, model: str) -> dict:
    from core.crypto import eth_address_from_private, secp256k1_public_key
    addr = eth_address_from_private(priv).lower()
    compose = json.dumps({"manifest_version": 2, "name": "fake-tee",
                          "docker_compose_file": "services: {vllm: {image: x@sha256:00}}"})
    ch = hashlib.sha256(compose.encode()).hexdigest()
    quote = bytearray(700)
    quote[0:2] = (4).to_bytes(2, "little")
    quote[4:8] = (0x81).to_bytes(4, "little")
    quote[48 + 184:48 + 232] = bytes.fromhex("01" + ch).ljust(48, b"\0")
    quote[48 + 520:48 + 584] = bytes.fromhex(addr[2:]).ljust(32, b"\0") + bytes.fromhex(nonce)
    att = {"model_name": model, "signing_address": addr, "signing_algo": "ecdsa",
           "signing_public_key": secp256k1_public_key(priv).hex(), "request_nonce": nonce,
           "intel_quote": bytes(quote).hex(),
           "info": {"compose_hash": ch, "tcb_info": {"app_compose": compose, "compose_hash": ch}}}
    return {"model_attestations": [att], "_aera": {"nonce": nonce, "model": model}}


def check() -> None:
    from core.crypto import eip191_sign, eth_address_from_private
    os.environ.pop("AERA_ATTEST_NRAS", None)
    model = "z-ai/glm-5.3-flash"
    mlist = [{"modelId": model, "metadata": {"verifiable": True, "attestationSupported": True}},
             {"modelId": "openai/gpt-5", "metadata": {"verifiable": False, "attestationSupported": False}}]
    tee = hashlib.sha256(b"fake tee key").digest()
    tee_addr = eth_address_from_private(tee).lower()
    nonce = new_nonce()
    assert len(nonce) == 64 and nonce != new_nonce()
    rep = _synthetic_report(tee, nonce, model)

    checks = check_report(rep, nonce, model, mlist)
    by = {c["name"]: c for c in checks}
    assert by["nonce_bound"]["status"] == PASS, by["nonce_bound"]
    assert by["compose_hash"]["status"] == PASS, by["compose_hash"]
    assert by["signing_key_present"]["status"] == PASS, by["signing_key_present"]
    assert by["model_verifiable"]["status"] == PASS
    assert by["tdx_quote_dcap"]["status"] in (SKIPPED, FAIL)  # fake quote; dcap absent -> skipped
    assert attested_addresses(checks, rep, model) == {tee_addr}

    # wrong nonce, tampered compose, proxied model
    assert {c["name"]: c for c in check_report(rep, new_nonce(), model, mlist)}["nonce_bound"]["status"] == FAIL
    bad = json.loads(json.dumps(rep))
    bad["model_attestations"][0]["info"]["tcb_info"]["app_compose"] += " "
    assert {c["name"]: c for c in check_report(bad, nonce, model, mlist)}["compose_hash"]["status"] == FAIL
    assert _check_model_verifiable("openai/gpt-5", mlist)["status"] == FAIL
    assert verdict(check_report(rep, nonce, "other/model", mlist)) == "failed"

    # signed response: pass, tampered body, wrong signer, unattested signer
    req = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}]}).encode()
    resp = b'{"id":"chatcmpl-1","choices":[{"message":{"content":"hello"}}]}'
    text = "%s:%s:%s" % (model, hashlib.sha256(req).hexdigest(), hashlib.sha256(resp).hexdigest())
    sp = {"text": text, "signature": eip191_sign(tee, text), "signing_address": tee_addr,
          "signing_algo": "ecdsa"}
    p = proof(model, "chatcmpl-1", req, resp, signature_payload=sp, report=rep, model_list=mlist)
    assert p["verdict"] == "attested", p["checks"]
    assert p["signing_address"] == tee_addr

    two_part = dict(sp, text=text.split(":", 1)[1])
    two_part["signature"] = eip191_sign(tee, two_part["text"])
    assert verdict(verify_response("c", model, req, resp, {tee_addr}, two_part)) == "partial"  # no report checks
    assert all(c["status"] == PASS for c in verify_response("c", model, req, resp, {tee_addr}, two_part))

    tampered = verify_response("c", model, req, resp + b" ", {tee_addr}, sp)
    assert tampered[0]["status"] == FAIL and "response hash" in tampered[0]["detail"]

    imposter = hashlib.sha256(b"attacker").digest()
    forged = dict(sp, signature=eip191_sign(imposter, text))
    fc = {c["name"]: c for c in verify_response("c", model, req, resp, {tee_addr}, forged)}
    assert fc["signer_recovered"]["status"] == FAIL and fc["signer_attested"]["status"] == FAIL

    honest_other = dict(sp, signature=eip191_sign(imposter, text),
                        signing_address=eth_address_from_private(imposter).lower())
    oc = {c["name"]: c for c in verify_response("c", model, req, resp, {tee_addr}, honest_other)}
    assert oc["signer_recovered"]["status"] == PASS and oc["signer_attested"]["status"] == FAIL
    assert proof(model, "c", req, resp, honest_other, rep, mlist)["verdict"] == "failed"

    # real report captured from cloud-api.near.ai (trimmed); checked against its own nonce
    if os.path.exists(_FIXTURE):
        with open(_FIXTURE) as f:
            real = json.load(f)
        rn, rm = real["_aera"]["nonce"], real["_aera"]["model"]
        rc = check_report(real, rn, rm, [{"modelId": rm, "metadata": {"verifiable": True}}])
        for c in rc:
            if c["name"] in ("nonce_bound", "compose_hash", "signing_key_present"):
                assert c["status"] == PASS, c
        scopes = {c.get("scope") for c in rc}
        assert "gateway" in scopes and any(s and s.startswith("model:") for s in scopes)
        assert len(attested_addresses(rc, real, rm)) >= 2
        assert {c["name"]: c for c in check_report(real, new_nonce(), rm, [])}["nonce_bound"]["status"] == FAIL
        print("attest: real sample ok (%d checks)" % len(rc))
    else:
        print("attest: real sample skipped (fixtures/near/attestation-sample.json absent)")
    print("attest ok")


demo = check


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--live":
        m = sys.argv[2] if len(sys.argv) > 2 else None
        r = fetch_report(m, use_cache=False)
        for c in check_report(r, r["_aera"]["nonce"], m):
            print("%-8s %-20s %-28s %s" % (c["status"], c["name"], c.get("scope", ""), c["detail"]))
    else:
        check()
