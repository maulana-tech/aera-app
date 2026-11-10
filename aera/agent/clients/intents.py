"""NEAR Intents 1Click REST client, standard library only.

Base ``https://1click.chaindefuser.com`` (OpenAPI: /docs/v0/openapi.yaml). An
optional ``ONECLICK_JWT`` is sent as ``Authorization: Bearer``; without it the
API still answers but charges its no-key fee.

Flow for a cross-chain payment / order:

    q = quote(origin, destination, amount_base, recipient, refund_to, dry=False)
    ok, reasons = check_quote_against_policy(q, recipient, max_in, max_slippage_bps)
    ... send amountIn of origin asset to q["quote"]["depositAddress"] (+ depositMemo)
    submit_deposit(deposit_address, tx_hash)          # optional, speeds things up
    status(deposit_address)  -> PENDING_DEPOSIT | KNOWN_DEPOSIT_TX | PROCESSING |
                                SUCCESS | INCOMPLETE_DEPOSIT | REFUNDED | FAILED

Manual live mode (not part of --check):

    python3 clients/intents.py --live tokens [SYMBOL]
    python3 clients/intents.py --live status <deposit_address>
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

BASE_URL = os.environ.get("ONECLICK_BASE_URL", "https://1click.chaindefuser.com").rstrip("/")
USER_AGENT = "AERA-agent/0.1 (+near-intents)"
TIMEOUT = 30.0

#: Terminal statuses of a 1Click swap.
TERMINAL = frozenset({"SUCCESS", "REFUNDED", "FAILED"})
STATUSES = frozenset({"KNOWN_DEPOSIT_TX", "PENDING_DEPOSIT", "INCOMPLETE_DEPOSIT",
                      "PROCESSING", "SUCCESS", "REFUNDED", "FAILED"})


class IntentsError(RuntimeError):
    def __init__(self, message: str, status: int = 0, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _headers() -> Dict[str, str]:
    h = {"Accept": "application/json", "User-Agent": USER_AGENT}
    jwt = os.environ.get("ONECLICK_JWT", "").strip()
    if jwt:
        h["Authorization"] = "Bearer " + jwt
    return h


def _request(method: str, path: str, query: Optional[Dict[str, str]] = None,
             body: Optional[dict] = None, retries: int = 3) -> Any:
    url = BASE_URL + path
    if query:
        url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
    data = json.dumps(body).encode() if body is not None else None
    last: Optional[IntentsError] = None
    for attempt in range(retries):
        headers = _headers()
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            try:
                parsed: Any = json.loads(raw)
            except ValueError:
                parsed = raw
            msg = parsed.get("message") if isinstance(parsed, dict) else str(parsed)[:300]
            err = IntentsError("1Click %s %s -> HTTP %d: %s" % (method, path, e.code, msg),
                               e.code, parsed)
            if e.code == 429 or e.code >= 500:
                last = err
                time.sleep(0.5 * 2 ** attempt)
                continue
            raise err
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = IntentsError("1Click unreachable: %s" % e)
            time.sleep(0.5 * 2 ** attempt)
    raise last or IntentsError("1Click request failed")


# --------------------------------------------------------------------------- API

def tokens() -> List[dict]:
    """[{assetId, decimals, blockchain, symbol, price, priceUpdatedAt, contractAddress}]"""
    return _request("GET", "/v0/tokens")


def build_quote_request(origin_asset: str, destination_asset: str, amount_base: str,
                        recipient: str, refund_to: str, swap_type: str = "EXACT_OUTPUT",
                        dry: bool = True, slippage_bps: int = 100, deadline_minutes: int = 10,
                        deposit_type: str = "ORIGIN_CHAIN",
                        recipient_type: str = "DESTINATION_CHAIN",
                        refund_type: str = "ORIGIN_CHAIN",
                        app_fees: Optional[Sequence[dict]] = None,
                        now: Optional[datetime] = None) -> dict:
    deadline = (now or datetime.now(timezone.utc)) + timedelta(minutes=deadline_minutes)
    req: Dict[str, Any] = {
        "dry": bool(dry),
        "swapType": swap_type,
        "slippageTolerance": int(slippage_bps),
        "originAsset": origin_asset,
        "depositType": deposit_type,
        "destinationAsset": destination_asset,
        "amount": str(amount_base),
        "refundTo": refund_to,
        "refundType": refund_type,
        "recipient": recipient,
        "recipientType": recipient_type,
        "deadline": deadline.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    if app_fees:
        req["appFees"] = [{"recipient": f["recipient"], "fee": int(f["fee"])} for f in app_fees]
    return req


def quote(origin_asset: str, destination_asset: str, amount_base: str, recipient: str,
          refund_to: str, swap_type: str = "EXACT_OUTPUT", dry: bool = True,
          slippage_bps: int = 100, deadline_minutes: int = 10,
          deposit_type: str = "ORIGIN_CHAIN", recipient_type: str = "DESTINATION_CHAIN",
          refund_type: str = "ORIGIN_CHAIN", app_fees: Optional[Sequence[dict]] = None) -> dict:
    """POST /v0/quote -> {correlationId, timestamp, signature, quoteRequest, quote{...}}"""
    body = build_quote_request(origin_asset, destination_asset, amount_base, recipient,
                               refund_to, swap_type, dry, slippage_bps, deadline_minutes,
                               deposit_type, recipient_type, refund_type, app_fees)
    return _request("POST", "/v0/quote", body=body, retries=2)


def submit_deposit(deposit_address: str, tx_hash: str, memo: Optional[str] = None,
                   near_sender_account: Optional[str] = None) -> dict:
    body: Dict[str, Any] = {"txHash": tx_hash, "depositAddress": deposit_address}
    if memo:
        body["memo"] = memo
    if near_sender_account:
        body["nearSenderAccount"] = near_sender_account
    return _request("POST", "/v0/deposit/submit", body=body)


def status(deposit_address: str, memo: Optional[str] = None) -> dict:
    """GET /v0/status -> {correlationId, quoteResponse, status, updatedAt, swapDetails}"""
    return _request("GET", "/v0/status", query={"depositAddress": deposit_address,
                                                "depositMemo": memo})


# --------------------------------------------------------------------------- policy

def _norm(addr: str) -> str:
    a = (addr or "").strip()
    return a.lower() if a.lower().startswith("0x") else a


def _parse_ts(text: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def check_quote_against_policy(q: dict, expected_recipient: str, max_amount_in_base: int,
                               max_slippage_bps: int, expected_origin_asset: Optional[str] = None,
                               expected_destination_asset: Optional[str] = None,
                               require_deposit_address: bool = False,
                               now: Optional[datetime] = None) -> Tuple[bool, List[str]]:
    """Refuse a quote whose recipient, size, slippage, assets or deadline drifted."""
    reasons: List[str] = []
    req = q.get("quoteRequest") or {}
    qt = q.get("quote") or {}
    if not q.get("correlationId"):
        reasons.append("missing correlationId")
    if _norm(req.get("recipient", "")) != _norm(expected_recipient):
        reasons.append("recipient %r != expected %r" % (req.get("recipient"), expected_recipient))
    for field, want in (("originAsset", expected_origin_asset),
                        ("destinationAsset", expected_destination_asset)):
        if want and req.get(field) != want:
            reasons.append("%s %r != expected %r" % (field, req.get(field), want))
    try:
        amount_in = int(qt.get("amountIn"))
        if amount_in > int(max_amount_in_base):
            reasons.append("amountIn %d > max %d" % (amount_in, int(max_amount_in_base)))
    except (TypeError, ValueError):
        reasons.append("quote has no integer amountIn")
    slip = req.get("slippageTolerance")
    if not isinstance(slip, (int, float)) or slip > max_slippage_bps:
        reasons.append("slippageTolerance %r > max %d bps" % (slip, max_slippage_bps))
    if req.get("swapType") == "EXACT_OUTPUT":
        try:
            if int(qt.get("amountOut")) < int(req.get("amount")):
                reasons.append("amountOut %s < requested %s" % (qt.get("amountOut"), req.get("amount")))
        except (TypeError, ValueError):
            reasons.append("quote has no integer amountOut")
    deadline = _parse_ts(qt.get("deadline") or "")
    if deadline is not None and deadline <= (now or datetime.now(timezone.utc)):
        reasons.append("quote deadline %s has passed" % qt.get("deadline"))
    if require_deposit_address and not qt.get("depositAddress"):
        reasons.append("quote has no depositAddress (dry quote?)")
    return (not reasons, reasons)


# --------------------------------------------------------------------------- self-check

_SAMPLE_QUOTE = {
    "correlationId": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-11-10T12:00:00.000Z",
    "signature": "ed25519:5Lk2...",
    "quoteRequest": {
        "dry": False, "swapType": "EXACT_OUTPUT", "slippageTolerance": 100,
        "originAsset": "nep141:arb-0xaf88d065e77c8cc2239327c5edb3a432268e5831.omft.near",
        "depositType": "ORIGIN_CHAIN",
        "destinationAsset": "nep141:17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1",
        "amount": "25000000", "refundTo": "0x2527D02599Ba641c19FEa793cD0F167589a0f10D",
        "refundType": "ORIGIN_CHAIN", "recipient": "aera-shop.near",
        "recipientType": "DESTINATION_CHAIN", "deadline": "2026-11-10T12:10:00.000Z",
    },
    "quote": {
        "depositAddress": "0x76b4c56085ED136a8744D52bE956396624a730E8",
        "amountIn": "25130000", "amountInFormatted": "25.13", "amountInUsd": "25.13",
        "minAmountIn": "25005000", "amountOut": "25000000", "amountOutFormatted": "25",
        "amountOutUsd": "25.00", "minAmountOut": "25000000",
        "deadline": "2026-11-11T12:00:00.000Z", "timeWhenInactive": "2026-11-11T12:00:00.000Z",
        "timeEstimate": 25,
    },
}


def check() -> None:
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    req = build_quote_request("nep141:a", "nep141:b", "25000000", "r.near", "0xabc",
                              app_fees=[{"recipient": "dev.near", "fee": 50}], now=now)
    assert req["deadline"] == "2026-11-10T12:10:00.000Z"
    assert req["swapType"] == "EXACT_OUTPUT" and req["dry"] is True
    assert req["slippageTolerance"] == 100 and req["amount"] == "25000000"
    assert req["appFees"] == [{"recipient": "dev.near", "fee": 50}]
    for f in ("dry", "swapType", "slippageTolerance", "originAsset", "depositType",
              "destinationAsset", "amount", "refundTo", "refundType", "recipient",
              "recipientType", "deadline"):  # required by the OpenAPI QuoteRequest
        assert f in req, f

    q = _SAMPLE_QUOTE
    ok, why = check_quote_against_policy(q, "aera-shop.near", 26_000_000, 100,
                                         require_deposit_address=True, now=now)
    assert ok and why == [], why
    ok, why = check_quote_against_policy(q, "attacker.near", 26_000_000, 100, now=now)
    assert not ok and "recipient" in why[0]
    ok, why = check_quote_against_policy(q, "aera-shop.near", 25_000_000, 100, now=now)
    assert not ok and "amountIn" in why[0]
    ok, why = check_quote_against_policy(q, "aera-shop.near", 26_000_000, 50, now=now)
    assert not ok and "slippage" in why[0]
    later = datetime(2026, 11, 12, tzinfo=timezone.utc)
    ok, why = check_quote_against_policy(q, "aera-shop.near", 26_000_000, 100, now=later)
    assert not ok and "deadline" in why[0]
    ok, why = check_quote_against_policy(q, "aera-shop.near", 26_000_000, 100,
                                         expected_destination_asset="nep141:other", now=now)
    assert not ok and "destinationAsset" in why[0]
    dry = {"correlationId": "x", "quoteRequest": dict(q["quoteRequest"]),
           "quote": {k: v for k, v in q["quote"].items() if k != "depositAddress"}}
    ok, why = check_quote_against_policy(dry, "aera-shop.near", 26_000_000, 100,
                                         require_deposit_address=True, now=now)
    assert not ok and "depositAddress" in why[0]
    assert _norm("0xAbC") == _norm("0xabc") and _norm("Bob.near") != _norm("bob.near")

    old = os.environ.pop("ONECLICK_JWT", None)
    assert "Authorization" not in _headers()
    os.environ["ONECLICK_JWT"] = "t0k"
    assert _headers()["Authorization"] == "Bearer t0k"
    os.environ.pop("ONECLICK_JWT")
    if old is not None:
        os.environ["ONECLICK_JWT"] = old
    print("intents ok")


demo = check


def _live(argv: List[str]) -> None:
    cmd = argv[0] if argv else "tokens"
    if cmd == "tokens":
        toks = tokens()
        sym = argv[1].upper() if len(argv) > 1 else None
        for t in toks:
            if sym is None or t.get("symbol", "").upper() == sym:
                print("%-8s %-10s %-4s %s" % (t.get("symbol"), t.get("blockchain"),
                                              t.get("decimals"), t.get("assetId")))
        print("%d tokens" % len(toks))
    elif cmd == "status":
        print(json.dumps(status(argv[1], argv[2] if len(argv) > 2 else None), indent=2))
    else:
        raise SystemExit("usage: intents.py --live tokens [SYMBOL] | status <deposit_address>")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--live":
        _live(sys.argv[2:])
    else:
        check()
