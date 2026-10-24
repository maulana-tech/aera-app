"""Connector to SAP AI Core, the organisers' model hub.

Two jobs, one client:

  * chat completions on `gpt-5.4`, the specialists' fallback brain that spends
    no AWS credit (core/llm.py speaks to it through `chat()`), and
  * tabular prediction on `sap-rpt-1.6`, Vega's slip ranking
    (tools/exposure.py, through `predict()`).

The credential is an AI Core service key: `clientid`, `clientsecret`, `url`
(the token endpoint's base) and `serviceurls.AI_API_URL`. It is read from
AICORE_SERVICE_KEY when set (the JSON itself, the way the organisers' Cloud
Foundry sample passes it), otherwise from SIGAP_AICORE_KEY_FILE, which defaults
to `.secrets/ai-core.json` next to this service. Both are kept out of git.

Like the SAP connector, a missing key does NOT turn into a guess. It raises
MissingServiceKey, and the caller decides what that means: core/llm.py reports
the model as not ready, the RPT tool returns Origin.MISSING.

Deployments are addressed by model name. The ids are looked up from
/v2/lm/deployments once per process, because they are the hackathon tenant's
and can be redeployed under a new id. SIGAP_AICORE_DEPLOYMENTS
(`gpt-5.4=d1a8...,sap-rpt-1.6=d76c...`) pins them when the lookup is not wanted.
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

import core.config  # noqa: F401  (loads .env before anything below reads it)

AGENT_DIR = pathlib.Path(__file__).resolve().parent.parent
CHAT_API_VERSION = "2024-12-01-preview"     # the version the 24 October test passed on
TIMEOUT = int(os.environ.get("AICORE_TIMEOUT", "120"))


class MissingServiceKey(RuntimeError):
    pass


class AICoreError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"AI Core answered {status}: {detail[:300]}")
        self.status = status


def _key_file() -> pathlib.Path:
    raw = os.environ.get("SIGAP_AICORE_KEY_FILE", ".secrets/ai-core.json")
    p = pathlib.Path(raw)
    return p if p.is_absolute() else AGENT_DIR / p


def service_key() -> Dict[str, Any]:
    """The service key, or MissingServiceKey. Never logged, never returned."""
    raw = os.environ.get("AICORE_SERVICE_KEY", "").strip()
    if not raw:
        f = _key_file()
        if not f.exists():
            raise MissingServiceKey(
                f"no AI Core service key: set AICORE_SERVICE_KEY or put it at {f}")
        raw = f.read_text()
    try:
        key = json.loads(raw)
    except ValueError as e:
        raise MissingServiceKey(f"the AI Core service key is not JSON: {e}") from None
    for field in ("clientid", "clientsecret", "url"):
        if not key.get(field):
            raise MissingServiceKey(f"the AI Core service key has no '{field}'")
    if not (key.get("serviceurls") or {}).get("AI_API_URL"):
        raise MissingServiceKey("the AI Core service key has no serviceurls.AI_API_URL")
    return key


def configured() -> bool:
    try:
        service_key()
        return True
    except MissingServiceKey:
        return False


class AICore:
    """One AI Core tenant. Thread-safe: the async dispatcher runs specialists on
    a pool, and they share the token and the deployment map."""

    def __init__(self, key: Optional[Dict[str, Any]] = None,
                 resource_group: Optional[str] = None):
        self._key = key or service_key()
        self.api = self._key["serviceurls"]["AI_API_URL"].rstrip("/")
        self.resource_group = resource_group or os.environ.get("AICORE_RESOURCE_GROUP", "default")
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._token_until = 0.0
        self._deployments: Optional[Dict[str, str]] = None

    # ------------------------------------------------------------------ auth
    def token(self) -> str:
        with self._lock:
            if self._token and time.monotonic() < self._token_until:
                return self._token
            basic = base64.b64encode(
                f"{self._key['clientid']}:{self._key['clientsecret']}".encode()).decode()
            req = urllib.request.Request(
                self._key["url"].rstrip("/") + "/oauth/token",
                data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
                headers={"Authorization": f"Basic {basic}",
                         "Content-Type": "application/x-www-form-urlencoded"})
            body = self._open(req, timeout=30)
            self._token = body["access_token"]
            # A minute of slack, so a token never expires between the check
            # and the call that uses it.
            self._token_until = time.monotonic() + max(60, int(body.get("expires_in", 3600)) - 60)
            return self._token

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}",
                "AI-Resource-Group": self.resource_group,
                "Content-Type": "application/json"}

    @staticmethod
    def _open(req: urllib.request.Request, timeout: int) -> Dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise AICoreError(e.code, e.read().decode(errors="replace")) from None

    def _get(self, path: str) -> Dict[str, Any]:
        return self._open(urllib.request.Request(self.api + path, headers=self._headers()),
                          timeout=30)

    def _post(self, path: str, body: Dict[str, Any], timeout: int = TIMEOUT) -> Dict[str, Any]:
        """POST with two retries on 429 and 5xx: the tenant is shared hackathon
        capacity, and a burst from another team is not this handling's fault."""
        data = json.dumps(body, ensure_ascii=False).encode()
        for attempt in range(3):
            req = urllib.request.Request(self.api + path, data=data, method="POST",
                                         headers=self._headers())
            try:
                return self._open(req, timeout=timeout)
            except AICoreError as e:
                if e.status not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
            except urllib.error.URLError:
                if attempt == 2:
                    raise
            time.sleep(1.5 * (attempt + 1))
        raise AssertionError("unreachable")

    # ----------------------------------------------------------- deployments
    def deployments(self) -> Dict[str, str]:
        """model name → id of its RUNNING deployment."""
        if self._deployments is not None:
            return self._deployments
        pinned = os.environ.get("SIGAP_AICORE_DEPLOYMENTS", "").strip()
        if pinned:
            found = dict(p.strip().split("=", 1) for p in pinned.split(",") if "=" in p)
        else:
            found = {}
            for d in self._get("/v2/lm/deployments").get("resources", []):
                if d.get("status") != "RUNNING":
                    continue
                res = (d.get("details") or {}).get("resources") or {}
                backend = res.get("backendDetails") or res.get("backend_details") or {}
                name = (backend.get("model") or {}).get("name")
                if name:
                    found.setdefault(name, d["id"])
        self._deployments = found
        return found

    def deployment(self, model: str) -> str:
        ids = self.deployments()
        if model in ids:
            return ids[model]
        if model in ids.values():          # already an id
            return model
        raise AICoreError(404, f"no RUNNING deployment of '{model}' in resource group "
                               f"'{self.resource_group}' (have: {', '.join(sorted(ids)) or 'none'})")

    # ------------------------------------------------------------- inference
    def chat(self, model: str, body: Dict[str, Any], timeout: int = TIMEOUT) -> Dict[str, Any]:
        """OpenAI Chat Completions against a model's deployment."""
        dep = self.deployment(model)
        return self._post(f"/v2/inference/deployments/{dep}/chat/completions"
                          f"?api-version={CHAT_API_VERSION}", body, timeout)

    def invoke(self, model: str, body: Dict[str, Any], timeout: int = TIMEOUT) -> Dict[str, Any]:
        """Bedrock InvokeModel, which is how AI Core serves `anthropic--*`: its
        chat/completions path is refused for those deployments."""
        dep = self.deployment(model)
        return self._post(f"/v2/inference/deployments/{dep}/invoke", body, timeout)

    def predict(self, model: str, body: Dict[str, Any], timeout: int = TIMEOUT) -> Dict[str, Any]:
        """SAP RPT tabular prediction. Rows carry `[PREDICT]` where a value is wanted."""
        dep = self.deployment(model)
        return self._post(f"/v2/inference/deployments/{dep}/predict", body, timeout)


