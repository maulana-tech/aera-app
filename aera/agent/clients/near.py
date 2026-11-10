"""NEAR JSON-RPC, Borsh transactions and signing, standard library only.

What the agent needs from NEAR and nothing more:

* views: ``view_call`` (contract view methods), ``view_account``,
  ``view_code_hash``, ``view_access_keys``, ``access_key``, ``block_final``
* writes: ``function_call`` / ``send_actions`` build a Borsh ``Transaction``,
  sign sha256(borsh(tx)) with Ed25519 (core.crypto) and submit it with
  ``send_tx`` (nearcore protocol 87; ``broadcast_tx_commit`` is deprecated).

Config from the environment:

    NEAR_NETWORK   testnet | mainnet            (default testnet)
    NEAR_RPC_URL   override the RPC endpoint    (default FastNEAR for the network)

Nonces: one ``threading.Lock`` per (account, public key). The lock is held from
reading the nonce until ``send_tx`` returns, so two callers in this process can
never sign the same nonce or land out of order. Retrying ``send_tx`` with the
same signed bytes is safe: it is the same transaction hash.

Manual live mode (never part of --check):

    python3 clients/near.py --live view <contract> <method> ['{"json":"args"}']
    python3 clients/near.py --live account <account_id>
    python3 clients/near.py --live keys <account_id>
    python3 clients/near.py --live block
    python3 clients/near.py --live tx <tx_hash> <sender_id>
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

if __package__ in (None, ""):  # allow `python3 clients/near.py` from aera/agent
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.crypto import (  # noqa: E402
    base58_decode,
    base58_encode,
    ed25519_public_key,
    ed25519_sign,
    ed25519_verify,
    near_public_key_str,
    parse_near_public_key,
    parse_near_secret,
)

USER_AGENT = "AERA-agent/0.1 (+near)"
TIMEOUT = float(os.environ.get("NEAR_RPC_TIMEOUT", "30"))
RETRIES = 3
TGAS = 10 ** 12
ONE_NEAR = 10 ** 24
ONE_YOCTO = 1

_DEFAULT_RPC = {
    "testnet": "https://test.rpc.fastnear.com",
    "mainnet": "https://free.rpc.fastnear.com",
}


class NearError(RuntimeError):
    """An RPC failure or a transaction that ended in Failure. ``body`` keeps the raw error."""

    def __init__(self, message: str, body: Any = None):
        super().__init__(message)
        self.body = body


def network() -> str:
    net = os.environ.get("NEAR_NETWORK", "testnet").strip().lower() or "testnet"
    if net not in _DEFAULT_RPC:
        raise NearError("NEAR_NETWORK must be testnet or mainnet, got %r" % net)
    return net


def rpc_url() -> str:
    return os.environ.get("NEAR_RPC_URL", "").strip() or _DEFAULT_RPC[network()]


# --------------------------------------------------------------------------- JSON-RPC

def _rpc(method: str, params: Any, timeout: Optional[float] = None) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "id": "aera", "method": method,
                          "params": params}).encode()
    last: Optional[Exception] = None
    for attempt in range(RETRIES):
        req = urllib.request.Request(rpc_url(), data=payload, method="POST", headers={
            "Content-Type": "application/json", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as r:
                body = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            if e.code == 429 or e.code >= 500:
                last = NearError("NEAR RPC HTTP %d: %s" % (e.code, raw[:300]), raw)
                time.sleep(0.5 * 2 ** attempt)
                continue
            # nearcore answers some errors with 4xx + a JSON-RPC error body
            try:
                body = json.loads(raw)
            except ValueError:
                raise NearError("NEAR RPC HTTP %d: %s" % (e.code, raw[:300]), raw)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = NearError("NEAR RPC unreachable: %s" % e)
            time.sleep(0.5 * 2 ** attempt)
            continue
        if "error" in body:
            err = body["error"]
            cause = (err.get("cause") or {}).get("name", "") if isinstance(err, dict) else ""
            if cause == "TIMEOUT_ERROR" and attempt + 1 < RETRIES:
                last = NearError("NEAR RPC timeout", err)
                continue
            raise NearError("NEAR RPC %s: %s" % (method, _err_text(err)), err)
        result = body.get("result")
        if isinstance(result, dict) and "error" in result and method == "query":
            raise NearError("NEAR query: %s" % result["error"], result)
        return result
    raise last or NearError("NEAR RPC failed")


def _err_text(err: Any) -> str:
    if not isinstance(err, dict):
        return str(err)
    cause = err.get("cause") or {}
    parts = [cause.get("name") or err.get("name") or "", json.dumps(cause.get("info") or err.get("data") or "")[:400]]
    return " ".join(p for p in parts if p)


# --------------------------------------------------------------------------- views

def view_call(contract: str, method: str, args: Optional[dict] = None,
              finality: str = "final") -> Any:
    res = _rpc("query", {
        "request_type": "call_function", "finality": finality,
        "account_id": contract, "method_name": method,
        "args_base64": base64.b64encode(json.dumps(args or {}).encode()).decode()})
    raw = bytes(res.get("result") or [])
    if not raw:
        return None
    try:
        return json.loads(raw.decode())
    except ValueError:
        return raw.decode(errors="replace")


def view_account(account_id: str) -> dict:
    return _rpc("query", {"request_type": "view_account", "finality": "final",
                          "account_id": account_id})


def view_code_hash(account_id: str) -> str:
    """base58 code hash; '11111111111111111111111111111111' means no contract."""
    return view_account(account_id)["code_hash"]


def view_access_keys(account_id: str) -> List[dict]:
    res = _rpc("query", {"request_type": "view_access_key_list", "finality": "final",
                         "account_id": account_id})
    return res.get("keys", [])


def access_key(account_id: str, public_key: str) -> dict:
    """{"nonce", "permission", "block_hash", "block_height"} for one key."""
    return _rpc("query", {"request_type": "view_access_key", "finality": "final",
                          "account_id": account_id, "public_key": public_key})


def block_final() -> dict:
    return _rpc("block", {"finality": "final"})


def tx_status(tx_hash: str, sender_id: str, wait: str = "EXECUTED_OPTIMISTIC") -> dict:
    return _rpc("tx", {"tx_hash": tx_hash, "sender_account_id": sender_id, "wait_until": wait})


# --------------------------------------------------------------------------- Borsh

def _u8(n: int) -> bytes:
    return struct.pack("<B", n)


def _u32(n: int) -> bytes:
    return struct.pack("<I", n)


def _u64(n: int) -> bytes:
    return struct.pack("<Q", n)


def _u128(n: int) -> bytes:
    if not 0 <= n < 2 ** 128:
        raise ValueError("u128 out of range")
    return n.to_bytes(16, "little")


def _string(s: str) -> bytes:
    b = s.encode("utf-8")
    return _u32(len(b)) + b


def _bytes(b: bytes) -> bytes:
    return _u32(len(b)) + b


def _pubkey(pub: bytes) -> bytes:
    if len(pub) != 32:
        raise ValueError("ed25519 public key must be 32 bytes")
    return _u8(0) + pub  # KeyType::ED25519 = 0


def _as_pub(key: Union[str, bytes]) -> bytes:
    return parse_near_public_key(key) if isinstance(key, str) else key


class Action:
    """One nearcore ``Action``; ``borsh()`` gives its enum-tagged encoding."""

    def __init__(self, kind: str, body: bytes, summary: Dict[str, Any]):
        self.kind = kind
        self.body = body
        self.summary = summary

    def borsh(self) -> bytes:
        return self.body

    def __repr__(self) -> str:
        return "Action(%s %s)" % (self.kind, self.summary)


def create_account() -> Action:
    return Action("CreateAccount", _u8(0), {})


def deploy_contract(code: bytes) -> Action:
    return Action("DeployContract", _u8(1) + _bytes(code),
                  {"code_sha256": hashlib.sha256(code).hexdigest()})


def function_call_action(method: str, args: Union[bytes, dict, None], gas: int = 30 * TGAS,
                         deposit: int = 0) -> Action:
    raw = args if isinstance(args, (bytes, bytearray)) else json.dumps(args or {}).encode()
    body = _u8(2) + _string(method) + _bytes(bytes(raw)) + _u64(gas) + _u128(deposit)
    return Action("FunctionCall", body, {"method": method, "gas": gas, "deposit": str(deposit)})


def transfer(deposit: int) -> Action:
    return Action("Transfer", _u8(3) + _u128(deposit), {"deposit": str(deposit)})


def add_full_access_key(public_key: Union[str, bytes]) -> Action:
    # AccessKey { nonce: u64, permission: AccessKeyPermission::FullAccess (1) }
    body = _u8(5) + _pubkey(_as_pub(public_key)) + _u64(0) + _u8(1)
    return Action("AddKey", body, {"permission": "FullAccess"})


def add_function_call_key(public_key: Union[str, bytes], receiver_id: str,
                          method_names: Sequence[str] = (),
                          allowance: Optional[int] = None) -> Action:
    # AccessKeyPermission::FunctionCall (0) { allowance: Option<u128>, receiver_id, method_names }
    perm = _u8(0)
    perm += _u8(0) if allowance is None else _u8(1) + _u128(allowance)
    perm += _string(receiver_id) + _u32(len(method_names)) + b"".join(_string(m) for m in method_names)
    body = _u8(5) + _pubkey(_as_pub(public_key)) + _u64(0) + perm
    return Action("AddKey", body, {"permission": "FunctionCall", "receiver_id": receiver_id,
                                   "method_names": list(method_names),
                                   "allowance": None if allowance is None else str(allowance)})


def delete_key(public_key: Union[str, bytes]) -> Action:
    return Action("DeleteKey", _u8(6) + _pubkey(_as_pub(public_key)), {})


def serialize_transaction(signer_id: str, public_key: bytes, nonce: int, receiver_id: str,
                          block_hash: bytes, actions: Sequence[Action]) -> bytes:
    """Borsh ``Transaction`` (V0): signer, key, nonce, receiver, block hash, actions."""
    if len(block_hash) != 32:
        raise ValueError("block hash must be 32 bytes")
    return (_string(signer_id) + _pubkey(public_key) + _u64(nonce) + _string(receiver_id)
            + block_hash + _u32(len(actions)) + b"".join(a.borsh() for a in actions))


def sign_transaction(seed: bytes, tx_bytes: bytes) -> Tuple[bytes, bytes]:
    """(signed_tx_bytes, tx_hash32). Signature is over sha256(borsh(tx))."""
    digest = hashlib.sha256(tx_bytes).digest()
    sig = ed25519_sign(seed, digest)
    return tx_bytes + _u8(0) + sig, digest  # Signature::ED25519 = 0


# --------------------------------------------------------------------------- signing

class Signer:
    """An account plus one Ed25519 key (``ed25519:<base58>`` secret)."""

    def __init__(self, account_id: str, secret: str):
        self.account_id = account_id
        self.seed = parse_near_secret(secret)
        self.public_key = ed25519_public_key(self.seed)
        self.public_key_str = near_public_key_str(self.public_key)

    @classmethod
    def from_env(cls, account_var: str = "NEAR_AGENT_ACCOUNT",
                 key_var: str = "NEAR_AGENT_KEY") -> "Signer":
        acct, key = os.environ.get(account_var, ""), os.environ.get(key_var, "")
        if not acct or not key:
            raise NearError("%s and %s must be set" % (account_var, key_var))
        return cls(acct, key)

    def __repr__(self) -> str:  # never print the secret
        return "Signer(%s, %s)" % (self.account_id, self.public_key_str)


_KEY_LOCKS: Dict[Tuple[str, str], threading.Lock] = {}
_KEY_NONCE: Dict[Tuple[str, str], int] = {}
_LOCKS_GUARD = threading.Lock()


def _key_lock(signer: Signer) -> threading.Lock:
    k = (signer.account_id, signer.public_key_str)
    with _LOCKS_GUARD:
        return _KEY_LOCKS.setdefault(k, threading.Lock())


def send_actions(signer: Signer, receiver: str, actions: Sequence[Action],
                 wait: str = "EXECUTED_OPTIMISTIC") -> dict:
    """Sign and submit one transaction; returns the parsed outcome (see ``outcome``)."""
    key = (signer.account_id, signer.public_key_str)
    with _key_lock(signer):
        for attempt in range(2):
            ak = access_key(signer.account_id, signer.public_key_str)
            nonce = max(int(ak["nonce"]), _KEY_NONCE.get(key, 0)) + 1
            block_hash = base58_decode(ak["block_hash"])
            tx = serialize_transaction(signer.account_id, signer.public_key, nonce,
                                       receiver, block_hash, actions)
            signed, digest = sign_transaction(signer.seed, tx)
            try:
                res = _rpc("send_tx", {"signed_tx_base64": base64.b64encode(signed).decode(),
                                       "wait_until": wait}, timeout=max(TIMEOUT, 60))
            except NearError as e:
                if "InvalidNonce" in json.dumps(e.body or "") and attempt == 0:
                    _KEY_NONCE.pop(key, None)
                    continue
                raise
            _KEY_NONCE[key] = nonce
            out = outcome(res)
            out.setdefault("tx_hash", base58_encode(digest))
            out["explorer"] = explorer_tx_url(out["tx_hash"])
            if out["status"] == "failure":
                raise NearError("transaction failed: %s" % out["error"], out)
            return out
    raise NearError("could not obtain a valid nonce")


def function_call(signer: Signer, contract: str, method: str, args: Optional[dict] = None,
                  gas: int = 30 * TGAS, deposit: int = 0,
                  wait: str = "EXECUTED_OPTIMISTIC") -> dict:
    """{tx_hash, status, result_json, logs, events, explorer}; NearError on panic."""
    return send_actions(signer, contract, [function_call_action(method, args, gas, deposit)], wait)


# --------------------------------------------------------------------------- outcomes

def parse_events(logs: Sequence[str]) -> List[dict]:
    """NEP-297 ``EVENT_JSON:{...}`` lines -> dicts (malformed lines skipped)."""
    out = []
    for line in logs:
        if line.startswith("EVENT_JSON:"):
            try:
                ev = json.loads(line[len("EVENT_JSON:"):])
            except ValueError:
                continue
            if isinstance(ev, dict):
                out.append(ev)
    return out


def _find_panic(failure: Any) -> str:
    """Dig the human message out of a nearcore Failure tree."""
    if isinstance(failure, dict):
        for k in ("ExecutionError", "MethodResolveError", "CompilationError"):
            if k in failure:
                return str(failure[k])
        for v in failure.values():
            msg = _find_panic(v)
            if msg:
                return msg
        return ""
    if isinstance(failure, str):
        return failure
    return ""


def outcome(res: dict) -> dict:
    """Normalise a ``send_tx`` / ``tx`` result."""
    tx = res.get("transaction") or {}
    logs: List[str] = []
    for o in [res.get("transaction_outcome")] + list(res.get("receipts_outcome") or []):
        if o:
            logs.extend(o.get("outcome", {}).get("logs", []))
    out: Dict[str, Any] = {
        "final_execution_status": res.get("final_execution_status"),
        "logs": logs, "events": parse_events(logs), "result_json": None,
        "result_raw": None, "error": None,
    }
    if tx.get("hash"):
        out["tx_hash"] = tx["hash"]
    status = res.get("status")
    if isinstance(status, dict) and "SuccessValue" in status:
        raw = base64.b64decode(status["SuccessValue"] or "")
        out["status"] = "success"
        out["result_raw"] = raw.decode(errors="replace")
        if raw:
            try:
                out["result_json"] = json.loads(raw.decode())
            except ValueError:
                pass
    elif isinstance(status, dict) and "SuccessReceiptId" in status:
        out["status"] = "success"
    elif isinstance(status, dict) and "Failure" in status:
        out["status"] = "failure"
        # receipt-level failures carry the readable panic
        msg = ""
        for o in res.get("receipts_outcome") or []:
            st = o.get("outcome", {}).get("status", {})
            if isinstance(st, dict) and "Failure" in st:
                msg = _find_panic(st["Failure"]) or msg
        out["error"] = msg or _find_panic(status["Failure"]) or json.dumps(status["Failure"])[:400]
    else:
        out["status"] = "pending"
    return out


# --------------------------------------------------------------------------- helpers

def usdc_to_base(amount: Union[str, float, int, Decimal], decimals: int = 6) -> int:
    d = Decimal(str(amount)) * (Decimal(10) ** decimals)
    if d != d.to_integral_value():
        raise ValueError("%s has more than %d decimals" % (amount, decimals))
    if d < 0:
        raise ValueError("negative amount")
    return int(d)


def base_to_usdc(base: Union[int, str], decimals: int = 6) -> str:
    d = Decimal(int(base)) / (Decimal(10) ** decimals)
    return format(d.quantize(Decimal(1).scaleb(-decimals)), "f")


def explorer_tx_url(tx_hash: str) -> str:
    host = "nearblocks.io" if network() == "mainnet" else "testnet.nearblocks.io"
    return "https://%s/txns/%s" % (host, tx_hash)


# --------------------------------------------------------------------------- self-check

def check() -> None:
    # 1. Independent vector: near-api-js test "serialize transfer tx"
    #    signer test.near, key ed25519:Anu7LYDfpLtkP7E16LT9imXF694BdQaa9ufVkQiwTQxC,
    #    nonce 1, receiver whatever.near, block 244ZQ9cgj3CQ6bWBdytfrJMuMQ1jdXLFGnr4HhvtCTnM,
    #    actions [transfer(1)].
    expected = bytes.fromhex(
        "09000000746573742e6e65617200917b3d268d4b58f7fec1b150bd68d69be3ee5d4cc39855e341538465"
        "bb77860d01000000000000000d00000077686174657665722e6e6561720fa473fd26901df296be6adc4c"
        "c4df34d040efa2435224b6986910e630c2fef6010000000301000000000000000000000000000000")
    pk = parse_near_public_key("ed25519:Anu7LYDfpLtkP7E16LT9imXF694BdQaa9ufVkQiwTQxC")
    bh = base58_decode("244ZQ9cgj3CQ6bWBdytfrJMuMQ1jdXLFGnr4HhvtCTnM")
    got = serialize_transaction("test.near", pk, 1, "whatever.near", bh, [transfer(1)])
    assert got == expected, got.hex()

    # 2. Hand-built layout for every action we emit (field order per nearcore).
    seed = bytes(range(32))
    pub = ed25519_public_key(seed)
    fc = function_call_action("request_payment", {"id": "p1"}, gas=30 * TGAS, deposit=1)
    args = b'{"id": "p1"}'
    assert fc.borsh() == (b"\x02" + b"\x0f\x00\x00\x00request_payment" + struct.pack("<I", len(args))
                          + args + struct.pack("<Q", 30 * TGAS) + (1).to_bytes(16, "little"))
    assert create_account().borsh() == b"\x00"
    assert deploy_contract(b"\x00asm").borsh() == b"\x01\x04\x00\x00\x00\x00asm"
    assert add_full_access_key(pub).borsh() == b"\x05\x00" + pub + b"\x00" * 8 + b"\x01"
    fck = add_function_call_key(pub, "vault.testnet", ["request_payment"], allowance=None)
    assert fck.borsh() == (b"\x05\x00" + pub + b"\x00" * 8 + b"\x00" + b"\x00"
                           + b"\x0d\x00\x00\x00vault.testnet" + b"\x01\x00\x00\x00"
                           + b"\x0f\x00\x00\x00request_payment")
    fck2 = add_function_call_key(near_public_key_str(pub), "v.testnet", [], allowance=ONE_NEAR // 4)
    assert fck2.borsh()[42:44] == b"\x00\x01" and fck2.borsh()[44:60] == (ONE_NEAR // 4).to_bytes(16, "little")
    assert fck2.borsh().endswith(b"\x00\x00\x00\x00")
    assert delete_key(pub).borsh() == b"\x06\x00" + pub

    tx = serialize_transaction("agent.testnet", pub, 7, "vault.testnet", bh, [fc])
    assert tx[:4] == struct.pack("<I", 13) and tx[4:17] == b"agent.testnet"
    assert tx[17] == 0 and tx[18:50] == pub and tx[50:58] == struct.pack("<Q", 7)
    assert tx[58:62] == struct.pack("<I", 13) and tx[62:75] == b"vault.testnet"
    assert tx[75:107] == bh and tx[107:111] == b"\x01\x00\x00\x00" and tx[111:] == fc.borsh()

    # 3. Sign -> verify, SignedTransaction framing.
    signed, digest = sign_transaction(seed, tx)
    assert digest == hashlib.sha256(tx).digest()
    assert signed[:len(tx)] == tx and signed[len(tx)] == 0 and len(signed) == len(tx) + 65
    assert ed25519_verify(pub, digest, signed[len(tx) + 1:])
    s = Signer("agent.testnet", "ed25519:" + base58_encode(seed + pub))
    assert s.public_key == pub and "ed25519:" not in repr(s).split(",")[0]

    # 4. Outcome parsing (shape of a send_tx EXECUTED_OPTIMISTIC result).
    ok = outcome({
        "final_execution_status": "EXECUTED_OPTIMISTIC",
        "status": {"SuccessValue": base64.b64encode(b'{"state":"Paid"}').decode()},
        "transaction": {"hash": "Hash1"},
        "transaction_outcome": {"outcome": {"logs": []}},
        "receipts_outcome": [{"outcome": {"logs": [
            'EVENT_JSON:{"standard":"aera","version":"1.0.0","event":"payment_sent","data":[{"id":"p1"}]}',
            "plain log", "EVENT_JSON:{broken"], "status": {"SuccessValue": ""}}}]})
    assert ok["status"] == "success" and ok["result_json"] == {"state": "Paid"}
    assert ok["tx_hash"] == "Hash1" and len(ok["logs"]) == 3
    assert ok["events"] == [{"standard": "aera", "version": "1.0.0", "event": "payment_sent",
                             "data": [{"id": "p1"}]}]
    bad = outcome({"status": {"Failure": {"ActionError": {"index": 0, "kind": {}}}},
                   "transaction": {"hash": "Hash2"},
                   "receipts_outcome": [{"outcome": {"logs": [], "status": {"Failure": {
                       "ActionError": {"kind": {"FunctionCallError": {
                           "ExecutionError": "Smart contract panicked: receiver not allowlisted"}}}}}}}]})
    assert bad["status"] == "failure" and "receiver not allowlisted" in bad["error"]

    # 5. Money helpers.
    assert usdc_to_base("12.5") == 12_500_000 and usdc_to_base(0.1) == 100_000
    assert usdc_to_base(3) == 3_000_000 and base_to_usdc(12_500_000) == "12.500000"
    try:
        usdc_to_base("0.0000001")
        raise AssertionError("sub-unit amount accepted")
    except ValueError:
        pass
    old = os.environ.get("NEAR_NETWORK")
    os.environ["NEAR_NETWORK"] = "testnet"
    assert explorer_tx_url("abc") == "https://testnet.nearblocks.io/txns/abc"
    assert rpc_url() == os.environ.get("NEAR_RPC_URL") or rpc_url() == "https://test.rpc.fastnear.com"
    os.environ["NEAR_NETWORK"] = "mainnet"
    assert explorer_tx_url("abc") == "https://nearblocks.io/txns/abc"
    if old is None:
        os.environ.pop("NEAR_NETWORK")
    else:
        os.environ["NEAR_NETWORK"] = old
    print("near ok")


demo = check


def _live(argv: List[str]) -> None:
    cmd = argv[0] if argv else "block"
    if cmd == "view":
        args = json.loads(argv[3]) if len(argv) > 3 else {}
        print(json.dumps(view_call(argv[1], argv[2], args), indent=2))
    elif cmd == "account":
        print(json.dumps(view_account(argv[1]), indent=2))
    elif cmd == "keys":
        print(json.dumps(view_access_keys(argv[1]), indent=2))
    elif cmd == "block":
        b = block_final()["header"]
        print(json.dumps({"height": b["height"], "hash": b["hash"], "network": network(),
                          "rpc": rpc_url()}, indent=2))
    elif cmd == "tx":
        print(json.dumps(outcome(tx_status(argv[1], argv[2])), indent=2))
    else:
        raise SystemExit("usage: near.py --live view|account|keys|block|tx ...")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--live":
        _live(sys.argv[2:])
    else:
        check()
