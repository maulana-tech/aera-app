"""Composio: mail from a real mailbox, through one API key.

AERA sends email as the company's own Gmail account by way of Composio, which
holds the OAuth grant, refreshes it and runs the send. AERA holds one project
API key and never the mailbox's password or token. Files go the same way: a
report is uploaded to Composio's storage first, and the send names it.

  COMPOSIO_API_KEY            the project key; a secret, in .secrets/notify.env
  AERA_COMPOSIO_USER_ID      whose connections AERA may use, default "aera"
  AERA_COMPOSIO_ACCOUNT      pin one connected account (ca_...), optional
  AERA_COMPOSIO_AUTH_CONFIG  the auth config a new connection is made with,
                              optional; else the project's Composio-managed one

One Composio project can hold other applications and their users' mailboxes.
AERA uses only a connection that belongs to its own user id, and refuses a
pinned one that belongs to anybody else: "the newest Gmail in the project" may
be a stranger's.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_BASE = "https://backend.composio.dev/api/v3.1"
TIMEOUT = 30
#: The GMAIL_SEND_EMAIL arguments below are written against this version of the
#: toolkit. Pinned, so a change on Composio's side cannot quietly change what a
#: send means; AERA_COMPOSIO_GMAIL_VERSION moves it deliberately.
GMAIL_VERSION = "20261023_00"
#: Gmail refuses a message over about 25 MB once encoded.
MAX_ATTACHMENTS_BYTES = 18_000_000
CACHE_SECONDS = 300

File = Tuple[bytes, str, str]                  # content, filename, media type


class NotConnected(RuntimeError):
    """No key, or no mailbox connected for AERA: nothing can be sent until a
    person sets it up, so a message waiting on it is skipped, not retried."""


class Failed(RuntimeError):
    """Composio or the mailbox refused, or could not be reached: worth a retry."""


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def base() -> str:
    return (_env("AERA_COMPOSIO_BASE") or DEFAULT_BASE).rstrip("/")


def configured() -> bool:
    return bool(_env("COMPOSIO_API_KEY"))


def user_id() -> str:
    return _env("AERA_COMPOSIO_USER_ID") or "aera"


def _call(method: str, path: str, body: Optional[dict] = None,
          query: Optional[Dict[str, Any]] = None) -> dict:
    if not configured():
        raise NotConnected("COMPOSIO_API_KEY is not set")
    url = base() + path
    if query:
        url += "?" + urllib.parse.urlencode(query, doseq=True)
    req = urllib.request.Request(
        url, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"x-api-key": _env("COMPOSIO_API_KEY"), "Accept": "application/json",
                 "Content-Type": "application/json", "User-Agent": "AERA/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            err = json.loads(detail).get("error") or {}
            detail = err.get("message") or detail
        except (ValueError, AttributeError):
            pass
        if e.code == 401:
            raise NotConnected(f"Composio refused the API key: {detail[:200]}") from None
        raise Failed(f"Composio HTTP {e.code}: {detail[:300]}") from None
    except (urllib.error.URLError, OSError) as e:
        raise Failed(f"Composio unreachable: {type(e).__name__}: {e}") from None
    return json.loads(raw) if raw else {}


# ------------------------------------------------------------------- accounts
_CACHE_LOCK = threading.Lock()
_CACHE: Dict[str, Tuple[float, Any]] = {}


def _cached(key: str, make):
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and time.monotonic() < hit[0]:
            return hit[1]
    value = make()
    with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic() + CACHE_SECONDS, value)
    return value


def forget() -> None:
    """After a connection changes: read it again rather than trust the cache."""
    with _CACHE_LOCK:
        _CACHE.clear()


def _slug(item: dict) -> str:
    return ((item.get("toolkit") or {}).get("slug") or "").lower()


def account(toolkit: str = "gmail") -> dict:
    """AERA's active connection to `toolkit`, or NotConnected saying why."""
    def look() -> dict:
        pinned = _env("AERA_COMPOSIO_ACCOUNT")
        if pinned:
            a = _call("GET", f"/connected_accounts/{urllib.parse.quote(pinned)}")
            if a.get("user_id") != user_id():
                raise NotConnected(f"AERA_COMPOSIO_ACCOUNT belongs to another user, not "
                                   f"'{user_id()}'; AERA does not send from it")
            if _slug(a) != toolkit:
                raise NotConnected(f"AERA_COMPOSIO_ACCOUNT is a {_slug(a)} connection, not {toolkit}")
            if a.get("status") != "ACTIVE":
                raise NotConnected(f"the pinned {toolkit} connection is {a.get('status')}; "
                                   "connect it again")
            return a
        items = _call("GET", "/connected_accounts",
                      query={"user_ids": user_id(), "toolkit_slugs": toolkit,
                             "statuses": "ACTIVE", "order_by": "updated_at",
                             "order_direction": "desc", "limit": 10}).get("items") or []
        # The filter is the server's; this is ours. A connection that is not
        # AERA's is never used, whatever the server returned.
        mine = [a for a in items if a.get("user_id") == user_id() and _slug(a) == toolkit
                and a.get("status") == "ACTIVE"]
        if not mine:
            raise NotConnected(f"no {toolkit} mailbox is connected for AERA "
                               f"(Composio user '{user_id()}'); connect one on the Contacts page")
        return mine[0]
    return _cached(f"account:{toolkit}", look)


