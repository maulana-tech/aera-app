"""Legal & Compliance, computed in code: what a text promises, which policy pages exist, what personal data AERA holds.

Three things a small business skips until it hurts, each answered from the record rather than from a model:

  review(text)       the rules a text breaks, each with the exact words that break it: the profile's forbidden
                     claims, unconditional promises, advice that sounds final, another contact's details,
                     instruction-like phrases. Findings are grounded: every one quotes the text.
  legal_pages()      which of the pages a business that sells online needs (terms, privacy, refund) exist among
                     its files and documents, and which are missing and why it needs them.
  register()         a record of processing: each kind of personal data AERA holds, where, how many records,
                     the oldest, why it is kept and who else sees it. Counted from the tables, never estimated.

The Compliance agent explains and drafts; it cannot publish a page or change a rule. None of this is legal advice,
and every document it files says so.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core import business, store

DISCLAIMER = "Prepared by AERA's Compliance agent from the business's own records. Not legal advice: a lawyer should review it."

_PROMISE = re.compile(r"\b(guarantee[ds]?|100\s?%|risk[- ]free|no risk|always works|never fails|will (?:double|triple|rank)|"
                      r"certain(?:ly)? (?:to|will)|money[- ]back)\b", re.I)
_FINAL_ADVICE = re.compile(r"\b(legal advice|tax advice|financial advice|you (?:must|should) (?:file|sue|invest)|"
                           r"this is legally|is fully compliant|is (?:legal|lawful) everywhere)\b", re.I)
_NOT_ADVICE = re.compile(r"\bnot (?:legal|tax|financial) advice\b", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")


def _quote(text: str, m: re.Match, pad: int = 40) -> str:
    a, b = max(0, m.start() - pad), min(len(text), m.end() + pad)
    return ("…" if a else "") + text[a:b].replace("\n", " ").strip() + ("…" if b < len(text) else "")


def review(text: str, profile: Optional[Dict[str, Any]] = None, *, customer: str = "") -> Dict[str, Any]:
    """Findings for one text, worst first. `customer` is the e-mail the text is meant for (its own details are fine)."""
    from core import guardian
    p = profile or business.current()
    text = text or ""
    findings: List[Dict[str, str]] = []
    low = text.lower()

    for f in p["constraints"]["forbidden"]:
        words = [w for w in re.findall(r"[a-z0-9]+", f.lower()) if len(w) > 3]
        if words and all(w in low for w in words):
            first = re.search(re.escape(words[0]), low)
            findings.append({"rule": "forbidden", "verdict": "block", "detail": f"the profile forbids: {f}",
                             "quote": _quote(text, first) if first else ""})
    m = guardian.INJECTION.search(text)
    if m:
        findings.append({"rule": "injection", "verdict": "block", "detail": "contains an instruction-like phrase",
                         "quote": _quote(text, m)})

    known = {(c.get("email") or "").lower(): c for c in store.list_contacts() if c.get("email")}
    for m in _EMAIL.finditer(text):
        e = m.group(0).lower().rstrip(".")
        if e in known and e != customer.lower():
            findings.append({"rule": "personal_data", "verdict": "block",
                             "detail": f"names a contact on record ({known[e]['name']}) who is not the recipient",
                             "quote": _quote(text, m)})
    for m in _PHONE.finditer(text):
        if sum(ch.isdigit() for ch in m.group(0)) >= 9:
            findings.append({"rule": "personal_data", "verdict": "warn", "detail": "contains a phone number; check it may be shared",
                             "quote": _quote(text, m)})
            break

    for m in _PROMISE.finditer(text):
        findings.append({"rule": "promise", "verdict": "warn",
                         "detail": "an unconditional promise: keep it only if the business can always honour it",
                         "quote": _quote(text, m)})
    if _FINAL_ADVICE.search(text) and not _NOT_ADVICE.search(text):
        m = _FINAL_ADVICE.search(text)
        findings.append({"rule": "advice", "verdict": "warn",
                         "detail": "reads as final legal, tax or financial advice; say it is not, or have a professional sign it",
                         "quote": _quote(text, m)})

    order = {"block": 0, "warn": 1}
    findings.sort(key=lambda f: order.get(f["verdict"], 2))
    verdict = "block" if any(f["verdict"] == "block" for f in findings) else ("warn" if findings else "pass")
    return {"verdict": verdict, "findings": findings[:20], "checked_chars": len(text),
            "summary": {"pass": "No rule in the profile or the standard checks applies.",
                        "warn": f"{len(findings)} point(s) to check before it goes out.",
                        "block": "Must not go out as it is."}[verdict]}


# --------------------------------------------------------------- policy pages
_PAGES = {
    "terms": (("terms", "conditions", "tos"), "Terms of service",
              "it sells to the public: what is sold, how it is delivered, what happens when something goes wrong"),
    "privacy": (("privacy",), "Privacy policy",
                "it collects customer details and inputs: what is kept, why, for how long, who else sees it"),
    "refund": (("refund", "returns", "cancellation"), "Refund policy",
               "it takes payment: when a refund is due and how it is paid (refunds always need a person in AERA)"),
}


def _doc_meta(mime: str) -> Dict[str, Any]:
    import json
    try:
        return json.loads(mime.split(";", 1)[1]) if ";" in (mime or "") else {}
    except ValueError:
        return {}


def legal_pages(profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Which policy pages the business needs, and which exist among its files and documents.

    A page counts as present only when it is final: a document saved as a draft, or titled as one, is a draft
    waiting for a person, and is reported as such. AERA's own reports (this register, the books, a systems
    review) are never mistaken for a policy page."""
    p = profile or business.current()
    sells = bool(p.get("offerings"))
    with store.connect() as c:
        files = [dict(r) for r in c.execute("SELECT id, name, mime FROM files ORDER BY uploaded_at DESC")]
    candidates = []
    for f in files:
        meta = _doc_meta(f["mime"])
        if meta.get("kind") in ("compliance_register", "finance_report", "systems_review", "autonomy_report"):
            continue
        name = f["name"].removeprefix("doc:")
        draft = meta.get("format") == "draft" or bool(re.search(r"\bdraft\b", name, re.I))
        candidates.append((f["id"], name, draft))
    out = []
    for key, (words, title, why) in _PAGES.items():
        hits = [x for x in candidates if any(re.search(r"\b" + w + r"\b", x[1], re.I) for w in words)]
        final = next((x for x in hits if not x[2]), None)
        hit = final or (hits[0] if hits else None)
        status = "present" if final else ("draft" if hit else ("missing" if sells else "not needed"))
        out.append({"page": key, "title": title, "needed": sells, "why": why if sells else "", "status": status,
                    "file": ({"id": hit[0], "name": hit[1]} if hit else None)})
    missing = [x["title"] for x in out if x["status"] == "missing"]
    drafts = [x["title"] for x in out if x["status"] == "draft"]
    parts = []
    if missing:
        parts.append(f"Missing: {', '.join(missing)}.")
    if drafts:
        parts.append(f"Waiting for a person's approval: {', '.join(drafts)}.")
    return {"pages": out, "missing": missing, "drafts": drafts,
            "summary": ("All the policy pages the business needs exist." if not parts
                        else " ".join(parts) + " The Compliance agent drafts; a person approves and publishes.")}


