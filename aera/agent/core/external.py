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
    apps_demo()


def apps_demo() -> None:
    """The same path for an app connected through Composio, with Composio itself stood in for."""
    import settle
    from clients import composio
    from core import registry, store
    calls: List[Dict[str, Any]] = []
    real = composio.execute
    composio.execute = lambda tool, args, account, version=None: calls.append({"tool": tool, "args": args, "account": account}) or {"ok": True, "tool": tool}
    try:
        schema = {"type": "object", "properties": {"channel": {"type": "string"}, "text": {"type": "string"}}, "required": ["channel"]}
        tools = [{"slug": "SLACK_LIST_CHANNELS", "name": "List channels", "description": "List channels.", "read_only": True,
                  "important": True, "version": "v1", "schema": schema, "enabled": True, "write_allowed": False},
                 {"slug": "SLACK_SEND_MESSAGE", "name": "Send message", "description": "Post a message.", "read_only": False,
                  "important": True, "version": "v1", "schema": schema, "enabled": True, "write_allowed": False}]
        store.save_app("slack", "Slack", None, "ca_check", tools, by="check")
        registry.forget_remote()
        assert not [n for n in registry.remote_tools() if n.startswith("app__")], "granted to nobody: offered to nobody"
        store.update_app("slack", agents=["sales"])
        registry.forget_remote()
        names = set(registry.remote_tools())
        assert "app__slack_list_channels" in names and "app__slack_send_message" not in names, names
        rid = store.start_run(store.record_work_item("request", "slack", "api", {}))
        with registry.bind_run(rid):
            got = registry.run("app__slack_list_channels", {"channel": "x"})
            assert got.value and calls[-1]["account"] == "ca_check" and registry.run_read_untrusted(), got
        # a writer, once allowed, raises an action and writes nothing until a person approves
        store.update_app("slack", tools=[{**t, "write_allowed": True} if not t["read_only"] else t for t in tools])
        registry.forget_remote()
        assert registry.may_call("sales", "app__slack_send_message") and not registry.may_call("writer", "app__slack_send_message")
        before = len(calls)
        with registry.bind_run(rid):
            act = registry.run("app__slack_send_message", {"channel": "#sales", "text": "hello"}).value
        assert act["kind"] == "external_write" and act["status"] == "pending" and len(calls) == before, act
        store.decide_action(act["id"], "owner@check", "owner", "approved")
        assert settle.execute(act["id"])["ok"] and calls[-1]["tool"] == "SLACK_SEND_MESSAGE"
        # permission withdrawn after approval: not performed
        with registry.bind_run(rid):
            again = registry.run("app__slack_send_message", {"channel": "#sales", "text": "again"}).value
        store.decide_action(again["id"], "owner@check", "owner", "approved")
        store.update_app("slack", enabled=False)
        before = len(calls)
        assert not settle.execute(again["id"])["ok"] and len(calls) == before
    finally:
        composio.execute = real
        registry.forget_remote()
    assert composio.clean_schema({"type": "object", "title": "x", "properties": {"a": {"type": "string", "examples": [1], "file_uploadable": True}},
                                  "required": ["a", "gone"]}) == {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    print("apps ok: offered only to granted agents ✓ · reads run and taint ✓ · writers off until allowed, then only an action ✓ "
          "· approved → performed ✓ · switched off → not performed ✓ · schemas trimmed ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_EXTERNAL_CHECK")
    demo()
