"""Finding customers and talking to them: the pipeline from a public page to a paid order.

    found (new) -> contacted -> replied -> interested -> won
                           \\-> no_reply      \\-> lost        (and opted_out, from any stage, for good)

What is decided here, in code, and not by a model:

  A lead is real.      Saved only with the public page it was found on, and an e-mail address only when
                       that page shows it. A model cannot invent a person to write to.
  Nobody twice.        One lead per address; the same company's other people are shown, not duplicated.
  Stop means stop.     A reply asking to stop opts the address out at once, without a model reading it;
                       the guardian blocks every later message to it, to anyone, forever.
  The pace.            The first message to a prospect waits for a person. Follow-ups go on the team's
                       authority, on the profile's schedule, only while nobody has answered, and stop after
                       the profile's number. Cold messages a day are capped (profile, and a hard ceiling).
  What happened.       A lead is `contacted` when the e-mail was delivered, not when it was drafted; it is
                       `won` when the address on a paid order is the lead's, not when an agent says so.
  Replies are data.    A reply becomes a work item that carries only who wrote and when. The words are read
                       with a tool that marks the run as having read outside text (guardian: untrusted_input).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from core import business, store

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
#: A reply that asks not to be written to again. Read in code, before and instead of any model.
_STOP = re.compile(
    r"\b(unsubscribe|remove me|take me off|stop (e-?mailing|emailing|contacting|writing|sending)|do not (e-?mail|contact|write)"
    r"|don'?t (e-?mail|contact|write to) me|no more (e-?mails|emails|messages)|opt(?:-| )?out"
    r"|berhenti (mengirim|menghubungi)|jangan (hubungi|kirim|email)|hapus (saya|email saya)|tidak usah (hubungi|kirim))\b",
    re.I)
_AUTO_SUBJECT = re.compile(r"(out of (the )?office|automatic reply|auto.?reply|autoreply|away from|on leave|"
                           r"delivery status notification|undeliverable|mail delivery (failed|subsystem)|returned mail)", re.I)
_BOUNCE = re.compile(r"(undeliverable|delivery status notification|mail delivery (failed|subsystem)|returned mail|"
                     r"address not found|user unknown|no such user)", re.I)
_QUOTE_START = re.compile(r"(?im)^(on .{4,200}wrote:|pada .{4,200}menulis:|-----\s*original message\s*-----|from: .+@.+)\s*$")

#: How long after the last follow-up a lead that never answered is closed as no_reply.
CLOSE_AFTER_DAYS = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _domain(url_or_email: str) -> Optional[str]:
    v = (url_or_email or "").strip().lower()
    if "@" in v and "/" not in v:
        host = v.rsplit("@", 1)[1]
    else:
        host = urlparse(v if "//" in v else "https://" + v).hostname or ""
    host = host[4:] if host.startswith("www.") else host
    return host or None


def settings(profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    p = profile or business.current()
    return p.get("prospecting") or dict(business.DEFAULTS["prospecting"])


# ------------------------------------------------------------------ finding
def page_shows(email: str, url: str) -> Tuple[bool, str]:
    """Whether the public page at `url` shows `email` (also written as name [at] domain [dot] com)."""
    from clients import feeds
    from tools import research
    u = urlparse((url or "").strip())
    if u.scheme not in ("http", "https") or not u.hostname:
        return False, "the source must be an http(s) page"
    if not research._public_host(u.hostname):
        return False, "the source is not a public address"
    try:
        raw, _ = feeds.get(u.geturl(), ttl=900, timeout=20, as_json=False)
    except feeds.FeedError as e:
        return False, f"the source page could not be read ({e})"
    from core import registry
    registry.mark_untrusted()
    text = research.page_text(raw).lower()
    text = re.sub(r"\s*[\[(]\s*at\s*[\])]\s*", "@", text)
    text = re.sub(r"\s*[\[(]\s*dot\s*[\])]\s*", ".", text)
    found = email.lower() in text or email.lower() in raw.lower()
    return found, "" if found else "the source page does not show this address"


def save_lead(name: str, email: str, company: str, source_url: str, why_fit: str, fit_score: int,
              title: str = "", website: str = "", by: str = "agent") -> Dict[str, Any]:
    """{"lead": row} or {"refused": why}. The person becomes a contact with the role `prospect`."""
    name, company = " ".join((name or "").split())[:120], " ".join((company or "").split())[:160]
    email = (email or "").strip().lower()
    if not company:
        return {"refused": "a lead needs the company (or the person's business) name"}
    if not source_url:
        return {"refused": "a lead needs the public page it was found on (source_url)"}
    if email and not _EMAIL.fullmatch(email):
        return {"refused": f"'{email}' is not an e-mail address"}
    if not email:
        return {"refused": "a lead without an e-mail address cannot be contacted; find the page that shows one"}
    out = store.opted_out(email)
    if out:
        return {"refused": f"{email} asked not to be contacted ({out['at'][:10]}); it is never saved as a lead again"}
    known = store.lead_by_email(email)
    if known:
        return {"lead": known, "note": f"already a lead ({known['stage']})"}
    contact = next((c for c in store.find_contact(email) if c["email"] == email), None)
    if contact and contact["role"] in ("customer", "vendor", "team", "approver", "contributor"):
        return {"refused": f"{email} is already a {contact['role']} on record, not a prospect"}
    shown, why = page_shows(email, source_url)
    if not shown:
        return {"refused": f"not saved: {why}. Save only an address the page itself shows; do not guess one "
                           "from a name and a domain"}
    domain = _domain(website or email)
    same = store.leads_at_domain(domain) if domain else []
    contact = contact or store.add_contact(name or email.split("@")[0], "prospect", email, title=title[:120] or None,
                                           notes=f"found on {source_url}")
    lead = store.add_lead(contact["id"], company=company, website=(website or "").strip()[:300] or None, domain=domain,
                          source_url=source_url.strip()[:500], why_fit=(why_fit or "").strip()[:1000],
                          fit_score=max(0, min(int(fit_score or 0), 100)), created_by=by)
    note = "new lead saved"
    if same:
        note += f"; {len(same)} other lead(s) at {domain} already: " + ", ".join(f"{x['name']} ({x['stage']})" for x in same[:3])
    return {"lead": lead, "note": note}


# ---------------------------------------------------------------- writing
def outreach_kind(lead: Dict[str, Any]) -> str:
    """first | follow_up | conversation, for the lead as it stands."""
    if lead["stage"] in ("replied", "interested"):
        return "conversation"
    return "first" if lead["step"] == 0 else "follow_up"


def guardian_reasons(payload: Dict[str, Any], profile: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """(rule, verdict, detail) for a message to a prospect, from the record. Called by core/guardian.py."""
    out: List[Tuple[str, str, str]] = []
    lead = store.get_lead(str(payload.get("lead_id") or ""))
    if not lead:
        return [("lead", "block", "no such lead on record")]
    if (lead.get("email") or "").lower() != str(payload.get("to") or "").lower():
        out.append(("recipient", "block", "the recipient is not the lead's address on record"))
    if lead["stage"] in store.LEAD_CLOSED:
        out.append(("lead_stage", "block", f"the lead is {lead['stage']}: nobody writes to it again"))
        return out
    s = settings(profile)
    kind = outreach_kind(lead)
    waiting = [a for a in store.list_actions(kind="message", limit=500)
               if a["status"] in ("pending", "approved") and (a["payload"] or {}).get("lead_id") == lead["id"]
               and (a["payload"] or {}).get("step") == lead["step"]
               and (a["payload"] or {}).get("subject") != payload.get("subject")]
    if waiting and kind != "conversation":
        out.append(("one_at_a_time", "block", f"another message to this lead is already waiting ({waiting[0]['id']}, "
                                              f"{waiting[0]['status']}); it is decided before a second one is written"))
    if kind in ("first", "follow_up"):
        sent_today = len(store.outreach_today())
        if sent_today >= s["per_day"]:
            out.append(("outreach_cap", "block", f"{sent_today} cold message(s) today already; the profile allows "
                                                 f"{s['per_day']} a day. Try again tomorrow"))
        else:
            out.append(("outreach_cap", "allow", f"{sent_today} of {s['per_day']} cold message(s) used today"))
    if kind == "first":
        out.append(("first_message", "warn", "the first message to a prospect waits for a person"))
    elif kind == "follow_up":
        if lead["step"] > s["follow_ups"]:
            out.append(("follow_ups", "block", f"{lead['step'] - 1} follow-up(s) sent already; the profile allows "
                                               f"{s['follow_ups']} without an answer"))
        due = lead.get("next_follow_up_at")
        if due and due > _iso(_now() + timedelta(hours=1)):
            out.append(("follow_up_early", "block", f"the next follow-up is due {due[:16].replace('T', ' ')} UTC, not before"))
        elif lead["step"] <= s["follow_ups"]:
            out.append(("follow_up", "allow", f"follow-up {lead['step']} of {s['follow_ups']}, on schedule, "
                                              "to someone a person already approved writing to"))
    else:
        out.append(("conversation", "allow", "an answer to a prospect who wrote back"))
    review = payload.get("compliance") or {}
    if review.get("verdict") == "block":
        out.append(("compliance", "block", "the compliance check blocks it: " + "; ".join(
            f"{f.get('rule')}: \"{f.get('quote')}\"" for f in review.get("findings", [])[:3])))
    elif review.get("verdict") == "warn":
        out.append(("compliance", "warn", "the compliance check has findings a person should read: " + "; ".join(
            f"{f.get('rule')}: \"{f.get('quote')}\"" for f in review.get("findings", [])[:3])))
    return out


def footer(profile: Optional[Dict[str, Any]] = None) -> str:
    p = profile or business.current()
    return (f"\n\n--\n{p.get('name') or 'AERA'}\n"
            "If you would rather not hear from us, reply \"unsubscribe\" and we will not write again.")


def on_delivered(action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """An e-mail to a lead was delivered: move the lead along and set its next follow-up."""
    p = action.get("payload") or {}
    lead = store.get_lead(str(p.get("lead_id") or ""))
    if not lead or lead["stage"] in store.LEAD_CLOSED:
        return lead
    now = _now()
    if lead["stage"] in ("replied", "interested"):
        return store.update_lead(lead["id"], last_contact_at=_iso(now))
    s = settings()
    step = lead["step"] + 1
    first = lead.get("first_contact_at") or _iso(now)
    try:
        start = datetime.fromisoformat(first)
    except ValueError:
        start = now
    days = s["follow_up_days"]
    if step <= s["follow_ups"] and step - 1 < len(days):
        nxt = max(start + timedelta(days=days[step - 1]), now + timedelta(days=1))
    else:
        nxt = now + timedelta(days=CLOSE_AFTER_DAYS)          # the last one: close it if nobody answers
    return store.update_lead(lead["id"], stage="contacted", step=step, first_contact_at=first,
                             last_contact_at=_iso(now), next_follow_up_at=_iso(nxt))


def due_follow_ups() -> Dict[str, int]:
    """Raise a work item for each follow-up that is due; close leads whose last follow-up went unanswered."""
    p = business.current()
    if p.get("kill_switch") or not p.get("name"):
        return {"raised": 0, "closed": 0}
    s = settings(p)
    raised = closed = 0
    for lead in store.leads_due_follow_up(_iso(_now())):
        if lead["step"] > s["follow_ups"]:
            store.update_lead(lead["id"], stage="no_reply", next_follow_up_at=None,
                              note=f"no answer to {lead['step']} message(s)")
            closed += 1
            continue
        wid = store.record_work_item(
            "follow_up", f"Follow up with {lead['name']} at {lead['company']} ({lead['step']} of {s['follow_ups']})",
            "schedule", {"lead_id": lead["id"], "follow_up": lead["step"], "of": s["follow_ups"],
                         "last_contact_at": lead.get("last_contact_at")},
            dedup_key=f"follow_up:{lead['id']}:{lead['step']}")
        raised += 1 if wid else 0
    return {"raised": raised, "closed": closed}


# --------------------------------------------------------------- listening
def _fresh_text(body: str) -> str:
    """What the sender wrote, without the quoted thread below it."""
    lines = []
    for line in (body or "").splitlines():
        if line.lstrip().startswith(">") or _QUOTE_START.match(line.strip()):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def classify(subject: str, body: str, headers: Optional[Dict[str, str]] = None) -> str:
    """unsubscribe | auto_reply | bounce | reply, from the words and headers alone."""
    h = {k.lower(): str(v) for k, v in (headers or {}).items()}
    if _BOUNCE.search(subject or "") or h.get("content-type", "").startswith("multipart/report"):
        return "bounce"
    if h.get("auto-submitted", "no").lower() not in ("", "no") or _AUTO_SUBJECT.search(subject or "") \
            or "precedence" in h and h["precedence"].lower() in ("auto_reply", "bulk", "junk"):
        return "auto_reply"
    fresh = _fresh_text(body)[:600]
    if _STOP.search(fresh) or _STOP.search(subject or ""):
        return "unsubscribe"
    return "reply"


def receive(message_id: str, sender: str, subject: str, body: str, via: str,
            headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """One e-mail in. Returns what was done with it."""
    name, addr = parseaddr(sender or "")
    addr = addr.strip().lower()
    if not _EMAIL.fullmatch(addr):
        return {"stored": False, "why": "no sender address"}
    message_id = (message_id or "").strip() or f"{addr}:{subject}:{len(body or '')}"
    kind = classify(subject, body, headers)
    contact = next((c for c in store.find_contact(addr) if c["email"] == addr), None)
    lead = store.lead_by_email(addr)
    if kind == "bounce":
        # The bounce comes from the mail system, not the lead: the lead is found in the bounce text.
        hit = next((store.lead_by_email(e) for e in _EMAIL.findall(body or "") if store.lead_by_email(e)), None)
        lead, contact = hit or lead, (store.get_contact(hit["contact_id"]) if hit else contact)
    stored_kind = kind if (contact or kind == "bounce") else "unknown_sender"
    row = store.record_inbound(message_id, addr, name or "", subject or "", body or "", via,
                               "auto_reply" if stored_kind == "bounce" else stored_kind,
                               contact["id"] if contact else None, lead["id"] if lead else None)
    if row is None:
        return {"stored": False, "why": "already received"}
    out: Dict[str, Any] = {"stored": True, "inbound_id": row["id"], "kind": stored_kind,
                           "lead_id": lead["id"] if lead else None}
    if kind == "unsubscribe":
        # Honoured for any sender, known or not: an address that asks to be left alone is left alone.
        store.opt_out(addr, "asked in a reply: " + _fresh_text(body)[:160].replace("\n", " "), via)
        if lead:
            store.update_lead(lead["id"], stage="opted_out", next_follow_up_at=None, last_reply_at=row["received_at"],
                              note="asked not to be contacted")
        out["opted_out"] = True
        return out
    if kind == "bounce":
        if lead and lead["stage"] not in store.LEAD_CLOSED:
            store.update_lead(lead["id"], stage="lost", next_follow_up_at=None, note="the address bounced")
            out["closed"] = "bounced"
        return out
    if kind == "auto_reply" or not contact or contact["role"] == "team":
        return out
    if lead and lead["stage"] not in store.LEAD_CLOSED:
        store.update_lead(lead["id"], stage="replied" if lead["stage"] in ("new", "contacted") else lead["stage"],
                          last_reply_at=row["received_at"], next_follow_up_at=None)
    who = f"{contact['name']}" + (f" ({lead['company']})" if lead else "")
    wid = store.record_work_item(
        "reply", f"Reply from {who}: {(subject or '(no subject)')[:80]}", via,
        {"inbound_id": row["id"], "contact_id": contact["id"], "lead_id": lead["id"] if lead else None,
         "from_role": contact["role"], "received_at": row["received_at"],
         "read_it_with": "read_reply(inbound_id)"},
        dedup_key=f"reply:{row['id']}")
    store.set_inbound_work(row["id"], wid)
    out["work_item_id"] = wid
    return out


# ------------------------------------------------------------------- money
def won_from_order(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A paid order whose customer is a lead's address wins the lead."""
    cust = str(order.get("customer") or "").strip().lower()
    lead = store.lead_by_email(cust) if "@" in cust else None
    if not lead or lead["stage"] in ("won", "opted_out"):
        return None
    return store.update_lead(lead["id"], stage="won", order_id=order["id"], next_follow_up_at=None,
                             note=f"paid order {order['id']}")


