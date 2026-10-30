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

PROTOCOL_VERSION = "2025-06-18"

#: What the spec calls streamable HTTP has two legal ways to answer one POST:
#: a JSON body, or an SSE stream carrying the same JSON in a `data:` line.
#: Both are in use - AWS Knowledge answers JSON, DeepWiki and Context7 answer
#: SSE - so a client that reads only JSON can reach about half of what is out
#: there and calls the other half broken.
ACCEPT = "application/json, text/event-stream"


def sanitize_schema(raw: Any) -> Dict[str, Any]:
    """A remote tool's input schema in the shape our registry guarantees.

    Every schema this project hands a model is an object with
    additionalProperties false, and graph's self-check asserts it on every
    tool every agent can see. A remote server promises nothing of the kind, so
    the envelope is rebuilt here rather than trusted: the property definitions
    are the other server's business, the envelope is ours.
    """
    props = raw.get("properties") if isinstance(raw, dict) else None
    if not isinstance(props, dict):
        props = {}
    asked = raw.get("required") if isinstance(raw, dict) else None
    required = ([k for k in asked if isinstance(k, str) and k in props]
                if isinstance(asked, list) else [])
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}


class RemoteError(RuntimeError):
    pass


def _parse(raw: bytes, content_type: str) -> Optional[dict]:
    """One JSON-RPC message out of either answer shape, or None for no body."""
    body = raw.strip()
    if not body:
        return None                      # 202 to a notification: nothing to read
    sse = ("text/event-stream" in content_type.lower()
           or body.startswith(b"event:") or body.startswith(b"data:"))
    if not sse:
        try:
            return json.loads(body)
        except ValueError as e:
            raise RemoteError(f"the server did not answer with JSON: {body[:120]!r}") from e
    for line in body.decode(errors="replace").splitlines():
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if not chunk:
            continue
        try:
            msg = json.loads(chunk)
        except ValueError:
            continue                     # a keep-alive or a partial frame
        if isinstance(msg, dict) and ("result" in msg or "error" in msg):
            return msg
    raise RemoteError(f"the stream carried no answer: {body[:120]!r}")


class _Session:
    """One conversation with a remote server.

    A stateful server hands back an `Mcp-Session-Id` on initialize and refuses
    every later request that does not carry it, so the handshake and the call
    cannot be two unrelated POSTs. A stateless server ignores all of this, and
    the same code serves both.
    """

    def __init__(self, url: str, token: Optional[str]) -> None:
        self.url, self.token, self.sid = url, token, None
        self.server = "unnamed server"
        self._id = 0

    def _post(self, payload: dict) -> Optional[dict]:
        headers = {"Content-Type": "application/json", "Accept": ACCEPT,
                   "MCP-Protocol-Version": PROTOCOL_VERSION}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.sid:
            headers["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw, info = r.read(), r.info()
        except urllib.error.HTTPError as e:
            detail = e.read()[:200].decode(errors="replace").strip()
            hint = " - this server wants OAuth, which SIGAP cannot do" if e.code == 401 else ""
            raise RemoteError(f"HTTP {e.code}: {detail}{hint}") from e
        except Exception as e:                                      # noqa: BLE001
            raise RemoteError(f"{type(e).__name__}: {e}") from e
        self.sid = info.get("Mcp-Session-Id") or self.sid
        reply = _parse(raw, info.get("Content-Type") or "")
        if reply and reply.get("error"):
            err = reply["error"]
            raise RemoteError(f"{err.get('code')}: {err.get('message')}")
        return (reply or {}).get("result") or {}

    def rpc(self, method: str, params: Optional[dict] = None) -> dict:
        self._id += 1
        return self._post({"jsonrpc": "2.0", "id": self._id,
                           "method": method, "params": params or {}}) or {}

    def notify(self, method: str) -> None:
        """A notification has no id and is owed no answer; failure is ignored."""
        try:
            self._post({"jsonrpc": "2.0", "method": method, "params": {}})
        except RemoteError:
            pass


def _open(url: str, token: Optional[str]) -> _Session:
    """Handshake, so the session carries whatever the server needs it to."""
    s = _Session(url, token)
    init = s.rpc("initialize", {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "sigap", "version": "1.0.0"},
    })
    s.server = (init.get("serverInfo") or {}).get("name") or "unnamed server"
    # Required by the spec before any request. A server that enforces it
    # rejects tools/list outright without this.
    s.notify("notifications/initialized")
    return s