def sender() -> Optional[str]:
    """The address mail goes out from, as Gmail reports it."""
    def look() -> Optional[str]:
        a = account("gmail")
        data = execute("GMAIL_GET_PROFILE", {"user_id": "me"}, a["id"], version="latest")
        return (data.get("response_data") or data).get("emailAddress")
    try:
        return _cached("sender", look)
    except (NotConnected, Failed):
        return None


def status() -> Dict[str, Any]:
    """Ready or not, and why, for the Contacts page. Never the key."""
    if not configured():
        return {"ready": False, "missing": ["COMPOSIO_API_KEY"]}
    try:
        a = account("gmail")
    except NotConnected as e:
        return {"ready": False, "missing": [str(e)], "connectable": True}
    except Failed as e:
        return {"ready": False, "missing": [str(e)], "unreachable": True}
    return {"ready": True, "missing": [], "account": a.get("id"), "sender": sender()}


def _auth_config(toolkit: str) -> str:
    """The auth config a new connection to `toolkit` is made with. AERA_COMPOSIO_AUTH_CONFIG is the mailbox's
    (Gmail) only; any other app uses the project's Composio-managed config for it, made here if there is none."""
    chosen = _env("AERA_COMPOSIO_AUTH_CONFIG")
    if chosen and toolkit == "gmail":
        return chosen
    items = _call("GET", "/auth_configs", query={"toolkit_slug": toolkit, "limit": 50}).get("items") or []
    managed = [c for c in items if _slug(c) == toolkit and c.get("status") == "ENABLED"
               and c.get("is_composio_managed")]
    if managed:
        return managed[0]["id"]
    if toolkit == "gmail":
        raise NotConnected("no Composio-managed gmail auth config in this project; set AERA_COMPOSIO_AUTH_CONFIG")
    try:
        r = _call("POST", "/auth_configs", {"toolkit": {"slug": toolkit},
                                            "auth_config": {"type": "use_composio_managed_auth"}})
    except Failed as e:
        raise NotConnected(f"Composio has no managed sign-in for {toolkit} in this project ({e}); create an auth "
                           "config for it in the Composio dashboard") from None
    cid = (r.get("auth_config") or {}).get("id") or r.get("id")
    if not cid:
        raise NotConnected(f"Composio did not return an auth config for {toolkit}")
    return cid


def connect_link(toolkit: str = "gmail", callback_url: str = "") -> Dict[str, str]:
    """A sign-in page for the mailbox AERA will send from. Whoever opens it and
    consents is the mailbox, so it goes to the person who asked, nobody else."""
    body = {"auth_config_id": _auth_config(toolkit), "user_id": user_id()}
    if callback_url:
        body["callback_url"] = callback_url
    r = _call("POST", "/connected_accounts/link", body)
    forget()
    return {"url": r["redirect_url"], "expires_at": r.get("expires_at", ""),
            "connected_account_id": r.get("connected_account_id", "")}


# ----------------------------------------------------------------------- apps
#: A tool Composio marks with this tag only reads. Every other tool is treated as one that changes something.
READ_HINT = "readOnlyHint"
#: The largest tool schema offered to a model, in characters of JSON: past it the tool is too intricate to offer.
SCHEMA_MAX = 6000
_SCHEMA_KEYS = ("type", "properties", "required", "items", "enum", "description", "default", "minimum", "maximum")


