"""Manual live spike for NEAR AI Cloud (not part of any --check).

    NEARAI_API_KEY=... python3 scripts/near_spike.py [--models a,b,c] [--no-proof]

(a) lists /v1/models and /v1/model/list and marks which models are attested;
(b) sends one OpenAI-format chat completion WITH a ``tools`` array to each
    candidate and reports whether ``tool_calls`` came back well-formed, latency
    and usage;
(c) runs core.attest.proof on the first successful call and prints the checks.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import attest  # noqa: E402

BASE = attest.BASE_URL
CANDIDATES = [
    "moonshotai/kimi-k3",
    "z-ai/glm-5.3",
    "z-ai/glm-5.3-flash",
    "Qwen/Qwen3.8-27B",
    "deepseek-ai/DeepSeek-V4.1-Flash-1017",
]
TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["city"],
        },
    },
}]


def _req(method: str, path: str, key: str, body: Optional[bytes] = None,
         timeout: float = 120) -> Tuple[int, bytes, float]:
    headers = {"Authorization": "Bearer " + key, "Accept": "application/json",
               "Accept-Encoding": "identity", "User-Agent": attest.USER_AGENT}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read(), time.time() - t0
    except (urllib.error.URLError, OSError) as e:
        return 0, str(e).encode(), time.time() - t0


def list_models(key: str) -> Dict[str, dict]:
    print("== (a) models")
    st, raw, _ = _req("GET", "/models", key)
    ids = []
    if st == 200:
        ids = [m.get("id") for m in json.loads(raw).get("data", [])]
    print("  /v1/models: HTTP %d, %d models" % (st, len(ids)))
    meta: Dict[str, dict] = {}
    try:
        for m in attest.fetch_model_list():
            meta[m.get("modelId")] = m.get("metadata") or {}
    except attest.AttestError as e:
        print("  /v1/model/list failed:", e)
    attested = sorted(k for k, v in meta.items() if v.get("verifiable") or v.get("attestationSupported"))
    print("  /v1/model/list: %d models, %d attested (verifiable)" % (len(meta), len(attested)))
    for k in attested:
        feats = ",".join(meta[k].get("supportedFeatures") or [])
        print("    TEE  %-45s %s" % (k, feats))
    return meta


def try_tools(key: str, model: str) -> Dict[str, Any]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "What's the weather in Jakarta right now? Use the tool."}],
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_tokens": 512,
        "stream": False,
    }).encode()
    st, raw, dt = _req("POST", "/chat/completions", key, body)
    row: Dict[str, Any] = {"model": model, "http": st, "latency_s": round(dt, 2),
                           "req": body, "resp": raw}
    if st != 200:
        row["error"] = raw[:300].decode(errors="replace")
        return row
    try:
        data = json.loads(raw)
    except ValueError:
        row["error"] = "non-JSON body"
        return row
    row["chat_id"] = data.get("id")
    row["usage"] = data.get("usage")
    msg = ((data.get("choices") or [{}])[0]).get("message") or {}
    calls = msg.get("tool_calls") or []
    good = False
    for c in calls:
        fn = c.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "")
            good = fn.get("name") == "get_weather" and isinstance(args, dict) and "city" in args \
                and bool(c.get("id")) and c.get("type") == "function"
        except ValueError:
            good = False
    row["tool_calls"] = len(calls)
    row["tool_calls_ok"] = good
    row["finish_reason"] = ((data.get("choices") or [{}])[0]).get("finish_reason")
    if not calls:
        row["content"] = (msg.get("content") or "")[:120]
    return row


def main(argv: List[str]) -> int:
    key = os.environ.get("NEARAI_API_KEY", "").strip()
    if not key:
        print("NEARAI_API_KEY is not set; nothing to do. Get one at https://cloud.near.ai")
        return 0
    models = CANDIDATES
    for i, a in enumerate(argv):
        if a == "--models" and i + 1 < len(argv):
            models = [m for m in argv[i + 1].split(",") if m]
    meta = list_models(key)

    print("\n== (b) tool calling")
    rows = []
    for m in models:
        md = meta.get(m, {})
        r = try_tools(key, m)
        rows.append(r)
        tag = "TEE" if md.get("verifiable") or md.get("attestationSupported") else "---"
        if "error" in r:
            print("  %s %-40s HTTP %s %.1fs  %s" % (tag, m, r["http"], r["latency_s"], r["error"]))
        else:
            print("  %s %-40s %.1fs tool_calls=%d ok=%s finish=%s usage=%s%s" % (
                tag, m, r["latency_s"], r["tool_calls"], r["tool_calls_ok"], r["finish_reason"],
                json.dumps(r["usage"]), "" if r["tool_calls"] else "  content=%r" % r.get("content")))

    if "--no-proof" in argv:
        return 0
    print("\n== (c) attestation proof")
    done = [r for r in rows if r.get("chat_id")]
    if not done:
        print("  no successful call to prove")
        return 1
    r = done[0]
    time.sleep(1.0)  # signature is stored asynchronously after the response
    p = attest.proof(r["model"], r["chat_id"], r["req"], r["resp"])
    print("  model=%s chat_id=%s signer=%s verdict=%s" % (p["model"], p["chat_id"],
                                                         p["signing_address"], p["verdict"]))
    for c in p["checks"]:
        print("    %-8s %-20s %-30s %s" % (c["status"], c["name"], c.get("scope", ""), c["detail"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
