"""Redacting personal data before it leaves for a channel the business does not control.

Team alerts go to Slack, Telegram or a webhook. Those are somebody else's
servers, and an alert quotes the supervisor's outcome, which can carry a
customer's name, email or phone. Before such a message leaves, its text goes
through NEAR AI Cloud's privacy filter (`openai/privacy-filter`, running in a
TEE) and the PII is replaced with placeholders.

    text, how = privacy.redact("Ana (ana@client.example) paid")
    # ("Ana (redacted1@example.com) paid", "redacted")  or  (text, "skipped: …")

Fail-open, and SAID: when the filter cannot be reached the message still goes
(an alert that never arrives is its own failure), and `how` says it was not
redacted so the caller can label it. Email to a contact on record is not
redacted: it is addressed to that person on purpose.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import List, Tuple

BASE = os.environ.get("NEARAI_BASE_URL", "https://cloud-api.near.ai/v1").rstrip("/")
MODEL = os.environ.get("AERA_PRIVACY_MODEL", "openai/privacy-filter")


def enabled() -> bool:
    return bool(os.environ.get("NEARAI_API_KEY", "").strip()) and \
        os.environ.get("AERA_REDACT", "1").strip() not in ("0", "false", "no")


def redact_many(texts: List[str], threshold: float = 0.5, timeout: float = 20) -> Tuple[List[str], str]:
    if not texts:
        return [], "nothing to redact"
    if not enabled():
        return texts, "skipped: no NEARAI_API_KEY (or AERA_REDACT=0)"
    body = json.dumps({"model": MODEL, "input": texts, "threshold": threshold}).encode()
    req = urllib.request.Request(f"{BASE}/privacy/redact", data=body, method="POST", headers={
        "Authorization": f"Bearer {os.environ['NEARAI_API_KEY'].strip()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return texts, f"skipped: the privacy filter answered HTTP {e.code}"
    except Exception as e:                                             # noqa: BLE001
        return texts, f"skipped: {type(e).__name__}"
    out = list(texts)
    for entry in data.get("data") or []:
        i = entry.get("index")
        if isinstance(i, int) and 0 <= i < len(out) and isinstance(entry.get("redacted"), str):
            out[i] = entry["redacted"]
    return out, "redacted"


def redact(text: str, **kw) -> Tuple[str, str]:
    out, how = redact_many([text], **kw)
    return out[0], how


def demo() -> None:
    saved = os.environ.pop("NEARAI_API_KEY", None)
    try:
        assert redact("Ana ana@x.example") == ("Ana ana@x.example", "skipped: no NEARAI_API_KEY (or AERA_REDACT=0)")
        # Parsing the documented response shape, with a stubbed transport.
        os.environ["NEARAI_API_KEY"] = "sk-test"
        real = urllib.request.urlopen

        class _R:
            def __init__(self, b): self.b = b
            def read(self): return self.b
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake(req, timeout=0):
            sent = json.loads(req.data)
            assert sent["model"] == MODEL and sent["input"] == ["mail ana@x.example", "ok"]
            return _R(json.dumps({"data": [{"index": 0, "redacted": "mail redacted1@example.com"},
                                           {"index": 1, "redacted": "ok"}], "model": MODEL}).encode())
        urllib.request.urlopen = fake                                  # type: ignore[assignment]
        try:
            out, how = redact_many(["mail ana@x.example", "ok"])
        finally:
            urllib.request.urlopen = real                              # type: ignore[assignment]
        assert out == ["mail redacted1@example.com", "ok"] and how == "redacted", (out, how)
    finally:
        os.environ.pop("NEARAI_API_KEY", None)
        if saved is not None:
            os.environ["NEARAI_API_KEY"] = saved
    print("privacy ok: fail-open and labelled ✓ · documented response parsed ✓")


if __name__ == "__main__":
    demo()
