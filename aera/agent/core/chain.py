"""The vault, as the rest of AERA sees it.

One adapter over clients/near.py, so the agent loop, the guardian and the
settlement worker never build a transaction themselves and never hold a key.
The only key this service holds is the agent's FUNCTION-CALL key on the vault
(AERA_NEAR_AGENT_KEY): it can call request_payment, deliver_receipt and
freeze, and it cannot attach a deposit, so it cannot move a token on its own.

When no vault is configured, AERA still runs: `configured()` is False, reads
come back MISSING, and the settlement worker records payments on the
"simulated" rail, labelled as such everywhere they are shown. Nothing is ever
reported as on-chain that was not.
"""
from __future__ import annotations

import os
import re
from decimal import Decimal
from typing import Any, Dict, Optional

#: The well-known USDC contracts (Circle, native on NEAR; 6 decimals).
USDC = {
    "mainnet": "17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1",
    "testnet": "3e2210e1184b45b64c8a434c0a7e7b23cc04ea7eb7a6c3c32520d03d4afcb8af",
}
DECIMALS = 6


class ChainUnavailable(RuntimeError):
    pass


def network() -> str:
    return (os.environ.get("NEAR_NETWORK") or "testnet").strip().lower()


def vault_id() -> str:
    return (os.environ.get("AERA_VAULT_CONTRACT") or "").strip()


def agent_id() -> str:
    return (os.environ.get("AERA_NEAR_AGENT_ACCOUNT") or "").strip()


def token_id() -> str:
    return (os.environ.get("AERA_USDC_TOKEN") or USDC.get(network(), "")).strip()


def configured() -> bool:
    """A vault and an agent key to call it with."""
    return bool(vault_id() and agent_id() and os.environ.get("AERA_NEAR_AGENT_KEY"))


def readable() -> bool:
    """A vault to read, even without a key (views need none)."""
    return bool(vault_id())


def _near():
    try:
        from clients import near
    except ImportError as e:                                           # pragma: no cover
        raise ChainUnavailable(f"clients/near.py is not available: {e}") from None
    return near


def to_base(usd: float) -> str:
    return str(int((Decimal(str(usd)) * (10 ** DECIMALS)).to_integral_value()))


def from_base(base: Any) -> float:
    try:
        return float(Decimal(str(base)) / (10 ** DECIMALS))
    except Exception:                                                  # noqa: BLE001
        return 0.0


_ACCOUNT = re.compile(r"^(([a-z\d]+[\-_])*[a-z\d]+\.)*([a-z\d]+[\-_])*[a-z\d]+$")


def valid_account(account_id: str) -> bool:
    a = (account_id or "").strip()
    return 2 <= len(a) <= 64 and bool(_ACCOUNT.match(a))


def request_id(idempotency_key: str) -> str:
    """The vault's request id for an action: its idempotency key, made safe."""
    return re.sub(r"[^A-Za-z0-9:_\-]", "_", idempotency_key)[:64]


def explorer(tx_hash: Optional[str]) -> Optional[str]:
    if not tx_hash:
        return None
    base = "https://testnet.nearblocks.io" if network() == "testnet" else "https://nearblocks.io"
    return f"{base}/txns/{tx_hash}"


# ---------------------------------------------------------------- views
def view(method: str, args: Optional[dict] = None) -> Any:
    if not readable():
        raise ChainUnavailable("AERA_VAULT_CONTRACT is not set")
    return _near().view_call(vault_id(), method, args or {})


def policy() -> Optional[Dict[str, Any]]:
    try:
        return view("get_policy")
    except Exception:                                                  # noqa: BLE001
        return None


def counterparty(account_id: str) -> Optional[Dict[str, Any]]:
    return view("get_counterparty", {"account_id": account_id})


def vault_balance() -> Optional[float]:
    try:
        base = _near().view_call(token_id(), "ft_balance_of", {"account_id": vault_id()})
        return from_base(base)
    except Exception:                                                  # noqa: BLE001
        return None


def account(account_id: str) -> Optional[Dict[str, Any]]:
    try:
        return _near().view_account(account_id)
    except Exception:                                                  # noqa: BLE001
        return None


def code_hash(account_id: str) -> Optional[str]:
    try:
        return _near().view_code_hash(account_id)
    except Exception:                                                  # noqa: BLE001
        return None


