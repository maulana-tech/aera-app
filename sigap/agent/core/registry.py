"""Tool registry: name → schema + function.

The schema here goes to the model verbatim as the tool definition. One source,
so what the model is shown and what actually runs can never drift apart.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

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
    assert owned_by("logistics") == []
    try:
        get("nope")
        raise AssertionError("an unregistered tool must raise")
    except KeyError:
        pass
    print(f"registry ok — {len(all_tools())} tool(s)")


if __name__ == "__main__":
    demo()