def probe(url: str, token: Optional[str] = None) -> Tuple[bool, str, List[dict]]:
    """(reachable, what happened, the tools it offers).

    Never raises: a page that lists servers must render when one of them is
    down, and "unreachable" is the useful answer rather than a stack trace.
    """
    try:
        session = _open(url, token)
    except RemoteError as e:
        return False, str(e), []
    try:
        listed = session.rpc("tools/list")
    except RemoteError as e:
        return False, f"{session.server} answered initialize but not tools/list: {e}", []
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
            # Kept, because an agent cannot be offered a tool whose arguments
            # nobody can describe. A server that sends no usable schema is
            # left with an empty one and the registry drops it.
            "schema": sanitize_schema(t.get("inputSchema")),
        })
    return True, f"{session.server}: {len(clean)} tool(s)", clean


def call(url: str, token: Optional[str], tool: str, arguments: dict) -> Dict[str, Any]:
    """Run one remote tool. Returns {ok, text, error}."""
    try:
        result = _open(url, token).rpc("tools/call",
                                       {"name": tool, "arguments": arguments or {}})
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
                     "annotations": {"readOnlyHint": True},
                     "inputSchema": {"type": "object",
                                     "properties": {"q": {"type": "string"}},
                                     "required": ["q", "ghost"]}},
                    # No annotations at all: must be treated as a writer.
                    {"name": "mutate", "description": "does something"},
                    # A schema that is not one: the envelope must still be sound.
                    {"name": "vague", "description": "says nothing useful",
                     "annotations": {"readOnlyHint": True},
                     "inputSchema": "not a schema"},
                    {"description": "nameless, must be dropped"},
                ]}
            elif m == "tools/call":
                name = (req.get("params") or {}).get("name")
                out = ({"content": [{"type": "text", "text": "42"}]} if name == "lookup"
                       else {"isError": True, "content": [{"type": "text", "text": "nope"}]})
            elif m and m.startswith("notifications/"):
                # A notification is owed no body, only an acknowledgement.
                self.send_response(202)
                self.end_headers()
                return
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

    class Streamed(Fake):
        """The same server, answering in SSE frames. Both shapes are legal and
        both are in use, so both are tested."""

        def do_POST(self):                # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
            m = req.get("method")
            if m and m.startswith("notifications/"):
                self.send_response(202)
                self.end_headers()
                return
            out = ({"serverInfo": {"name": "streamer", "version": "1"}} if m == "initialize"
                   else {"tools": [{"name": "peek", "description": "reads",
                                    "annotations": {"readOnlyHint": True},
                                    "inputSchema": {"type": "object", "properties": {}}}]}
                   if m == "tools/list"
                   else {"content": [{"type": "text", "text": "streamed 7"}]})
            body = json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": out})
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(f": keep-alive\n\nevent: message\ndata: {body}\n\n".encode())

    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/mcp"
    try:
        ok, note, tools = probe(url)
        assert ok and "fake" in note, (ok, note)
        assert [t["name"] for t in tools] == ["lookup", "mutate", "vague"], tools
        assert tools[0]["read_only"] is True

        # The envelope is ours on every tool, however the server wrote it.
        for t in tools:
            assert t["schema"]["type"] == "object", t
            assert t["schema"]["additionalProperties"] is False, t
        # The server's own properties survive; a required key it never defined
        # does not, because a model cannot be asked for a field that is not in
        # the schema it was shown.
        assert tools[0]["schema"]["properties"] == {"q": {"type": "string"}}
        assert tools[0]["schema"]["required"] == ["q"], tools[0]["schema"]
        assert tools[2]["schema"]["properties"] == {}, tools[2]
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

    # The same exchange, answered in SSE frames instead of a JSON body.
    sse = HTTPServer(("127.0.0.1", 0), Streamed)
    threading.Thread(target=sse.serve_forever, daemon=True).start()
    sse_url = f"http://127.0.0.1:{sse.server_address[1]}/mcp"
    try:
        ok, note, tools = probe(sse_url)
        assert ok and "streamer" in note, (ok, note)
        assert [t["name"] for t in tools] == ["peek"], tools
        got = call(sse_url, None, "peek", {})
        assert got["ok"] and got["text"] == "streamed 7", got
    finally:
        sse.shutdown()
    print("  a remote server is probed, its silence read as 'writes', its absence survived ✓")
    print("  the same server answering in SSE frames reads the same ✓")
    print("mcp_client ok")


if __name__ == "__main__":
    demo()
