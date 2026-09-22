"""Identity and authority.

The hole this closed: 'who approved it' used to come from the request body,
which meant anyone could claim any role. Identity now comes ONLY from a
session token the server signed.

# ponytail: local auth on an HMAC token. In a real company this becomes SSO —
#           `from_token()` is the single place that changes.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.store import connect, _now

SECRET = os.environ.get("SIGAP_SECRET", "")
SESSION_HOURS = 12

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id         TEXT PRIMARY KEY,
  email      TEXT NOT NULL UNIQUE,
  name       TEXT NOT NULL,
  role       TEXT NOT NULL,
  password   TEXT NOT NULL,        -- pbkdf2$iterations$salt$derived
  active     INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
"""

# How much action value each role may approve (rupiah).
ROLE_LIMITS = {
    "planner": 0,                    # read only
    "buyer": 500_000_000,
    "procurement_lead": 10_000_000_000,
    "admin": 10_000_000_000,
}


class NotAuthorised(PermissionError):
    pass


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str
    role: str

    @property
    def limit_idr(self) -> int:
        return ROLE_LIMITS.get(self.role, 0)

    def may_approve(self, value_idr: int) -> bool:
        return self.limit_idr > 0 and value_idr <= self.limit_idr


# ------------------------------------------------------------------ passwords
def _hash_password(password: str, salt: Optional[bytes] = None,
                   iterations: int = 200_000) -> str:
    s = salt or secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), s, iterations)
    return f"pbkdf2${iterations}${base64.b64encode(s).decode()}${base64.b64encode(derived).decode()}"


def _password_matches(password: str, stored: str) -> bool:
    try:
        _, it, s, d = stored.split("$")
        again = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(s), int(it))
        return hmac.compare_digest(again, base64.b64decode(d))
    except Exception:                                                # noqa: BLE001
        return False


# ---------------------------------------------------------------------- token
def _secret() -> bytes:
    if not SECRET:
        raise RuntimeError(
            "SIGAP_SECRET is not set. Without it session tokens can be forged. "
            "Generate one with: python3 -c \"import secrets;print(secrets.token_hex(32))\""
        )
    return SECRET.encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_token(u: User) -> str:
    claims = {"sub": u.id, "email": u.email, "name": u.name, "role": u.role,
              "exp": (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)).timestamp()}
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def from_token(token: str) -> User:
    """The only way identity enters the system. Swap this body for SSO."""
    try:
        payload, sig = token.split(".")
    except ValueError:
        raise NotAuthorised("malformed token")

    expected = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        raise NotAuthorised("token signature does not match")

    claims = json.loads(_unb64(payload))
    if claims["exp"] < datetime.now(timezone.utc).timestamp():
        raise NotAuthorised("session expired")
    return User(claims["sub"], claims["email"], claims["name"], claims["role"])


# ---------------------------------------------------------------------- users
def prepare() -> None:
    with connect() as c:
        c.executescript(SCHEMA)


def add_user(email: str, name: str, role: str, password: str) -> User:
    if role not in ROLE_LIMITS:
        raise ValueError(f"unknown role: {role}")
    prepare()
    uid = "usr_" + secrets.token_hex(6)
    with connect() as c:
        c.execute("INSERT INTO users (id,email,name,role,password,created_at)"
                  " VALUES (?,?,?,?,?,?)",
                  (uid, email.lower(), name, role, _hash_password(password), _now()))
    return User(uid, email.lower(), name, role)


def log_in(email: str, password: str) -> User:
    prepare()
    with connect() as c:
        r = c.execute("SELECT * FROM users WHERE email=? AND active=1",
                      (email.lower(),)).fetchone()
    # compare regardless, so a missing user takes the same time as a wrong password
    stored = r["password"] if r else _hash_password("x")
    if not _password_matches(password, stored) or not r:
        raise NotAuthorised("wrong email or password")
    return User(r["id"], r["email"], r["name"], r["role"])


def demo() -> None:
    os.environ.setdefault("SIGAP_SECRET", secrets.token_hex(16))
    global SECRET
    SECRET = os.environ["SIGAP_SECRET"]

    u = User("usr_1", "budi@kpn.co.id", "Budi", "buyer")
    t = issue_token(u)
    assert from_token(t).email == u.email

    payload, sig = t.split(".")
    forged = json.loads(_unb64(payload)); forged["role"] = "admin"
    try:
        from_token(f"{_b64(json.dumps(forged).encode())}.{sig}")
        raise AssertionError("a forged token must be rejected")
    except NotAuthorised:
        pass
    print("  token: valid ✓ · tampered → rejected ✓")

    assert User("u", "e", "n", "planner").may_approve(1) is False
    assert User("u", "e", "n", "buyer").may_approve(94_000_000) is True
    assert User("u", "e", "n", "buyer").may_approve(900_000_000) is False
    assert User("u", "e", "n", "procurement_lead").may_approve(900_000_000) is True
    print("  authority: planner none · buyer to Rp 500m · lead above that ✓")

    h = _hash_password("secret123")
    assert _password_matches("secret123", h) and not _password_matches("wrong", h)
    print("  passwords: pbkdf2 ✓")
    print("identity ok")


if __name__ == "__main__":
    demo()
