"""Otto's tools (Precedent).

Institutional memory: what was done last time something like this happened,
and how it turned out.
"""
from __future__ import annotations

from core.provenance import Origin, Result
from core.registry import register


@register("search_past_incidents", "precedent",
          "Find comparable past incidents and how their handling ended.",
          {"keywords": {"type": "string"}}, ["keywords"])
def search_past_incidents(keywords: str) -> Result:
    return Result([], Origin.MISSING, "Bedrock Knowledge Bases",
                  note="the incident knowledge base is empty — this is the first one")
