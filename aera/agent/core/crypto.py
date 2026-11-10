"""Pure-Python crypto primitives for the NEAR and NEAR AI Cloud integrations.

Standard library only, so the agent service needs no wheels:

* base58 (Bitcoin alphabet, as NEAR uses it for keys and hashes)
* Ed25519 sign/verify (RFC 8032) for NEAR transaction signing
* NEAR key-string helpers (``ed25519:<base58>``)
* Keccak-256 (original Keccak padding 0x01, *not* ``hashlib.sha3_256``)
* secp256k1 + EIP-191 ``personal_sign``: sign (RFC 6979 deterministic k) and
  public-key recovery, used to check NEAR AI Cloud response signatures

None of this is constant-time. The signing paths are fine for an agent signing
its own transactions on a server it controls; do not reuse them where an
attacker can time the signer.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional, Tuple, Union

# --------------------------------------------------------------------------- base58

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_IDX = {c: i for i, c in enumerate(_B58)}


def base58_encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = []
    while n:
        n, r = divmod(n, 58)
        out.append(_B58[r])
    pad = len(data) - len(data.lstrip(b"\0"))
    return "1" * pad + "".join(reversed(out))


def base58_decode(text: str) -> bytes:
    n = 0
    for c in text:
        if c not in _B58_IDX:
            raise ValueError("invalid base58 character %r" % c)
        n = n * 58 + _B58_IDX[c]
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(text) - len(text.lstrip("1"))
    return b"\0" * pad + body


# --------------------------------------------------------------------------- Ed25519

_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _ed_recover_x(y: int, sign: int) -> Optional[int]:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_GY = 4 * pow(5, _P - 2, _P) % _P
_GX = _ed_recover_x(_GY, 0)
_G_ED = (_GX, _GY, 1, _GX * _GY % _P)  # extended coordinates (X, Y, Z, T)
_ED_ZERO = (0, 1, 1, 0)


def _ed_add(p, q):
    a = (p[1] - p[0]) * (q[1] - q[0]) % _P
    b = (p[1] + p[0]) * (q[1] + q[0]) % _P
    c = 2 * p[3] * q[3] * _D % _P
    d = 2 * p[2] * q[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _ed_mul(s: int, p):
    q = _ED_ZERO
    while s > 0:
        if s & 1:
            q = _ed_add(q, p)
        p = _ed_add(p, p)
        s >>= 1
    return q


def _ed_equal(p, q) -> bool:
    return ((p[0] * q[2] - q[0] * p[2]) % _P == 0
            and (p[1] * q[2] - q[1] * p[2]) % _P == 0)


def _ed_compress(p) -> bytes:
    zinv = pow(p[2], _P - 2, _P)
    x, y = p[0] * zinv % _P, p[1] * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _ed_decompress(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _ed_recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _ed_expand(seed: bytes) -> Tuple[int, bytes]:
    if len(seed) != 32:
        raise ValueError("ed25519 seed must be 32 bytes")
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def ed25519_public_key(seed32: bytes) -> bytes:
    a, _ = _ed_expand(seed32)
    return _ed_compress(_ed_mul(a, _G_ED))


def ed25519_sign(seed32: bytes, msg: bytes) -> bytes:
    a, prefix = _ed_expand(seed32)
    pub = _ed_compress(_ed_mul(a, _G_ED))
    r = int.from_bytes(hashlib.sha512(prefix + msg).digest(), "little") % _L
    rs = _ed_compress(_ed_mul(r, _G_ED))
    k = int.from_bytes(hashlib.sha512(rs + pub + msg).digest(), "little") % _L
    s = (r + k * a) % _L
    return rs + int.to_bytes(s, 32, "little")


def ed25519_verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    if len(pub) != 32 or len(sig) != 64:
        return False
    a = _ed_decompress(pub)
    r = _ed_decompress(sig[:32])
    if a is None or r is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _L:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _L
    return _ed_equal(_ed_mul(s, _G_ED), _ed_add(r, _ed_mul(k, a)))


# --------------------------------------------------------------------------- NEAR keys

def parse_near_secret(secret: str) -> bytes:
    """``ed25519:<base58>`` (64-byte seed||pub or 32-byte seed) -> 32-byte seed."""
    text = secret.strip()
    if ":" in text:
        curve, text = text.split(":", 1)
        if curve != "ed25519":
            raise ValueError("unsupported key type %r (only ed25519)" % curve)
    raw = base58_decode(text)
    if len(raw) == 64:
        seed, pub = raw[:32], raw[32:]
        if ed25519_public_key(seed) != pub:
            raise ValueError("secret key: embedded public key does not match seed")
        return seed
    if len(raw) == 32:
        return raw
    raise ValueError("secret key must decode to 32 or 64 bytes, got %d" % len(raw))


def near_public_key_str(pub: bytes) -> str:
    return "ed25519:" + base58_encode(pub)


def near_secret_key_str(seed32: bytes) -> str:
    return "ed25519:" + base58_encode(seed32 + ed25519_public_key(seed32))


def parse_near_public_key(text: str) -> bytes:
    if text.startswith("ed25519:"):
        text = text[len("ed25519:"):]
    raw = base58_decode(text)
    if len(raw) != 32:
        raise ValueError("ed25519 public key must be 32 bytes")
    return raw


def implicit_account_id(pub: bytes) -> str:
    return pub.hex()


# --------------------------------------------------------------------------- Keccak-256

_KECCAK_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_KECCAK_ROT = [
    [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
]
_M64 = (1 << 64) - 1


def _rol(x: int, n: int) -> int:
    n %= 64
    return ((x << n) | (x >> (64 - n))) & _M64 if n else x


def _keccak_f(a):
    for rc in _KECCAK_RC:
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        a = [[a[x][y] ^ d[x] for y in range(5)] for x in range(5)]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rol(a[x][y], _KECCAK_ROT[x][y])
        a = [[b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) for y in range(5)]
             for x in range(5)]
        a[0][0] ^= rc
    return a


def keccak256(data: bytes) -> bytes:
    rate = 136
    msg = bytearray(data)
    msg.append(0x01)
    while len(msg) % rate:
        msg.append(0)
    msg[-1] |= 0x80
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(msg), rate):
        block = msg[off:off + rate]
        for i in range(rate // 8):
            x, y = i % 5, i // 5
            a[x][y] ^= int.from_bytes(block[8 * i:8 * i + 8], "little")
        a = _keccak_f(a)
    out = b""
    for i in range(4):
        out += a[i % 5][i // 5].to_bytes(8, "little")
    return out


# --------------------------------------------------------------------------- secp256k1

_SP = 2 ** 256 - 2 ** 32 - 977
_SN = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_SG = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
       0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)


def _jac_double(p):
    x, y, z = p
    if y == 0 or z == 0:
        return (0, 1, 0)
    s = 4 * x * y * y % _SP
    m = 3 * x * x % _SP
    nx = (m * m - 2 * s) % _SP
    ny = (m * (s - nx) - 8 * pow(y, 4, _SP)) % _SP
    nz = 2 * y * z % _SP
    return (nx, ny, nz)


def _jac_add(p, q):
    if p[2] == 0:
        return q
    if q[2] == 0:
        return p
    u1 = p[0] * q[2] * q[2] % _SP
    u2 = q[0] * p[2] * p[2] % _SP
    s1 = p[1] * pow(q[2], 3, _SP) % _SP
    s2 = q[1] * pow(p[2], 3, _SP) % _SP
    if u1 == u2:
        return _jac_double(p) if s1 == s2 else (0, 1, 0)
    h = u2 - u1
    r = s2 - s1
    h2 = h * h % _SP
    h3 = h * h2 % _SP
    u1h2 = u1 * h2 % _SP
    nx = (r * r - h3 - 2 * u1h2) % _SP
    ny = (r * (u1h2 - nx) - s1 * h3) % _SP
    nz = h * p[2] * q[2] % _SP
    return (nx, ny, nz)


def _jac_mul(p, k: int):
    q = (0, 1, 0)
    a = (p[0], p[1], 1)
    while k:
        if k & 1:
            q = _jac_add(q, a)
        a = _jac_double(a)
        k >>= 1
    return q


def _to_affine(p) -> Optional[Tuple[int, int]]:
    if p[2] == 0:
        return None
    zi = pow(p[2], _SP - 2, _SP)
    return (p[0] * zi * zi % _SP, p[1] * zi * zi * zi % _SP)


def _sec_mul(k: int, p=_SG) -> Optional[Tuple[int, int]]:
    return _to_affine(_jac_mul(p, k))


def to_checksum_address(addr20: bytes) -> str:
    """EIP-55 mixed-case address."""
    h = addr20.hex()
    digest = keccak256(h.encode()).hex()
    return "0x" + "".join(c.upper() if int(digest[i], 16) >= 8 else c for i, c in enumerate(h))


def _address_from_point(pt: Tuple[int, int]) -> str:
    raw = pt[0].to_bytes(32, "big") + pt[1].to_bytes(32, "big")
    return to_checksum_address(keccak256(raw)[12:])


def eth_address_from_private(priv32: bytes) -> str:
    k = int.from_bytes(priv32, "big")
    if not 0 < k < _SN:
        raise ValueError("invalid secp256k1 private key")
    return _address_from_point(_sec_mul(k))


def secp256k1_public_key(priv32: bytes) -> bytes:
    """64-byte uncompressed X||Y (no 0x04 prefix)."""
    k = int.from_bytes(priv32, "big")
    if not 0 < k < _SN:
        raise ValueError("invalid secp256k1 private key")
    pt = _sec_mul(k)
    return pt[0].to_bytes(32, "big") + pt[1].to_bytes(32, "big")


def eth_address_from_public(pub: bytes) -> str:
    """Address from a 64-byte X||Y (or 65-byte 0x04-prefixed) public key."""
    if len(pub) == 65 and pub[0] == 4:
        pub = pub[1:]
    if len(pub) != 64:
        raise ValueError("public key must be 64 bytes X||Y")
    return to_checksum_address(keccak256(pub)[12:])


def _as_bytes(message: Union[bytes, str]) -> bytes:
    return message.encode("utf-8") if isinstance(message, str) else bytes(message)


def eip191_hash(message: Union[bytes, str]) -> bytes:
    """keccak256("\\x19Ethereum Signed Message:\\n" + len + message)."""
    m = _as_bytes(message)
    return keccak256(b"\x19Ethereum Signed Message:\n" + str(len(m)).encode() + m)


def _rfc6979_k(priv: int, h1: bytes):
    """Deterministic nonces (RFC 6979 §3.2, HMAC-SHA256), yielded until one is valid."""
    x = priv.to_bytes(32, "big")
    h = (int.from_bytes(h1, "big") % _SN).to_bytes(32, "big")
    v = b"\x01" * 32
    k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + x + h, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + x + h, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        v = hmac.new(k, v, hashlib.sha256).digest()
        cand = int.from_bytes(v, "big")
        if 0 < cand < _SN:
            yield cand
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def secp256k1_sign_hash(priv32: bytes, digest: bytes) -> Tuple[int, int, int]:
    """(r, s, recid) with low-s normalisation."""
    d = int.from_bytes(priv32, "big")
    z = int.from_bytes(digest, "big")
    for k in _rfc6979_k(d, digest):
        pt = _sec_mul(k)
        r = pt[0] % _SN
        if r == 0:
            continue
        s = pow(k, _SN - 2, _SN) * (z + r * d) % _SN
        if s == 0:
            continue
        recid = (pt[1] & 1) | (2 if pt[0] >= _SN else 0)
        if s > _SN // 2:
            s = _SN - s
            recid ^= 1
        return r, s, recid
    raise RuntimeError("unreachable")


def eip191_sign(priv32: bytes, message: Union[bytes, str]) -> str:
    """personal_sign: 0x-hex r||s||v with v in {27, 28}."""
    r, s, recid = secp256k1_sign_hash(priv32, eip191_hash(message))
    return "0x" + r.to_bytes(32, "big").hex() + s.to_bytes(32, "big").hex() + "%02x" % (27 + recid)


def secp256k1_recover(digest: bytes, r: int, s: int, recid: int) -> Optional[Tuple[int, int]]:
    if not (0 < r < _SN and 0 < s < _SN) or recid not in (0, 1, 2, 3):
        return None
    x = r + (_SN if recid & 2 else 0)
    if x >= _SP:
        return None
    alpha = (pow(x, 3, _SP) + 7) % _SP
    beta = pow(alpha, (_SP + 1) // 4, _SP)
    if beta * beta % _SP != alpha:
        return None
    y = beta if (beta & 1) == (recid & 1) else _SP - beta
    z = int.from_bytes(digest, "big")
    rinv = pow(r, _SN - 2, _SN)
    # Q = r^-1 (sR - zG) = (s/r)R + (-z/r)G
    q = _jac_add(_jac_mul((x, y), s * rinv % _SN), _jac_mul(_SG, (-z) * rinv % _SN))
    return _to_affine(q)


def recover_eth_address(message: Union[bytes, str], signature_hex: str) -> Optional[str]:
    """Recover the EIP-55 address that personal_sign'ed ``message``; None if invalid."""
    sig_hex = signature_hex[2:] if signature_hex.startswith(("0x", "0X")) else signature_hex
    try:
        sig = bytes.fromhex(sig_hex)
    except ValueError:
        return None
    if len(sig) != 65:
        return None
    v = sig[64]
    if v in (27, 28):
        v -= 27
    if v not in (0, 1):
        return None
    r = int.from_bytes(sig[:32], "big")
    s = int.from_bytes(sig[32:64], "big")
    pt = secp256k1_recover(eip191_hash(message), r, s, v)
    if pt is None:
        return None
    return _address_from_point(pt)


