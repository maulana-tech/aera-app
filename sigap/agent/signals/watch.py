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

# Vega is Prevent mode: it looks for risk that has not happened yet. Nothing it
# finds is urgent, so it runs on its own, slower cadence.
EXPOSURE_INTERVAL_SECONDS = 7 * 24 * 3600

# The scan returns dozens of findings. Raising all of them would bury the queue
# it exists to inform, which is the same mistake as re-raising every quake, so
# only the most valuable few become events.
EXPOSURE_TOP_N = 3

# A standing exposure is not news every week. It is news again if it is still
# there a month later and nobody has acted on it.
EXPOSURE_QUIET_DAYS = 30


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


def as_exposure_event(finding: dict) -> dict:
    """One Vega finding, in the shape POST /events expects."""
    where = finding.get("plant") or "-"
    return {
        "kind": "exposure",
        "title": f"{finding['pattern']}: {finding['material']}"[:120],
        # The trigger is the finding's identity, so the same standing risk
        # dedupes against itself while a different one still gets through.
        "trigger": f"Vega: {finding['pattern']} · {finding['material']} · {where}"[:200],
        "payload": finding,
        "source": "tools/exposure.py",
    }


def sweep_exposure(raise_event: Callable[[dict], str]) -> List[str]:
    """One Prevent-mode pass. Raises the few most valuable findings."""
    from core import registry, store
    import tools  # noqa: F401  (registers every tool)

    r = registry.run("scan_supply_exposure", {})
    if not r.value:
        return []

    ranked = sorted(r.value, key=lambda f: f.get("value_idr") or 0, reverse=True)
    raised: List[str] = []
    for finding in ranked[:EXPOSURE_TOP_N]:
        body = as_exposure_event(finding)
        if store.event_exists(body["title"], body["trigger"], within_days=EXPOSURE_QUIET_DAYS):
            continue
        raised.append(raise_event(body))
    return raised


def _loop(name: str, one_pass: Callable[[], List[str]], interval: int) -> None:
    while True:
        try:
            raised = one_pass()
            if raised:
                print(f"  watch: raised {len(raised)} event(s) from {name}", flush=True)
        except Exception:                                            # noqa: BLE001
            # A watcher that dies on a bad response stops watching, and nobody
            # finds out until the demo. Lose the round, keep the thread.
            traceback.print_exc()
        time.sleep(interval)


def start(raise_event: Callable[[dict], str],
          interval: int = INTERVAL_SECONDS,
          exposure_interval: int = EXPOSURE_INTERVAL_SECONDS) -> List[threading.Thread]:
    """Both watches: react to what happened, and look for what has not yet."""
    threads = [
        threading.Thread(target=_loop, daemon=True,
                         args=("BMKG", lambda: sweep(raise_event), interval)),
        threading.Thread(target=_loop, daemon=True,
                         args=("Vega", lambda: sweep_exposure(raise_event), exposure_interval)),
    ]
    for t in threads:
        t.start()
    print(f"  watch: BMKG every {interval}s · Vega every {exposure_interval}s", flush=True)
    return threads


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

    # Prevent mode. The scan finds dozens; only the few worth a person's
    # attention become events, and a standing risk does not reappear weekly.
    before = len(seen)
    first = sweep_exposure(fake_raise)
    assert len(first) <= EXPOSURE_TOP_N, f"the queue must not be buried: {len(first)}"
    if first:
        ranked = [b["payload"]["value_idr"] for b in seen[before:]]
        assert ranked == sorted(ranked, reverse=True), "the most valuable should go first"
        assert all(b["kind"] == "exposure" for b in seen[before:])
        print(f"  Vega raised the top {len(first)} of the scan, worth "
              f"Rp {ranked[0]:,} at the head")
    assert sweep_exposure(fake_raise) == [], "a standing exposure was raised twice"
    print("  the same standing risk does not come back next pass ✓")
    print("watch ok")


if __name__ == "__main__":
    from core.config import fixtures_only

    fixtures_only(__file__, "SIGAP_WATCH_CHECK")
    demo()
