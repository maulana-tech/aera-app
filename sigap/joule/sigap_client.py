"""The shim's way into SIGAP: a service user's session, nothing more.

Joule reaches the shim through a `NoAuthentication` destination and carries no
user identity, so the shim cannot act as whoever is typing. It signs in to
SIGAP as one service user whose role is `planner`. `ROLE_LIMITS` in
`sigap/agent/core/identity.py` gives that role an approval limit of 0, so even a
shim that misbehaved could not approve anything: the server refuses, whatever
the shim sends.

Two ways in, chosen by SIGAP_API_MODE:

  direct  SIGAP_API is the agent service itself (`python3 api.py`), and the
          token goes in `Authorization: Bearer`. For a local run, or once nginx
          routes the agent API directly.
  bridge  SIGAP_API is the public web app. Calls go to `<base>/api/sigap/...`,
          and the token goes ONLY in the `sigap_session` cookie, because the
          Next bridge (`app/api/sigap/[...path]/route.ts`) reads the token from
          that cookie and drops any Authorization header it is sent.

Sessions last 12 hours (`SESSION_HOURS`). The token is cached and the shim
signs in again when SIGAP answers 401, once per call, so an expired session
costs one extra round trip rather than a failed answer.

Standard library only, so it runs (and self-checks) on the agent service's
Python 3.9 as well as on the shim's 3.13.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

TIMEOUT = int(os.environ.get("SIGAP_TIMEOUT", "20"))


class SigapError(RuntimeError):
    """SIGAP answered, but not with what was asked for."""

    def __init__(self, status: int, detail: str):
        super().__init__(f"SIGAP answered {status}: {detail[:300]}")
        self.status = status
        self.detail = detail


class SigapUnreachable(RuntimeError):
    """SIGAP did not answer at all."""


class NotConfigured(RuntimeError):
    pass


def _default_mode(base: str) -> str:
    host = urllib.parse.urlparse(base).hostname or ""
    return "direct" if host in ("127.0.0.1", "localhost", "::1") else "bridge"


class SigapClient:
    def __init__(self, base: str, email: str, password: str,
                 mode: Optional[str] = None, timeout: int = TIMEOUT):
        if not base:
            raise NotConfigured("SIGAP_API is not set")
        if not (email and password):
            raise NotConfigured("SIGAP_SHIM_EMAIL and SIGAP_SHIM_PASSWORD are not set")
        self.base = base.rstrip("/")
        self.mode = (mode or _default_mode(self.base)).lower()
        if self.mode not in ("direct", "bridge"):
            raise NotConfigured(f"SIGAP_API_MODE must be 'direct' or 'bridge', not '{self.mode}'")
        self._email, self._password = email, password
        self.timeout = timeout
        self._token: Optional[str] = None
        self._lock = threading.Lock()
        self.logins = 0                      # read by the self-checks

    @classmethod
    def from_env(cls) -> "SigapClient":
        return cls(os.environ.get("SIGAP_API", ""),
                   os.environ.get("SIGAP_SHIM_EMAIL", ""),
                   os.environ.get("SIGAP_SHIM_PASSWORD", ""),
                   mode=os.environ.get("SIGAP_API_MODE") or None)

    # ---------------------------------------------------------------- wire
    def _url(self, path: str) -> str:
        prefix = "/api/sigap" if self.mode == "bridge" else ""
        return f"{self.base}{prefix}{path}"

    def _send(self, method: str, path: str, body: Optional[dict],
              token: Optional[str]) -> Tuple[int, Any]:
        headers = {"content-type": "application/json", "accept": "application/json"}
        if token:
            if self.mode == "bridge":
                headers["cookie"] = f"sigap_session={token}"
            else:
                headers["authorization"] = f"Bearer {token}"
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
        req = urllib.request.Request(self._url(path), data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read().decode()
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            try:
                parsed: Any = json.loads(raw)
            except ValueError:
                parsed = {"error": raw[:300]}
            return e.code, parsed
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise SigapUnreachable(f"SIGAP is not answering at {self.base}: {e}") from None

    # ---------------------------------------------------------------- auth
    def _login(self) -> str:
        status, data = self._send("POST", "/login",
                                  {"email": self._email, "password": self._password}, None)
        if status != 200 or not isinstance(data, dict) or not data.get("token"):
            raise SigapError(status, _detail(data) or "sign-in refused")
        self.logins += 1
        return data["token"]

    def _current_token(self, refresh: bool = False) -> str:
        with self._lock:
            if refresh or not self._token:
                self._token = self._login()
            return self._token

    def request(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        token = self._current_token()
        status, data = self._send(method, path, body, token)
        if status == 401:
            # The session expired, or the service restarted with a new secret.
            token = self._current_token(refresh=True)
            status, data = self._send(method, path, body, token)
        if status >= 400:
            raise SigapError(status, _detail(data))
        return data

    # ----------------------------------------------------------- the calls
    def raise_event(self, event: dict) -> dict:
        return self.request("POST", "/events", event)

    def run(self, run_id: str) -> dict:
        return self.request("GET", f"/runs/{urllib.parse.quote(run_id)}")

    def runs(self) -> list:
        return (self.request("GET", "/runs") or {}).get("runs", [])

    def exposure(self) -> dict:
        return self.request("GET", "/exposure")

    def assess_option(self, option_id: str) -> dict:
        """Rule one option through MCP, which is the same registry SIGAP's own
        agents call. Going through /mcp rather than a bespoke endpoint means
        Joule cannot be handed a different answer from the one Kira gives."""
        reply = self.request("POST", "/mcp", {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "check_local_constraints",
                       "arguments": {"option_id": option_id}},
        })
        return reply or {}


def _detail(data: Any) -> str:
    if isinstance(data, dict):
        return str(data.get("error") or data.get("detail") or "")
    return str(data or "")


def demo() -> None:
    # Offline: the routing decisions only. The wire is exercised end to end
    # against a stub SIGAP (README, "Test without Joule").
    c = SigapClient("https://sigap.example.org/", "svc@example.org", "pw")
    assert c.mode == "bridge" and c._url("/runs") == "https://sigap.example.org/api/sigap/runs"
    c = SigapClient("http://127.0.0.1:8797", "svc@example.org", "pw")
    assert c.mode == "direct" and c._url("/runs") == "http://127.0.0.1:8797/runs"
    c = SigapClient("http://10.0.0.5:8787", "svc@example.org", "pw", mode="direct")
    assert c.mode == "direct", "an explicit mode wins over the guess"
    for bad in (("", "a", "b"), ("http://x", "", "b")):
        try:
            SigapClient(*bad)
            raise AssertionError(f"must refuse {bad}")
        except NotConfigured:
            pass
    print("sigap_client ok, bridge vs direct ✓ · missing config refused ✓")


if __name__ == "__main__":
    demo()
