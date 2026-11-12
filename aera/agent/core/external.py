"""Writes on servers AERA does not operate, end to end (the guarded write path).

The path, in one place so it can be read and tested as a whole:

  1. An owner allows one write tool on one connected MCP server (POST /mcp/servers/{id}/write).
     Nothing else is offered to agents as a writer; a server that says nothing about a tool is
     treated as a writer and stays off.
  2. An agent granted that server sees the tool, told plainly that calling it changes nothing yet.
  3. Its call becomes an `external_write` action (core/registry._run_remote). The Guardian checks
     the arguments like any outgoing text and always asks a person; if the run has read anything
     from outside AERA, that is said too (untrusted_input).
  4. A person approves; settle._external performs the call, after checking again that the server
     and the tool are still allowed. The result is recorded on the action.

Reads stay as they were: a remote read is data, labelled with its server, and marks the run as
having read outside text.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List


def _fake_server(calls: List[Dict[str, Any]]):
    """A local MCP server with one reader and one writer, for the self-check."""

    class Fake(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):                                                # noqa: N802
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            m = req.get("method")
            if m and m.startswith("notifications/"):
                self.send_response(202)
                self.end_headers()
                return
            if m == "initialize":
                out: Dict[str, Any] = {"serverInfo": {"name": "sheets", "version": "1"}, "capabilities": {"tools": {}}}
            elif m == "tools/list":
                out = {"tools": [
                    {"name": "read_rows", "description": "Read rows of a sheet.", "annotations": {"readOnlyHint": True},
                     "inputSchema": {"type": "object", "properties": {"sheet": {"type": "string"}}, "required": ["sheet"]}},
                    {"name": "append_row", "description": "Append a row to a sheet.", "annotations": {"readOnlyHint": False},
                     "inputSchema": {"type": "object", "properties": {"sheet": {"type": "string"}, "row": {"type": "string"}},
                                     "required": ["sheet", "row"]}},
                ]}
            elif m == "tools/call":
                params = req.get("params") or {}
                calls.append(params)
                text = "orders: ord_1 paid" if params.get("name") == "read_rows" else "appended row 7"
                out = {"content": [{"type": "text", "text": text}]}
            else:
                out = {}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": out}).encode())

    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def demo() -> None:
    from clients import mcp_client
    from core import business, guardian, registry, store
    import settle

    calls: List[Dict[str, Any]] = []
    srv = _fake_server(calls)
    url = f"http://127.0.0.1:{srv.server_address[1]}/mcp"
    try:
        store.save_profile(business.EXAMPLE, by="check")
        ok, _, tools = mcp_client.probe(url, None)
        assert ok and {t["name"]: t["read_only"] for t in tools} == {"read_rows": True, "append_row": False}
        row = store.add_mcp_server("sheets", url, None, "check", ["ops"])
        store.update_mcp_server(row["id"], tools=tools)
        registry.forget_remote()
        assert "mcp__sheets__append_row" not in registry.remote_tools(refresh=True), "a writer is off until allowed"

        for t in tools:
            if t["name"] == "append_row":
                t["write_allowed"] = True
        store.update_mcp_server(row["id"], tools=tools)
        registry.forget_remote()
        offered = registry.remote_tools(refresh=True)
        assert offered["mcp__sheets__append_row"]["write"] is True
        spec = next(s for s in registry.schemas_for_model("ops") if s["name"] == "mcp__sheets__append_row")
        assert "does not change anything yet" in spec["description"]

        rid = store.start_run(store.record_work_item("request", "log the order", "api", {}))
        with registry.bind_run(rid):
            res = registry.run("mcp__sheets__append_row", {"sheet": "Orders", "row": "ord_1, $15"})
            assert not calls, "calling a writer must not write"
            action = res.value
            assert action["kind"] == "external_write" and action["status"] == "pending", action
            # a read from the same server marks the run; money or writes after it need a person
            assert not registry.run_read_untrusted()
            registry.run("mcp__sheets__read_rows", {"sheet": "Orders"})
            assert registry.run_read_untrusted() and calls[-1]["name"] == "read_rows"
            v = guardian.check_action("payment", {"amount_usd": 1, "to": "x"}, record=False)
            assert any(r["rule"] == "untrusted_input" for r in v["reasons"]), v

        store.decide_action(action["id"], "owner@check", "owner", "approved")
        out = settle.execute(action["id"])
        assert out["ok"] and calls[-1] == {"name": "append_row", "arguments": {"sheet": "Orders", "row": "ord_1, $15"}}, (out, calls)
        assert store.get_action(action["id"])["status"] == "sent"

        # withdrawn permission: an approved write that is no longer allowed is not performed
        with registry.bind_run(rid):
            again = registry.run("mcp__sheets__append_row", {"sheet": "Orders", "row": "ord_2, $5"}).value
        store.decide_action(again["id"], "owner@check", "owner", "approved")
        for t in tools:
            t["write_allowed"] = False
        store.update_mcp_server(row["id"], tools=tools)
        before = len(calls)
        assert not settle.execute(again["id"])["ok"] and len(calls) == before
    finally:
        srv.shutdown()
        registry.forget_remote()
    print("external ok: writers off until allowed ✓ · a call raises an action, writes nothing ✓ · "
          "approved → performed ✓ · permission withdrawn → not performed ✓ · outside reads taint the run ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_EXTERNAL_CHECK")
    demo()
