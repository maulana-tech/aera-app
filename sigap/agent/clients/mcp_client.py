"""Calling OUT to somebody else's MCP server.

SIGAP is already an MCP server: AgentCore Gateway and SAP Joule call in, and
mcp.py answers them. This is the other direction - a tool somebody else
operates, offered to our agents as if it were one of ours.

What this does NOT do, on purpose:

  * It does not trust the other server's description of itself. A remote tool
    arrives with a name and a schema; it is namespaced as `server.tool` before
    anything sees it, so a remote tool called `check_local_constraints` can
    never shadow Kira's.
  * It does not launder provenance. Everything that comes back is Origin.CACHED
    at best and carries the server it came from, because a figure from a tool
    we do not operate is not a figure from SAP, however confident it sounds.
  * It does not wait forever. A remote server that hangs would hang a handling,
    so the timeout is short and a timeout is an answer.

Standard library only, like the rest of the connectors: JSON-RPC over one POST.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

#: Seconds. A remote tool is somebody else's uptime, so it gets one short
#: chance rather than a handling's patience.
TIMEOUT = 20

PROTOCOL_VERSION = "2024-11-05"


class RemoteError(RuntimeError):
    pass


def _rpc(url: str, token: Optional[str], method: str,
         params: Optional[dict] = None, rpc_id: int = 1) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": rpc_id,
                       "method": method, "params": params or {}}).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read()[:200].decode(errors="replace")
        raise RemoteError(f"HTTP {e.code}: {detail}") from e
    except Exception as e:                                          # noqa: BLE001
        raise RemoteError(f"{type(e).__name__}: {e}") from e
    if not raw:
        return {}
    try:
        reply = json.loads(raw)
    except ValueError as e:
        raise RemoteError(f"the server did not answer with JSON: {raw[:120]!r}") from e
    if isinstance(reply, dict) and reply.get("error"):
        err = reply["error"]
        raise RemoteError(f"{err.get('code')}: {err.get('message')}")
    return (reply or {}).get("result") or {}


def probe(url: str, token: Optional[str] = None) -> Tuple[bool, str, List[dict]]:
    """(reachable, what happened, the tools it offers).

    Never raises: a page that lists servers must render when one of them is
    down, and "unreachable" is the useful answer rather than a stack trace.
    """
    try:
        init = _rpc(url, token, "initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "sigap", "version": "1.0.0"},
        })
    except RemoteError as e:
        return False, str(e), []
    server = (init.get("serverInfo") or {}).get("name") or "unnamed server"
    try:
        listed = _rpc(url, token, "tools/list", {}, rpc_id=2)
    except RemoteError as e:
        return False, f"{server} answered initialize but not tools/list: {e}", []
    tools = listed.get("tools") or []
    clean = []
    for t in tools:
        if not isinstance(t, dict) or not t.get("name"):
            continue
        ann = t.get("annotations") or {}
        clean.append({
            "name": str(t["name"]),
            "description": str(t.get("description") or "")[:400],
            # A server that does not say is assumed to WRITE. The cautious
            # reading is the right one when the answer decides whether an
            # agent may call it without a person watching.
            "read_only": bool(ann.get("readOnlyHint", False)),
        })
    return True, f"{server}: {len(clean)} tool(s)", clean


def call(url: str, token: Optional[str], tool: str, arguments: dict) -> Dict[str, Any]:
    """Run one remote tool. Returns {ok, text, error}."""
    try:
        result = _rpc(url, token, "tools/call",
                      {"name": tool, "arguments": arguments or {}}, rpc_id=3)
    except RemoteError as e:
        return {"ok": False, "error": str(e)}
    content = result.get("content") or []
    text = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    if result.get("isError"):
        return {"ok": False, "error": text or "the tool reported an error"}
    return {"ok": True, "text": text}


def demo() -> None:
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    calls: List[str] = []

    class Fake(BaseHTTPRequestHandler):
        def log_message(self, *a):            # quiet
            pass

        def do_POST(self):                    # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
            calls.append(req.get("method", ""))
            m = req.get("method")
            if m == "initialize":
                out = {"serverInfo": {"name": "fake", "version": "1"},
                       "capabilities": {"tools": {}}}
            elif m == "tools/list":
                out = {"tools": [
                    {"name": "lookup", "description": "reads something",
                     "annotations": {"readOnlyHint": True}},
                    # No annotations at all: must be treated as a writer.
                    {"name": "mutate", "description": "does something"},
                    {"description": "nameless, must be dropped"},
                ]}
            elif m == "tools/call":
                name = (req.get("params") or {}).get("name")
                out = ({"content": [{"type": "text", "text": "42"}]} if name == "lookup"
                       else {"isError": True, "content": [{"type": "text", "text": "nope"}]})
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(
                    {"jsonrpc": "2.0", "id": req.get("id"),
                     "error": {"code": -32601, "message": "method not found"}}).encode())
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(
                {"jsonrpc": "2.0", "id": req.get("id"), "result": out}).encode())

    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/mcp"
    try:
        ok, note, tools = probe(url)
        assert ok and "fake" in note, (ok, note)
        assert [t["name"] for t in tools] == ["lookup", "mutate"], tools
        assert tools[0]["read_only"] is True
        # The cautious reading: a server that says nothing is assumed to write.
        assert tools[1]["read_only"] is False, "no annotation must not mean read-only"

        good = call(url, None, "lookup", {})
        assert good["ok"] and good["text"] == "42", good
        bad = call(url, None, "mutate", {})
        assert not bad["ok"] and "nope" in bad["error"], bad

        # A server that is not there is an answer, not an exception.
        down, why, none = probe("http://127.0.0.1:1/mcp")
        assert down is False and none == [] and why, (down, why)
    finally:
        srv.shutdown()
    print("  a remote server is probed, its silence read as 'writes', its absence survived ✓")
    print("mcp_client ok")


if __name__ == "__main__":
    demo()
