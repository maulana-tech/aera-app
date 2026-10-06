"""The tool registry, spoken as MCP.

One surface, two consumers. AWS AgentCore Gateway wants our tools as MCP, and
so does SAP Joule, which registers an MCP server by namespace and path in
`da.sapdas.yaml`. Neither needs a second registry: `core/registry.py` already
holds every tool and already runs them, so this is a translation layer and
nothing more.

What it must not lose on the way across is the origin label. A tool result
carries where its value came from, and a figure that arrives in Joule without
that label is exactly the kind of confident unlabelled number this product
exists to refuse. So every reply states it, and a MISSING origin is returned
as an MCP error rather than as a value someone might read as real.

# ponytail: JSON-RPC over plain POST, no SSE. Joule discovers and calls; it
#           does not need the server to push, so streaming is not written.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from core import registry
from core.provenance import Origin

PROTOCOL_VERSION = "2024-11-05"
SERVER = {"name": "sigap", "version": "1.0.0"}


def _as_mcp_tool(t) -> dict:
    """Our schema is Anthropic-shaped. MCP spells one key differently."""
    return {
        "name": t.name,
        "description": t.description,
        "inputSchema": t.schema,
    }


def _text(payload: Any) -> str:
    return payload if isinstance(payload, str) else json.dumps(
        payload, ensure_ascii=False, default=str, indent=1)


def handle(req: dict) -> Dict[str, Any]:
    """One JSON-RPC request in, one response out. Notifications return {}."""
    method = req.get("method", "")
    rpc_id = req.get("id")
    params = req.get("params") or {}

    def ok(result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": rpc_id, "result": result}

    def fail(code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok({
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER,
        })

    # A notification has no id and expects no reply.
    if method.startswith("notifications/"):
        return {}

    if method == "ping":
        return ok({})

    if method == "tools/list":
        return ok({"tools": [_as_mcp_tool(t) for t in registry.all_tools().values()]})

    if method == "tools/call":
        name = params.get("name") or ""
        arguments = params.get("arguments") or {}
        try:
            result = registry.run(name, arguments)
        except KeyError:
            return fail(-32602, f"unknown tool: {name}")
        except Exception as e:                                       # noqa: BLE001
            # A tool that threw has no Result, so it has no origin either. Say
            # that, in the same shape as every other reply, so a caller never
            # has to guess whether it is holding JSON or prose.
            return ok({
                "isError": True,
                "content": [{"type": "text", "text": _text({
                    "unavailable": True,
                    "tool": name,
                    "reason": f"{type(e).__name__}: {e}",
                })}],
            })

        label = result.brief()
        if result.origin is Origin.MISSING:
            # Returned as an error on purpose. A caller that ignores the label
            # must still not be handed something that reads like an answer.
            return ok({
                "isError": True,
                "content": [{"type": "text", "text": _text({
                    "unavailable": True,
                    "tool": name,
                    "provenance": label,
                })}],
            })

        return ok({
            "content": [{"type": "text", "text": _text({
                "value": result.value,
                "provenance": label,
                "trusted": result.trusted,
            })}],
        })

    return fail(-32601, f"method not found: {method}")


def demo() -> None:
    import tools  # noqa: F401  (registers every tool)

    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "sigap"

    listed = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert len(listed) == len(registry.all_tools()) > 0
    assert all({"name", "description", "inputSchema"} <= set(t) for t in listed), \
        "MCP spells it inputSchema, not input_schema"
    print(f"  tools/list: {len(listed)} tools, MCP-shaped ✓")

    # Every tool, called with no arguments. Whatever comes back, it must be
    # JSON and it must say either where the value came from or why there is none.
    labelled = 0
    for t in listed:
        r = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": t["name"], "arguments": {}}})["result"]
        body = json.loads(r["content"][0]["text"])       # never prose
        if r.get("isError"):
            assert body["unavailable"] is True and ("reason" in body or "provenance" in body)
        else:
            assert "provenance" in body, \
                f"{t['name']} returned a value with no origin, which is the thing we refuse"
            assert body["provenance"]["origin"] in {o.value for o in Origin}
            labelled += 1
    print(f"  tools/call: {len(listed)} tools exercised, {labelled} returned a labelled value ✓")

    unknown = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                      "params": {"name": "no_such_tool", "arguments": {}}})
    assert unknown["error"]["code"] == -32602
    assert handle({"jsonrpc": "2.0", "id": 5, "method": "nonsense"})["error"]["code"] == -32601
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) == {}
    print("  unknown tool and unknown method both refused ✓")
    print("mcp ok")


if __name__ == "__main__":
    demo()
