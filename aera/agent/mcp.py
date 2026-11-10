"""The tool registry, spoken as MCP.

One surface for any MCP client, AWS AgentCore Gateway among them. None needs a
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
from typing import Any, Dict, Tuple

from core import registry
from core.provenance import Origin

PROTOCOL_VERSION = "2024-11-05"
SERVER = {"name": "aera", "version": "1.0.0"}


def _as_mcp_tool(t) -> dict:
    """Our schema is Anthropic-shaped. MCP spells one key differently.

    The annotations are the part that matters to a caller it did not write.
    Fifty-one tools arrive in one list and nine of them raise an action; a
    client with no way to tell them apart has to treat all of them as
    dangerous, or none. readOnlyHint says which is which, and destructiveHint
    stays false throughout because nothing here deletes or overwrites: a
    write raises a draft that a person still has to approve in AERA.
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
            "openWorldHint": t.owner in ("logistics", "precedent"),
        },
    }


#: What a caller may read as a document rather than by calling a tool. Each is
#: the record AERA already keeps, exposed in the shape MCP asks for.
RESOURCES = [
    {"uri": "aera://rules/pack",
     "name": "Rule pack",
     "description": "The rules Kira rules from, each with its source and whether "
                    "anybody verified it. Read this before trusting a ruling.",
     "mimeType": "application/json"},
    {"uri": "aera://agents",
     "name": "Agent roster",
     "description": "The twelve agents, what each owns, and which tools each holds.",
     "mimeType": "application/json"},
    {"uri": "aera://handlings/recent",
     "name": "Recent handlings",
     "description": "The last disruptions handled, with their status and what each "
                    "still owes a person.",
     "mimeType": "application/json"},
]

#: The same three entry points the A2A agent card offers, so a client reaching
#: AERA over MCP is not handed a worse front door than one reaching it over
#: A2A. Prompts, not tools: they compose the tools rather than replace them.
PROMPTS = [
    {"name": "investigate_disruption",
     "description": "Raise a supply disruption with the agent team and follow it through.",
     "arguments": [{"name": "event", "description": "what happened, in a sentence",
                    "required": True}]},
    {"name": "assess_option",
     "description": "Rule one replacement option against local content, import law and "
                    "landed cost, and say plainly whether it clears.",
     "arguments": [{"name": "option_id", "description": "the option id as it was listed",
                    "required": True}]},
    {"name": "disruption_status",
     "description": "Read one handling: status, which agents worked on it, the "
                    "recommendation, and what still waits on a person.",
     "arguments": [{"name": "run_id", "description": "the run id, e.g. run_1a2b3c4d5e6f",
                    "required": True}]},
    {"name": "scan_risk",
     "description": "Vega's exposure scan: single sources, concentrated lanes, cover "
                    "below policy, and the orders most likely to slip.",
     "arguments": []},
]

_PROMPT_TEXT = {
    "investigate_disruption":
        "A supply disruption has been reported: {event}\n\n"
        "Investigate it with the AERA tools. Establish which materials and orders are "
        "affected, what cover remains, and what the options cost once landed. Rule every "
        "option against local content and import law before comparing prices. State what "
        "you could NOT establish as plainly as what you could, and do not offer a figure "
        "whose origin is missing.",
    "assess_option":
        "Rule option {option_id} using check_local_constraints. Report whether it clears, "
        "the rules it was judged against, and whether each of those rules is verified or "
        "an assumption. If it does not clear, say which rule stopped it.",
    "disruption_status":
        "Read handling {run_id} and report it: its status, which agents worked on it, "
        "the recommendation and the reasoning behind it, what is still waiting for a "
        "person, and which of its figures are modelled or missing rather than live. "
        "Do not approve anything; approval happens on AERA web, by a signed-in person.",
    "scan_risk":
        "Run scan_supply_exposure. Report the concentrations, with the value behind "
        "each. Say which figures are modelled rather than live.",
}


def _text(payload: Any) -> str:
    return payload if isinstance(payload, str) else json.dumps(
        payload, ensure_ascii=False, default=str, indent=1)


