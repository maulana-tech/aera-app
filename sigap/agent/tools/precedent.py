"""Otto's tools (Precedent).

Institutional memory: what was done last time something like this happened,
and how it turned out.

The memory is the runs and events tables. Every disruption the system has
finished handling is already written there with its decision, its cost and
who approved it, so there is nothing to build: there was only a tool that
never looked. A Bedrock Knowledge Base can sit in front of this later for
semantic recall, but it would be a second index over the same record, not a
second record.
"""
from __future__ import annotations

import re

from core.provenance import Origin, Result
from core.registry import register

LIMIT = 5


def _terms(keywords: str) -> list[str]:
    """Words worth matching on. Two letters and under are noise, not signal."""
    return [t for t in re.split(r"[^\w-]+", keywords.lower()) if len(t) > 2]


@register("search_past_incidents", "precedent",
          "Find comparable past incidents and how their handling ended.",
          {"keywords": {"type": "string"}}, ["keywords"])
def search_past_incidents(keywords: str) -> Result:
    from core import store

    terms = _terms(keywords)
    if not terms:
        return Result([], Origin.MISSING, "runs + events tables",
                      note="no searchable word in the request")

    matches, total = store.past_incidents(terms, LIMIT)
    source = "runs + events tables"
    held = f"{total} handled incident{'' if total == 1 else 's'}"

    # Three outcomes, and only one of them is missing data. An empty list from
    # a search that genuinely ran is a determinate answer and says so; an empty
    # list because nothing has ever been handled is a hole. Collapsing the two
    # is how an agent ends up reading "no precedent" as "no risk".
    if total == 0:
        return Result([], Origin.MISSING, source,
                      note="nothing has been handled to completion yet, so there is "
                           "no memory to search. This is the first one")
    if not matches:
        return Result([], Origin.DERIVED, source,
                      note=f"searched {held}, none mentions "
                           f"{', '.join(terms)}")
    return Result(matches, Origin.DERIVED, source,
                  note=f"{len(matches)} of {held} matched")


def demo() -> None:
    from core import store

    terms = _terms("Typhoon closes the Port of Ningbo, M-4471 at KRW1")
    assert "typhoon" in terms and "ningbo" in terms
    assert "of" not in terms and "at" not in terms, "short words are noise"

    before = search_past_incidents("typhoon Ningbo")
    total_before = store.past_incidents(terms)[1]
    if total_before == 0:
        assert before.origin is Origin.MISSING and not before.trusted, before.brief()
        print("  no memory yet, and it says so rather than returning an empty answer")

    # Write one finished incident, then prove Otto can find it and that an
    # unrelated search still comes back determinate rather than missing.
    eid = store.record_event("port_closure", "Typhoon closes the Port of Ningbo",
                             "BMKG: test", {"port": "Ningbo"}, "precedent-check")
    rid = store.start_run(eid, "guided")
    store.close_run(rid, "done", decision={"status": "done", "chose": "B+C"}, cost_idr=1500)

    hit = search_past_incidents("typhoon Ningbo")
    assert hit.origin is Origin.DERIVED and hit.trusted, hit.brief()
    assert hit.value and hit.value[0]["title"].endswith("Ningbo"), hit.value
    assert hit.value[0]["decision"]["chose"] == "B+C", hit.value[0]
    assert hit.value[0]["matched"] == 2, hit.value[0]
    print(f"  found it: {hit.value[0]['title']} -> {hit.value[0]['decision']['chose']}")

    # The loop: an action that was sent, then what came of it. A precedent that
    # stops at "we decided X" is a diary; the useful part is "and it was late".
    from core import registry
    with registry.bind_run(rid):
        from tools.execution import raise_action
        act = raise_action("stock_transfer", True, material="M-4471",
                           from_plant="SBY1", to_plant="KRW1", qty=55, cost_idr=1_000_000)
    store.record_outcome(act.value["id"], "late",
                         {"note": "arrived 3 days after the promised date"})

    learned = search_past_incidents("typhoon Ningbo")
    acts = learned.value[0]["actions"]
    assert acts and acts[0]["outcome"] == "late", acts
    assert acts[0]["outcome_detail"]["note"].startswith("arrived 3 days"), acts[0]
    print(f"  and what came of it: {acts[0]['kind']} -> {acts[0]['outcome']}, "
          f"{acts[0]['outcome_detail']['note']}")

    # Reality is read once. A second reading does not quietly replace the first.
    again = store.record_outcome(act.value["id"], "delivered")
    assert again["repeated"] and again["outcome"] == "late", again
    print("  a second outcome does not overwrite the first")

    none = search_past_incidents("earthquake Surabaya")
    assert none.value == [] and none.origin is Origin.DERIVED, none.brief()
    assert none.trusted, "a search that ran and found nothing is an answer, not a gap"
    print(f"  unrelated search: empty but trusted, '{none.note}'")

    print("precedent ok")


if __name__ == "__main__":
    # This check writes a specimen incident, so it must not touch a real DB.
    from core.config import fixtures_only

    fixtures_only(__file__, "SIGAP_PRECEDENT_CHECK")
    demo()