# --------------------------------------------------------------- record of processing
def _age_days(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, (datetime.now(timezone.utc) - t).days)


def processors() -> List[Dict[str, Any]]:
    """Everyone outside AERA that business data can reach, and on what terms: the models, the mail, the alert channels,
    every app connected through Composio and every outside MCP server. Read from the configuration and the record."""
    import os
    from core import llm
    out: List[Dict[str, Any]] = [{
        "name": "NEAR AI Cloud", "kind": "models",
        "gets": "prompts: the work, order inputs, documents, what agents read",
        "terms": ("inside attested TEEs; each call's attestation and signature verified" if llm.private_mode()
                  else "private mode is off: models outside a TEE may be used"),
        "private": llm.private_mode()}]
    try:
        from clients import channels, composio
        via = channels.email_via()
        if via == "composio" and composio.configured():
            out.append({"name": "Gmail through Composio", "kind": "mail",
                        "gets": "messages to customers and prospects, deliveries, alerts to the team",
                        "terms": "only what a person approved or the record produced; outside production, outward mail goes "
                                 "only to a test address", "private": False})
        elif not channels.missing("email"):
            out.append({"name": "SMTP mail server", "kind": "mail", "gets": "messages, deliveries, alerts",
                        "terms": "only what a person approved or the record produced", "private": False})
        for ch in channels.team_channels():
            out.append({"name": ch.capitalize(), "kind": "alerts", "gets": "alerts to the team",
                        "terms": "personal data is replaced before it leaves (NEAR AI privacy filter)", "private": True})
    except Exception:                                                  # noqa: BLE001
        pass
    for a in store.list_apps():
        if not a.get("enabled"):
            continue
        on = [t for t in a.get("tools") or [] if t.get("enabled")]
        writes = [t for t in on if not t.get("read_only") and t.get("write_allowed")]
        out.append({"name": f"{a['name']} (through Composio)", "kind": "app",
                    "gets": (f"{len(writes)} write tool(s) allowed: what an agent proposes to write, after a person approves it"
                             if writes else "nothing is written there; agents only read from it"),
                    "terms": f"given to {', '.join(a.get('agents') or []) or 'no agent'}; {len(on)} tool(s) in use; reads are "
                             "outside text; every write waits for a person and the Guardian flags personal data in it",
                    "private": not writes})
    for srv in store.mcp_servers():
        if not srv.get("enabled"):
            continue
        writes = [t for t in srv.get("tools") or [] if t.get("write_allowed")]
        out.append({"name": f"{srv['name']} (MCP server)", "kind": "app",
                    "gets": f"{len(writes)} write tool(s) allowed" if writes else "nothing is written there",
                    "terms": "every write waits for a person", "private": not writes})
    if os.environ.get("AERA_TENANT"):
        out.append({"name": "This install's hub", "kind": "isolation",
                    "gets": "nothing: this business runs as its own service with its own database and keys",
                    "terms": "no other business on the install can read its record", "private": True})
    return out


