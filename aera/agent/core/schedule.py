"""What runs on its own, and when.

signals/watch.py started one thread per feed with a sleep in it. That was fine
for one feed; with a hazard feed, a weather feed, an outbox and a daily digest
it is five copies of the same loop, none of which can say when it last ran or
be switched off without a restart. This is the one loop instead.

A job is either `every` N seconds or `at` "HH:MM" Jakarta time (WIB, UTC+7,
no daylight saving). Its memory is the `jobs` table, so a restart does not
re-run a weekly scan that ran yesterday, and does not forget one that failed.

Three rules, each from a way a scheduler goes wrong:

  - A job never overlaps itself. A slow feed (GDACS takes ~17 s) on a short
    interval would otherwise stack threads until the process falls over.
  - A daily job that was missed by more than GRACE is skipped, not caught up:
    a digest that arrives at four in the afternoon because the server was
    down at half past seven is noise, and the next one is tomorrow.
  - A job that raises loses that round, not the schedule. The error is kept
    on the job so the Schedule page shows it.

Switches, all read at start:
  AERA_SCHEDULE=0   nothing runs on its own (manual runs still work)
  AERA_WATCH=0      the jobs that watch the outside world stay off; the
                     outbox and the sender still run
"""
from __future__ import annotations

import os
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from core import store

WIB = timezone(timedelta(hours=7))
TICK_SECONDS = 15
GRACE = timedelta(hours=2)


@dataclass(frozen=True)
class Job:
    name: str
    what: str
    fn: Callable[[], str]               # returns a one-line account of what it did
    every: Optional[int] = None         # seconds
    at: Optional[str] = None            # "HH:MM" WIB
    signal: bool = False                # watches the outside world

    def cadence(self) -> str:
        if self.at:
            return f"daily at {self.at} WIB"
        s = self.every or 0
        if s % 86400 == 0:
            n = s // 86400
            return "weekly" if n == 7 else f"every {n} day{'s' * (n > 1)}"
        if s % 3600 == 0:
            return f"every {s // 3600} h"
        if s % 60 == 0:
            return f"every {s // 60} min"
        return f"every {s} s"


