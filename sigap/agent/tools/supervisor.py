"""Arya's tools (Team lead).

One way in: a disruption event that is already on the record. Arya does not
invent triggers — she reads what arrived through POST /events.
"""
from __future__ import annotations

import json

from core.provenance import Origin, Result
from core.registry import register


@register("detect_disruption", "supervisor",
          "Take a disruption signal from an outside feed. In this application events "
          "arrive via POST /events, so this tool reads what has been recorded.",
          {"event_id": {"type": "string"}}, ["event_id"])
def detect_disruption(event_id: str) -> Result:
    from core import store
    with store.connect() as c:
        r = c.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if not r:
        return Result(None, Origin.MISSING, "events table")
    return Result({"kind": r["kind"], "title": r["title"], "trigger": r["trigger"],
                   **json.loads(r["payload"])}, Origin.LIVE, r["source"])
