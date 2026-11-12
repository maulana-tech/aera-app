"""Capability `systems`: the Tech Lead reads how the machinery is doing and files a review. Changes nothing.

Figures come from core/systems.py (runs, steps, proofs, servers, the vault). The owner keeps every switch: models,
outside servers, write permissions, the kill switch.
"""
from __future__ import annotations

import json

from core import business, store, systems
from core.provenance import Origin, Result
from core.registry import register


def _days(days: int) -> int:
    try:
        return max(1, min(int(days or 7), 90))
    except (TypeError, ValueError):
        return 7


@register("systems_status", "systems",
          "How the business's machinery is doing over the last `days` (default 7): model per agent and whether it can be "
          "called, attestation by model, fallback use, AI spend today against the cap, runs by outcome and duration, "
          "failing tools, outside servers and their write permissions, the vault; and the issues those figures point to.",
          {"days": {"type": "integer"}}, [])
def systems_status(days: int = 7) -> Result:
    return Result(systems.status(_days(days)), Origin.CACHED, "AERA record", note="figures computed in code; quote them")


@register("recent_incidents", "systems",
          "Runs that failed, were held or finished partly in the last `days`, with the work they were for and why.",
          {"days": {"type": "integer"}}, [])
def recent_incidents(days: int = 7) -> Result:
    return Result(systems.incidents(_days(days)), Origin.CACHED, "runs")


@register("save_tech_review", "systems",
          "File a systems review as a PDF document: the figures are filled in by AERA; `commentary` is your reading "
          "(what is wrong, the likely cause, what the owner should change and where).",
          {"commentary": {"type": "string"}, "days": {"type": "integer"}}, ["commentary"], writes=True)
def save_tech_review(commentary: str, days: int = 7) -> Result:
    from core import registry
    d = _days(days)
    p = business.current()
    md = systems.review_markdown(systems.status(d), systems.incidents(d), commentary[:6000], p.get("name") or "the business")
    meta = {"title": f"Systems review — last {d} days", "format": "pdf", "order_id": None,
            "run_id": registry.current_run(), "kind": "systems_review"}
    f = store.save_file(f"doc:{meta['title']}", "text/markdown;" + json.dumps(meta), md,
                        by=f"agent:{registry.current_agent() or 'tech'}")
    return Result({**f, "title": meta["title"]}, Origin.DERIVED, "documents")


def demo() -> None:
    from core import registry
    store.save_profile(business.EXAMPLE, by="check")
    assert "issues" in systems_status().value and isinstance(recent_incidents(3).value, list)
    assert _days("x") == 7 and _days(500) == 90
    rid = store.start_run(store.record_work_item("request", "systems review", "api", {}))
    with registry.bind_run(rid):
        saved = save_tech_review("Nothing to change.")
    assert "Nothing to change." in store.get_file(saved.value["id"])["text"]
    print("tools/systems ok: status and incidents from the record ✓ · review filed with the agent's notes only ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_TOOLS_SYSTEMS_CHECK")
    demo()
