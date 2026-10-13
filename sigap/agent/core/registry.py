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


_REGISTRY: Dict[str, Tool] = {}


def register(name: str, owner: str, description: str,
             properties: Optional[Dict[str, Any]] = None,
             required: Optional[List[str]] = None) -> Callable:
    def wrap(fn: Callable[..., Result]) -> Callable[..., Result]:
        _REGISTRY[name] = Tool(
            name=name, owner=owner, description=description,
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


def owned_by(agent_code: str) -> List[Tool]:
    return [t for t in _REGISTRY.values() if t.owner == agent_code]


def schemas_for_model(agent_code: str) -> List[dict]:
    """The shape sent to Claude as the `tools` parameter."""
    return [
        {"name": t.name, "description": t.description, "input_schema": t.schema, "strict": True}
        for t in owned_by(agent_code)
    ]


def all_tools() -> Dict[str, Tool]:
    return dict(_REGISTRY)


def run(name: str, arguments: Dict[str, Any]) -> Result:
    return get(name).fn(**arguments)


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
    print(f"registry ok, {len(all_tools())} tool(s)")


if __name__ == "__main__":
    demo()
