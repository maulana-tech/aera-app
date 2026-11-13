"""The business's inbox: e-mail that comes back, read over IMAP.

    AERA_IMAP_HOST       imap.gmail.com, outlook.office365.com, your host...
    AERA_IMAP_PORT       993 (TLS)
    AERA_IMAP_USER       the mailbox
    AERA_IMAP_PASSWORD   an app password, never the account password
    AERA_IMAP_FOLDER     INBOX

Only unread messages are fetched, and fetching marks them read, so each is taken once (the message id is
also stored, so a message read twice is still handled once). Two other ways in, for hosts that forward mail
instead: POST /public/inbound/email with the AERA_INBOUND_SECRET header, and `manage.py inbound` by hand.

What is taken from a message: the sender, the subject, the plain-text body (HTML is reduced to text), and the
headers that say a machine wrote it (Auto-Submitted, Precedence, Content-Type). Attachments are not read.
"""
from __future__ import annotations

import email
import imaplib
import os
from email.header import decode_header, make_header
from email.message import Message
from typing import Dict, List


class NotConfigured(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def configured() -> bool:
    return bool(_env("AERA_IMAP_HOST") and _env("AERA_IMAP_USER") and _env("AERA_IMAP_PASSWORD"))


def missing() -> List[str]:
    return [k for k in ("AERA_IMAP_HOST", "AERA_IMAP_USER", "AERA_IMAP_PASSWORD") if not _env(k)]


def _text(h: str) -> str:
    try:
        return str(make_header(decode_header(h or "")))
    except (UnicodeDecodeError, LookupError, ValueError):
        return h or ""


def body_text(msg: Message) -> str:
    """The plain-text body; HTML reduced to text when there is no plain part."""
    plain, html = [], []
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_maintype() == "multipart" or part.get("Content-Disposition", "").startswith("attachment"):
            continue
        try:
            raw = part.get_payload(decode=True) or b""
            text = raw.decode(part.get_content_charset() or "utf-8", errors="replace")
        except (LookupError, AttributeError):
            continue
        (plain if part.get_content_type() == "text/plain" else html if part.get_content_type() == "text/html" else []).append(text)
    if plain:
        return "\n".join(plain).strip()
    if html:
        from tools.research import page_text
        return page_text("\n".join(html))
    return ""


def parse(raw: bytes) -> Dict[str, object]:
    msg = email.message_from_bytes(raw)
    return {"message_id": (msg.get("Message-ID") or "").strip(), "from": _text(msg.get("From", "")),
            "subject": _text(msg.get("Subject", "")), "body": body_text(msg)[:20000],
            "headers": {k: str(msg.get(k)) for k in ("Auto-Submitted", "Precedence", "Content-Type") if msg.get(k)}}


def fetch_unread(limit: int = 25) -> List[Dict[str, object]]:
    if not configured():
        raise NotConfigured("the inbox is not set up: " + ", ".join(missing()))
    box = imaplib.IMAP4_SSL(_env("AERA_IMAP_HOST"), int(_env("AERA_IMAP_PORT", "993") or 993))
    try:
        box.login(_env("AERA_IMAP_USER"), _env("AERA_IMAP_PASSWORD"))
        box.select(_env("AERA_IMAP_FOLDER", "INBOX") or "INBOX")
        typ, data = box.search(None, "UNSEEN")
        ids = (data[0] or b"").split()[:limit] if typ == "OK" else []
        out = []
        for i in ids:
            typ, got = box.fetch(i, "(RFC822)")                    # marks it \\Seen
            if typ == "OK" and got and isinstance(got[0], tuple):
                out.append(parse(got[0][1]))
        return out
    finally:
        try:
            box.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def poll() -> str:
    """Read what is new and hand each message to core/prospects.receive."""
    if not configured():
        return "inbox not set up"
    from core import prospects
    got = fetch_unread()
    kinds: Dict[str, int] = {}
    for m in got:
        r = prospects.receive(str(m["message_id"]), str(m["from"]), str(m["subject"]), str(m["body"]), "imap",
                              m.get("headers") or {})                  # type: ignore[arg-type]
        k = str(r.get("kind") or r.get("why"))
        kinds[k] = kinds.get(k, 0) + 1
    return f"{len(got)} new e-mail(s)" + (": " + ", ".join(f"{v} {k}" for k, v in kinds.items()) if kinds else "")


def demo() -> None:
    raw = (b"From: =?utf-8?q?Rina_S=C3=A1?= <rina@studio.example>\r\nSubject: Re: Market briefs\r\n"
           b"Message-ID: <abc@studio.example>\r\nMIME-Version: 1.0\r\nContent-Type: multipart/alternative; boundary=b\r\n\r\n"
           b"--b\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>Yes, <b>send</b> the price.</p>\r\n--b--\r\n")
    m = parse(raw)
    assert m["from"] == "Rina Sá <rina@studio.example>" and m["message_id"] == "<abc@studio.example>", m
    assert m["body"] == "Yes, send the price.", m["body"]
    auto = parse(b"From: a@b.example\r\nSubject: Away\r\nAuto-Submitted: auto-replied\r\n\r\nI am away.")
    assert auto["headers"]["Auto-Submitted"] == "auto-replied" and auto["body"] == "I am away."
    saved = {k: os.environ.pop(k, None) for k in ("AERA_IMAP_HOST", "AERA_IMAP_USER", "AERA_IMAP_PASSWORD")}
    try:
        assert poll() == "inbox not set up"
        try:
            fetch_unread()
            raise AssertionError("an inbox with no settings must say so")
        except NotConfigured as e:
            assert "AERA_IMAP_HOST" in str(e)
    finally:
        os.environ.update({k: v for k, v in saved.items() if v})
    print("inbox ok: headers decoded ✓ · HTML body reduced to text ✓ · machine headers kept ✓ · no settings says so ✓")


if __name__ == "__main__":
    demo()
