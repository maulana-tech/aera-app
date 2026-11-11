"""Tells people. The record holds what the team did; this reads the record
and delivers it. Nothing reaches a person except through here, and every
figure in a message (status, what waits, its value, who may approve it) comes
from the tables, never from a model's prose.

Kinds of message:
  handling  a work item finished: what was done, what waits for a person.
  digest    once a day: money in and out, what waits, what the guardian blocked.
  outreach  an approved message from the team to a contact (settle.py queued it).
  delivery  a finished document to the customer who paid (settle.py queued it).
  test      on request, to prove a channel works.

    python3 notify.py            # deliver what is queued
    python3 notify.py --digest   # queue today's digest, then deliver
    python3 notify.py --check    # the self-check, on a scratch database
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

from clients import channels
from core import store
from core.config import CFG

MAX_ATTEMPTS = 3
OUTCOME_CHARS = 900


def _usd(n: float) -> str:
    return f"${float(n or 0):,.2f}"


def _who_may_approve(value: float) -> str:
    from core.identity import ROLE_LIMITS
    for role, limit in sorted(ROLE_LIMITS.items(), key=lambda kv: kv[1]):
        if limit and value <= limit:
            return f"{role} or above"
    return "an owner"


def _recipients(kind: str) -> List[dict]:
    """Team contacts whose notify_for covers this kind ('*' is every kind)."""
    out = []
    for c in store.list_contacts():
        if c["role"] not in ("team", "approver") or not c.get("email"):
            continue
        kinds = {k.strip() for k in (c.get("notify_for") or "*").split(",")}
        if "*" in kinds or kind in kinds:
            out.append(c)
    return out


def _excerpt(text: str, n: int = OUTCOME_CHARS) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


def handling_message(run: dict) -> Dict[str, str]:
    decision = run.get("decision") or {}
    waiting = [a for a in run.get("actions", []) if a["status"] == "pending"]
    blocked = [a for a in run.get("actions", []) if a["status"] == "blocked"]
    head = {"done": "Done", "partial": "Stopped early", "held": "Held", "failed": "Failed"}.get(run["status"], run["status"])
    lines = [run["title"], f"{head} · {run['kind']} · run {run['id']}", ""]
    if decision.get("recommendation"):
        lines += ["The supervisor's outcome, as written:", _excerpt(decision["recommendation"]), ""]
    elif run.get("error"):
        lines += [run["error"], ""]
    if waiting:
        lines.append(f"Waiting for a person: {len(waiting)} action(s)")
        for a in waiting:
            lines.append(f"  - {a['kind']} · {_usd(a['value_usd'])} · needs {_who_may_approve(a['value_usd'])}"
                         f" · {a.get('reason') or ''}")
        lines.append("")
    if blocked:
        lines.append(f"Blocked by the guardian: {len(blocked)} action(s)")
        for a in blocked:
            lines.append(f"  - {a['kind']} · {a.get('reason') or ''}")
        lines.append("")
    proofs = run.get("proofs") or []
    if proofs:
        ok = sum(1 for p in proofs if p["verdict"] == "attested")
        lines.append(f"Model calls verified in a TEE: {ok}/{len(proofs)}")
    lines.append(f"Open it: {CFG.web_url}/work/{run['id']}")
    tag = "action needed" if waiting else head.lower()
    return {"subject": f"[AERA] {tag}: {run['title']}"[:180], "body": "\n".join(lines)}


def queue_handling(run_id: str) -> int:
    run = store.get_run(run_id)
    if not run or run["status"] == "running":
        return 0
    msg = handling_message(run)
    n = 0
    for c in _recipients(run["kind"]):
        n += store.enqueue_notification(f"handling:{run_id}:{run['status']}:email:{c['email']}", "handling",
                                        "email", c["email"], msg["subject"], msg["body"], run_id)
    for ch in channels.team_channels():
        n += store.enqueue_notification(f"handling:{run_id}:{run['status']}:{ch}", "handling", ch, ch,
                                        msg["subject"], msg["body"], run_id)
    return n


def digest_message(now: Optional[datetime] = None) -> Dict[str, str]:
    now = now or datetime.now(timezone.utc)
    led = store.ledger(1)
    money_in = sum(m["total"] for m in led["money"] if m["direction"] == "in")
    money_out = sum(m["total"] for m in led["money"] if m["direction"] == "out" and m["status"] == "sent")
    waiting = store.list_actions(status="pending", limit=50)
    day = now.strftime("%d %b %Y")
    lines = [f"AERA, {day}", "",
             f"Last 24 hours: {_usd(money_in)} in · {_usd(money_out)} out · model spend {_usd(led['model_spend_usd'])}"
             f" · {led['blocked_by_guardian']} blocked by the guardian",
             f"Waiting for a person: {len(waiting)} action(s), {_usd(sum(a['value_usd'] for a in waiting))} in all", ""]
    for a in waiting[:8]:
        lines.append(f"  - {a['kind']} {_usd(a['value_usd'])} for \"{a['work_title']}\"  {CFG.web_url}/work/{a['run_id']}")
    return {"subject": f"[AERA] Daily digest, {day}", "body": "\n".join(lines), "key": now.strftime("%Y-%m-%d")}


def queue_digest(now: Optional[datetime] = None) -> int:
    msg = digest_message(now)
    n = 0
    for c in _recipients("digest"):
        n += store.enqueue_notification(f"digest:{msg['key']}:email:{c['email']}", "digest", "email",
                                        c["email"], msg["subject"], msg["body"])
    for ch in channels.team_channels():
        n += store.enqueue_notification(f"digest:{msg['key']}:{ch}", "digest", ch, ch, msg["subject"], msg["body"])
    return n


def queue_test(requested_by: str) -> int:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body = f"Sent on request by {requested_by} at {stamp}. If you can read this, alerts reach this channel."
    targets = [(ch, ch) for ch in channels.team_channels()]
    if not channels.missing("email"):
        targets.append(("email", requested_by))
    return sum(store.enqueue_notification(f"test:{stamp}:{ch}:{addr}", "test", ch, addr, "[AERA] Test alert", body)
               for ch, addr in targets)


def files_for(specs: Optional[List[dict]]) -> list:
    """Render what a message names: {"document": id, "format": "pdf"}."""
    import settle
    out = []
    for spec in specs or []:
        doc = store.get_file(str(spec.get("document") or ""))
        if not doc:
            raise LookupError(f"document {spec.get('document')} is not on record")
        title = doc["name"][4:] if doc["name"].startswith("doc:") else doc["name"]
        out.append((settle.render_document(doc), f"{title[:60]}.pdf", "application/pdf"))
    return out


#: Messages that leave the business. Outside production they go to one test
#: address (AERA_EXTERNAL_REDIRECT) or nowhere, so a demo never emails a stranger.
EXTERNAL_KINDS = ("outreach", "delivery")


def _external_target(n: dict):
    """(address to use, why it changed) for an outward message."""
    import os
    if n["kind"] not in EXTERNAL_KINDS or n["channel"] != "email":
        return n["address"], None
    if CFG.production:
        allowed = [d.strip().lower() for d in os.environ.get("AERA_EXTERNAL_DOMAINS", "").split(",") if d.strip()]
        if allowed and n["address"].rsplit("@", 1)[-1].lower() not in allowed:
            return None, f"{n['address']} is outside AERA_EXTERNAL_DOMAINS"
        return n["address"], None
    redirect = os.environ.get("AERA_EXTERNAL_REDIRECT", "").strip()
    if not redirect:
        return None, "not production and no AERA_EXTERNAL_REDIRECT: outward messages are not sent"
    return redirect, f"redirected from {n['address']} (not production)"


def deliver(limit: int = 50) -> Dict[str, int]:
    """Send what is queued. A channel that is not set up marks its messages
    skipped, with what it lacks, rather than holding them."""
    counts = {"sent": 0, "failed": 0, "skipped": 0, "retry": 0}
    for n in store.pending_notifications(limit):
        address, why = _external_target(n)
        if address is None:
            store.mark_notification(n["id"], "skipped", why)
            counts["skipped"] += 1
            continue
        if why:
            n = {**n, "address": address, "body": f"[{why}]\n\n{n['body']}"}
        if n["channel"] in ("slack", "telegram", "webhook"):
            # Somebody else's servers: personal data is replaced first (core/privacy.py).
            from core import privacy
            (subject, body), how = privacy.redact_many([n["subject"], n["body"]])
            n = {**n, "subject": subject,
                 "body": body if how == "redacted" else f"{body}\n\n[not redacted: {how}]"}
            store.record_privacy_event(n["id"], n["channel"], "redacted" if how == "redacted" else "not_redacted",
                                       "" if how == "redacted" else how)
        try:
            files = files_for(n.get("attachments")) if n["channel"] == "email" else []
            ref = channels.send(n["channel"], n["address"], n["subject"], n["body"],
                                {"kind": n["kind"], "run_id": n["run_id"],
                                 "url": f"{CFG.web_url}/work/{n['run_id']}" if n["run_id"] else CFG.web_url},
                                files=files)
            store.mark_notification(n["id"], "sent", reference=ref)
            counts["sent"] += 1
        except channels.NotConfigured as e:
            store.mark_notification(n["id"], "skipped", str(e))
            counts["skipped"] += 1
        except LookupError as e:
            store.mark_notification(n["id"], "failed", str(e))
            counts["failed"] += 1
        except channels.DeliveryFailed as e:
            final = n["attempts"] + 1 >= MAX_ATTEMPTS
            store.mark_notification(n["id"], "failed" if final else "pending", str(e))
            counts["failed" if final else "retry"] += 1
    return counts


def deliver_summary() -> str:
    c = deliver()
    return " · ".join(f"{v} {k}" for k, v in c.items() if v) or "nothing queued"


def check() -> None:
    from core import business, registry
    from core.actions import raise_action
    store.save_profile(business.EXAMPLE, by="check")
    store.add_contact("Owner", "team", "owner@lumen.example", notify_for="*")
    wid = store.record_work_item("request", "Buy data", "api", {})
    rid = store.start_run(wid)
    with registry.bind_run(rid):
        raise_action("payment", {"receiver": "v.testnet", "amount_usd": 40}, {"verdict": "warn", "reasons": [
            {"rule": "cap", "verdict": "warn", "detail": "over the cap"}]}, value_usd=40, execute=False)
    store.close_run(rid, "done", {"recommendation": "STATUS: waiting for a person."})
    msg = handling_message(store.get_run(rid))
    assert "action needed" in msg["subject"] and "$40.00" in msg["body"] and "operator or above" in msg["body"], msg
    assert queue_handling(rid) >= 1 and queue_handling(rid) == 0, "never queued twice"
    d = digest_message()
    assert "Waiting for a person: 1" in d["body"], d["body"]
    import os
    os.environ.pop("AERA_EXTERNAL_REDIRECT", None)
    assert _external_target({"kind": "outreach", "channel": "email", "address": "x@y.z"})[0] is None
    os.environ["AERA_EXTERNAL_REDIRECT"] = "me@test.example"
    assert _external_target({"kind": "delivery", "channel": "email", "address": "x@y.z"})[0] == "me@test.example"
    assert _external_target({"kind": "handling", "channel": "email", "address": "t@lumen.example"})[0] == "t@lumen.example"
    print("notify ok: figures from the record ✓ · queued once ✓ · digest ✓")


if __name__ == "__main__":
    if "--check" in sys.argv:
        from core.config import fixtures_only
        fixtures_only(__file__, "AERA_NOTIFY_CHECK")
        check()
    elif "--digest" in sys.argv:
        print(f"{queue_digest()} queued; {deliver_summary()}")
    else:
        print(deliver_summary())