def _parse(ts: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(ts) if ts else None


def _slot(job: Job, now: datetime) -> datetime:
    """Today's occurrence of a daily job, in UTC."""
    h, m = (int(x) for x in job.at.split(":"))
    local = now.astimezone(WIB)
    return local.replace(hour=h, minute=m, second=0, microsecond=0).astimezone(timezone.utc)


def next_run(job: Job, last_started: Optional[datetime], now: datetime) -> datetime:
    """When the job will next start, given when it last did."""
    if job.at:
        slot = _slot(job, now)
        done_today = last_started is not None and last_started >= slot
        if now < slot:
            return slot
        if not done_today and now <= slot + GRACE:
            return now
        return slot + timedelta(days=1)
    if last_started is None:
        return now
    return last_started + timedelta(seconds=job.every or 0)


class Scheduler:
    def __init__(self, jobs: List[Job], watch: Optional[bool] = None,
                 enabled: Optional[bool] = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        names = [j.name for j in jobs]
        assert len(names) == len(set(names)), f"duplicate job names: {names}"
        self.jobs: Dict[str, Job] = {j.name: j for j in jobs}
        self.watch = os.environ.get("AERA_WATCH", "1") != "0" if watch is None else watch
        self.enabled = os.environ.get("AERA_SCHEDULE", "1") != "0" if enabled is None else enabled
        self.clock = clock
        self._running: set = set()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    # -------------------------------------------------------------- state
    def off_why(self, job: Job, state: dict) -> Optional[str]:
        """Why a job will not start on its own, or None if it will."""
        if not self.enabled:
            return "AERA_SCHEDULE=0"
        if job.signal and not self.watch:
            return "AERA_WATCH=0"
        if not state.get("enabled", 1):
            return "switched off"
        return None

    def due(self, now: Optional[datetime] = None) -> List[Job]:
        now = now or self.clock()
        states = store.job_states()
        out = []
        for job in self.jobs.values():
            st = states.get(job.name, {})
            if self.off_why(job, st) or job.name in self._running:
                continue
            if next_run(job, _parse(st.get("last_started")), now) <= now:
                out.append(job)
        return out

    def describe(self) -> List[dict]:
        now = self.clock()
        states = store.job_states()
        out = []
        for job in self.jobs.values():
            st = states.get(job.name, {})
            off = self.off_why(job, st)
            last = _parse(st.get("last_started"))
            out.append({
                "name": job.name, "what": job.what, "cadence": job.cadence(),
                "signal": job.signal, "enabled": bool(st.get("enabled", 1)),
                "off": off, "running": job.name in self._running,
                "next_at": None if off else next_run(job, last, now).isoformat(timespec="seconds"),
                **{k: st.get(k) for k in ("last_started", "last_finished", "last_status",
                                          "last_detail")},
                "runs": st.get("runs", 0), "failures": st.get("failures", 0),
            })
        return out

    # ------------------------------------------------------------ running
    def _run(self, job: Job) -> None:
        try:
            store.job_started(job.name)
            detail = job.fn() or "done"
            store.job_finished(job.name, True, str(detail))
        except Exception as e:                                       # noqa: BLE001
            traceback.print_exc()
            store.job_finished(job.name, False, f"{type(e).__name__}: {e}")
        finally:
            with self._lock:
                self._running.discard(job.name)

    def _launch(self, job: Job) -> bool:
        with self._lock:
            if job.name in self._running:
                return False
            self._running.add(job.name)
        threading.Thread(target=self._run, args=(job,), daemon=True,
                         name=f"job:{job.name}").start()
        return True

    def run_now(self, name: str) -> bool:
        """Start a job outside its schedule. False if it is already running.
        Works when the job, or the whole schedule, is switched off: a person
        asking for one run is not the schedule deciding to run it."""
        if name not in self.jobs:
            raise KeyError(name)
        return self._launch(self.jobs[name])

    def tick(self) -> List[str]:
        return [j.name for j in self.due() if self._launch(j)]

    def start(self) -> None:
        if not self.enabled:
            print("  schedule: off (AERA_SCHEDULE=0)", flush=True)
            return

        def loop() -> None:
            while True:
                try:
                    self.tick()
                except Exception:                                    # noqa: BLE001
                    traceback.print_exc()
                time.sleep(TICK_SECONDS)

        self._thread = threading.Thread(target=loop, daemon=True, name="schedule")
        self._thread.start()
        on = [j for j in self.jobs.values() if not (j.signal and not self.watch)]
        print(f"  schedule: {', '.join(f'{j.name} {j.cadence()}' for j in on)}"
              + ("" if self.watch else " · watchers off (AERA_WATCH=0)"), flush=True)

    def wait_idle(self, timeout: float = 10) -> None:
        end = time.time() + timeout
        while self._running and time.time() < end:
            time.sleep(0.02)


def demo() -> None:
    # job_started stamps the real time, so the fake clock starts there too.
    now = {"t": datetime.now(timezone.utc)}
    calls: List[str] = []
    gate = threading.Event()

    def quick() -> str:
        calls.append("quick")
        return "1 thing"

    def slow() -> str:
        calls.append("slow")
        gate.wait(5)
        return "slow done"

    def broken() -> str:
        raise RuntimeError("feed reshaped")

    jobs = [Job("quick", "q", quick, every=300),
            Job("slow", "s", slow, every=60),
            Job("broken", "b", broken, every=60, signal=True)]
    digest = Job("digest", "d", lambda: calls.append("digest") or "sent", at="07:30")
    s = Scheduler(jobs, watch=True, enabled=True, clock=lambda: now["t"])

    assert sorted(s.tick()) == ["broken", "quick", "slow"], "never run means due now"
    assert "slow" not in s.tick(), "a running job does not start again"
    gate.set()
    s.wait_idle()
    st = store.job_states()
    assert st["broken"]["last_status"] == "failed" and "feed reshaped" in st["broken"]["last_detail"]
    assert st["quick"]["last_detail"] == "1 thing"

    real = _parse(st["quick"]["last_started"])
    now["t"] = real + timedelta(seconds=120)
    assert sorted(j.name for j in s.due()) == ["broken", "slow"], "quick is not due for 300 s"
    now["t"] = real + timedelta(seconds=301)
    assert "quick" in [j.name for j in s.due()]

    # Daily: due inside the window, skipped outside it, once a day.
    s2 = Scheduler([digest], watch=True, enabled=True, clock=lambda: now["t"])
    day = datetime(2030, 1, 1, tzinfo=timezone.utc)                     # after any real stamp
    slot = day.replace(hour=0, minute=30)                               # 07:30 WIB
    assert next_run(digest, None, slot - timedelta(minutes=5)) == slot
    assert next_run(digest, None, slot + timedelta(minutes=10)) == slot + timedelta(minutes=10)
    assert next_run(digest, None, slot + GRACE + timedelta(minutes=1)) == slot + timedelta(days=1), \
        "a digest missed by hours is skipped, not sent late"
    assert next_run(digest, slot + timedelta(minutes=1), slot + timedelta(hours=1)) == \
        slot + timedelta(days=1), "once a day"
    now["t"] = slot + timedelta(minutes=1)
    s2.tick()
    s2.wait_idle()
    assert calls.count("digest") == 1

    # Switches.
    store.set_job_enabled("quick", False)
    off = {d["name"]: d for d in Scheduler(jobs, watch=False, enabled=True,
                                           clock=lambda: now["t"]).describe()}
    assert off["quick"]["off"] == "switched off" and off["quick"]["next_at"] is None
    assert off["broken"]["off"] == "AERA_WATCH=0", "a watcher stays off when watching is"
    assert off["slow"]["off"] is None, "the outbox and the sender are not watchers"
    s3 = Scheduler(jobs, watch=False, enabled=True, clock=lambda: now["t"] + timedelta(days=9))
    assert "quick" not in [j.name for j in s3.due()] and "broken" not in [j.name for j in s3.due()]
    assert s3.run_now("quick"), "a person may still run a switched-off job"
    s3.wait_idle()
    assert Job("x", "", quick, every=7 * 86400).cadence() == "weekly"
    assert Job("x", "", quick, every=300).cadence() == "every 5 min"
    print("  schedule: due when never run ✓ · no overlap ✓ · a failure is kept, not fatal ✓ "
          "· daily once, skipped when missed ✓ · switches ✓ · run now overrides ✓")
    print("schedule ok")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_SCHEDULE_CHECK")
    demo()