def clean_schema(s: Any, depth: int = 0) -> Any:
    """A tool's input schema with only what a model needs (types, fields, what is required, descriptions)."""
    if not isinstance(s, dict) or depth > 6:
        return {"type": "string"} if depth else {"type": "object", "properties": {}}
    out: Dict[str, Any] = {}
    for k in _SCHEMA_KEYS:
        if k not in s:
            continue
        v = s[k]
        if k == "properties" and isinstance(v, dict):
            out[k] = {name: clean_schema(sub, depth + 1) for name, sub in list(v.items())[:40]}
        elif k == "items":
            out[k] = clean_schema(v, depth + 1)
        elif k == "description" and isinstance(v, str):
            out[k] = v[:300]
        else:
            out[k] = v
    if "type" not in out:
        out["type"] = "object" if "properties" in out else "string"
    if isinstance(out.get("required"), list) and isinstance(out.get("properties"), dict):
        out["required"] = [r for r in out["required"] if r in out["properties"]]
    return out


def search_toolkits(query: str = "", limit: int = 24) -> List[Dict[str, Any]]:
    """Apps Composio can connect, matching `query`."""
    q: Dict[str, Any] = {"limit": max(1, min(limit, 50))}
    if query.strip():
        q["search"] = query.strip()[:80]
    return [_hit(t) for t in _call("GET", "/toolkits", query=q).get("items") or []]


def _hit(t: dict) -> Dict[str, Any]:
    m = t.get("meta") or {}
    return {"slug": t.get("slug"), "name": t.get("name"), "description": (m.get("description") or "")[:300],
            "logo": m.get("logo"), "categories": [c.get("name") if isinstance(c, dict) else c for c in m.get("categories") or []][:3],
            "tools_count": m.get("tools_count"), "no_auth": bool(t.get("no_auth")),
            "managed": bool(t.get("composio_managed_auth_schemes"))}


def catalogue(query: str = "", category: str = "", cursor: str = "", limit: int = 24) -> Dict[str, Any]:
    """One page of the apps Composio can connect: most used first, or matching a search, or in one category."""
    q: Dict[str, Any] = {"limit": max(1, min(limit, 50))}
    if query.strip():
        q["search"] = query.strip()[:80]
    else:
        q["sort_by"] = "usage"
    if category.strip():
        q["category"] = category.strip()[:80]
    if cursor:
        q["cursor"] = cursor[:300]
    r = _call("GET", "/toolkits", query=q)
    return {"toolkits": [_hit(t) for t in r.get("items") or [] if not t.get("is_local_toolkit")],
            "next_cursor": r.get("next_cursor") or None, "total": r.get("total_items")}


def categories() -> List[Dict[str, str]]:
    """The catalogue's categories, each once."""
    def look() -> List[Dict[str, str]]:
        seen: Dict[str, str] = {}
        for c in _call("GET", "/toolkits/categories").get("items") or []:
            cid = str(c.get("id") or c.get("slug") or "").strip()
            if cid and cid not in seen and cid != "popular":
                name = str(c.get("name") or cid)
                seen[cid] = name[:1].upper() + name[1:]
        return [{"id": k, "name": v} for k, v in seen.items()]
    return _cached("categories", look)


def toolkit_tools(toolkit: str, limit: int = 300) -> List[Dict[str, Any]]:
    """Every current tool of one app: what it does, whether it only reads, and a schema a model can use."""
    out: List[Dict[str, Any]] = []
    cursor = None
    while len(out) < limit:
        q: Dict[str, Any] = {"toolkit_slug": toolkit, "limit": 100}
        if cursor:
            q["cursor"] = cursor
        r = _call("GET", "/tools", query=q)
        for t in r.get("items") or []:
            if t.get("is_deprecated"):
                continue
            schema = clean_schema(t.get("input_parameters") or {})
            if len(json.dumps(schema)) > SCHEMA_MAX:
                continue
            tags = [str(x) for x in t.get("tags") or []]
            out.append({"slug": t.get("slug"), "name": t.get("name") or t.get("slug"),
                        "description": (t.get("description") or t.get("human_description") or "")[:600],
                        "read_only": READ_HINT in tags, "important": "important" in tags,
                        "version": t.get("version") or "latest", "schema": schema})
        cursor = r.get("next_cursor")
        if not cursor:
            break
    return out


def connections(toolkit: Optional[str] = None) -> List[Dict[str, Any]]:
    """AERA's own active connections (this Composio user's), optionally for one app."""
    q: Dict[str, Any] = {"user_ids": user_id(), "statuses": "ACTIVE", "limit": 100}
    if toolkit:
        q["toolkit_slugs"] = toolkit
    items = _call("GET", "/connected_accounts", query=q).get("items") or []
    return [{"id": a.get("id"), "toolkit": _slug(a), "status": a.get("status"), "updated_at": a.get("updated_at")}
            for a in items if a.get("user_id") == user_id() and a.get("status") == "ACTIVE"
            and (not toolkit or _slug(a) == toolkit)]


