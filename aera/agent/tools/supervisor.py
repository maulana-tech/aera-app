"""Arya's tools (Team lead).

One way in: a disruption event that is already on the record. Arya does not
invent triggers, she reads what arrived through POST /events.
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


def demo() -> None:
    """Arya has one way in, and the thing worth checking is that it is the
    only one: she reads an event off the record, she does not invent a trigger."""
    from core import store

    eid = store.record_event("port_closure", "Ningbo closes for 72 hours",
                             "GDACS cyclone warning", {"port": "CNNGB", "days": 3}, "check")
    r = detect_disruption(eid)
    assert r.origin is Origin.LIVE and r.source == "check", r.brief()
    assert r.value["kind"] == "port_closure", r.value
    assert r.value["title"] == "Ningbo closes for 72 hours", r.value
    assert r.value["trigger"] == "GDACS cyclone warning", r.value
    # The payload is merged in, so the port and the span the feed carried are
    # readable without a second call.
    assert r.value["port"] == "CNNGB" and r.value["days"] == 3, r.value

    # An event that is not on the record is a gap. Returning something
    # plausible here would be Arya inventing the disruption she then handles.
    nothing = detect_disruption("evt_not_a_real_id")
    assert nothing.origin is Origin.MISSING and nothing.value is None, nothing.brief()
    assert not nothing.trusted

    print("  the recorded event, payload merged ✓ · an unknown id is a gap, not a guess ✓")
    print("supervisor ok")


if __name__ == "__main__":
    # This writes a specimen event, so it must not touch the real database.
    from core.config import fixtures_only

    fixtures_only(__file__, "AERA_SUPERVISOR_CHECK")
    demo()
