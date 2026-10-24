"""Where an alert goes. Each channel is either configured or it is not; nothing
is guessed, and a channel that is not set up is reported, not silently skipped.

  email     One message per contact on the Contacts page, with files attached
            when there are any (a report as PDF or a workbook). Two ways out:
            smtp      SIGAP_SMTP_HOST, SIGAP_SMTP_PORT (587), SIGAP_SMTP_USER,
                      SIGAP_SMTP_PASSWORD, SIGAP_SMTP_SECURITY (starttls | ssl |
                      none), SIGAP_MAIL_FROM. AWS SES, Gmail with an app password
                      and any company relay speak SMTP.
            composio  COMPOSIO_API_KEY and a Gmail mailbox connected for SIGAP
                      (clients/composio.py). Mail leaves from that mailbox, so a
                      reply comes back to a person.
            SIGAP_EMAIL_VIA picks one; unset, SMTP when it is configured, else
            Composio when its key is.
  slack     SIGAP_SLACK_WEBHOOK_URL. One message to the team's channel.
  telegram  SIGAP_TELEGRAM_BOT_TOKEN and SIGAP_TELEGRAM_CHAT_ID (a person or a
            group the bot is in).
  webhook   SIGAP_WEBHOOK_URL. The message as JSON, for whatever routes it on:
            Teams through Power Automate, n8n, a ticketing system.

The password, the bot token, the webhook URLs and the Composio key are all
secrets (a webhook URL is a credential: anyone holding it can post). They belong
in .secrets/notify.env, which core/config.py reads the way it reads .env.

Files travel by email only. A team channel gets the message, whose link opens
the same report in SIGAP.
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from clients import composio

TIMEOUT = 20
TELEGRAM_API = "https://api.telegram.org"
TELEGRAM_MAX = 4096                       # Telegram refuses a longer message

TEAM_CHANNELS = ("slack", "telegram", "webhook")
CHANNELS = ("email",) + TEAM_CHANNELS

File = Tuple[bytes, str, str]                  # content, filename, media type


class NotConfigured(RuntimeError):
    pass


class DeliveryFailed(RuntimeError):
    pass


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def email_via() -> str:
    """smtp | composio: which way email leaves."""
    chosen = _env("SIGAP_EMAIL_VIA").lower()
    if chosen in ("smtp", "composio"):
        return chosen
    if _env("SIGAP_SMTP_HOST") or not composio.configured():
        return "smtp"
    return "composio"


def missing(channel: str) -> List[str]:
    """What a channel still needs. Empty means it is ready. Names variables or
    steps, never values."""
    if channel == "email" and email_via() == "composio":
        return composio.status()["missing"]
    need = {"email": ["SIGAP_SMTP_HOST", "SIGAP_MAIL_FROM"],
            "slack": ["SIGAP_SLACK_WEBHOOK_URL"],
            "telegram": ["SIGAP_TELEGRAM_BOT_TOKEN", "SIGAP_TELEGRAM_CHAT_ID"],
            "webhook": ["SIGAP_WEBHOOK_URL"]}[channel]
    return [v for v in need if not _env(v)]


def status() -> Dict[str, Dict[str, Any]]:
    """Per channel: ready, and what it lacks. Names variables, never values."""
    out: Dict[str, Dict[str, Any]] = {c: {"ready": not missing(c), "missing": missing(c)}
                                      for c in TEAM_CHANNELS}
    via = email_via()
    if via == "composio":
        c = composio.status()
        out["email"] = {"ready": c["ready"], "missing": c["missing"], "via": "composio",
                        "sender": c.get("sender"), "connectable": bool(c.get("connectable"))}
    else:
        gaps = missing("email")
        out["email"] = {"ready": not gaps, "missing": gaps, "via": "smtp",
                        "sender": _env("SIGAP_MAIL_FROM") or None,
                        "connectable": composio.configured()}
    return {c: out[c] for c in CHANNELS}


def team_channels() -> List[str]:
    return [c for c in TEAM_CHANNELS if not missing(c)]


def _post_json(url: str, body: dict) -> None:
    req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode(),
                                 method="POST", headers={"Content-Type": "application/json",
                                                         "User-Agent": "SIGAP/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise DeliveryFailed(f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}") from None
    except (urllib.error.URLError, OSError) as e:
        raise DeliveryFailed(f"{type(e).__name__}: {e}") from None


def _email(address: str, subject: str, body: str, files: Sequence[File] = ()) -> str:
    host, sender = _env("SIGAP_SMTP_HOST"), _env("SIGAP_MAIL_FROM")
    security = (_env("SIGAP_SMTP_SECURITY") or "starttls").lower()
    port = int(_env("SIGAP_SMTP_PORT") or (465 if security == "ssl" else 587))
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, address, subject
    msg["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1] if "@" in sender else None)
    msg.set_content(body)
    for content, name, media in files:
        main, _, sub = media.partition("/")
        msg.add_attachment(content, maintype=main, subtype=sub or "octet-stream", filename=name)
    try:
        if security == "ssl":
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT,
                                                  context=ssl.create_default_context())
        else:
            smtp = smtplib.SMTP(host, port, timeout=TIMEOUT)
        with smtp:
            if security == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if _env("SIGAP_SMTP_USER"):
                smtp.login(_env("SIGAP_SMTP_USER"), _env("SIGAP_SMTP_PASSWORD"))
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise DeliveryFailed(f"{type(e).__name__}: {e}") from None
    return msg["Message-ID"]


def send(channel: str, address: str, subject: str, body: str,
         extra: Optional[dict] = None, files: Sequence[File] = ()) -> Optional[str]:
    """Deliver one message, or raise NotConfigured / DeliveryFailed. Returns
    the message's id where the channel gives one (email does)."""
    if channel not in CHANNELS:
        raise NotConfigured(f"no channel '{channel}'")
    if channel == "email" and email_via() == "composio":
        # Asked of Composio at the moment of sending, not from a status read
        # earlier: "unreachable" must be retried, "not connected" must not.
        try:
            return composio.send_email(address, subject, body, files)
        except composio.NotConnected as e:
            raise NotConfigured(f"email via Composio is not set up: {e}") from None
        except composio.Failed as e:
            raise DeliveryFailed(str(e)) from None
    gaps = missing(channel)
    if gaps:
        raise NotConfigured(f"{channel} is not set up: {', '.join(gaps)}")
    if channel == "email":
        return _email(address, subject, body, files)
    elif channel == "slack":
        _post_json(_env("SIGAP_SLACK_WEBHOOK_URL"), {"text": f"*{subject}*\n{body}"})
    elif channel == "telegram":
        text = f"{subject}\n\n{body}"
        _post_json(f"{TELEGRAM_API}/bot{_env('SIGAP_TELEGRAM_BOT_TOKEN')}/sendMessage",
                   {"chat_id": _env("SIGAP_TELEGRAM_CHAT_ID"), "disable_web_page_preview": True,
                    "text": text if len(text) <= TELEGRAM_MAX else text[:TELEGRAM_MAX - 1] + "…"})
    else:
        _post_json(_env("SIGAP_WEBHOOK_URL"), {"subject": subject, "text": body, **(extra or {})})
    return None