# ------------------------------------------------------------------ execution
def execute(tool: str, arguments: dict, account_id: str, version: Optional[str] = None) -> dict:
    r = _call("POST", f"/tools/execute/{tool}",
              {"connected_account_id": account_id, "user_id": user_id(), "arguments": arguments,
               "version": version or _env("AERA_COMPOSIO_GMAIL_VERSION") or GMAIL_VERSION})
    if not r.get("successful"):
        raise Failed(f"{tool}: {r.get('error') or 'refused'} (log {r.get('log_id', '?')})")
    return r.get("data") or {}


def _put(url: str, content: bytes, media: str, storage: str) -> None:
    headers = {"Content-Type": media}
    if storage == "azure_blob_storage":
        headers["x-ms-blob-type"] = "BlockBlob"
    req = urllib.request.Request(url, data=content, method="PUT", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT * 2) as r:
            if r.status not in (200, 201):
                raise Failed(f"file upload answered {r.status}")
    except urllib.error.HTTPError as e:
        raise Failed(f"file upload refused: HTTP {e.code}") from None
    except (urllib.error.URLError, OSError) as e:
        raise Failed(f"file upload failed: {type(e).__name__}: {e}") from None


def upload(f: File, tool: str = "GMAIL_SEND_EMAIL", toolkit: str = "gmail") -> dict:
    """Put one file in Composio's storage; returns what a tool argument names."""
    content, name, media = f
    meta = _call("POST", "/files/upload/request",
                 {"toolkit_slug": toolkit, "tool_slug": tool, "filename": name, "mimetype": media,
                  "md5": hashlib.md5(content).hexdigest()})
    _put(meta["new_presigned_url"], content, media,
         (meta.get("metadata") or {}).get("storage_backend", "s3"))
    return {"name": name, "mimetype": media, "s3key": meta["key"]}


def send_email(to: str, subject: str, body: str, files: Sequence[File] = ()) -> str:
    """Send from AERA's connected Gmail. Returns Gmail's message id."""
    size = sum(len(f[0]) for f in files)
    if size > MAX_ATTACHMENTS_BYTES:
        raise Failed(f"attachments are {size:,} bytes; Gmail takes about "
                     f"{MAX_ATTACHMENTS_BYTES:,} once encoded")
    a = account("gmail")
    args: Dict[str, Any] = {"recipient_email": to, "subject": subject, "body": body,
                            "is_html": False, "user_id": "me"}
    if files:
        args["attachment"] = [upload(f) for f in files]
    data = execute("GMAIL_SEND_EMAIL", args, a["id"])
    sent = data.get("response_data") or data
    return str(sent.get("id") or sent.get("threadId") or "")