def register(profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """What personal data AERA holds, counted from its own tables."""
    from core import llm
    p = profile or business.current()
    private = llm.private_mode()
    model_line = ("the model provider, inside an attested TEE (the operator cannot read it)" if private
                  else "the model provider (not in a TEE: private mode is off)")
    with store.connect() as c:
        def one(sql: str) -> Any:
            return c.execute(sql).fetchone()
        contacts = one("SELECT COUNT(*), SUM(email != ''), SUM(near_account IS NOT NULL AND near_account != ''),"
                       " SUM(payout_address IS NOT NULL AND payout_address != ''), SUM(phone IS NOT NULL AND phone != ''),"
                       " MIN(created_at) FROM contacts")
        orders = one("SELECT COUNT(*), SUM(inputs NOT IN ('{}', '')), MIN(created_at) FROM orders")
        visitors = one("SELECT COUNT(*), COUNT(DISTINCT session), MIN(at) FROM public_chats WHERE role='visitor'")
        chats = one("SELECT COUNT(*), MIN(at) FROM messages")
        files = one("SELECT COUNT(*), MIN(uploaded_at) FROM files")
        redactions = one("SELECT COUNT(*), SUM(outcome='redacted') FROM privacy_events")
        leads = one("SELECT COUNT(*), MIN(created_at) FROM leads")
        inbound = one("SELECT COUNT(*), MIN(received_at) FROM inbound")
        optouts = one("SELECT COUNT(*), MIN(at) FROM optouts")
    inputs = sorted({i for o in p.get("offerings") or [] for i in o.get("inputs") or []})
    rows = [
        {"category": "Contacts", "where": "contacts",
         "what": f"names and roles; {contacts[1] or 0} with e-mail, {contacts[4] or 0} with phone, "
                 f"{contacts[2] or 0} with a NEAR account, {contacts[3] or 0} with a payout address",
         "records": contacts[0] or 0, "oldest_days": _age_days(contacts[5]),
         "purpose": "to deliver orders, answer customers and pay vendors",
         "shared_with": "nobody outside AERA; a payout address is used only by the vault"},
        {"category": "Order inputs", "where": "orders",
         "what": f"what customers typed at checkout ({', '.join(inputs) or 'no inputs asked'})",
         "records": orders[0] or 0, "oldest_days": _age_days(orders[2]),
         "purpose": "to do the work that was paid for", "shared_with": model_line},
        {"category": "Visitor questions", "where": "public_chats",
         "what": f"questions asked on the public checkout page, from {visitors[1] or 0} visitor session(s); no names or logins",
         "records": visitors[0] or 0, "oldest_days": _age_days(visitors[2]),
         "purpose": "to answer and to check the answers afterwards", "shared_with": model_line},
        {"category": "Team chat", "where": "messages",
         "what": "what owners and staff wrote to the agents", "records": chats[0] or 0, "oldest_days": _age_days(chats[1]),
         "purpose": "to keep the conversation", "shared_with": model_line},
        {"category": "Business files and documents", "where": "files",
         "what": "uploaded files and the documents the team wrote, including deliverables",
         "records": files[0] or 0, "oldest_days": _age_days(files[1]),
         "purpose": "the business's own material and its deliveries", "shared_with": model_line},
        {"category": "Prospects (leads)", "where": "leads",
         "what": "names, business e-mail addresses and the public page each was found on; never an address the page "
                 "did not show",
         "records": leads[0] or 0, "oldest_days": _age_days(leads[1]),
         "purpose": "to offer the business's services; the first message waits for a person, every message says how to stop",
         "shared_with": model_line + "; the e-mail provider when a message is sent"},
        {"category": "E-mail received", "where": "inbound",
         "what": "replies from leads and customers: sender, subject, text",
         "records": inbound[0] or 0, "oldest_days": _age_days(inbound[1]),
         "purpose": "to answer them; read as outside text", "shared_with": model_line},
        {"category": "Opt-outs", "where": "optouts",
         "what": "addresses that asked not to be written to, and when",
         "records": optouts[0] or 0, "oldest_days": _age_days(optouts[1]),
         "purpose": "kept so they are never written to again (the Guardian blocks it)", "shared_with": "nobody"},
    ]
    sensitive = (p.get("privacy") or {}).get("sensitive") or []
    notes = []
    old = [r["category"] for r in rows if (r["oldest_days"] or 0) > 365]
    if old:
        notes.append(f"Kept for more than a year: {', '.join(old)}. Decide how long each should be kept.")
    if not private:
        notes.append("Private mode is off: prompts go to models outside a TEE.")
    notes.append("No retention period is set yet: records are kept until someone deletes them.")
    return {"rows": rows, "processors": processors(), "sensitive": sensitive, "tee_only": bool((p.get("privacy") or {}).get("tee_only")),
            "private_mode": private, "redaction": {"events": redactions[0] or 0, "redacted": redactions[1] or 0},
            "raw_prompts_stored": False, "notes": notes,
            "summary": f"{sum(r['records'] for r in rows)} records across {sum(1 for r in rows if r['records'])} kinds of data."}


def register_markdown(reg: Dict[str, Any], pages: Dict[str, Any], commentary: str, name: str) -> str:
    filed = datetime.now(timezone.utc).strftime("%d %B %Y")
    lines = [f"# Data and policy register — {name}", "", f"Filed {filed}. _{DISCLAIMER}_", "",
             "## Personal data held", "", "| Data | Records | Oldest | Why | Who else sees it |", "|---|---:|---:|---|---|"]
    for r in reg["rows"]:
        oldest = "—" if r["oldest_days"] is None else f"{r['oldest_days']} days"
        lines.append(f"| {r['category']}: {r['what']} | {r['records']} | {oldest} | {r['purpose']} | {r['shared_with']} |")
    lines += ["", f"Marked sensitive in the profile: {', '.join(reg['sensitive']) or 'nothing'}.",
              f"Private mode: {'on' if reg['private_mode'] else 'off'}. Raw prompts stored: no.", ""]
    lines += ["## Policy pages", "", "| Page | Status | Why it is needed |", "|---|---|---|"]
    for x in pages["pages"]:
        lines.append(f"| {x['title']} | {x['status']} | {x['why'] or '—'} |")
    lines += ["", "## Points to decide", ""] + [f"- {n}" for n in reg["notes"]] + [""]
    if commentary.strip():
        lines += ["## Compliance notes", "", commentary.strip(), ""]
    lines += ["_Counts computed by AERA from its own tables; the notes above are the Compliance agent's._"]
    return "\n".join(lines)


def overview() -> Dict[str, Any]:
    return {"register": register(), "pages": legal_pages()}


def demo() -> None:
    p = dict(business.EXAMPLE)
    store.save_profile(p, by="check")
    store.add_contact("Ana", "customer", "ana@client.example", near_account="ana.testnet")
    assert review("Your brief arrives in 2 hours.", p)["verdict"] == "pass"
    r = review("We promise investment returns of 20% and it is guaranteed.", p)
    assert r["verdict"] == "block" and r["findings"][0]["rule"] == "forbidden" and "investment" in r["findings"][0]["quote"]
    assert any(f["rule"] == "promise" for f in r["findings"])
    leak = review("Ana (ana@client.example) ordered the same brief.", p, customer="bo@x.example")
    assert leak["verdict"] == "block" and leak["findings"][0]["rule"] == "personal_data"
    assert review("Sent to ana@client.example", p, customer="ana@client.example")["verdict"] == "pass", "the recipient's own address is fine"
    assert review("This is legal advice: file now.", p)["verdict"] == "warn"
    assert review("Some notes on filing. This is not legal advice.", p)["verdict"] == "pass"

    pages = legal_pages(p)
    assert pages["missing"] == ["Terms of service", "Privacy policy", "Refund policy"], pages
    store.save_file("doc:Privacy policy (DRAFT)", 'text/markdown;{"format": "draft"}', "# Privacy", by="check")
    assert legal_pages(p)["drafts"] == ["Privacy policy"], "a draft is not a published page"
    store.save_file("doc:Privacy policy", 'text/markdown;{"format": "pdf"}', "# Privacy", by="check")
    store.save_file("doc:Photos for the site", "text/markdown", "x", by="check")
    store.save_file("doc:Data and policy register", 'text/markdown;{"kind": "compliance_register"}', "x", by="check")
    lp = legal_pages(p)
    assert "Privacy policy" not in lp["missing"] and not lp["drafts"], lp
    assert "Terms of service" in lp["missing"], "'photos' is not a terms page; the register is not a policy page"

    reg = register(p)
    by = {r["category"]: r for r in reg["rows"]}
    assert by["Contacts"]["records"] >= 1 and "1 with a NEAR account" in by["Contacts"]["what"], by["Contacts"]
    assert "industry" in by["Order inputs"]["what"] and reg["raw_prompts_stored"] is False
    md = register_markdown(reg, legal_pages(p), "Set a retention period.", p["name"])
    assert "Not legal advice" in md and "| Contacts:" in md and "Set a retention period." in md
    print("compliance ok: findings quote the text ✓ · recipient's own details allowed ✓ · policy pages found ✓ · "
          "data register counted from the tables ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_COMPLIANCE_CHECK")
    demo()
