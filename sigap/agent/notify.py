"""Tells people. The agents decide and the record holds what they decided; this
reads the record and delivers it, the way sender.py delivers approved actions
to SAP. It is kept apart from the agents for the same reason: nothing reaches
a person except through here, and here quotes the record. A recommendation is
quoted as the lead wrote it and labelled as such; every figure in the message
around it (status, what waits for approval, its value, who may approve it)
comes from the tables, not from the model's prose.

Kinds of message:

  handling  a handling finished: done, held or failed. To every contact whose
            notify_for covers the event's kind, and to the team channels.
            Carries what waits for approval and who may approve it, and what
            Bram's `notify` asked to be told to a role. By email it carries
            the handling's report as a PDF too (SIGAP_ALERT_ATTACH).
  digest    once a day: what came in, what still waits, what failed.
  report    on request: a report sent to contacts, as PDF and/or workbook.
  test      on request, to prove a channel works.
  outreach  an approved message to a supplier or a customer, queued by
            outreach.py and delivered here like the rest.

Files are named in the outbox and rendered when the message is sent, from the
record as it then stands, so the outbox never holds stale copies of a report.

    python3 notify.py            # deliver what is queued
    python3 notify.py --digest   # queue today's digest, then deliver
    python3 notify.py --test     # a test message to every channel that is set up
    python3 notify.py --check    # the self-check, on a scratch database
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from clients import channels
from core import store
from core.config import CFG
from core.identity import ROLE_LIMITS

MAX_ATTEMPTS = 3
RECOMMENDATION_CHARS = 900
WIB = timezone(timedelta(hours=7))

_HEADLINE = {"done": "Recommendation ready", "held": "Held, no decision made",
             "failed": "Handling failed"}


def _idr(n: float) -> str:
    return f"Rp {int(n or 0):,}"


def _value(action: dict) -> int:
    """What approving this action commits: the figure decide() checks a role's
    limit against."""
    return int((action.get("payload") or {}).get("cost_idr", 0) or 0)


def _who_may_approve(value: int, kind: str = "") -> str:
    import outreach
    if kind in outreach.APPROVERS:
        return outreach.APPROVERS[kind][0]
    roles = [r for r, limit in sorted(ROLE_LIMITS.items(), key=lambda x: x[1])
             if limit > 0 and value <= limit and r != "admin"]
    return roles[0] if roles else "nobody below admin"


def _alert_formats() -> List[str]:
    """What a handling alert carries by email: pdf (the default), xlsx, both,
    or none."""
    raw = os.environ.get("SIGAP_ALERT_ATTACH", "pdf").strip().lower()
    return [f for f in ("pdf", "xlsx") if f in {x.strip() for x in raw.split(",")}]


def files_for(specs: Optional[List[dict]]) -> List[channels.File]:
    """Render what a message names: {"report": run_id | "portfolio", "format"}."""
    from engine import report
    out = []
    for spec in specs or []:
        fmt = spec.get("format") if spec.get("format") in ("pdf", "xlsx") else "pdf"
        target = str(spec.get("report") or "")
        f = report.portfolio_file(fmt) if target == "portfolio" else report.run_file(target, fmt)
        if not f:
            raise LookupError(f"report {target} is not on record")
        out.append(f)
    return out


def _recipients(kind: str) -> List[dict]:
    """Contacts whose notify_for covers this kind of event ('*' is every kind)."""
    out = []
    for c in store.list_contacts():
        kinds = {k.strip() for k in (c.get("notify_for") or "*").split(",")}
        if "*" in kinds or kind in kinds:
            out.append(c)
    return out


def _excerpt(text: str, n: int = RECOMMENDATION_CHARS) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


def handling_message(run: dict) -> Dict[str, str]:
    """Subject and body for one finished handling, from the record."""
    status = run["status"]
    decision = run.get("decision") or {}
    lines = [run["title"], f"{_HEADLINE.get(status, status)} · {run['kind']} · run {run['id']}", ""]
    if status == "done" and decision.get("recommendation"):
        if decision.get("status") == "partial":
            lines.append("The lead ran out of time; this is what it had so far.")
        lines += ["The lead's recommendation, as written:", _excerpt(decision["recommendation"]), ""]
    elif decision.get("reason"):
        lines += [decision["reason"], ""]
    elif status == "failed":
        lines += [f"Error: {run.get('error') or 'unknown'}", ""]

    # What was actually done is the actions table, not the prose above it. A
    # small model has written "executed" over a turn that recorded nothing.
    acts = [a for a in run.get("actions", []) if a["kind"] != "notify"]
    pending = [a for a in acts if a["status"] == "pending"]
    if not acts:
        lines += ["Recorded actions: none. Nothing was carried out or queued for approval, "
                  "whatever the text above says.", ""]
    else:
        done = [a for a in acts if a["status"] in ("sent", "approved")]
        if done:
            lines.append(f"Recorded as carried out or approved ({len(done)}):")
            for a in done:
                ref = f"SAP {a['sap_reference']}" if a.get("sap_reference") else "not posted to SAP"
                lines.append(f"  - {a['kind']} · {_idr(_value(a))} · {a['status']} · {ref}")
            lines.append("")
        if pending:
            lines.append(f"Waiting for approval ({len(pending)}):")
            for a in pending:
                v = _value(a)
                lines.append(f"  - {a['kind']} · {_idr(v)} · needs {_who_may_approve(v, a['kind'])}")
            lines.append("")
    asks = [a["payload"] for a in run.get("actions", [])
            if a["kind"] == "notify" and (a.get("payload") or {}).get("message")]
    for p in asks:
        lines.append(f"For {p.get('role', 'the team')}: {p['message']}")
    if asks:
        lines.append("")
    untrusted = decision.get("untrusted_on_board") or []
    if untrusted:
        lines += [f"{len(untrusted)} piece(s) of evidence were modelled or missing, not live. "
                  "Check them before acting.", ""]
    lines.append(f"Open it: {CFG.web_url}/disruptions/{run['id']}")
    return {"subject": f"[SIGAP] {_HEADLINE.get(status, status)}: {run['title']}"[:180],
            "body": "\n".join(lines)}


def queue_handling(run_id: str) -> int:
    """Queue the message for a finished handling. Returns how many were queued;
    asking twice for the same run and status queues nothing more."""
    run = store.get_run(run_id)
    if not run or run["status"] == "running":
        return 0
    msg = handling_message(run)
    files = ([{"report": run_id, "format": f} for f in _alert_formats()]
             if run["status"] in ("done", "held") else [])
    n = 0
    for c in _recipients(run["kind"]):
        n += store.enqueue_notification(f"handling:{run_id}:{run['status']}:email:{c['email']}",
                                        "handling", "email", c["email"], msg["subject"],
                                        msg["body"], run_id, attachments=files)
    for ch in channels.team_channels():
        n += store.enqueue_notification(f"handling:{run_id}:{run['status']}:{ch}", "handling",
                                        ch, ch, msg["subject"], msg["body"], run_id)
    return n


def digest_message(now: Optional[datetime] = None) -> Dict[str, str]:
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=1)).isoformat(timespec="seconds")
    runs = store.list_runs(200)
    recent = [r for r in runs if (r.get("started_at") or "") >= since]
    with store.connect() as c:
        waiting = [dict(r) for r in c.execute(
            "SELECT a.kind, a.payload, e.title, a.run_id FROM actions a"
            " JOIN runs r ON r.id = a.run_id JOIN events e ON e.id = r.event_id"
            " WHERE a.status='pending' ORDER BY a.created_at").fetchall()]
    total = sum(int((json.loads(w["payload"]) or {}).get("cost_idr", 0) or 0) for w in waiting)
    by_status: Dict[str, int] = {}
    for r in recent:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    day = now.astimezone(WIB).strftime("%d %b %Y")
    lines = [f"SIGAP, {day}", "",
             f"Last 24 hours: {len(recent)} handling(s)"
             + (" · " + " · ".join(f"{v} {k}" for k, v in sorted(by_status.items())) if recent else ""),
             f"Waiting for approval: {len(waiting)} action(s), {_idr(total)} in all", ""]
    for r in recent[:10]:
        lines.append(f"  - [{r['status']}] {r['title']}  {CFG.web_url}/disruptions/{r['id']}")
    if waiting:
        lines += ["", "Oldest waiting:"]
        for w in waiting[:5]:
            lines.append(f"  - {w['kind']} for \"{w['title']}\"  {CFG.web_url}/disruptions/{w['run_id']}")
    return {"subject": f"[SIGAP] Daily digest, {day}", "body": "\n".join(lines),
            "key": now.astimezone(WIB).strftime("%Y-%m-%d")}


def queue_digest(now: Optional[datetime] = None) -> int:
    msg = digest_message(now)
    n = 0
    for c in _recipients("digest"):
        n += store.enqueue_notification(f"digest:{msg['key']}:email:{c['email']}", "digest",
                                        "email", c["email"], msg["subject"], msg["body"])
    for ch in channels.team_channels():
        n += store.enqueue_notification(f"digest:{msg['key']}:{ch}", "digest", ch, ch,
                                        msg["subject"], msg["body"])
    return n


def queue_test(requested_by: str) -> int:
    """One message to every channel that is set up, and to the asker by email."""
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    subject = "[SIGAP] Test alert"
    body = (f"Sent on request by {requested_by} at {stamp}. If you can read this, "
            f"alerts reach this channel.\n\nOpen SIGAP: {CFG.web_url}")
    targets = [(ch, ch) for ch in channels.team_channels()]
    if not channels.missing("email"):
        targets.append(("email", requested_by))
    return sum(store.enqueue_notification(f"test:{stamp}:{ch}:{addr}", "test", ch, addr,
                                          subject, body) for ch, addr in targets)


def queue_report(target: str, formats: List[str], emails: List[str], requested_by: str,
                 note: str = "") -> int:
    """A report sent on request: one handling (`target` is its run id) or the
    operations report ("portfolio"), to each address, with the files asked for."""
    formats = [f for f in ("pdf", "xlsx") if f in formats] or ["pdf"]
    if target == "portfolio":
        title, url = "Operations report", f"{CFG.web_url}/reports/portfolio"
    else:
        run = store.get_run(target)
        if not run:
            raise LookupError(f"no handling {target}")
        title, url = run["title"], f"{CFG.web_url}/reports/{target}"
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [f"{requested_by} sent you this report from SIGAP: {title}.", ""]
    if note.strip():
        lines += [note.strip(), ""]
    lines += [f"Attached: the report as {' and '.join({'pdf': 'a PDF', 'xlsx': 'an Excel workbook'}[f] for f in formats)}.",
              f"Open it in SIGAP: {url}"]
    files = [{"report": target, "format": f} for f in formats]
    return sum(store.enqueue_notification(f"report:{target}:{stamp}:{e}", "report", "email", e,
                                          f"[SIGAP] Report: {title}"[:180], "\n".join(lines),
                                          None if target == "portfolio" else target,
                                          attachments=files)
               for e in dict.fromkeys(emails))


def deliver(limit: int = 50) -> Dict[str, int]:
    """Send what is queued. A channel that is not set up marks its messages
    skipped, with what it lacks, rather than holding them: switching a channel
    on later must not deliver last month's alerts all at once."""
    import outreach
    counts = {"sent": 0, "failed": 0, "skipped": 0, "retry": 0}
    for n in store.pending_notifications(limit):
        try:
            files = files_for(n.get("attachments")) if n["channel"] == "email" else []
            ref = channels.send(n["channel"], n["address"], n["subject"], n["body"],
                                {"kind": n["kind"], "run_id": n["run_id"],
                                 "url": f"{CFG.web_url}/disruptions/{n['run_id']}" if n["run_id"] else CFG.web_url},
                                files=files)
            store.mark_notification(n["id"], "sent", reference=ref)
            if n.get("action_id"):
                outreach.delivered(n["action_id"], ref)
            counts["sent"] += 1
        except channels.NotConfigured as e:
            store.mark_notification(n["id"], "skipped", str(e))
            counts["skipped"] += 1
        except LookupError as e:
            # The report it was to carry is gone: no retry brings it back.
            store.mark_notification(n["id"], "failed", str(e))
            counts["failed"] += 1
        except channels.DeliveryFailed as e:
            final = n["attempts"] + 1 >= MAX_ATTEMPTS
            store.mark_notification(n["id"], "failed" if final else "pending", str(e))
            counts["failed" if final else "retry"] += 1
    return counts