def funnel(days: int = 30) -> Dict[str, Any]:
    """The pipeline in numbers, from the record: how many were found, written to, answered, won, and what the
    model work on prospecting cost per lead and per win."""
    since = _iso(_now() - timedelta(days=days))
    leads = [x for x in store.list_leads(limit=5000) if x["created_at"] >= since]
    counts = {s: 0 for s in store.LEAD_STAGES}
    for x in leads:
        counts[x["stage"]] += 1
    contacted = sum(1 for x in leads if x["step"] > 0)
    replied = sum(1 for x in leads if x.get("last_reply_at"))
    won = counts["won"]
    revenue = 0.0
    for x in leads:
        if x.get("order_id"):
            o = store.get_order(x["order_id"])
            revenue += float(o["amount_usd"]) if o else 0.0
    runs = {x["created_by"][4:] for x in leads if (x.get("created_by") or "").startswith("run:")}
    for w in ("follow_up", "reply"):
        for r in store.list_runs(500):
            if r.get("kind") == w and (r.get("started_at") or "") >= since:
                runs.add(r["id"])
    spend = 0.0
    for rid in runs:
        r = store.get_run(rid)
        spend += float((r or {}).get("cost_usd") or 0)
    return {"days": days, "leads": len(leads), "stages": counts, "contacted": contacted, "replied": replied,
            "won": won, "opted_out": counts["opted_out"],
            "reply_rate": round(replied / contacted, 3) if contacted else None,
            "win_rate": round(won / contacted, 3) if contacted else None,
            "revenue_usd": round(revenue, 2), "model_spend_usd": round(spend, 4),
            "cost_per_lead_usd": round(spend / len(leads), 4) if leads else None,
            "cost_per_win_usd": round(spend / won, 4) if won else None,
            "opted_out_total": len(store.list_optouts())}


