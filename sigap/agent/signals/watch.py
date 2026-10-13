"""The thing that makes "anticipation" more than a word in the name.

`bmkg.poll()` has always been able to find a quake near a plant and raise it.
Nothing ever called it, so every event in the system arrived because a person
posted one. This runs it on a timer inside the API process, which is what the
product claims to do.

Two things it must not do, both learned from what the feed actually returns:

  - Raise the same quake twice. BMKG keeps a quake in its list for hours, so a
    watcher polling every few minutes sees it on every pass. `event_exists`
    settles it against the record rather than against a set in memory, so a
    restart does not re-raise yesterday's news.
  - Die quietly. A feed that is down, slow, or reshaped must cost one skipped
    round, not the watcher. Anything that escapes is caught and reported.

# ponytail: one feed, one thread, fixed interval. A second signal source wants
#           a scheduler rather than a copy of this file.
"""
from __future__ import annotations

import threading
import time
import traceback
from typing import Callable, List

from core import store
from signals import bmkg

# BMKG publishes on the order of minutes and a quake stays in the list for
# hours, so polling faster buys nothing and just burns the feed's goodwill.
INTERVAL_SECONDS = 300


def sweep(raise_event: Callable[[dict], str]) -> List[str]:
    """One pass. Returns the ids of events actually raised, newest first.

    `raise_event` is injected so the self-check can run the whole path without
    a server: in the service it is the same call POST /events makes.
    """
    out = bmkg.poll()
    if out["origin"] == "missing":
        return []

    raised: List[str] = []
    for hit in out["hits"]:
        body = bmkg.as_event(hit)
        if store.event_exists(body["title"], body["trigger"]):
            continue
        raised.append(raise_event(body))
    return raised


def _loop(raise_event: Callable[[dict], str], interval: int) -> None:
    while True:
        try:
            raised = sweep(raise_event)
            if raised:
                print(f"  watch: raised {len(raised)} event(s) from BMKG", flush=True)
        except Exception:                                            # noqa: BLE001
            # A watcher that dies on a bad response stops watching, and nobody
            # finds out until the demo. Lose the round, keep the thread.
            traceback.print_exc()
        time.sleep(interval)


def start(raise_event: Callable[[dict], str], interval: int = INTERVAL_SECONDS) -> threading.Thread:
    t = threading.Thread(target=_loop, args=(raise_event, interval), daemon=True)
    t.start()
    print(f"  watch: BMKG every {interval}s", flush=True)
    return t


def demo() -> None:
    seen: List[dict] = []

    def fake_raise(body: dict) -> str:
        seen.append(body)
        eid = store.record_event(body["kind"], body["title"], body["trigger"],
                                 body["payload"], body["source"])
        return eid

    first = sweep(fake_raise)
    if not seen:
        # Offline, or a quiet day. Both are real answers, so prove the dedup
        # against a synthetic signal instead of pretending the feed was there.
        body = {"kind": "seismic", "title": "M5.9 quake 48 km from KRW1 plant",
                "trigger": "BMKG: test region, 2026-10-13T00:00:00+00:00",
                "payload": {"facility": "KRW1"}, "source": "watch-check"}
        assert not store.event_exists(body["title"], body["trigger"])
        fake_raise(body)
        assert store.event_exists(body["title"], body["trigger"])
        print("  feed quiet or offline; dedup proven against a synthetic signal ✓")
    else:
        print(f"  first sweep raised {len(first)} event(s) from the live feed")

    # The point of the whole file: a second pass must raise nothing new.
    again = sweep(fake_raise)
    assert again == [], f"the same quakes were raised twice: {again}"
    print("  second sweep raised nothing, so a restart will not replay the feed ✓")
    print("watch ok")


if __name__ == "__main__":
    from core.config import fixtures_only

    fixtures_only(__file__, "SIGAP_WATCH_CHECK")
    demo()
