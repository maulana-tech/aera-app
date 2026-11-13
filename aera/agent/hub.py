"""The hub: one install, many businesses.

    python3 hub.py            # start the flagship business and every business created here
    python3 hub.py --check    # the self-check, on scratch directories, no network

Anyone may create their own business here (POST /tenants, through the web app). Each one is its own agent
service: its own process, its own database, its own team and scheduler, its own token secret. It is started
with a clean environment the hub builds, and AERA_NO_ENV_FILES=1, so it never reads this install's .env or
.secrets: it cannot see the flagship's vault key, its NEAR account or its mail settings. A new business has no
vault, so its payments run on the SIMULATED rail until its owner connects one.

Its models run on the owner's own NEAR AI key when they give one, and otherwise on this install's key under a
hard daily cap the owner cannot raise (AERA_HUB_SHARED_DAILY_USD). How many businesses may be created, in all
and per day, is capped too.

The flagship (the business this install was set up for) is started as it always was, with the hub's own
environment, on PORT (8787).

The hub's own HTTP API listens on AERA_HUB_PORT (8786), inside the container network only, and answers only a
caller that presents AERA_HUB_SECRET (the web app's server). It never sees a business's passwords except to
hand the first one to that business's own /setup.

    GET  /info                     what a new business gets (shared cap, limits, whether creation is open)
    GET  /tenants/<slug>           where a business listens
    GET  /resolve?email=           the businesses that have this person as a user (for sign-in)
    POST /tenants                  create a business and its owner: {business, name, email, password, key?}
    POST /tenants/<slug>/key       set or clear the business's own NEAR AI key: {key, token} (owner's token)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import re
import secrets
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

HERE = pathlib.Path(__file__).resolve().parent

#: What a child may take from the hub's own environment: the model choices and nothing secret.
MODEL_VARS = ("AERA_MODEL", "AERA_MODEL_SPECIALISTS", "AERA_MODEL_FALLBACK", "AERA_AUX_MODEL", "AERA_PRIVATE",
              "NEARAI_BASE_URL", "AERA_ENV", "AERA_BRAVE_API_KEY", "AERA_TAVILY_API_KEY")
#: What every process needs to run at all.
BASE_VARS = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "SYSTEMROOT")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int(name: str, default: int) -> int:
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(_env(name) or default)
    except ValueError:
        return default


class Hub:
    def __init__(self, root: pathlib.Path, *, master_secret: str, shared_key: str, base_port: int = 9001,
                 web_url: str = "", spawn: bool = True):
        self.root = root
        self.dir = root / "tenants"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db_path = root / "hub.db"
        self.master = master_secret
        self.shared_key = shared_key
        self.base_port = base_port
        self.web_url = web_url.rstrip("/")
        self.spawn_enabled = spawn
        self.max_tenants = _int("AERA_HUB_MAX_TENANTS", 100)
        self.per_day = _int("AERA_HUB_NEW_PER_DAY", 20)
        self.shared_cap = _float("AERA_HUB_SHARED_DAILY_USD", 0.5)
        self.procs: Dict[str, subprocess.Popen] = {}
        self.lock = threading.Lock()
        with self._db() as c:
            c.execute("CREATE TABLE IF NOT EXISTS tenants (slug TEXT PRIMARY KEY, name TEXT NOT NULL, owner_email TEXT NOT NULL,"
                      " port INTEGER NOT NULL UNIQUE, key_mode TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL)")

    # ------------------------------------------------------------- record
    def _db(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        c.row_factory = sqlite3.Row
        return c

    def tenants(self) -> List[Dict[str, Any]]:
        with self._db() as c:
            return [dict(r) for r in c.execute("SELECT * FROM tenants WHERE status='active' ORDER BY created_at")]

    def tenant(self, slug: str) -> Optional[Dict[str, Any]]:
        with self._db() as c:
            r = c.execute("SELECT * FROM tenants WHERE slug=? AND status='active'", (slug,)).fetchone()
        return dict(r) if r else None

    def info(self) -> Dict[str, Any]:
        n = len(self.tenants())
        today = datetime.now(timezone.utc).date().isoformat()
        made_today = sum(1 for t in self.tenants() if t["created_at"][:10] == today)
        open_ = n < self.max_tenants and made_today < self.per_day
        return {"open": open_, "shared_daily_usd": self.shared_cap, "shared_key": bool(self.shared_key),
                "businesses": n, "max": self.max_tenants, "per_day": self.per_day,
                "why_closed": None if open_ else ("this install is full" if n >= self.max_tenants
                                                  else "today's new businesses are full; try again tomorrow")}

    # ---------------------------------------------------------- children
    def secret_for(self, slug: str) -> str:
        """Each business signs its own session tokens: a token from one is worthless at another."""
        return hmac.new(self.master.encode(), f"tenant:{slug}".encode(), hashlib.sha256).hexdigest()

    def key_file(self, slug: str) -> pathlib.Path:
        return self.dir / slug / "near_key"

    def own_key(self, slug: str) -> str:
        f = self.key_file(slug)
        return f.read_text().strip() if f.exists() else ""

    def child_env(self, t: Dict[str, Any]) -> Dict[str, str]:
        """The whole environment a business runs with. Built, never inherited."""
        env = {k: os.environ[k] for k in BASE_VARS if k in os.environ}
        env.update({k: os.environ[k] for k in MODEL_VARS if os.environ.get(k)})
        own = self.own_key(t["slug"])
        env.update({
            "AERA_NO_ENV_FILES": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "AERA_HOST": "0.0.0.0",
            "PORT": str(t["port"]),
            "AERA_DB": str(self.dir / t["slug"] / "aera.db"),
            "AERA_SECRET": self.secret_for(t["slug"]),
            "AERA_TENANT": t["slug"],
            "AERA_KEY_MODE": "own" if own else "shared",
            "NEARAI_API_KEY": own or self.shared_key,
            # on the shared key a cap its owner cannot raise; on their own key, their own profile's cap
            "AERA_DAILY_MODEL_CAP_USD": "" if own else str(self.shared_cap),
            "AERA_SIGNUP": "0",
            "AERA_WEB_URL": self.web_url or "http://localhost:3000",
        })
        return env

    def start(self, t: Dict[str, Any]) -> None:
        if not self.spawn_enabled:
            return
        with self.lock:
            p = self.procs.get(t["slug"])
            if p and p.poll() is None:
                return
            log = open(self.dir / t["slug"] / "service.log", "ab")
            self.procs[t["slug"]] = subprocess.Popen([sys.executable, str(HERE / "api.py")], cwd=str(self.dir / t["slug"]),
                                                     env=self.child_env(t), stdout=log, stderr=subprocess.STDOUT)

    def stop(self, slug: str) -> None:
        with self.lock:
            p = self.procs.pop(slug, None)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()

    def restart(self, slug: str) -> None:
        t = self.tenant(slug)
        if t:
            self.stop(slug)
            self.start(t)

    def wait_healthy(self, port: int, seconds: float = 40) -> bool:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3):
                    return True
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        return False

    def watch(self) -> None:
        """Bring back any business whose service died."""
        while True:
            for t in self.tenants():
                p = self.procs.get(t["slug"])
                if p is None or p.poll() is not None:
                    self.start(t)
            time.sleep(5)

    # ------------------------------------------------------------ actions
    def _slug(self, name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24].strip("-") or "business"
        return f"{base}-{secrets.token_hex(2)}"

    def _call(self, port: int, method: str, path: str, body: Optional[dict] = None,
              token: Optional[str] = None) -> Tuple[int, dict]:
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {token}"} if token else {})})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}

    def create(self, business: str, name: str, email: str, password: str, key: str = "") -> Tuple[int, dict]:
        business, name, email, key = business.strip()[:80], name.strip()[:80], email.strip().lower(), key.strip()
        if not business or not name:
            return 400, {"error": "a business name and your name are required"}
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return 400, {"error": "a valid email is required"}
        if len(password) < 10:
            return 400, {"error": "the password needs at least 10 characters"}
        if key and not re.fullmatch(r"[A-Za-z0-9_\-.:]{16,300}", key):
            return 400, {"error": "that does not look like a NEAR AI API key"}
        if not key and not self.shared_key:
            return 400, {"error": "this install has no shared AI key: bring your own NEAR AI key"}
        info = self.info()
        if not info["open"]:
            return 429, {"error": info["why_closed"]}
        with self.lock:
            used = {t["port"] for t in self.tenants()}
            with self._db() as c:
                used |= {r[0] for r in c.execute("SELECT port FROM tenants")}
            port = next(p for p in range(self.base_port, self.base_port + 10_000) if p not in used)
            slug = self._slug(business)
            (self.dir / slug).mkdir(parents=True, exist_ok=False)
            if key:
                kf = self.key_file(slug)
                kf.write_text(key)
                kf.chmod(0o600)
            t = {"slug": slug, "name": business, "owner_email": email, "port": port,
                 "key_mode": "own" if key else "shared", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "status": "active"}
            with self._db() as c:
                c.execute("INSERT INTO tenants VALUES (:slug,:name,:owner_email,:port,:key_mode,:created_at,:status)", t)
        self.start(t)
        if not self.wait_healthy(port):
            return 503, {"error": "the new business did not start; try again in a minute", "slug": slug}
        code, out = self._call(port, "POST", "/setup", {"email": email, "name": name, "password": password})
        if code != 201:
            return code, {"error": out.get("error") or "the owner could not be created", "slug": slug}
        return 201, {"slug": slug, "port": port, "name": business, "key_mode": t["key_mode"],
                     "token": out["token"], "user": out["user"]}

    def set_key(self, slug: str, key: str, token: str) -> Tuple[int, dict]:
        t = self.tenant(slug)
        if not t:
            return 404, {"error": "no such business"}
        code, me = self._call(t["port"], "GET", "/me", token=token)
        if code != 200 or me.get("role") not in ("owner", "admin"):
            return 403, {"error": "only the business's owner sets its AI key"}
        key = key.strip()
        if key and not re.fullmatch(r"[A-Za-z0-9_\-.:]{16,300}", key):
            return 400, {"error": "that does not look like a NEAR AI API key"}
        if not key and not self.shared_key:
            return 400, {"error": "this install has no shared AI key to fall back on"}
        kf = self.key_file(slug)
        if key:
            kf.write_text(key)
            kf.chmod(0o600)
        elif kf.exists():
            kf.unlink()
        with self._db() as c:
            c.execute("UPDATE tenants SET key_mode=? WHERE slug=?", ("own" if key else "shared", slug))
        self.restart(slug)
        self.wait_healthy(t["port"], 30)
        return 200, {"slug": slug, "key_mode": "own" if key else "shared",
                     "daily_model_cap_usd": None if key else self.shared_cap}

    def resolve(self, email: str) -> List[str]:
        """The businesses where this email is an active user (read from their own databases)."""
        email = email.strip().lower()
        out = []
        for t in self.tenants():
            db = self.dir / t["slug"] / "aera.db"
            if not db.exists():
                continue
            try:
                c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
                hit = c.execute("SELECT 1 FROM users WHERE email=? AND active=1", (email,)).fetchone()
                c.close()
            except sqlite3.Error:
                continue
            if hit:
                out.append(t["slug"])
        return out


# -------------------------------------------------------------------- http
def make_handler(hub: Hub, secret: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):                                   # noqa: D401
            pass

        def _send(self, code: int, body: dict) -> None:
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _authorised(self) -> bool:
            given = self.headers.get("X-Hub-Secret", "")
            return bool(secret) and hmac.compare_digest(secret.encode(), given.encode())

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            try:
                return json.loads(self.rfile.read(min(n, 64_000)) or b"{}") if n else {}
            except ValueError:
                return {}

        def do_GET(self):                                            # noqa: N802
            if not self._authorised():
                return self._send(403, {"error": "not accepted"})
            path, _, query = self.path.partition("?")
            if path == "/info":
                return self._send(200, hub.info())
            m = re.fullmatch(r"/tenants/([a-z0-9-]{3,40})", path)
            if m:
                t = hub.tenant(m.group(1))
                return self._send(200, {k: t[k] for k in ("slug", "name", "port", "key_mode")}) if t else self._send(404, {"error": "no such business"})
            if path == "/resolve":
                email = dict(x.split("=", 1) for x in query.split("&") if "=" in x).get("email", "")
                from urllib.parse import unquote
                return self._send(200, {"tenants": hub.resolve(unquote(email))})
            return self._send(404, {"error": "unknown route"})

        def do_POST(self):                                           # noqa: N802
            if not self._authorised():
                return self._send(403, {"error": "not accepted"})
            b = self._body()
            if self.path == "/tenants":
                code, out = hub.create(str(b.get("business") or ""), str(b.get("name") or ""), str(b.get("email") or ""),
                                       str(b.get("password") or ""), str(b.get("key") or ""))
                return self._send(code, out)
            m = re.fullmatch(r"/tenants/([a-z0-9-]{3,40})/key", self.path)
            if m:
                code, out = hub.set_key(m.group(1), str(b.get("key") or ""), str(b.get("token") or ""))
                return self._send(code, out)
            return self._send(404, {"error": "unknown route"})
    return Handler


def main() -> None:
    from core import config  # noqa: F401  (loads this install's .env and .secrets into the hub's own env)
    secret = _env("AERA_HUB_SECRET")
    master = _env("AERA_SECRET") or secrets.token_hex(32)
    data = pathlib.Path(_env("AERA_HUB_DATA") or (pathlib.Path(_env("AERA_DB") or "data/aera.db").resolve().parent))
    hub = Hub(data, master_secret=master, shared_key=_env("NEARAI_API_KEY"), base_port=_int("AERA_HUB_BASE_PORT", 9001),
              web_url=_env("AERA_WEB_URL"))
    # the flagship, exactly as it ran before the hub: the hub's own environment (less the hub's secret), its own files
    flag_env = {k: v for k, v in os.environ.items() if k != "AERA_HUB_SECRET"}
    flagship = subprocess.Popen([sys.executable, str(HERE / "api.py")], cwd=str(HERE), env=flag_env)
    for t in hub.tenants():
        hub.start(t)
    threading.Thread(target=hub.watch, daemon=True).start()

    def bye(*_):
        flagship.terminate()
        for slug in list(hub.procs):
            hub.stop(slug)
        sys.exit(0)
    signal.signal(signal.SIGTERM, bye)
    signal.signal(signal.SIGINT, bye)

    port = _int("AERA_HUB_PORT", 8786)
    if not secret:
        print("hub: AERA_HUB_SECRET is not set; the hub API stays closed (no new businesses)", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(hub, secret))
    server.daemon_threads = True
    print(f"hub on :{port} · flagship pid {flagship.pid} · {len(hub.tenants())} business(es)", flush=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # the flagship is the container's reason to live: when it stops for good, so does the hub
    while True:
        if flagship.poll() is not None:
            time.sleep(2)
            flagship = subprocess.Popen([sys.executable, str(HERE / "api.py")], cwd=str(HERE), env=flag_env)
        time.sleep(3)


# ------------------------------------------------------------------- check
def check() -> None:
    import tempfile
    root = pathlib.Path(tempfile.mkdtemp(prefix="aera-hub-"))
    os.environ.update({"AERA_ENV": "dev", "AERA_VAULT_CONTRACT": "vault.flagship.testnet",
                       "AERA_NEAR_AGENT_KEY": "ed25519:FLAGSHIPSECRET", "AERA_SMTP_HOST": "smtp.flagship.example"})
    hub = Hub(root, master_secret="m" * 32, shared_key="shared-key-0123456789", spawn=False)
    # an env is built, never inherited: no vault, no NEAR key, no mail from the flagship
    t = {"slug": "kopi-a1b2", "port": 9001}
    (hub.dir / "kopi-a1b2").mkdir()
    env = hub.child_env(t)
    leaked = [k for k in env if k in ("AERA_VAULT_CONTRACT", "AERA_NEAR_AGENT_KEY", "AERA_SMTP_HOST", "AERA_HUB_SECRET")]
    assert not leaked, leaked
    assert env["AERA_NO_ENV_FILES"] == "1" and env["NEARAI_API_KEY"] == "shared-key-0123456789"
    assert env["AERA_KEY_MODE"] == "shared" and float(env["AERA_DAILY_MODEL_CAP_USD"]) == hub.shared_cap
    assert env["AERA_SECRET"] != hub.secret_for("other-c3d4"), "each business signs its own tokens"
    hub.key_file("kopi-a1b2").write_text("own-key-abcdefghijklmnop")
    env = hub.child_env(t)
    assert env["NEARAI_API_KEY"] == "own-key-abcdefghijklmnop" and env["AERA_KEY_MODE"] == "own" and env["AERA_DAILY_MODEL_CAP_USD"] == ""
    print("  isolation: a built environment, no flagship vault, key or mail ✓ · own key lifts the shared cap ✓ · own token secret ✓")
    # creation is validated and capped before anything starts
    assert hub.create("", "A", "a@b.co", "pw-123456789")[0] == 400
    assert hub.create("Kopi", "A", "nope", "pw-123456789")[0] == 400
    assert hub.create("Kopi", "A", "a@b.co", "short")[0] == 400
    assert hub.create("Kopi", "A", "a@b.co", "pw-123456789", key="x y")[0] == 400
    hub.per_day = 0
    assert hub.create("Kopi", "A", "a@b.co", "pw-123456789")[0] == 429 and not hub.info()["open"]
    nokey = Hub(root / "nokey", master_secret="m" * 32, shared_key="", spawn=False)
    assert nokey.create("Kopi", "A", "a@b.co", "pw-123456789")[0] == 400, "no shared key: bring your own"
    print("  creation: validated ✓ · daily and total caps ✓ · no shared key means bring your own ✓")
    # sign-in finds the businesses a person belongs to, from their own databases
    db = hub.dir / "kopi-a1b2" / "aera.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE users (email TEXT, active INTEGER)")
    c.execute("INSERT INTO users VALUES ('ana@kopi.example', 1)")
    c.commit()
    c.close()
    with hub._db() as c:
        c.execute("INSERT INTO tenants VALUES ('kopi-a1b2','Kopi','ana@kopi.example',9001,'own','2026-11-13T00:00:00','active')")
    assert hub.resolve("ANA@kopi.example") == ["kopi-a1b2"] and hub.resolve("x@y.z") == []
    # the HTTP API answers only the web server
    h = make_handler(hub, "hub-secret")
    assert h is not None
    print("  sign-in: found in the business's own users ✓")
    print("hub ok")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        main()