def deliver_summary() -> str:
    c = deliver()
    return ", ".join(f"{v} {k}" for k, v in c.items() if v) or "nothing queued"


def demo() -> None:
    """Against a scratch database: the __main__ block guarantees one."""
    import os
    saved = {k: os.environ.pop(k, None) for k in ("SIGAP_SMTP_HOST", "SIGAP_MAIL_FROM",
                                                  "SIGAP_SLACK_WEBHOOK_URL", "SIGAP_WEBHOOK_URL",
                                                  "SIGAP_TELEGRAM_BOT_TOKEN", "SIGAP_TELEGRAM_CHAT_ID",
                                                  "COMPOSIO_API_KEY", "SIGAP_EMAIL_VIA",
                                                  "SIGAP_ALERT_ATTACH")}
    sent: List[tuple] = []
    real_send = channels.send

    def fake_send(channel, address, subject, body, extra=None, files=()):
        if channels.missing(channel):
            raise channels.NotConfigured(f"{channel} is not set up")
        if address == "broken@x":
            raise channels.DeliveryFailed("550 mailbox unavailable")
        sent.append((channel, address, subject, body, [(f[1], f[2]) for f in files]))
        return f"<{len(sent)}@x>"

    channels.send = fake_send
    try:
        store.add_contact("Rina", "buyer", "rina@x", "port_closure")
        store.add_contact("Dodi", "planner", "dodi@x", "quality_hold")
        store.add_contact("Broken", "buyer", "broken@x", "*")
        eid = store.record_event("port_closure", "Ningbo closes", "advisory", {}, "check")
        rid = store.start_run(eid, "autonomous")
        store.record_action(rid, "k1", "draft_po", False, {"cost_idr": 94_000_000, "material": "M-4471"})
        store.record_action(rid, "k2", "notify", True, {"role": "buyer", "message": "Hold 55 t at SBY1."})
        store.close_run(rid, "done", {"recommendation": "Recommend B+C. " * 200,
                                      "untrusted_on_board": ["impact.get_material_stock"]})

        os.environ["SIGAP_WEBHOOK_URL"] = "http://127.0.0.1:9/hook"
        assert queue_handling(rid) == 3, "Rina and Broken by email, the webhook; not Dodi"
        assert queue_handling(rid) == 0, "a second ask for the same run queues nothing"
        msg = handling_message(store.get_run(rid))
        assert "draft_po · Rp 94,000,000 · needs buyer" in msg["body"]
        assert "Recorded actions: none" not in msg["body"]
        assert "For buyer: Hold 55 t at SBY1." in msg["body"]
        assert "were modelled or missing" in msg["body"] and f"/disruptions/{rid}" in msg["body"]
        assert len(msg["body"]) < 2000, "a recommendation is quoted, not pasted whole"

        c = deliver()
        assert c == {"sent": 1, "failed": 0, "skipped": 2, "retry": 0}, c
        assert sent == [] or sent[0][0] == "webhook"
        skipped = [n for n in store.list_notifications() if n["status"] == "skipped"]
        assert all("email is not set up" in n["error"] for n in skipped)

        os.environ["SIGAP_SMTP_HOST"], os.environ["SIGAP_MAIL_FROM"] = "smtp.x", "sigap@x"
        rid2 = store.start_run(eid, "autonomous")
        store.close_run(rid2, "failed", error="boom")
        assert "Recorded actions: none." in handling_message(store.get_run(rid2))["body"], \
            "a handling that recorded nothing says so, whatever its prose claims"
        queue_handling(rid2)
        for _ in range(MAX_ATTEMPTS):
            deliver()
        rows = {n["address"]: n for n in store.list_notifications() if n["run_id"] == rid2}
        assert rows["broken@x"]["status"] == "failed" and rows["broken@x"]["attempts"] == MAX_ATTEMPTS
        assert rows["rina@x"]["status"] == "sent"

        assert queue_digest() >= 1 and queue_digest() == 0, "one digest a day"
        assert "Waiting for approval: 1 action(s), Rp 94,000,000" in digest_message()["body"]

        # A finished handling's email carries its report; a team channel the link.
        rid3 = store.start_run(eid, "guided")
        store.close_run(rid3, "held", {"reason": "two figures modelled"})
        sent.clear()
        queue_handling(rid3)
        deliver()
        by_mail = [x for x in sent if x[0] == "email"]
        assert by_mail and all(x[4] and x[4][0][0].endswith(".pdf") for x in by_mail), sent
        assert all(not x[4] for x in sent if x[0] != "email"), "files travel by email only"
        rows = {n["address"]: n for n in store.list_notifications() if n["run_id"] == rid3}
        assert rows["rina@x"]["reference"] and rows["rina@x"]["attachments"] == \
            [{"report": rid3, "format": "pdf"}], rows["rina@x"]

        # A report sent on request: once per address, with what was asked for.
        sent.clear()
        assert queue_report(rid, ["xlsx", "pdf"], ["rina@x", "rina@x"], "lead@x", "For Monday.") == 1
        assert queue_report("portfolio", ["xlsx"], ["dodi@x"], "lead@x") == 1
        deliver()
        (one, two) = sorted(sent, key=lambda x: x[1])
        assert [n for n, _ in two[4]] and two[4][0][0].endswith(".pdf") and two[4][1][0].endswith(".xlsx"), two
        assert "For Monday." in two[3] and "lead@x sent you" in two[3]
        assert one[4][0][1].startswith("application/vnd.openxml"), one
        try:
            queue_report("run_missing", ["pdf"], ["rina@x"], "lead@x")
            raise AssertionError("a report that does not exist cannot be sent")
        except LookupError:
            pass
        assert _who_may_approve(0, "customer_notice") == "procurement_lead"
        os.environ["SIGAP_ALERT_ATTACH"] = "none"
        assert _alert_formats() == []
    finally:
        channels.send = real_send
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    # A kind the watchers raise but the Contacts page does not offer reaches
    # only those who chose every kind: nobody can ask for it alone.
    from pathlib import Path
    from signals.hazards import EONET_KIND, GDACS_KIND
    raised = {*GDACS_KIND.values(), *EONET_KIND.values(),
              "seismic", "port_weather", "plant_weather", "exposure"}
    page = Path(__file__).resolve().parents[2] / "app" / "(app)" / "contacts" / "Manage.tsx"
    if page.exists():
        offered = page.read_text()
        absent = sorted(k for k in raised if f'"{k}"' not in offered)
        assert not absent, f"Contacts page offers no {absent}, which the watchers raise"
    print("  notify: recipients by kind ✓ · once per run ✓ · approvals and actions from the record ✓ "
          "· unconfigured skipped, not held ✓ · retried, then failed ✓ · one digest a day ✓ "
          "· every kind raised can be chosen ✓ · reports go as PDF and workbook, by email only ✓")
    print("notify ok")


if __name__ == "__main__":
    if "--check" in sys.argv:
        from core import config
        config.fixtures_only(__file__, "SIGAP_NOTIFY_CHECK")
        demo()
    else:
        if "--test" in sys.argv:
            print(f"queued {queue_test('cli@localhost')} test message(s)")
        if "--digest" in sys.argv:
            print(f"queued {queue_digest()} digest message(s)")
        print(deliver_summary())