# --------------------------------------------------------------------------- self-check

_RFC8032 = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
     "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
     "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
     "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
     "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
     "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
     "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]


def check() -> None:
    # base58
    assert base58_encode(b"") == "" and base58_decode("") == b""
    assert base58_encode(b"\0\0\x01") == "112"
    assert base58_encode(b"hello world") == "StV1DL6CwTryKyV"
    assert base58_decode("StV1DL6CwTryKyV") == b"hello world"
    for blob in (b"\0", b"\0\0abc", bytes(range(32))):
        assert base58_decode(base58_encode(blob)) == blob

    # Ed25519, RFC 8032 §7.1 tests 1-3
    for sk, pk, msg, sig in _RFC8032:
        seed, pub, m, s = (bytes.fromhex(x) for x in (sk, pk, msg, sig))
        assert ed25519_public_key(seed) == pub
        assert ed25519_sign(seed, m) == s
        assert ed25519_verify(pub, m, s)
        assert not ed25519_verify(pub, m + b"x", s)
        bad = bytearray(s)
        bad[5] ^= 1
        assert not ed25519_verify(pub, m, bytes(bad))

    # NEAR key strings
    seed = bytes.fromhex(_RFC8032[0][0])
    pub = ed25519_public_key(seed)
    sk_str = near_secret_key_str(seed)
    assert parse_near_secret(sk_str) == seed
    assert parse_near_secret("ed25519:" + base58_encode(seed)) == seed
    assert parse_near_public_key(near_public_key_str(pub)) == pub
    assert implicit_account_id(pub) == _RFC8032[0][1]
    try:
        parse_near_secret("ed25519:" + base58_encode(seed + b"\0" * 32))
        raise AssertionError("mismatched secret accepted")
    except ValueError:
        pass

    # Keccak-256 (not SHA3)
    assert keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert keccak256(b"abc").hex() == "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"
    assert keccak256(b"abc") != hashlib.sha3_256(b"abc").digest()
    assert len(keccak256(b"x" * 300)) == 32  # multi-block absorb

    # secp256k1 / EIP-191
    one = (1).to_bytes(32, "big")
    assert eth_address_from_private(one) == "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
    assert eth_address_from_public(secp256k1_public_key(one)) == eth_address_from_private(one)
    assert secp256k1_public_key(one)[:32].hex() == "%064x" % _SG[0]
    sig = eip191_sign(one, "hello")
    assert len(sig) == 2 + 130 and sig[-2:] in ("1b", "1c")
    assert eip191_sign(one, "hello") == sig, "RFC 6979 must be deterministic"
    assert recover_eth_address("hello", sig) == "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
    assert recover_eth_address(b"hello", sig[:-2] + "%02x" % (int(sig[-2:], 16) - 27)) \
        == "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
    assert recover_eth_address("hellO", sig) != "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
    assert recover_eth_address("hello", "0x1234") is None
    # Published eth-account example (docs, "sign_message"): key b25c..., message "I♥SF".
    ext_key = bytes.fromhex("b25c7db31feed9122727bf0939dc769a96564b2de4c4726d035b36ecf1e5b364")
    ext_sig = ("0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb3"
               "3e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce1c")
    assert eth_address_from_private(ext_key) == "0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E"
    assert eip191_sign(ext_key, "I♥SF") == ext_sig
    assert recover_eth_address("I♥SF", ext_sig) == "0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E"
    print("crypto ok")


demo = check

if __name__ == "__main__":
    check()