def _resource(uri: str) -> Any:
    """One resource, read live. None when the uri is not one of ours.

    These read the same record the tools read, so a caller cannot get a
    different answer by asking a different way - which is the whole reason to
    offer them as resources rather than as a second set of tools.
    """
    if uri == "aera://rules/pack":
        from tools.compliance import pack_status
        return pack_status()
    if uri == "aera://agents":
        from agents.definitions import ALL
        return [{"code": a.code, "name": a.nickname, "title": a.title,
                 "owns": a.brief, "tools": list(a.tools)} for a in ALL.values()]
    if uri == "aera://handlings/recent":
        from core import store
        from engine import triage
        with store.connect() as c:
            rows = [dict(r) for r in c.execute(
                "SELECT r.id, r.status, r.started_at, e.title, e.kind"
                " FROM runs r JOIN events e ON e.id = r.event_id"
                " ORDER BY r.started_at DESC LIMIT 20").fetchall()]
        out = []
        for r in rows:
            run = store.get_run(r["id"])
            v = triage.verdict(triage.facts_from_run(run)) if run else None
            out.append({**r, "verdict": v.state if v else None,
                        "asks": v.headline if v else None})
        return out
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
        return ok({"tools": [_as_mcp_tool(t) for t in registry.all_tools().values()]})

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
        return ok({"prompts": PROMPTS})

    if method == "prompts/get":
        name = params.get("name") or ""
        if name not in _PROMPT_TEXT:
            return fail(-32602, f"unknown prompt: {name}")
        args = params.get("arguments") or {}
        spec = next(p for p in PROMPTS if p["name"] == name)
        missing = [a["name"] for a in spec["arguments"]
                   if a.get("required") and not args.get(a["name"])]
        if missing:
            return fail(-32602, f"{name} needs: {', '.join(missing)}")
        try:
            text = _PROMPT_TEXT[name].format(**args)
        except KeyError as e:
            return fail(-32602, f"{name} has no argument {e}")
        return ok({
            "description": spec["description"],
            "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
        })

    if method == "tools/call":
        name = params.get("name") or ""
        arguments = params.get("arguments") or {}
        # Resolved before running, not by catching KeyError. A tool that raises
        # KeyError itself is a broken tool, not a missing one, and conflating
        # the two reported a live field mismatch as "unknown tool".
        if name not in registry.all_tools():
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

    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "aera"

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

    # A registered tool that throws must never be reported as a missing one.
    for t in listed:
        r = handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                    "params": {"name": t["name"], "arguments": {}}})
        assert "error" not in r, \
            f"{t['name']} is registered but came back as {r['error']}"

    unknown = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                      "params": {"name": "no_such_tool", "arguments": {}}})
    assert unknown["error"]["code"] == -32602
    assert handle({"jsonrpc": "2.0", "id": 5, "method": "nonsense"})["error"]["code"] == -32601
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) == {}
    print("  unknown tool and unknown method both refused ✓")
    # --- a caller must be able to tell a read from a write -----------------
    # Fifty-one tools arrive in one list and nine of them raise an action. A
    # client with no way to tell them apart has to treat all of them as
    # dangerous or none, and both of those are wrong.
    tools_out = handle({"jsonrpc": "2.0", "id": 10, "method": "tools/list"})["result"]["tools"]
    assert all("annotations" in t for t in tools_out), "every tool carries annotations"
    writers = [t["name"] for t in tools_out if not t["annotations"]["readOnlyHint"]]
    assert writers, "the execution tools must be marked"
    assert "create_draft_po" in writers and "get_material_stock" not in writers, writers
    assert all(t["annotations"]["destructiveHint"] is False for t in tools_out), \
        "nothing here deletes: a write raises a draft a person still approves"

    # --- the same front door over MCP as over A2A --------------------------
    caps = handle({"jsonrpc": "2.0", "id": 11, "method": "initialize",
                   "params": {}})["result"]["capabilities"]
    assert "resources" in caps and "prompts" in caps, caps

    res = handle({"jsonrpc": "2.0", "id": 12, "method": "resources/list"})["result"]["resources"]
    assert {r["uri"] for r in res} >= {"aera://rules/pack", "aera://agents"}, res
    pack = handle({"jsonrpc": "2.0", "id": 13, "method": "resources/read",
                   "params": {"uri": "aera://rules/pack"}})["result"]
    assert pack["contents"][0]["uri"] == "aera://rules/pack"
    assert "verified" in pack["contents"][0]["text"], "a pack read states its trust"
    gone = handle({"jsonrpc": "2.0", "id": 14, "method": "resources/read",
                   "params": {"uri": "aera://nope"}})
    assert gone["error"]["code"] == -32602, gone

    prompts = handle({"jsonrpc": "2.0", "id": 15, "method": "prompts/list"})["result"]["prompts"]
    assert {p["name"] for p in prompts} == set(_PROMPT_TEXT), prompts
    # The two front doors offer the same four entry points. A client reaching
    # AERA over MCP must not be handed a worse door than one reaching it over
    # A2A, which is the claim the architecture makes out loud.
    assert {p["name"] for p in prompts} == {
        "investigate_disruption", "disruption_status", "assess_option", "scan_risk"}, prompts
    got = handle({"jsonrpc": "2.0", "id": 16, "method": "prompts/get",
                  "params": {"name": "assess_option",
                             "arguments": {"option_id": "E"}}})["result"]
    assert "option E" in got["messages"][0]["content"]["text"], got
    # A required argument left out is refused rather than formatted into a
    # prompt that quietly asks about nothing.
    bare = handle({"jsonrpc": "2.0", "id": 17, "method": "prompts/get",
                   "params": {"name": "assess_option"}})
    assert bare["error"]["code"] == -32602 and "option_id" in bare["error"]["message"], bare
    print("  reads and writes are told apart, and resources and prompts answer ✓")

    print("mcp ok")


if __name__ == "__main__":
    demo()