def demo() -> None:
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    keys = ("SIGAP_SMTP_HOST", "SIGAP_MAIL_FROM", "SIGAP_SLACK_WEBHOOK_URL",
            "SIGAP_TELEGRAM_BOT_TOKEN", "SIGAP_TELEGRAM_CHAT_ID", "SIGAP_WEBHOOK_URL",
            "SIGAP_EMAIL_VIA", "COMPOSIO_API_KEY", "SIGAP_SMTP_PORT", "SIGAP_SMTP_SECURITY")
    saved = {k: os.environ.pop(k, None) for k in keys}
    got: List[dict] = []

    class Sink(BaseHTTPRequestHandler):
        def do_POST(self):                                           # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            got.append({"path": self.path, "body": json.loads(self.rfile.read(n))})
            self.send_response(500 if self.path == "/broken" else 200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Sink)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    global TELEGRAM_API
    real_tg = TELEGRAM_API
    try:
        assert not any(s["ready"] for s in status().values())
        assert status()["email"]["missing"] == ["SIGAP_SMTP_HOST", "SIGAP_MAIL_FROM"]
        try:
            send("slack", "team", "s", "b")
            raise AssertionError("an unconfigured channel must say so")
        except NotConfigured as e:
            assert "SIGAP_SLACK_WEBHOOK_URL" in str(e)

        os.environ["SIGAP_SLACK_WEBHOOK_URL"] = base + "/slack"
        os.environ["SIGAP_WEBHOOK_URL"] = base + "/hook"
        os.environ["SIGAP_TELEGRAM_BOT_TOKEN"], os.environ["SIGAP_TELEGRAM_CHAT_ID"] = "T0K", "42"
        TELEGRAM_API = base
        assert team_channels() == ["slack", "telegram", "webhook"]
        send("slack", "team", "Ningbo closed", "body")
        send("telegram", "team", "Ningbo closed", "x" * 5000)
        send("webhook", "team", "Ningbo closed", "body", {"run_id": "run_1"})
        slack, tg, hook = got
        assert slack["body"]["text"].startswith("*Ningbo closed*")
        assert tg["path"] == "/botT0K/sendMessage" and len(tg["body"]["text"]) == TELEGRAM_MAX
        assert hook["body"] == {"subject": "Ningbo closed", "text": "body", "run_id": "run_1"}
        os.environ["SIGAP_WEBHOOK_URL"] = base + "/broken"
        try:
            send("webhook", "team", "s", "b")
            raise AssertionError("a refused delivery must raise")
        except DeliveryFailed as e:
            assert "500" in str(e)

        # Email over SMTP, with a report attached: what the relay receives.
        relayed: List[bytes] = []

        class Relay:
            def __init__(self, *_a, **_k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def send_message(self, m):
                relayed.append(m.as_bytes())

        real_smtp = smtplib.SMTP
        smtplib.SMTP = Relay                                         # type: ignore[misc]
        os.environ.update({"SIGAP_SMTP_HOST": "relay.example", "SIGAP_MAIL_FROM": "sigap@co.example",
                           "SIGAP_SMTP_SECURITY": "none"})
        try:
            assert email_via() == "smtp" and status()["email"]["ready"]
            mid = send("email", "rina@co.example", "Report", "Attached.",
                       files=[(b"%PDF-1.4 x", "report.pdf", "application/pdf")])
        finally:
            smtplib.SMTP = real_smtp                                 # type: ignore[misc]
        assert mid and mid.endswith("@co.example>"), mid
        raw = relayed[0].decode()
        assert 'filename="report.pdf"' in raw and "application/pdf" in raw, raw[:400]

        # Composio chosen but not connected: email says so, nothing guessed.
        os.environ.update({"SIGAP_EMAIL_VIA": "composio"})
        assert status()["email"] == {"ready": False, "missing": ["COMPOSIO_API_KEY"],
                                     "via": "composio", "sender": None, "connectable": False}
        try:
            send("email", "rina@co.example", "s", "b")
            raise AssertionError("email via an unconfigured Composio must say so")
        except NotConfigured as e:
            assert "COMPOSIO_API_KEY" in str(e)
    finally:
        TELEGRAM_API = real_tg
        srv.shutdown()
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    print("  channels: unconfigured says what is missing ✓ · slack, telegram, webhook delivered ✓ "
          "· telegram clipped to its limit ✓ · a refusal raises ✓ · email carries its attachment ✓ "
          "· Composio unset says so ✓")
    print("channels ok")


if __name__ == "__main__":
    demo()