# ----------------------------------------------------------------------- check
def demo() -> None:
    import threading as th
    from http.server import BaseHTTPRequestHandler, HTTPServer

    keys = ("COMPOSIO_API_KEY", "AERA_COMPOSIO_BASE", "AERA_COMPOSIO_USER_ID",
            "AERA_COMPOSIO_ACCOUNT", "AERA_COMPOSIO_AUTH_CONFIG", "AERA_COMPOSIO_GMAIL_VERSION")
    saved = {k: os.environ.pop(k, None) for k in keys}
    seen: List[dict] = []
    stranger = {"id": "ca_other", "user_id": "another-app-user", "status": "ACTIVE",
                "toolkit": {"slug": "gmail"}}
    ours = {"id": "ca_ours", "user_id": "aera", "status": "ACTIVE", "toolkit": {"slug": "gmail"}}

    class Fake(BaseHTTPRequestHandler):
        def _reply(self, code: int, body: Any) -> None:
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _body(self) -> bytes:
            return self.rfile.read(int(self.headers.get("Content-Length") or 0))

        def do_GET(self):                                            # noqa: N802
            seen.append({"m": "GET", "path": self.path, "key": self.headers.get("x-api-key")})
            if self.path.startswith("/connected_accounts/ca_other"):
                return self._reply(200, stranger)
            if self.path.startswith("/connected_accounts?"):
                q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                # A careless server: it returns the stranger's mailbox too.
                return self._reply(200, {"items": [stranger] + ([ours] if FAKE["connected"] else [])
                                         if q.get("user_ids") == ["aera"] else []})
            if self.path.startswith("/auth_configs"):
                return self._reply(200, {"items": [{"id": "ac_1", "status": "ENABLED",
                                                    "is_composio_managed": True,
                                                    "toolkit": {"slug": "gmail"}}]})
            self._reply(404, {"error": {"message": "no"}})

        def do_POST(self):                                           # noqa: N802
            body = json.loads(self._body() or b"{}")
            seen.append({"m": "POST", "path": self.path, "body": body})
            if self.path == "/files/upload/request":
                return self._reply(200, {"key": f"projects/p/{body['filename']}",
                                         "new_presigned_url": f"{BASE}/put/{body['filename']}",
                                         "metadata": {"storage_backend": "s3"}})
            if self.path == "/connected_accounts/link":
                return self._reply(201, {"redirect_url": "https://connect.example/x",
                                         "connected_account_id": "ca_new", "expires_at": "soon"})
            if self.path == "/tools/execute/GMAIL_SEND_EMAIL":
                if body["arguments"]["recipient_email"] == "bounce@x.example":
                    return self._reply(200, {"successful": False, "error": "Invalid To header",
                                             "log_id": "log_1", "data": {}})
                return self._reply(200, {"successful": True, "error": None,
                                         "data": {"response_data": {"id": "18f0c1"}}})
            if self.path == "/tools/execute/GMAIL_GET_PROFILE":
                return self._reply(200, {"successful": True,
                                         "data": {"response_data": {"emailAddress": "ops@co.example"}}})
            self._reply(404, {"error": {"message": "no"}})

        def do_PUT(self):                                            # noqa: N802
            seen.append({"m": "PUT", "path": self.path, "type": self.headers.get("Content-Type"),
                         "size": len(self._body())})
            self._reply(200, {})

        def log_message(self, *a):
            pass

    FAKE = {"connected": False}
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    th.Thread(target=srv.serve_forever, daemon=True).start()
    BASE = f"http://127.0.0.1:{srv.server_port}"
    try:
        assert status() == {"ready": False, "missing": ["COMPOSIO_API_KEY"]}
        os.environ["COMPOSIO_API_KEY"], os.environ["AERA_COMPOSIO_BASE"] = "k-test", BASE
        forget()
        s = status()
        assert not s["ready"] and s.get("connectable") and "no gmail mailbox" in s["missing"][0], s
        assert "another-app-user" not in json.dumps(s), "a stranger's mailbox is never offered"

        link = connect_link("gmail", "http://localhost:3000/contacts")
        posted = seen[-1]["body"]
        assert link["url"] == "https://connect.example/x" and posted["user_id"] == "aera" \
            and posted["auth_config_id"] == "ac_1", posted

        FAKE["connected"] = True
        forget()
        assert account()["id"] == "ca_ours", "ours, though the server listed a stranger's first"
        pdf = (b"%PDF-1.4 test", "report.pdf", "application/pdf")
        mid = send_email("buyer@co.example", "Report", "Attached.", [pdf])
        assert mid == "18f0c1", mid
        put = next(x for x in seen if x["m"] == "PUT")
        assert put["type"] == "application/pdf" and put["size"] == len(pdf[0]), put
        sent = [x for x in seen if x["path"] == "/tools/execute/GMAIL_SEND_EMAIL"][-1]["body"]
        assert sent["connected_account_id"] == "ca_ours" and sent["version"] == GMAIL_VERSION
        assert sent["arguments"]["attachment"] == [{"name": "report.pdf", "mimetype": "application/pdf",
                                                    "s3key": "projects/p/report.pdf"}], sent
        assert all(x.get("key") in (None, "k-test") for x in seen)
        assert status()["sender"] == "ops@co.example"

        try:
            send_email("bounce@x.example", "s", "b")
            raise AssertionError("a refused send must raise")
        except Failed as e:
            assert "Invalid To header" in str(e) and "log_1" in str(e)
        try:
            send_email("a@co.example", "s", "b", [(b"x" * (MAX_ATTACHMENTS_BYTES + 1), "big.pdf",
                                                   "application/pdf")])
            raise AssertionError("an oversized message must be refused before it is sent")
        except Failed as e:
            assert "attachments" in str(e)

        os.environ["AERA_COMPOSIO_ACCOUNT"] = "ca_other"
        forget()
        try:
            account()
            raise AssertionError("a pinned account that is not AERA's must be refused")
        except NotConnected as e:
            assert "another user" in str(e)
    finally:
        srv.shutdown()
        forget()
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    print("  composio: no key says so ✓ · only AERA's own mailbox, never another user's ✓ "
          "· connect link for AERA's user ✓ · attachment uploaded with its type ✓ "
          "· refusal and oversize raise ✓")
    print("composio ok")


if __name__ == "__main__":
    demo()
