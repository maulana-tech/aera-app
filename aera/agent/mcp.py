"""The tool registry, spoken as MCP.

One surface for any MCP client: another agent, an IDE, a gateway. None needs a
second registry: `core/registry.py` already
holds every tool and already runs them, so this is a translation layer and
nothing more.

What it must not lose on the way across is the origin label. A tool result
carries where its value came from, and a figure that arrives in a client without
that label is exactly the kind of confident unlabelled number this product
exists to refuse. So every reply states it, and a MISSING origin is returned
as an MCP error rather than as a value someone might read as real.

# ponytail: JSON-RPC over plain POST, no SSE. A client discovers and calls; it
#           does not need the server to push, so streaming is not written.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from core import registry
from core.provenance import Origin

PROTOCOL_VERSION = "2024-11-05"
SERVER = {"name": "aera", "version": "1.0.0"}


def _as_mcp_tool(t) -> dict:
    """Our schema is Anthropic-shaped. MCP spells one key differently.

    The annotations are the part that matters to a caller it did not write.
    Only read-only tools are offered (see exposed()), so readOnlyHint is
    always true; it is stated anyway for clients that check.
    """
    return {
        "name": t.name,
        "description": t.description,
        "inputSchema": t.schema,
        "annotations": {
            "title": t.name.replace("_", " "),
            "readOnlyHint": not t.writes,
            "destructiveHint": False,
            # A read is idempotent; raising an action is too, because the
            # idempotency key collapses a repeat into the same action.
            "idempotentHint": True,
            "openWorldHint": t.owner == "research",
        },
    }


def exposed() -> Dict[str, Any]:
    """The tools offered over MCP: READ-ONLY ones only, and never a locked
    capability. A client of ours can read what the team can read; it can never
    raise a payment, a message or a delivery through this door - those happen
    inside a handling, under the guardian, or not at all."""
    return {n: t for n, t in registry.all_tools().items()
            if not t.writes and t.owner not in ("treasury", "guardian", "supervisor")}


RESOURCES = [
    {"uri": "aera://business/profile", "name": "Business profile",
     "description": "What the business sells, its limits, forbidden actions and sensitive data.",
     "mimeType": "application/json"},
    {"uri": "aera://agents", "name": "Agent team",
     "description": "The team composed for this business: each agent, its brief and capabilities.",
     "mimeType": "application/json"},
    {"uri": "aera://work/recent", "name": "Recent work",
     "description": "The last work items handled, with status and what still waits for a person.",
     "mimeType": "application/json"},
    {"uri": "aera://ledger", "name": "Public ledger",
     "description": "Money in and out, model spend, guardian blocks and TEE proofs (30 days).",
     "mimeType": "application/json"},
]


def _prompts():
    from core import skills
    return [s for s in skills.CATALOGUE if s.external]


def _prompt_list() -> list:
    return [{"name": s.name, "description": s.description,
             "arguments": [{"name": "context", "description": "what this is about", "required": False}]}
            for s in _prompts()]


def _prompt_text(name: str, context: str) -> str:
    s = next(x for x in _prompts() if x.name == name)
    steps = "\n".join(f"{i}. {st}" for i, st in enumerate(s.steps, 1))
    return (f"{s.title}{': ' + context if context else ''}\n\n{s.description}\n\nSteps:\n{steps}\n\n"
            "Every value AERA returns carries its origin; do not present a missing one as real.")


def _text(payload: Any) -> str:
    return payload if isinstance(payload, str) else json.dumps(
        payload, ensure_ascii=False, default=str, indent=1)


def _resource(uri: str) -> Any:
    from core import business, store
    if uri == "aera://business/profile":
        return {k: v for k, v in business.current().items() if not k.startswith("_")}
    if uri == "aera://agents":
        from agents import roster
        return [{"code": a.code, "name": a.nickname, "title": a.title, "brief": a.brief,
                 "capabilities": a.capabilities, "veto": a.veto} for a in roster.load().values()]
    if uri == "aera://work/recent":
        return [{k: r.get(k) for k in ("id", "title", "kind", "status", "started_at", "action_count", "attested",
                                       "proofs")} for r in store.list_runs(20)]
    if uri == "aera://ledger":
        return store.ledger(30)
    return None


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
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": SERVER,
        })

    # A notification has no id and expects no reply.
    if method.startswith("notifications/"):
        return {}

    if method == "ping":
        return ok({})

    if method == "tools/list":
        return ok({"tools": [_as_mcp_tool(t) for t in exposed().values()]})

    if method == "resources/list":
        return ok({"resources": RESOURCES})

    if method == "resources/read":
        uri = params.get("uri") or ""
        body = _resource(uri)
        if body is None:
            return fail(-32602, f"unknown resource: {uri}")
        return ok({"contents": [{"uri": uri, "mimeType": "application/json",
                                 "text": _text(body)}]})

    if method == "prompts/list":
        return ok({"prompts": _prompt_list()})

    if method == "prompts/get":
        name = params.get("name") or ""
        if name not in {x.name for x in _prompts()}:
            return fail(-32602, f"unknown prompt: {name}")
        args = params.get("arguments") or {}
        spec = next(p for p in _prompt_list() if p["name"] == name)
        return ok({
            "description": spec["description"],
            "messages": [{"role": "user", "content": {"type": "text",
                                                      "text": _prompt_text(name, str(args.get("context") or ""))}}],
        })

    if method == "tools/call":
        name = params.get("name") or ""
        arguments = params.get("arguments") or {}
        # Resolved before running, not by catching KeyError. A tool that raises
        # KeyError itself is a broken tool, not a missing one, and conflating
        # the two reported a live field mismatch as "unknown tool".
        if name not in exposed():
            return fail(-32602, f"unknown tool: {name}")
        try:
            result = registry.run(name, arguments)
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
    from core import business, store, team
    store.save_profile(business.EXAMPLE, by="check")
    team.apply(team.compose(), by="check")

    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "aera"
    listed = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    names = {t["name"] for t in listed}
    assert names and all(t["annotations"]["readOnlyHint"] for t in listed)
    for never in ("pay_vendor", "propose_refund", "freeze_payments", "deliver_order", "draft_message",
                  "check_action", "get_work_item", "write_document"):
        assert never not in names, f"{never} must not be reachable over MCP"
    refused = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                      "params": {"name": "pay_vendor", "arguments": {}}})
    assert refused["error"]["code"] == -32602, refused
    print(f"  tools/list: {len(listed)} read-only tools; money, messages and deliveries are not offered ✓")

    for t in listed:
        r = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                    "params": {"name": t["name"], "arguments": {}}})
        assert "error" not in r, (t["name"], r)
        body = json.loads(r["result"]["content"][0]["text"])
        assert body.get("unavailable") or body["provenance"]["origin"] in {o.value for o in Origin}
    print("  every exposed tool answers with a labelled value or a labelled absence ✓")

    for uri in ("aera://business/profile", "aera://agents", "aera://work/recent", "aera://ledger"):
        got = handle({"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {"uri": uri}})
        assert "result" in got, (uri, got)
    prompts = handle({"jsonrpc": "2.0", "id": 6, "method": "prompts/list"})["result"]["prompts"]
    assert {p["name"] for p in prompts} >= {"fulfil_order", "pay_for_something"}
    got = handle({"jsonrpc": "2.0", "id": 7, "method": "prompts/get",
                  "params": {"name": "fulfil_order", "arguments": {"context": "order ord_1"}}})["result"]
    assert "order ord_1" in got["messages"][0]["content"]["text"]
    assert handle({"jsonrpc": "2.0", "id": 8, "method": "nonsense"})["error"]["code"] == -32601
    print("mcp ok")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_MCP_CHECK")
    demo()