_SHARED: Optional[AICore] = None
_SHARED_LOCK = threading.Lock()


def shared() -> AICore:
    """The process-wide client, so every caller reuses one token."""
    global _SHARED
    with _SHARED_LOCK:
        if _SHARED is None:
            _SHARED = AICore()
        return _SHARED


def demo() -> None:
    # No network here: the parts that decide what is sent and refused.
    os.environ["SIGAP_AICORE_DEPLOYMENTS"] = "gpt-5.4=dep-chat,sap-rpt-1.6=dep-rpt"
    fake = {"clientid": "x", "clientsecret": "y", "url": "https://auth.invalid",
            "serviceurls": {"AI_API_URL": "https://api.invalid/"}}
    ai = AICore(key=fake)
    assert ai.api == "https://api.invalid", "a trailing slash must not double up in paths"
    assert ai.deployment("gpt-5.4") == "dep-chat"
    assert ai.deployment("dep-rpt") == "dep-rpt", "an id is accepted as itself"
    try:
        ai.deployment("tabpfn-3.5-plus")
        raise AssertionError("an unknown model must not resolve to anything")
    except AICoreError as e:
        assert e.status == 404 and "gpt-5.4" in str(e), e
    del os.environ["SIGAP_AICORE_DEPLOYMENTS"]

    saved = os.environ.pop("AICORE_SERVICE_KEY", None), os.environ.get("SIGAP_AICORE_KEY_FILE")
    os.environ["SIGAP_AICORE_KEY_FILE"] = "/nonexistent/ai-core.json"
    try:
        assert not configured(), "a missing key file is not a configured tenant"
        os.environ["AICORE_SERVICE_KEY"] = '{"clientid": "x"}'
        try:
            service_key()
            raise AssertionError("a key without a secret must be refused")
        except MissingServiceKey as e:
            assert "clientsecret" in str(e)
    finally:
        os.environ.pop("AICORE_SERVICE_KEY", None)
        if saved[0] is not None:
            os.environ["AICORE_SERVICE_KEY"] = saved[0]
        if saved[1] is None:
            os.environ.pop("SIGAP_AICORE_KEY_FILE", None)
        else:
            os.environ["SIGAP_AICORE_KEY_FILE"] = saved[1]
    print("aicore ok, deployments by name ✓ · ids accepted ✓ · a missing or partial key refused ✓"
          + ("" if configured() else " (no service key here, live calls not exercised)"))


if __name__ == "__main__":
    demo()