def account_age_days(account_id: str) -> Optional[float]:
    """Days since the account was created, from NearBlocks. None when unknown."""
    import json
    import urllib.request
    from datetime import datetime, timezone
    base = "https://api-testnet.nearblocks.io" if network() == "testnet" else "https://api.nearblocks.io"
    try:
        # NearBlocks retired /v1 (testnet 2026-11-05, mainnet 2026-11-22); /v3 returns
        # {"data": {"created": {"block_timestamp": "<ns>"}, ...}}.
        req = urllib.request.Request(f"{base}/v3/accounts/{account_id}",
                                     headers={"User-Agent": "aera-agent", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        acct = data.get("data") or {}
        if isinstance(acct, list):
            acct = acct[0] if acct else {}
        ts = (acct.get("created") or {}).get("block_timestamp")
        if not ts:
            return None
        created = datetime.fromtimestamp(int(ts) / 1e9, tz=timezone.utc)
        return (datetime.now(timezone.utc) - created).total_seconds() / 86400
    except Exception:                                                  # noqa: BLE001
        return None


# ---------------------------------------------------------------- calls
def _signer():
    if not configured():
        raise ChainUnavailable("the vault or the agent's function-call key is not configured")
    near = _near()
    return near.Signer(agent_id(), os.environ["AERA_NEAR_AGENT_KEY"])


def call(method: str, args: dict, gas_tgas: int = 100) -> Dict[str, Any]:
    """Call the vault with the agent's function-call key. No deposit, ever."""
    near = _near()
    out = near.function_call(_signer(), vault_id(), method, args, gas=gas_tgas * 10 ** 12, deposit=0)
    out["explorer"] = explorer(out.get("tx_hash"))
    return out


def request_payment(req_id: str, receiver: str, amount_usd: float, purpose: str, reference: str) -> Dict[str, Any]:
    # 50 Tgas: the method itself plus 10 for ft_transfer and 10 for the on_transfer callback.
    # Prepaid gas is charged against the function-call key's allowance, so no more than needed.
    return call("request_payment", {"request_id": request_id(req_id), "receiver_id": receiver,
                                    "amount": to_base(amount_usd), "purpose": purpose[:200],
                                    "reference": reference[:100]}, gas_tgas=50)


def payment_failed(out: Dict[str, Any], req_id: str) -> bool:
    """True when the vault's own callback said the transfer for this request failed.

    The vault returns "sent" when it STARTS ft_transfer; the token can still refuse it (most
    often: the receiver holds no USDC storage). The callback then emits `payment_failed`, which
    lands in the same transaction's receipts."""
    rid = request_id(req_id)
    for e in out.get("events") or []:
        if e.get("event") != "payment_failed":
            continue
        data = e.get("data")
        # NEP-297: `data` is an array of objects (the vault emits [ {...} ]); accept a bare object too.
        for d in data if isinstance(data, list) else [data]:
            if isinstance(d, dict) and d.get("request_id") == rid:
                return True
    return False


def deliver_receipt(order_id: str, content_hash: str) -> Dict[str, Any]:
    return call("deliver_receipt", {"order_id": order_id, "content_hash": content_hash}, gas_tgas=30)


def freeze() -> Dict[str, Any]:
    return call("freeze", {}, gas_tgas=30)


def demo() -> None:
    assert to_base(15) == "15000000" and to_base(0.1) == "100000" and from_base("2500000") == 2.5
    assert request_id("payment:ab/cd ef") == "payment:ab_cd_ef"
    failed = {"events": [{"standard": "aera-vault", "event": "payment_failed",
                          "data": [{"request_id": "payment:ab", "amount": "1"}]}]}
    assert payment_failed(failed, "payment:ab") and not payment_failed(failed, "payment:cd")
    assert not payment_failed({"events": [{"event": "payment_sent", "data": [{"request_id": "payment:ab"}]}]},
                              "payment:ab")
    for ok in ("vendor.testnet", "a1.b-c_d.near", "17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1"):
        assert valid_account(ok), ok
    for bad in ("", "A.near", "x", "a..b", "-a.near", "a" * 65, "bad account"):
        assert not valid_account(bad), bad
    print(f"chain ok (vault {'configured' if configured() else 'not configured: simulated rail'})")


if __name__ == "__main__":
    demo()
