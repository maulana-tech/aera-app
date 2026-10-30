"""Tool registry: name → schema + function.

The schema here goes to the model verbatim as the tool definition. One source,
so what the model is shown and what actually runs can never drift apart.

The registry also carries which run the current call belongs to. A tool that
records an action has to say, because actions.run_id references runs(id) and
the id cannot ride along as an argument: the schema is shown to the model as
it stands and additionalProperties is false, so there is no spare parameter to
carry it.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional

from core.provenance import Result


@dataclass
class Tool:
    name: str
    owner: str                  # agent code
    description: str
    schema: Dict[str, Any]
    fn: Callable[..., Result]
    #: Whether calling it changes the record. Declared, not guessed from the
    #: name: a caller reaching this registry over MCP sees fifty-odd tools and
    #: has no other way to tell which three of them raise an action. Reading is
    #: the default because the overwhelming majority of these only read.
    writes: bool = False


_REGISTRY: Dict[str, Tool] = {}


def register(name: str, owner: str, description: str,
             properties: Optional[Dict[str, Any]] = None,
             required: Optional[List[str]] = None,
             writes: bool = False) -> Callable:
    def wrap(fn: Callable[..., Result]) -> Callable[..., Result]:
        _REGISTRY[name] = Tool(
            name=name, owner=owner, description=description, writes=writes,
            schema={
                "type": "object",
                "properties": properties or {},
                "required": required or [],
                "additionalProperties": False,
            },
            fn=fn,
        )
        return fn
    return wrap


def get(name: str) -> Tool:
    if name not in _REGISTRY:
        raise KeyError(f"tool '{name}' is not registered")
    return _REGISTRY[name]


#: An owner meaning "every agent". Almost nothing should be this: a tool every
#: specialist can reach is a tool no specialist is accountable for, and the
#: roster's one-owner rule is what keeps a handling's trail readable. It exists
#: for the few that are about how an agent works rather than what it knows.
SHARED = "*"


def owned_by(agent_code: str) -> List[Tool]:
    return [t for t in _REGISTRY.values()
            if t.owner == agent_code or t.owner == SHARED]


def shared_tools() -> List[Tool]:
    return [t for t in _REGISTRY.values() if t.owner == SHARED]


def schemas_for_model(agent_code: str) -> List[dict]:
    """The shape sent to Claude as the `tools` parameter.

    Our own tools first, then any remote tool granted to this agent, so a
    specialist's own instruments stay at the top of what it is shown.
    """
    specs = [
        {"name": t.name, "description": t.description, "input_schema": t.schema, "strict": True}
        for t in owned_by(agent_code)
    ]
    specs.extend(
        {"name": name, "description": _remote_description(r),
         "input_schema": r["schema"], "strict": True}
        for name, r in sorted(remote_tools().items())
        if agent_code in r["agents"]
    )
    return specs


def all_tools() -> Dict[str, Tool]:
    return dict(_REGISTRY)


# ------------------------------------------------- tools somebody else owns
#
# A remote MCP server is registered through /mcp/servers and its read-only
# tools are offered to the agents named on that server. Three limits hold, and
# each of them is a limit on authority rather than on plumbing:
#
#   * Read-only only. A tool that writes, or a server that did not say whether
#     its tool writes, is never offered. Something we do not operate must not
#     be able to change a record.
#   * Never re-exported. These stay out of all_tools(), so mcp.py does not
#     offer somebody else's tools to Joule as if they were SIGAP's.
#   * Never evidence. tools/execution.py will not let an action rest on one
#     (see _is_evidence there).

#: A remote tool is addressed `mcp__<server>__<tool>`. Underscores and not the
#: dot used for board keys: a model tool name is [a-zA-Z0-9_-], so `server.tool`
#: would be refused by the API before the handling began.
REMOTE_PREFIX = "mcp__"

#: The API caps a tool name. A qualified name that does not fit is dropped
#: rather than truncated, because a truncated name is a name that can collide.
REMOTE_NAME_MAX = 64

#: Seconds the server list is reused for. A specialist asks for its tool list
#: every round of every handling, and that must not be a database read a round.
REMOTE_TTL = 60.0

_remote_at = 0.0
_remote: Dict[str, Dict[str, Any]] = {}
_remote_off = False


@contextmanager
def no_remote() -> Iterator[None]:
    """No remote tools for the duration. Self-checks run inside this.

    Without it `manage.py check` would assert against whichever servers happen
    to be registered on the machine running it, and the suite would pass or
    fail by local configuration - the bug compliance's demo() had with
    sap_s4.available.
    """
    global _remote_off
    was = _remote_off
    _remote_off = True
    try:
        yield
    finally:
        _remote_off = was


def forget_remote() -> None:
    """Drop the cached list: a server was added, changed, tested or removed."""
    global _remote_at
    _remote_at = 0.0


def remote_name(server: str, tool: str) -> str:
    return f"{REMOTE_PREFIX}{server}__{tool}"


def remote_tools(refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """Every remote tool our agents may call, by qualified name."""
    global _remote_at, _remote
    if _remote_off:
        return {}
    if not refresh and _remote_at and (time.monotonic() - _remote_at) < REMOTE_TTL:
        return _remote
    try:
        from core import store
        rows = store.mcp_servers(include_token=True)
    except Exception:                                               # noqa: BLE001
        # No database yet, or none reachable. No remote tools is the right
        # answer to that, rather than a handling that cannot start.
        rows = []
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        if not r.get("enabled"):
            continue
        agents = [str(a) for a in (r.get("agents") or [])]
        if not agents:
            # Registered and verified, but granted to nobody. Managing a
            # server and giving an agent its tools are two separate acts.
            continue
        for t in r.get("tools") or []:
            if not isinstance(t, dict) or not t.get("name"):
                continue
            if not t.get("read_only"):
                continue
            bare = str(t["name"])
            if bare in _REGISTRY:
                # Already ours under that name. An agent is not given two
                # routes to the same answer, one of them through somebody
                # else's uptime - and a remote `check_local_constraints` can
                # never stand in for Kira's.
                continue
            schema = t.get("schema")
            if not isinstance(schema, dict) or schema.get("type") != "object":
                continue    # probed before schemas were kept: re-test it
            qualified = remote_name(str(r["name"]), bare)
            if len(qualified) > REMOTE_NAME_MAX or qualified in out:
                continue
            out[qualified] = {
                "server": str(r["name"]), "url": r["url"], "token": r.get("token"),
                "tool": bare, "agents": agents, "schema": schema,
                "description": str(t.get("description") or ""),
            }
    _remote, _remote_at = out, time.monotonic()
    return out


def _remote_description(r: Dict[str, Any]) -> str:
    """What the model is told about a tool we do not operate.

    It is told plainly, because the alternative is an agent that cites a
    third-party answer as though it came from SAP.
    """
    return (f"On '{r['server']}', an MCP server SIGAP does not operate. Reads only. "
            f"Cite what it returns as '{r['server']}', never as SAP or as our own "
            f"records, and do not let an action rest on it alone. "
            f"{r['description']}")[:1800]


#: Argument name → a check that returns the canonical value or raises
#: ValueError. The tools package installs them (tools/__init__.py), because
#: what counts as a real material id is a question about the data, not about
#: the registry. They run on every call, from any model and from MCP alike.
_ARGUMENT_CHECKS: Dict[str, Callable[[str], str]] = {}


def check_argument(name: str, fn: Callable[[str], str]) -> None:
    _ARGUMENT_CHECKS[name] = fn


def run(name: str, arguments: Dict[str, Any]) -> Result:
    if name.startswith(REMOTE_PREFIX):
        return _run_remote(name, arguments)
    args = dict(arguments)
    for key, fn in _ARGUMENT_CHECKS.items():
        if isinstance(args.get(key), str):
            args[key] = fn(args[key])
    return get(name).fn(**args)


def _run_remote(name: str, arguments: Dict[str, Any]) -> Result:
    """Run one tool on somebody else's server.

    The argument checks are deliberately not applied. They canonicalise our
    own identifiers - a material against our master data - and a Jira key or a
    Notion page id is not ours to correct.

    A failure comes back as MISSING with the reason on it, not as an exception:
    somebody else's downtime is an answer about them, not a broken handling.
    """
    from clients import mcp_client
    from core.provenance import Origin

    r = remote_tools().get(name)
    if r is None:
        raise KeyError(f"tool '{name}' is not registered")
    source = f"{r['server']} via MCP (not operated by SIGAP)"
    out = mcp_client.call(r["url"], r.get("token"), r["tool"], dict(arguments or {}))
    if not out.get("ok"):
        return Result(None, Origin.MISSING, source,
                      note=str(out.get("error") or "the server did not answer")[:300])
    return Result(out.get("text") or "", Origin.CACHED, source,
                  note="third-party MCP server; not from SAP and not our own record")


_CURRENT_RUN: ContextVar[Optional[str]] = ContextVar("sigap_run_id", default=None)


def current_run() -> Optional[str]:
    """The run this call belongs to, or None when there is no run open.

    None is a real state, not a missing value: a question asked in chat opens
    no run, and a tool that records an action has to be able to say so instead
    of writing a row that points at nothing.
    """
    return _CURRENT_RUN.get()


_CURRENT_BOARD: ContextVar[Optional[Any]] = ContextVar("sigap_board", default=None)


def current_board() -> Optional[Any]:
    """The blackboard this call belongs to, or None outside a handling.

    Tools read it to find out how trustworthy the evidence under them is. It is
    typed loosely on purpose: core must not import graph, and all a caller
    needs from it is `untrusted_keys()`.
    """
    return _CURRENT_BOARD.get()


@contextmanager
def bind_board(board: Any) -> Iterator[Any]:
    """Make `board` the evidence in force for the duration of a handling."""
    token = _CURRENT_BOARD.set(board)
    try:
        yield board
    finally:
        _CURRENT_BOARD.reset(token)


_CURRENT_AGENT: ContextVar[Optional[str]] = ContextVar("sigap_agent", default=None)


def current_agent() -> Optional[str]:
    """Whose call this is, or None outside a specialist's loop.

    A tool that needs to know is told by the loop rather than by the model: a
    parameter the model fills with an agent code is a parameter it can fill
    with somebody else's.
    """
    return _CURRENT_AGENT.get()


@contextmanager
def bind_agent(agent_code: str) -> Iterator[str]:
    """Make `agent_code` the caller for the duration of its tool loop."""
    token = _CURRENT_AGENT.set(agent_code)
    try:
        yield agent_code
    finally:
        _CURRENT_AGENT.reset(token)


@contextmanager
def bind_run(run_id: str) -> Iterator[str]:
    """Make `run_id` the current run for the duration of a handling."""
    token = _CURRENT_RUN.set(run_id)
    try:
        yield run_id
    finally:
        _CURRENT_RUN.reset(token)


def demo() -> None:
    from core.provenance import Origin

    @register("probe", "inventory", "A registered probe.",
              {"material": {"type": "string"}}, ["material"])
    def probe(material: str) -> Result:
        return Result({"material": material}, Origin.LIVE, "test")

    t = get("probe")
    assert t.owner == "inventory" and t.schema["required"] == ["material"]
    assert t.schema["additionalProperties"] is False

    # What the model sees must name the same tool that actually runs.
    (spec,) = schemas_for_model("inventory")
    assert spec["name"] == "probe" and spec["strict"] is True
    assert spec["input_schema"] is t.schema

    assert run("probe", {"material": "M-4471"}).value["material"] == "M-4471"

    # An argument check runs before the tool, on a copy: it can correct a value
    # or refuse it, and the caller's arguments are left as they were.
    def only_known(v: str) -> str:
        if "M-4471" not in v:
            raise ValueError(f"no material '{v}' on record")
        return "M-4471"
    check_argument("material", only_known)
    try:
        args = {"material": "KRW1 M-4471 resin"}
        assert run("probe", args).value["material"] == "M-4471"
        assert args == {"material": "KRW1 M-4471 resin"}
        try:
            run("probe", {"material": "steel"})
            raise AssertionError("a refused argument must not reach the tool")
        except ValueError:
            pass
    finally:
        _ARGUMENT_CHECKS.pop("material")

    # The run in force reaches a tool, and does not outlive its scope: an action
    # recorded after a handling has ended must not attach itself to that run.
    assert current_run() is None, current_run()
    with bind_run("run_probe"):
        assert current_run() == "run_probe"
        assert run("probe", {"material": "M-4471"}).value["material"] == "M-4471"
    assert current_run() is None, "bind_run leaked past its scope"

    assert owned_by("logistics") == []
    try:
        get("nope")
        raise AssertionError("an unregistered tool must raise")
    except KeyError:
        pass

    _check_remote()
    print(f"registry ok, {len(all_tools())} tool(s)")


def _check_remote() -> None:
    """Tools on a server we do not operate: what is offered, and what is not."""
    import core.registry as me
    from clients import mcp_client
    from core import store
    from core.provenance import Origin

    offered = [
        {"name": "search_tickets", "description": "Find issues.", "read_only": True,
         "schema": {"type": "object", "properties": {"jql": {"type": "string"}},
                    "required": ["jql"], "additionalProperties": False}},
        # Everything below must be dropped, each for its own reason.
        {"name": "create_ticket", "description": "Opens an issue.", "read_only": False,
         "schema": {"type": "object", "properties": {}, "required": [],
                    "additionalProperties": False}},
        {"name": "probe", "description": "Shadows one of ours.", "read_only": True,
         "schema": {"type": "object", "properties": {}, "required": [],
                    "additionalProperties": False}},
        {"name": "unschemaed", "description": "Probed before schemas were kept.",
         "read_only": True},
    ]
    rows = [
        {"name": "jira", "url": "http://jira.invalid/mcp", "token": "t",
         "enabled": True, "agents": ["inventory"], "tools": offered},
        {"name": "notion", "url": "http://notion.invalid/mcp", "token": None,
         "enabled": True, "agents": [], "tools": offered},        # granted to nobody
        {"name": "off", "url": "http://off.invalid/mcp", "token": None,
         "enabled": False, "agents": ["inventory"], "tools": offered},
    ]
    real_servers, real_call = store.mcp_servers, mcp_client.call
    store.mcp_servers = lambda include_token=False: rows                # type: ignore[assignment]
    asked: List[tuple] = []

    def fake_call(url, token, tool, arguments):
        asked.append((url, token, tool, arguments))
        if tool == "search_tickets" and arguments.get("jql") == "down":
            return {"ok": False, "error": "HTTP 503: unavailable"}
        return {"ok": True, "text": "SUP-14 open"}

    mcp_client.call = fake_call                                        # type: ignore[assignment]
    try:
        names = list(remote_tools(refresh=True))
        assert names == ["mcp__jira__search_tickets"], names
        assert "mcp__jira__create_ticket" not in names, "a remote writer must not be offered"
        assert "mcp__jira__probe" not in names, "a remote tool must not shadow one of ours"
        assert "mcp__jira__unschemaed" not in names, "no schema, no tool"
        assert not any("notion" in n for n in names), "granted to nobody means offered to nobody"
        assert not any("off" in n for n in names), "a disabled server offers nothing"

        # It reaches the agent it was granted to, and nobody else.
        inv = [sp["name"] for sp in schemas_for_model("inventory")]
        assert "mcp__jira__search_tickets" in inv, inv
        assert not any(sp["name"].startswith(REMOTE_PREFIX)
                       for sp in schemas_for_model("logistics"))

        (spec,) = [sp for sp in schemas_for_model("inventory")
                   if sp["name"].startswith(REMOTE_PREFIX)]
        assert spec["strict"] is True
        assert spec["input_schema"]["additionalProperties"] is False
        # The model is told whose server it is, in the description itself.
        assert "jira" in spec["description"] and "does not operate" in spec["description"]

        # Never re-exported: mcp.py offers all_tools(), so a caller of ours is
        # never handed somebody else's tool as though it were SIGAP's.
        assert "mcp__jira__search_tickets" not in all_tools()

        res = run("mcp__jira__search_tickets", {"jql": "project = SUP"})
        assert asked == [("http://jira.invalid/mcp", "t", "search_tickets",
                          {"jql": "project = SUP"})], asked
        assert res.value == "SUP-14 open" and res.origin is Origin.CACHED
        assert "jira" in res.source and "not operated by SIGAP" in res.source

        # Somebody else's downtime is an answer about them, not an exception.
        down = run("mcp__jira__search_tickets", {"jql": "down"})
        assert down.origin is Origin.MISSING and down.value is None
        assert "503" in down.note, down.note

        # A name that was never granted does not become callable by guessing it.
        try:
            run("mcp__jira__create_ticket", {})
            raise AssertionError("a remote writer must not be callable")
        except KeyError:
            pass

        with no_remote():
            assert remote_tools(refresh=True) == {}
            assert not any(sp["name"].startswith(REMOTE_PREFIX)
                           for sp in schemas_for_model("inventory"))
    finally:
        store.mcp_servers, mcp_client.call = real_servers, real_call   # type: ignore[assignment]
        forget_remote()
    print("  a remote read-only tool reaches its agent; writers, shadows and "
          "ungranted servers do not ✓")


if __name__ == "__main__":
    demo()
