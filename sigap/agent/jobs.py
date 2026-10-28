"""Everything SIGAP does on its own, in one list.

The cadences, and why each one:

  bmkg       5 min    BMKG publishes within minutes and keeps a quake listed
                      for hours; faster buys nothing.
  hazards    30 min   GDACS, NASA EONET and USGS near a port or a plant.
                      GDACS answers in ~17 s and grades a cyclone every few
                      hours, so polling it often only costs the feed.
  weather    3 h      Open-Meteo, three days ahead at the watched places. Its
                      models run every few hours; a three-day outlook does
                      not change in between.
  exposure   weekly   Vega's Prevent-mode scan of our own data. Nothing it
                      finds is urgent.
  notify     30 s     The outbox. Alerts are queued the moment a handling
                      ends; this is how long one waits at most.
  sap_send   10 min   Approved actions into SAP (sender.py).
  digest     07:30    The morning summary, WIB.

The first four raise events, and an event starts a handling that spends model
credit; SIGAP_WATCH=0 turns those four off and leaves the rest.
"""
from __future__ import annotations

from typing import Callable, List

from core.schedule import Job, Scheduler

RaiseEvent = Callable[[dict], str]


def _raised(ids: List[str], source: str) -> str:
    return f"{len(ids)} event(s) raised from {source}" if ids else f"{source}: nothing new"


def all_jobs(raise_event: RaiseEvent) -> List[Job]:
    def bmkg() -> str:
        from signals import watch
        return _raised(watch.sweep(raise_event), "BMKG")

    def hazards() -> str:
        from signals import hazards as h
        return _raised(h.sweep(raise_event), "GDACS, EONET, USGS")

    def weather() -> str:
        from signals import weather as w
        return _raised(w.sweep(raise_event), "Open-Meteo")

    def exposure() -> str:
        from signals import watch
        return _raised(watch.sweep_exposure(raise_event), "Vega")

    def certificates() -> str:
        from signals import watch
        return _raised(watch.sweep_certificates(raise_event), "rule pack")

    def deliver() -> str:
        import notify
        import outreach
        # An approval recorded while the mailbox was not connected is picked
        # up here once it is.
        n = outreach.queue_approved()
        return (f"{n} outward message(s) queued; " if n else "") + notify.deliver_summary()

    def digest() -> str:
        import notify
        n = notify.queue_digest()
        return f"{n} digest message(s) queued; {notify.deliver_summary()}"

    def sap_send() -> str:
        from clients import sap_s4
        if not sap_s4.available():
            return "SAP not connected; nothing sent"
        import sender
        return f"{sender.send_approved()} action(s) sent"

    return [
        Job("bmkg", "Earthquakes near a plant, from BMKG", bmkg, every=300, signal=True),
        Job("hazards", "Cyclones, floods and quakes near a port or plant (GDACS, NASA EONET, USGS)",
            hazards, every=1800, signal=True),
        Job("weather", "Gales, high seas and heavy rain forecast at a port or plant (Open-Meteo)",
            weather, every=3 * 3600, signal=True),
        Job("exposure", "Vega's scan for risk that has not happened yet", exposure,
            every=7 * 86400, signal=True),
        Job("certificates",
            "TKDN certificates running out, which no feed can see (rule pack)",
            certificates, every=24 * 3600, signal=True),
        Job("notify", "Deliver queued alerts and approved outward messages", deliver, every=30),
        Job("sap_send", "Send approved actions to SAP", sap_send, every=600),
        Job("digest", "The morning digest", digest, at="07:30"),
    ]


def scheduler(raise_event: RaiseEvent) -> Scheduler:
    return Scheduler(all_jobs(raise_event))


def demo() -> None:
    s = scheduler(lambda body: "evt_x")
    d = {j["name"]: j for j in s.describe()}
    watchers = ("bmkg", "hazards", "weather", "exposure", "certificates")
    assert list(d) == [*watchers, "notify", "sap_send", "digest"]
    assert d["digest"]["cadence"] == "daily at 07:30 WIB" and d["exposure"]["cadence"] == "weekly"
    assert all(d[n]["signal"] for n in watchers)
    assert not any(d[n]["signal"] for n in ("notify", "sap_send", "digest"))
    off = {j["name"]: j["off"] for j in Scheduler(all_jobs(lambda b: ""), watch=False).describe()}
    # Certificates are a watcher too: SIGAP_WATCH=0 must silence it with the rest.
    assert off["hazards"] == off["certificates"] == "SIGAP_WATCH=0" and off["notify"] is None
    # The two that touch nothing outside: run them for real on the scratch db.
    assert s.run_now("sap_send") and s.run_now("notify")
    s.wait_idle()
    st = {j["name"]: j for j in s.describe()}
    assert st["sap_send"]["last_status"] == "ok", st["sap_send"]
    assert st["notify"]["last_detail"] == "nothing queued", st["notify"]
    print("  jobs: eight, with their cadences ✓ · SIGAP_WATCH=0 stops only the watchers ✓ "
          "· outbox and SAP sender run ✓")
    print("jobs ok")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_JOBS_CHECK")
    demo()