# -------------------------------------------------------------- self-check
def demo() -> None:
    from clients import feeds
    from core import guardian, registry
    p = {**business.EXAMPLE, "prospecting": {"ideal_customer": "Agencies in Jakarta", "per_day": 2, "follow_ups": 2,
                                              "follow_up_days": [3, 7]}}
    store.save_profile(p, by="check")
    page = "https://studio-example.co.id/contact"
    feeds.prime(page, "<html><body><h1>Studio Example</h1><p>Write to hello [at] studio-example.co.id</p>"
                      "<p>Rina, founder: rina@studio-example.co.id</p></body></html>")
    import tools.research as research
    real_public = research._public_host
    research._public_host = lambda host: True
    try:
        guessed = save_lead("Budi", "budi@studio-example.co.id", "Studio Example", page, "agency", 70)
        assert "refused" in guessed and "does not show" in guessed["refused"], guessed
        ok = save_lead("Rina", "rina@studio-example.co.id", "Studio Example", page, "a 12-person agency in Jakarta", 80,
                       title="Founder", website="https://studio-example.co.id", by="run:run_check")
        lead = ok["lead"]
        assert lead["stage"] == "new" and lead["domain"] == "studio-example.co.id" and lead["name"] == "Rina", lead
        assert save_lead("Rina", "rina@studio-example.co.id", "Studio Example", page, "", 0)["note"].startswith("already")
        obf = save_lead("", "hello@studio-example.co.id", "Studio Example", page, "", 50)
        assert "lead" in obf and "1 other lead" in obf["note"], obf
    finally:
        research._public_host = real_public
        feeds.forget(page)
    print("  leads: an address the page does not show is refused ✓ · [at] spelling read ✓ · one lead per address ✓")

    msg = {"to": lead["email"], "lead_id": lead["id"], "subject": "Hi", "body": "Hello Rina", "cold": True,
           "compliance": {"verdict": "pass"}}
    first = guardian.check_action("message", msg, profile=p, record=False)
    assert first["verdict"] == "warn" and any(r["rule"] == "first_message" for r in first["reasons"]), first
    wrong = guardian.check_action("message", {**msg, "to": "someone@else.example"}, profile=p, record=False)
    assert wrong["verdict"] == "block", wrong

    # delivered: contacted, follow-up 1 due in 3 days; an early follow-up is refused
    lead = on_delivered({"payload": {"lead_id": lead["id"]}})
    assert lead["stage"] == "contacted" and lead["step"] == 1 and lead["next_follow_up_at"] > _iso(_now() + timedelta(days=2))
    early = guardian.check_action("message", msg, profile=p, record=False)
    assert early["verdict"] == "block" and any(r["rule"] == "follow_up_early" for r in early["reasons"]), early
    store.update_lead(lead["id"], next_follow_up_at=_iso(_now() - timedelta(minutes=1)))
    on_time = guardian.check_action("message", msg, profile=p, record=False)
    assert on_time["verdict"] == "allow", on_time
    print("  writing: first message waits for a person ✓ · wrong recipient blocked ✓ · follow-up only when due ✓")

    # the job raises the due follow-up once
    assert due_follow_ups()["raised"] == 1 and due_follow_ups()["raised"] == 0
    # cap: two cold messages pending today fill a cap of two
    wid = store.record_work_item("request", "outreach", "api", {})
    rid = store.start_run(wid)
    from core.actions import raise_action
    with registry.bind_run(rid):
        for i in range(2):
            raise_action("message", {**msg, "subject": f"Hi {i}", "step": 1}, {"verdict": "warn", "reasons": []}, execute=False)
    second = guardian.check_action("message", {**msg, "subject": "A different first line"}, profile=p, record=False)
    assert any(r["rule"] == "one_at_a_time" for r in second["reasons"]), second
    capped = guardian.check_action("message", msg, profile=p, record=False)
    assert capped["verdict"] == "block" and any(r["rule"] == "outreach_cap" for r in capped["reasons"]), capped
    print("  pace: due follow-ups raised once ✓ · one message waiting per lead ✓ · daily cold cap blocks ✓")

    # replies: an answer becomes a work item; the words stay out of it
    r = receive("<m1@x>", "Rina <rina@studio-example.co.id>", "Re: Hi", "Sounds good, what does it cost?\n\n"
                "On Mon, 9 Nov 2026 at 10:00, Lumen wrote:\n> Hello Rina", "manual")
    assert r["kind"] == "reply" and r["work_item_id"], r
    assert store.get_lead(lead["id"])["stage"] == "replied"
    item = next(w for w in store.list_work_items(50) if w["id"] == r["work_item_id"])
    assert "cost" not in str(item["payload"]), "the reply's words are not in the work item"
    assert receive("<m1@x>", "rina@studio-example.co.id", "Re: Hi", "again", "manual")["why"] == "already received"
    talk = guardian.check_action("message", {**msg, "cold": False}, profile=p, record=False)
    assert talk["verdict"] == "allow" and any(x["rule"] == "conversation" for x in talk["reasons"]), talk
    # out of office does not count as an answer; a stop does, for good
    other = store.lead_by_email("hello@studio-example.co.id")
    oo = receive("<m2@x>", "hello@studio-example.co.id", "Out of Office: back Monday", "I am away", "manual")
    assert oo["kind"] == "auto_reply" and store.get_lead(other["id"])["stage"] == "new"
    stop = receive("<m3@x>", "hello@studio-example.co.id", "Re: Hi", "Please remove me from your list.", "manual")
    assert stop.get("opted_out") and store.get_lead(other["id"])["stage"] == "opted_out"
    blocked = guardian.check_action("message", {"to": "hello@studio-example.co.id", "body": "one more"}, profile=p, record=False)
    assert blocked["verdict"] == "block" and any(x["rule"] == "opted_out" for x in blocked["reasons"]), blocked
    assert "refused" in save_lead("H", "hello@studio-example.co.id", "Studio Example", page, "", 1)
    stranger = receive("<m4@x>", "spam@nowhere.example", "Buy now", "cheap", "manual")
    assert stranger["kind"] == "unknown_sender" and not stranger.get("work_item_id")
    assert classify("Undeliverable: Hi", "550 user unknown") == "bounce"
    assert classify("Re: Hi", "Not now, maybe next quarter.\n> unsubscribe link below") == "reply", "a quoted stop is not a stop"
    print("  replies: work item without the words ✓ · once ✓ · out-of-office ignored ✓ · stop honoured forever ✓ "
          "· strangers start no work ✓")

    order = store.create_order("ord_check_lead", "brief", 15.0, {}, customer="rina@studio-example.co.id", status="paid")
    won = won_from_order(order)
    assert won["stage"] == "won" and won["order_id"] == "ord_check_lead"
    f = funnel(30)
    assert f["won"] == 1 and f["contacted"] == 1 and f["revenue_usd"] == 15.0 and f["opted_out"] == 1, f
    print("  money: a paid order from the lead's address wins it ✓ · funnel from the record ✓")
    print("prospects ok")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_PROSPECTS_CHECK")
    demo()
