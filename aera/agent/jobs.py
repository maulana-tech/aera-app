"""Everything AERA does on its own, in one list.

  work      20 s    Claim the oldest new work item and hand it to the team.
  settle    30 s    Execute approved actions, follow payments the vault holds,
                    and turn orders paid to the vault into work items.
  notify    30 s    The outbox.
  attest    2 min   Settle TEE proofs whose verification never finished (a
                    restart drops the in-memory bytes; the proof says so).
  goals     daily   The profile's standing goals become work items.
  inbox     2 min   Read new e-mail (IMAP): a stop opts out at once, a reply from
                    a contact becomes a work item.
  follow_ups hourly Follow-ups that are due become work items; leads whose last
                    follow-up went unanswered are closed.
  digest    07:30   The morning summary.

`work`, `goals`, `inbox` and `follow_ups` start handlings that spend model credit
or read the outside world; AERA_WATCH=0 turns them off (somewhere that should
not act on its own) and leaves the rest.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, List

from core.schedule import Job, Scheduler

StartWork = Callable[[dict], str]


def all_jobs(start_work: StartWork) -> List[Job]:
    def work() -> str:
        from core import business, store
        p = business.current()
        if p.get("kill_switch"):
            return "kill switch on: no new work started"
        spent = sum(r.get("cost_usd") or 0 for r in store.list_runs(200)
                    if (r.get("started_at") or "")[:10] == datetime.now(timezone.utc).date().isoformat())
        cap = p["constraints"]["inference_max_usd_per_day"]
        if cap and spent >= cap:
            return f"model spend today ${spent:.2f} reached the ${cap:.2f} daily cap: waiting until tomorrow"
        item = store.next_new_work_item()
        if not item:
            return "nothing new"
        return f"started {start_work(item)} for {item['id']}"

    def settle_() -> str:
        import settle
        return settle.run_once()

    def deliver() -> str:
        import notify
        return notify.deliver_summary()

    def attest() -> str:
        from core import llm, store
        stale = 0
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        for p in store.pending_proofs(50):
            if p["created_at"] < cutoff and p["id"] not in llm._PENDING_BYTES:
                store.settle_proof(p["id"], "partial", [{"name": "signature_text", "status": "skipped",
                                                         "detail": "the service restarted before the response "
                                                                   "signature was checked; the call's hashes are kept"}], None)
                stale += 1
        llm.refresh_attested()
        return f"{stale} stale proof(s) settled"

    def goals() -> str:
        from core import business, store
        p = business.current()
        if p.get("kill_switch") or not p.get("name"):
            return "no business or kill switch on"
        day = datetime.now(timezone.utc).date().isoformat()
        raised = [store.record_work_item("goal", g[:120], "schedule", {"goal": g, "day": day},
                                         dedup_key=f"goal:{day}:{g[:80]}") for g in p.get("goals", [])]
        return f"{len([r for r in raised if r])} goal(s) raised"

    def inbox() -> str:
        from clients import inbox as box
        return box.poll()

    def follow_ups() -> str:
        from core import prospects
        r = prospects.due_follow_ups()
        return f"{r['raised']} follow-up(s) raised · {r['closed']} lead(s) closed without an answer"

    def digest() -> str:
        import notify
        n = notify.queue_digest()
        return f"{n} digest message(s) queued; {notify.deliver_summary()}"

    return [
        Job("work", "Hand the oldest new work item to the team", work, every=20, signal=True),
        Job("settle", "Execute approved actions; follow the vault; ingest paid orders", settle_, every=30),
        Job("notify", "Deliver queued alerts, messages and deliveries", deliver, every=30),
        Job("attest", "Settle TEE proofs that never finished verifying", attest, every=120),
        Job("goals", "Turn the profile's standing goals into work items", goals, every=24 * 3600, signal=True),
        Job("inbox", "Read new e-mail: stops opt out, replies become work", inbox, every=120, signal=True),
        Job("follow_ups", "Raise follow-ups that are due; close leads nobody answered", follow_ups, every=3600, signal=True),
        Job("digest", "The morning digest", digest, at="07:30"),
    ]


def scheduler(start_work: StartWork) -> Scheduler:
    return Scheduler(all_jobs(start_work))


def demo() -> None:
    from core import business, store
    store.save_profile(business.EXAMPLE, by="check")
    started: List[str] = []
    s = scheduler(lambda item: started.append(item["id"]) or "run_x")
    names = [j["name"] for j in s.describe()]
    assert names == ["work", "settle", "notify", "attest", "goals", "inbox", "follow_ups", "digest"], names
    store.record_work_item("request", "hello", "api", {})
    assert s.run_now("work") and s.run_now("settle") and s.run_now("goals")
    s.wait_idle()
    st = {j["name"]: j for j in s.describe()}
    assert st["work"]["last_status"] == "ok" and started, st["work"]
    assert "1 goal(s) raised" in st["goals"]["last_detail"], st["goals"]
    off = {j["name"]: j["off"] for j in Scheduler(all_jobs(lambda i: ""), watch=False).describe()}
    assert off["work"] == off["goals"] == off["inbox"] == off["follow_ups"] == "AERA_WATCH=0" and off["settle"] is None
    print("jobs ok: eight jobs ✓ · work claims one item ✓ · goals raise work ✓ · AERA_WATCH=0 stops the autonomous two ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_JOBS_CHECK")
    demo()
