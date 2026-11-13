"""Persistence. SQLite, one file, zero dependencies.

# ponytail: SQLite; move to Postgres once this is multi-tenant or needs concurrent writes

What lands here is the official record of the business AERA runs: the profile
a person wrote, the team composed from it, every piece of work and how it was
handled, what the agents decided and on what evidence, who approved it, what
money moved and the proof that a model ran where it said it ran.

Rows in `actions`, `approvals`, `payments` and `guardian_checks` are never
rewritten to say something else; a correction is a new row (status columns
move forward only).
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional

from core.config import CFG

SCHEMA = """
-- The business a person defined. One active row; every edit is a new version,
-- so "what were the rules when the agent did that" always has an answer.
CREATE TABLE IF NOT EXISTS business (
  version     INTEGER PRIMARY KEY AUTOINCREMENT,
  profile     TEXT NOT NULL,             -- JSON, see core/business.py
  active      INTEGER NOT NULL DEFAULT 1,
  changed_by  TEXT NOT NULL,
  note        TEXT,
  at          TEXT NOT NULL
);

-- The team. Composed from the profile (core/team.py); three core roles are
-- always present and cannot be disabled. A specialist proposed by a model is
-- `draft` until a person approves it.
CREATE TABLE IF NOT EXISTS agents (
  code        TEXT PRIMARY KEY,          -- supervisor | guardian | treasurer | <slug>
  nickname    TEXT NOT NULL,
  title       TEXT NOT NULL,
  brief       TEXT NOT NULL,
  role        TEXT NOT NULL,             -- a key in agents/roles.py, or 'custom'
  core        INTEGER NOT NULL DEFAULT 0,
  veto        INTEGER NOT NULL DEFAULT 0,
  prompt      TEXT NOT NULL,
  capabilities TEXT NOT NULL DEFAULT '[]',  -- JSON list of capability names
  effort      TEXT NOT NULL DEFAULT 'medium',
  status      TEXT NOT NULL DEFAULT 'active',  -- active | draft | disabled
  version     INTEGER NOT NULL DEFAULT 1,
  origin      TEXT NOT NULL DEFAULT 'composer', -- composer | person | model
  updated_by  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

-- Everything the team is asked to do. 
CREATE TABLE IF NOT EXISTS work_items (
  id          TEXT PRIMARY KEY,
  kind        TEXT NOT NULL,             -- order | request | goal | payable
  title       TEXT NOT NULL,
  source      TEXT NOT NULL,             -- vault | intents | chat | email | schedule | api
  payload     TEXT NOT NULL,             -- JSON
  dedup_key   TEXT UNIQUE,
  status      TEXT NOT NULL DEFAULT 'new', -- new | running | done | held | failed
  received_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  id            TEXT PRIMARY KEY,
  work_item_id  TEXT NOT NULL REFERENCES work_items(id),
  status        TEXT NOT NULL,           -- running | done | partial | held | failed
  started_at    TEXT NOT NULL,
  finished_at   TEXT,
  cost_usd      REAL DEFAULT 0,
  team_version  TEXT,                    -- JSON {code: version} the run used
  profile_version INTEGER,
  decision      TEXT,                    -- JSON
  error         TEXT
);

CREATE TABLE IF NOT EXISTS steps (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id        TEXT NOT NULL REFERENCES runs(id),
  seq           INTEGER NOT NULL,
  stage         TEXT NOT NULL,
  agent         TEXT NOT NULL,
  agent_name    TEXT NOT NULL,
  summary       TEXT NOT NULL,
  tools         TEXT NOT NULL,           -- JSON array
  origin        TEXT,
  source        TEXT,
  detail        TEXT NOT NULL,           -- JSON
  at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_steps_run ON steps(run_id, seq);

-- Anything that leaves the building or moves money. Never UPDATEd except to
-- move its status forward and stamp what it became.
CREATE TABLE IF NOT EXISTS actions (
  id              TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL REFERENCES runs(id),
  idempotency_key TEXT NOT NULL UNIQUE,  -- a retry never becomes a second payment
  kind            TEXT NOT NULL,         -- payment | refund | message | deliver_order
  autonomous      INTEGER NOT NULL,
  value_usd       REAL NOT NULL DEFAULT 0,
  payload         TEXT NOT NULL,
  status          TEXT NOT NULL,         -- pending | approved | rejected | sent | failed | blocked
  reason          TEXT,                  -- why it waits, or why it was blocked
  reference       TEXT,                  -- tx hash, message id, document hash
  outcome         TEXT,
  outcome_detail  TEXT,
  outcome_at      TEXT,
  created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  action_id     TEXT NOT NULL REFERENCES actions(id),
  decided_by    TEXT NOT NULL,
  role          TEXT NOT NULL,
  decision      TEXT NOT NULL,           -- approved | rejected | escalated
  note          TEXT,
  at            TEXT NOT NULL
);

-- Guardian's rulings. One row per check, whatever the verdict, so "what did the
-- guardian refuse this week" is a query and not a search through prose.
CREATE TABLE IF NOT EXISTS guardian_checks (
  id          TEXT PRIMARY KEY,
  run_id      TEXT,
  action_id   TEXT,
  kind        TEXT NOT NULL,             -- action | counterparty
  subject     TEXT NOT NULL,
  verdict     TEXT NOT NULL,             -- allow | warn | block
  reasons     TEXT NOT NULL,             -- JSON list of {rule, verdict, detail, origin}
  at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_guardian_at ON guardian_checks(at);

-- Money out (through the vault) and money in (orders paid to it), as the chain
-- reported it. `request_id` is the action's idempotency key: idempotent here
-- and on chain.
CREATE TABLE IF NOT EXISTS payments (
  id           TEXT PRIMARY KEY,
  action_id    TEXT REFERENCES actions(id),
  direction    TEXT NOT NULL,            -- out | in | split | refund
  rail         TEXT NOT NULL,            -- vault | intents | simulated
  request_id   TEXT,
  counterparty TEXT NOT NULL,            -- NEAR account or foreign address
  amount_usd   REAL NOT NULL,
  token        TEXT NOT NULL,
  status       TEXT NOT NULL,            -- submitted | sent | pending_onchain | approved | rejected | failed
  tx_hash      TEXT,
  detail       TEXT,                     -- JSON: quote, events, error
  created_at   TEXT NOT NULL,
  settled_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status, created_at);

CREATE TABLE IF NOT EXISTS orders (
  id            TEXT PRIMARY KEY,        -- the order_id the customer paid against
  offering      TEXT NOT NULL,
  customer      TEXT,                    -- NEAR account or contact id
  inputs        TEXT NOT NULL DEFAULT '{}',
  amount_usd    REAL NOT NULL DEFAULT 0,
  status        TEXT NOT NULL,           -- awaiting_payment | paid | working | delivered | refunded | failed
  work_item_id  TEXT,
  paid_tx       TEXT,
  delivery      TEXT,                    -- JSON {hash, file, sent_to}
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

-- Free samples the team published to the public samples page: a snapshot of the document as it was
-- published (later edits to the document do not change what the public reads). Views are a count only.
CREATE TABLE IF NOT EXISTS samples (
  slug            TEXT PRIMARY KEY,
  file_id         TEXT NOT NULL,
  title           TEXT NOT NULL,
  teaser          TEXT NOT NULL DEFAULT '',
  offering        TEXT NOT NULL,
  text            TEXT NOT NULL,
  action_id       TEXT,
  published_at    TEXT NOT NULL,
  unpublished_at  TEXT,
  views           INTEGER NOT NULL DEFAULT 0
);

-- Other businesses that run on AERA: the address of a vendor's AERA, set by a person on its contact.
CREATE TABLE IF NOT EXISTS peers (
  contact_id  TEXT PRIMARY KEY,
  url         TEXT NOT NULL,
  set_by      TEXT NOT NULL,
  at          TEXT NOT NULL
);

-- What this business ordered from another AERA business, and what came back (core/peers.py).
CREATE TABLE IF NOT EXISTS purchases (
  order_id    TEXT PRIMARY KEY,         -- the seller's order id
  contact_id  TEXT NOT NULL,
  url         TEXT NOT NULL,
  offering    TEXT NOT NULL,
  amount_usd  REAL NOT NULL,
  action_id   TEXT,                     -- the payment action on this side
  status      TEXT NOT NULL,            -- ordered | paid | delivered | failed
  file_id     TEXT,                     -- the deliverable, filed as outside text
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

-- Where an order came from, when the checkout link carried a source (a published sample).
CREATE TABLE IF NOT EXISTS order_sources (
  order_id  TEXT PRIMARY KEY,
  source    TEXT NOT NULL,
  at        TEXT NOT NULL
);

-- Proof that a model call ran inside an attested TEE (core/attest.py).
CREATE TABLE IF NOT EXISTS tee_proofs (
  id              TEXT PRIMARY KEY,
  run_id          TEXT,
  step_seq        INTEGER,
  agent           TEXT NOT NULL,
  model           TEXT NOT NULL,
  chat_id         TEXT NOT NULL,
  signing_address TEXT,
  req_sha256      TEXT,
  resp_sha256     TEXT,
  checks          TEXT NOT NULL DEFAULT '[]',
  verdict         TEXT NOT NULL,         -- pending | attested | partial | failed
  created_at      TEXT NOT NULL,
  verified_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_tee_run ON tee_proofs(run_id);
CREATE INDEX IF NOT EXISTS idx_tee_verdict ON tee_proofs(verdict, created_at);

-- What happened to personal data on its way to a channel the business does not control
-- (core/privacy.py): redacted, or sent as it was and why. The text itself is not kept here.
CREATE TABLE IF NOT EXISTS privacy_events (
  id              TEXT PRIMARY KEY,
  notification_id TEXT,
  channel         TEXT NOT NULL,
  outcome         TEXT NOT NULL,         -- redacted | not_redacted
  detail          TEXT,
  at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_privacy_at ON privacy_events(at);

-- Questions from visitors on the public checkout page and Sales' answers (core/public_chat.py).
CREATE TABLE IF NOT EXISTS public_chats (
  id        TEXT PRIMARY KEY,
  session   TEXT NOT NULL,
  offering  TEXT,
  role      TEXT NOT NULL,               -- visitor | sales
  text      TEXT NOT NULL,
  cost_usd  REAL NOT NULL DEFAULT 0,
  note      TEXT,                        -- withheld: why · checkout prefilled · model unavailable
  at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_public_chats_at ON public_chats(at);

-- What the business knows that no API does: price lists, briefs, style
-- guides. Text only; read by the agents through read_business_file.
CREATE TABLE IF NOT EXISTS files (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  mime        TEXT NOT NULL,
  text        TEXT NOT NULL,
  size        INTEGER NOT NULL,
  uploaded_by TEXT NOT NULL,
  uploaded_at TEXT NOT NULL
);

-- People and accounts the business deals with. The payout address of a
-- counterparty lives here and ONLY here: a payment tool reads it from this
-- row, never from a model or a message.
CREATE TABLE IF NOT EXISTS contacts (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  role        TEXT NOT NULL,             -- customer | vendor | contributor | team | approver
  email       TEXT NOT NULL DEFAULT '',
  notify_for  TEXT NOT NULL DEFAULT '',  -- work kinds, comma separated; * = all
  near_account TEXT,
  payout_chain TEXT,                     -- near | base | eth | sol | ...
  payout_address TEXT,
  address_changed_at TEXT,
  phone       TEXT,
  title       TEXT,
  department  TEXT,
  notes       TEXT,
  active      INTEGER NOT NULL DEFAULT 1,
  created_at  TEXT NOT NULL,
  updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
  id         TEXT PRIMARY KEY,
  agent      TEXT NOT NULL,
  user_id    TEXT NOT NULL,
  title      TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversations_owner
  ON conversations(user_id, agent, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  seq     INTEGER NOT NULL,
  role    TEXT NOT NULL,                -- person | agent | error
  body    TEXT NOT NULL,
  at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, seq);

CREATE TABLE IF NOT EXISTS mcp_servers (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  url         TEXT NOT NULL,
  token       TEXT,
  enabled     INTEGER NOT NULL DEFAULT 1,
  agents      TEXT NOT NULL DEFAULT '[]',
  tools       TEXT NOT NULL DEFAULT '[]',
  last_ok     TEXT,
  last_error  TEXT,
  added_by    TEXT NOT NULL,
  added_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skills (
  name        TEXT PRIMARY KEY,
  title       TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  agents      TEXT NOT NULL DEFAULT '[]',
  tools       TEXT NOT NULL DEFAULT '[]',
  steps       TEXT NOT NULL DEFAULT '[]',
  added_by    TEXT NOT NULL,
  added_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_usage (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  skill      TEXT NOT NULL,
  agent      TEXT NOT NULL,
  run_id     TEXT,
  found      INTEGER NOT NULL,
  at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_skill_usage ON skill_usage(skill, at);

CREATE TABLE IF NOT EXISTS settings (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
  id         TEXT PRIMARY KEY,
  dedup_key  TEXT NOT NULL UNIQUE,
  run_id     TEXT,
  kind       TEXT NOT NULL,              -- handling | digest | test | outreach | delivery
  channel    TEXT NOT NULL,              -- email | slack | telegram | webhook
  address    TEXT NOT NULL,
  subject    TEXT NOT NULL,
  body       TEXT NOT NULL,
  status     TEXT NOT NULL,              -- pending | sent | failed | skipped
  attempts   INTEGER NOT NULL DEFAULT 0,
  error      TEXT,
  attachments TEXT,
  action_id  TEXT,
  reference  TEXT,
  created_at TEXT NOT NULL,
  sent_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status, created_at);

CREATE TABLE IF NOT EXISTS jobs (
  name         TEXT PRIMARY KEY,
  enabled      INTEGER NOT NULL DEFAULT 1,
  last_started TEXT,
  last_finished TEXT,
  last_status  TEXT,
  last_detail  TEXT,
  runs         INTEGER NOT NULL DEFAULT 0,
  failures     INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _j(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def _load(v: Optional[str], default: Any = None) -> Any:
    if v is None or v == "":
        return default
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return default


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    p = pathlib.Path(CFG.database)
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA journal_mode = WAL")
    try:
        c.executescript(SCHEMA)
        yield c
        c.commit()
    finally:
        c.close()


# ------------------------------------------------------------------- business
def active_profile() -> Optional[Dict[str, Any]]:
    """The business profile in force, with its version, or None before onboarding."""
    with connect() as c:
        r = c.execute("SELECT * FROM business WHERE active=1 ORDER BY version DESC LIMIT 1").fetchone()
    if not r:
        return None
    return {**_load(r["profile"], {}), "_version": r["version"], "_changed_by": r["changed_by"],
            "_at": r["at"]}


def save_profile(profile: Dict[str, Any], by: str, note: str = "") -> int:
    """Write a new version and make it the only active one. Returns the version."""
    clean = {k: v for k, v in profile.items() if not k.startswith("_")}
    with connect() as c:
        c.execute("UPDATE business SET active=0 WHERE active=1")
        cur = c.execute("INSERT INTO business (profile, active, changed_by, note, at) VALUES (?,?,?,?,?)",
                        (_j(clean), 1, by, note or None, _now()))
        return int(cur.lastrowid)


def profile_history(limit: int = 20) -> List[Dict[str, Any]]:
    with connect() as c:
        rows = c.execute("SELECT version, active, changed_by, note, at FROM business"
                         " ORDER BY version DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------- agents
_AGENT_JSON = ("capabilities",)


def _agent(r: sqlite3.Row) -> Dict[str, Any]:
    d = dict(r)
    d["capabilities"] = _load(d.get("capabilities"), [])
    d["core"], d["veto"] = bool(d["core"]), bool(d["veto"])
    return d


def list_agents(include_inactive: bool = False) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM agents" + ("" if include_inactive else " WHERE status='active'")
    with connect() as c:
        rows = c.execute(sql + " ORDER BY core DESC, code").fetchall()
    return [_agent(r) for r in rows]


def get_agent(code: str) -> Optional[Dict[str, Any]]:
    with connect() as c:
        r = c.execute("SELECT * FROM agents WHERE code=?", (code,)).fetchone()
    return _agent(r) if r else None


def upsert_agent(a: Dict[str, Any], by: str) -> Dict[str, Any]:
    """Insert, or update and bump the version when anything that matters changed."""
    fields = ("nickname", "title", "brief", "role", "core", "veto", "prompt", "capabilities",
              "effort", "status", "origin")
    vals = {k: a.get(k) for k in fields}
    vals["capabilities"] = _j(list(a.get("capabilities") or []))
    vals["core"], vals["veto"] = int(bool(a.get("core"))), int(bool(a.get("veto")))
    vals["effort"] = vals["effort"] or "medium"
    vals["status"] = vals["status"] or "active"
    vals["origin"] = vals["origin"] or "composer"
    with connect() as c:
        old = c.execute("SELECT * FROM agents WHERE code=?", (a["code"],)).fetchone()
        if old is None:
            c.execute("INSERT INTO agents (code," + ",".join(fields) + ", version, updated_by, updated_at)"
                      " VALUES (?," + ",".join("?" * len(fields)) + ",1,?,?)",
                      (a["code"], *[vals[k] for k in fields], by, _now()))
        else:
            changed = any(str(old[k]) != str(vals[k]) for k in fields)
            if changed:
                c.execute("UPDATE agents SET " + ", ".join(f"{k}=?" for k in fields)
                          + ", version=version+1, updated_by=?, updated_at=? WHERE code=?",
                          (*[vals[k] for k in fields], by, _now(), a["code"]))
        return _agent(c.execute("SELECT * FROM agents WHERE code=?", (a["code"],)).fetchone())


def set_agent_status(code: str, status: str, by: str) -> Optional[Dict[str, Any]]:
    if status not in ("active", "draft", "disabled"):
        raise ValueError(f"unknown status {status!r}")
    with connect() as c:
        r = c.execute("SELECT core FROM agents WHERE code=?", (code,)).fetchone()
        if r is None:
            return None
        if r["core"] and status != "active":
            raise ValueError(f"'{code}' is a core role and cannot be {status}")
        c.execute("UPDATE agents SET status=?, version=version+1, updated_by=?, updated_at=?"
                  " WHERE code=?", (status, by, _now(), code))
    return get_agent(code)


def delete_agent(code: str) -> bool:
    with connect() as c:
        r = c.execute("SELECT core FROM agents WHERE code=?", (code,)).fetchone()
        if r is None or r["core"]:
            return False
        c.execute("DELETE FROM agents WHERE code=?", (code,))
    return True


# ----------------------------------------------------------------- work items
def record_work_item(kind: str, title: str, source: str, payload: dict,
                     dedup_key: Optional[str] = None) -> Optional[str]:
    """Write a work item. A dedup_key already on record returns None: the same
    paid order or the same inbound message is never worked twice."""
    wid = new_id("wrk")
    with connect() as c:
        try:
            c.execute("INSERT INTO work_items (id, kind, title, source, payload, dedup_key, status,"
                      " received_at) VALUES (?,?,?,?,?,?,?,?)",
                      (wid, kind, title, source, _j(payload), dedup_key, "new", _now()))
        except sqlite3.IntegrityError:
            return None
    return wid


def get_work_item(wid: str) -> Optional[Dict[str, Any]]:
    with connect() as c:
        r = c.execute("SELECT * FROM work_items WHERE id=?", (wid,)).fetchone()
    return dict(r) | {"payload": _load(r["payload"], {})} if r else None


def note_run_again(wid: str, by: str) -> Dict[str, Any]:
    """Record on the work item who ran it again, so the team can tell a person's retry from an attack."""
    item = get_work_item(wid)
    payload = dict(item.get("payload") or {})
    payload["runs_again"] = [*payload.get("runs_again", []), {"by": by, "at": _now()}][-10:]
    with connect() as c:
        c.execute("UPDATE work_items SET payload=? WHERE id=?", (_j(payload), wid))
    return get_work_item(wid)


def set_work_status(wid: str, status: str) -> None:
    with connect() as c:
        c.execute("UPDATE work_items SET status=? WHERE id=?", (status, wid))


def list_work_items(limit: int = 100, status: Optional[str] = None) -> List[Dict[str, Any]]:
    sql, args = "SELECT w.*, (SELECT r.id FROM runs r WHERE r.work_item_id=w.id ORDER BY r.started_at DESC LIMIT 1) AS run_id FROM work_items w", []
    if status:
        sql += " WHERE w.status=?"
        args.append(status)
    with connect() as c:
        rows = c.execute(sql + " ORDER BY w.received_at DESC LIMIT ?", (*args, limit)).fetchall()
    return [dict(r) | {"payload": _load(r["payload"], {})} for r in rows]


def next_new_work_item() -> Optional[Dict[str, Any]]:
    """Claim the oldest new item (atomic: the UPDATE only wins once)."""
    with connect() as c:
        r = c.execute("SELECT id FROM work_items WHERE status='new' ORDER BY received_at LIMIT 1").fetchone()
        if not r:
            return None
        won = c.execute("UPDATE work_items SET status='running' WHERE id=? AND status='new'",
                        (r["id"],)).rowcount
    return get_work_item(r["id"]) if won else None


# ----------------------------------------------------------------------- runs
def start_run(work_item_id: str, team_version: Optional[dict] = None,
              profile_version: Optional[int] = None) -> str:
    rid = new_id("run")
    with connect() as c:
        c.execute("INSERT INTO runs (id, work_item_id, status, started_at, team_version, profile_version)"
                  " VALUES (?,?,?,?,?,?)",
                  (rid, work_item_id, "running", _now(), _j(team_version or {}), profile_version))
        c.execute("UPDATE work_items SET status='running' WHERE id=?", (work_item_id,))
    return rid


def close_run(run_id: str, status: str, decision: Optional[dict] = None,
              error: Optional[str] = None, cost_usd: float = 0.0) -> None:
    with connect() as c:
        c.execute("UPDATE runs SET status=?, finished_at=?, decision=?, error=?, cost_usd=? WHERE id=?",
                  (status, _now(), _j(decision) if decision else None, error, float(cost_usd or 0), run_id))
        r = c.execute("SELECT work_item_id FROM runs WHERE id=?", (run_id,)).fetchone()
        if r:
            ws = {"done": "done", "partial": "done", "held": "held"}.get(status, "failed")
            if status == "partial" and (decision or {}).get("retryable"):
                ws = "held"      # stopped early with no outcome: a paid order must not read as done
            c.execute("UPDATE work_items SET status=? WHERE id=?", (ws, r["work_item_id"]))


def save_step(run_id: str, s: dict) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO steps (run_id, seq, stage, agent, agent_name, summary,"
            " tools, origin, source, detail, at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, s["seq"], s["stage"], s["agent"], s["agent_name"], s["summary"],
             _j(s["tools"]), s.get("origin"), s.get("source"), _j(s.get("detail", {})), s["at"]),
        )


def list_runs(limit: int = 50) -> List[dict]:
    with connect() as c:
        rows = c.execute(
            "SELECT r.*, w.title, w.kind, w.source AS work_source,"
            " (SELECT count(*) FROM steps s WHERE s.run_id = r.id) AS step_count,"
            " (SELECT count(*) FROM steps s WHERE s.run_id = r.id AND s.stage = 'TOOL') AS tool_count,"
            " (SELECT count(*) FROM actions a WHERE a.run_id = r.id) AS action_count,"
            " (SELECT count(*) FROM tee_proofs t WHERE t.run_id = r.id AND t.verdict='attested') AS attested,"
            " (SELECT count(*) FROM tee_proofs t WHERE t.run_id = r.id) AS proofs"
            " FROM runs r JOIN work_items w ON w.id = r.work_item_id"
            " ORDER BY r.started_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) | {"decision": _load(r["decision"]), "team_version": _load(r["team_version"], {})}
            for r in rows]


def get_run(run_id: str) -> Optional[dict]:
    with connect() as c:
        r = c.execute(
            "SELECT r.*, w.title, w.kind, w.source AS work_source, w.payload AS work_payload"
            " FROM runs r JOIN work_items w ON w.id = r.work_item_id WHERE r.id=?",
            (run_id,)).fetchone()
        if not r:
            return None
        steps = c.execute("SELECT * FROM steps WHERE run_id=? ORDER BY seq", (run_id,)).fetchall()
        actions = c.execute("SELECT * FROM actions WHERE run_id=? ORDER BY created_at", (run_id,)).fetchall()
        approvals = c.execute(
            "SELECT p.* FROM approvals p JOIN actions a ON a.id = p.action_id"
            " WHERE a.run_id=? ORDER BY p.at", (run_id,)).fetchall()
        checks = c.execute("SELECT * FROM guardian_checks WHERE run_id=? ORDER BY at", (run_id,)).fetchall()
    return {
        **dict(r),
        "work_payload": _load(r["work_payload"], {}),
        "decision": _load(r["decision"]),
        "team_version": _load(r["team_version"], {}),
        "steps": [dict(s) | {"tools": _load(s["tools"], []), "detail": _load(s["detail"], {})} for s in steps],
        "actions": [_action(a) for a in actions],
        "approvals": [dict(p) for p in approvals],
        "guardian": [_check(x) for x in checks],
        "proofs": proofs_for_run(run_id),
    }


# -------------------------------------------------------------------- actions
def _action(r: sqlite3.Row) -> Dict[str, Any]:
    return dict(r) | {"payload": _load(r["payload"], {}),
                      "outcome_detail": _load(r["outcome_detail"]),
                      "autonomous": bool(r["autonomous"])}


def record_action(run_id: str, idempotency_key: str, kind: str, autonomous: bool,
                  payload: dict, value_usd: float = 0.0, status: Optional[str] = None,
                  reason: Optional[str] = None) -> Dict[str, Any]:
    """Idempotent: the same key never produces a second action."""
    with connect() as c:
        existing = c.execute("SELECT * FROM actions WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if existing:
            return _action(existing) | {"repeated": True}
        aid = new_id("act")
        c.execute(
            "INSERT INTO actions (id, run_id, idempotency_key, kind, autonomous, value_usd, payload,"
            " status, reason, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (aid, run_id, idempotency_key, kind, int(autonomous), float(value_usd), _j(payload),
             status or ("approved" if autonomous else "pending"), reason, _now()))
        return _action(c.execute("SELECT * FROM actions WHERE id=?", (aid,)).fetchone()) | {"repeated": False}


def get_action(action_id: str) -> Optional[dict]:
    with connect() as c:
        r = c.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
    return _action(r) if r else None


def list_actions(status: Optional[str] = None, kind: Optional[str] = None,
                 limit: int = 100) -> List[Dict[str, Any]]:
    where, args = [], []
    if status:
        where.append("a.status=?")
        args.append(status)
    if kind:
        where.append("a.kind=?")
        args.append(kind)
    sql = ("SELECT a.*, w.title AS work_title FROM actions a JOIN runs r ON r.id=a.run_id"
           " JOIN work_items w ON w.id=r.work_item_id")
    if where:
        sql += " WHERE " + " AND ".join(where)
    with connect() as c:
        rows = c.execute(sql + " ORDER BY a.created_at DESC LIMIT ?", (*args, limit)).fetchall()
    return [_action(r) | {"work_title": r["work_title"]} for r in rows]


#: Status moves forward only. Anything else is a bug, not an update.
_FORWARD = {
    "pending": {"approved", "rejected", "blocked"},
    "approved": {"sent", "failed", "blocked"},
    # A vault payment reads "sent" when the transfer starts; the token can still refuse it.
    "sent": {"failed"},
    "failed": {"approved"},          # a resend after a fix is a fresh approval
    "rejected": set(),
    "blocked": set(),
}


def move_action(action_id: str, status: str, reference: Optional[str] = None,
                reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with connect() as c:
        a = c.execute("SELECT status FROM actions WHERE id=?", (action_id,)).fetchone()
        if a is None:
            return None
        if status != a["status"] and status not in _FORWARD.get(a["status"], set()):
            raise ValueError(f"action {action_id} cannot go from {a['status']} to {status}")
        c.execute("UPDATE actions SET status=?, reference=COALESCE(?, reference),"
                  " reason=COALESCE(?, reason) WHERE id=?", (status, reference, reason, action_id))
    return get_action(action_id)


def decide_action(action_id: str, decided_by: str, role: str, decision: str,
                  note: str = "") -> Dict[str, Any]:
    nxt = {"approved": "approved", "rejected": "rejected", "escalated": "pending"}
    if decision not in nxt:
        raise ValueError(f"unknown decision: {decision}")
    with connect() as c:
        a = c.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        if not a:
            raise KeyError(action_id)
        if a["status"] != "pending":
            return _action(a) | {"unchanged": True}
        c.execute("INSERT INTO approvals (action_id, decided_by, role, decision, note, at)"
                  " VALUES (?,?,?,?,?,?)", (action_id, decided_by, role, decision, note, _now()))
        c.execute("UPDATE actions SET status=? WHERE id=?", (nxt[decision], action_id))
        return _action(c.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone())


def record_outcome(action_id: str, outcome: str, detail: Optional[dict] = None) -> Dict[str, Any]:
    with connect() as c:
        if not c.execute("SELECT 1 FROM actions WHERE id=?", (action_id,)).fetchone():
            raise KeyError(action_id)
        c.execute("UPDATE actions SET outcome=?, outcome_detail=?, outcome_at=? WHERE id=?",
                  (outcome, _j(detail or {}), _now(), action_id))
    return get_action(action_id) or {}


def spent_today_usd(kind: str = "payment") -> float:
    """Autonomous money moved today (UTC), by this service, for the profile's daily cap."""
    day = datetime.now(timezone.utc).date().isoformat()
    with connect() as c:
        r = c.execute("SELECT COALESCE(SUM(value_usd),0) FROM actions WHERE kind=? AND autonomous=1"
                      " AND status IN ('approved','sent') AND substr(created_at,1,10)=?",
                      (kind, day)).fetchone()
    return float(r[0] or 0)


# ------------------------------------------------------------------- guardian
def _check(r: sqlite3.Row) -> Dict[str, Any]:
    return dict(r) | {"reasons": _load(r["reasons"], [])}


def record_check(kind: str, subject: str, verdict: str, reasons: List[dict],
                 run_id: Optional[str] = None, action_id: Optional[str] = None) -> Dict[str, Any]:
    cid = new_id("chk")
    with connect() as c:
        c.execute("INSERT INTO guardian_checks (id, run_id, action_id, kind, subject, verdict, reasons, at)"
                  " VALUES (?,?,?,?,?,?,?,?)", (cid, run_id, action_id, kind, subject, verdict, _j(reasons), _now()))
        return _check(c.execute("SELECT * FROM guardian_checks WHERE id=?", (cid,)).fetchone())


def list_checks(limit: int = 100, verdict: Optional[str] = None) -> List[Dict[str, Any]]:
    sql, args = "SELECT * FROM guardian_checks", []
    if verdict:
        sql += " WHERE verdict=?"
        args.append(verdict)
    with connect() as c:
        rows = c.execute(sql + " ORDER BY at DESC LIMIT ?", (*args, limit)).fetchall()
    return [_check(r) for r in rows]


# ------------------------------------------------------------------- payments
def _payment(r: sqlite3.Row) -> Dict[str, Any]:
    return dict(r) | {"detail": _load(r["detail"], {})}


def record_payment(direction: str, rail: str, counterparty: str, amount_usd: float, token: str,
                   status: str, action_id: Optional[str] = None, request_id: Optional[str] = None,
                   tx_hash: Optional[str] = None, detail: Optional[dict] = None) -> Dict[str, Any]:
    pid = new_id("pay")
    with connect() as c:
        c.execute("INSERT INTO payments (id, action_id, direction, rail, request_id, counterparty, amount_usd,"
                  " token, status, tx_hash, detail, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (pid, action_id, direction, rail, request_id, counterparty, float(amount_usd), token,
                   status, tx_hash, _j(detail or {}), _now()))
        return _payment(c.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone())


def update_payment(pid: str, status: str, tx_hash: Optional[str] = None,
                   detail: Optional[dict] = None) -> Optional[Dict[str, Any]]:
    settled = status in ("sent", "approved", "rejected", "failed")
    with connect() as c:
        old = c.execute("SELECT detail FROM payments WHERE id=?", (pid,)).fetchone()
        if old is None:
            return None
        merged = {**_load(old["detail"], {}), **(detail or {})}
        c.execute("UPDATE payments SET status=?, tx_hash=COALESCE(?, tx_hash), detail=?,"
                  " settled_at=CASE WHEN ? THEN COALESCE(settled_at, ?) ELSE settled_at END WHERE id=?",
                  (status, tx_hash, _j(merged), int(settled), _now(), pid))
        return _payment(c.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone())


def payment_for_action(action_id: str) -> Optional[Dict[str, Any]]:
    with connect() as c:
        r = c.execute("SELECT * FROM payments WHERE action_id=? ORDER BY created_at DESC LIMIT 1",
                      (action_id,)).fetchone()
    return _payment(r) if r else None


def list_payments(limit: int = 200, status: Optional[str] = None) -> List[Dict[str, Any]]:
    sql, args = "SELECT * FROM payments", []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    with connect() as c:
        rows = c.execute(sql + " ORDER BY created_at DESC LIMIT ?", (*args, limit)).fetchall()
    return [_payment(r) for r in rows]


# --------------------------------------------------------------------- orders
def _order(r: sqlite3.Row) -> Dict[str, Any]:
    return dict(r) | {"inputs": _load(r["inputs"], {}), "delivery": _load(r["delivery"])}


def create_order(order_id: str, offering: str, amount_usd: float, inputs: dict,
                 customer: Optional[str] = None, status: str = "awaiting_payment") -> Dict[str, Any]:
    with connect() as c:
        existing = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if existing:
            return _order(existing)
        c.execute("INSERT INTO orders (id, offering, customer, inputs, amount_usd, status, created_at, updated_at)"
                  " VALUES (?,?,?,?,?,?,?,?)",
                  (order_id, offering, customer, _j(inputs), float(amount_usd), status, _now(), _now()))
        return _order(c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())


def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    with connect() as c:
        r = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    return _order(r) if r else None


def update_order(order_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    allowed = ("status", "customer", "work_item_id", "paid_tx", "delivery", "amount_usd")
    sets = {k: (_j(v) if k == "delivery" else v) for k, v in fields.items() if k in allowed}
    if sets:
        with connect() as c:
            c.execute("UPDATE orders SET " + ", ".join(f"{k}=?" for k in sets) + ", updated_at=? WHERE id=?",
                      (*sets.values(), _now(), order_id))
    return get_order(order_id)


def list_orders(limit: int = 100, status: Optional[str] = None) -> List[Dict[str, Any]]:
    sql, args = "SELECT * FROM orders", []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    with connect() as c:
        rows = c.execute(sql + " ORDER BY created_at DESC LIMIT ?", (*args, limit)).fetchall()
    return [_order(r) for r in rows]


# ----------------------------------------------------------------- tee proofs
def _proof(r: sqlite3.Row) -> Dict[str, Any]:
    return dict(r) | {"checks": _load(r["checks"], [])}


def record_proof(agent: str, model: str, chat_id: str, req_sha256: str, resp_sha256: str,
                 run_id: Optional[str] = None, step_seq: Optional[int] = None) -> str:
    pid = new_id("tee")
    with connect() as c:
        c.execute("INSERT INTO tee_proofs (id, run_id, step_seq, agent, model, chat_id, req_sha256, resp_sha256,"
                  " verdict, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (pid, run_id, step_seq, agent, model, chat_id, req_sha256, resp_sha256, "pending", _now()))
    return pid


def settle_proof(pid: str, verdict: str, checks: List[dict], signing_address: Optional[str]) -> None:
    with connect() as c:
        c.execute("UPDATE tee_proofs SET verdict=?, checks=?, signing_address=?, verified_at=? WHERE id=?",
                  (verdict, _j(checks), signing_address, _now(), pid))


def pending_proofs(limit: int = 20) -> List[Dict[str, Any]]:
    with connect() as c:
        rows = c.execute("SELECT * FROM tee_proofs WHERE verdict='pending' ORDER BY created_at LIMIT ?",
                         (limit,)).fetchall()
    return [_proof(r) for r in rows]


def proofs_for_run(run_id: str) -> List[Dict[str, Any]]:
    with connect() as c:
        rows = c.execute("SELECT * FROM tee_proofs WHERE run_id=? ORDER BY created_at", (run_id,)).fetchall()
    return [_proof(r) for r in rows]


def proof_summary(days: int = 30) -> Dict[str, int]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect() as c:
        rows = c.execute("SELECT verdict, count(*) n FROM tee_proofs WHERE created_at >= ? GROUP BY verdict",
                         (since,)).fetchall()
    return {r["verdict"]: r["n"] for r in rows}


# ---------------------------------------------------------------------- files
FILE_MAX_CHARS = 200_000


def save_file(name: str, mime: str, text: str, by: str) -> Dict[str, Any]:
    fid = new_id("fil")
    text = text[:FILE_MAX_CHARS]
    with connect() as c:
        c.execute("INSERT INTO files (id, name, mime, text, size, uploaded_by, uploaded_at) VALUES (?,?,?,?,?,?,?)",
                  (fid, name, mime, text, len(text), by, _now()))
    return {"id": fid, "name": name, "mime": mime, "size": len(text)}


def run_documents(run_ids: List[str]) -> List[Dict[str, Any]]:
    """The team's documents written in these runs (write_document records its run in the meta)."""
    out: List[Dict[str, Any]] = []
    if not run_ids:
        return out
    with connect() as c:
        rows = c.execute("SELECT id, name, mime, uploaded_by, uploaded_at FROM files WHERE name LIKE 'doc:%'"
                         " ORDER BY uploaded_at").fetchall()
    for r in rows:
        try:
            meta = json.loads(r["mime"].split(";", 1)[1]) if ";" in r["mime"] else {}
        except ValueError:
            meta = {}
        if meta.get("run_id") in run_ids:
            out.append({"id": r["id"], "title": r["name"][4:], "by": r["uploaded_by"],
                        "run_id": meta.get("run_id"), "format": meta.get("format")})
    return out


def earlier_runs(work_item_id: str, before: Optional[str] = None) -> List[Dict[str, Any]]:
    """Earlier runs of one work item, oldest first (excluding `before`, the run starting now)."""
    with connect() as c:
        rows = c.execute("SELECT id, status, started_at, decision FROM runs WHERE work_item_id=?"
                         " ORDER BY started_at", (work_item_id,)).fetchall()
    return [{"id": r["id"], "status": r["status"], "started_at": r["started_at"],
             "reason": (_load(r["decision"], {}) or {}).get("reason")} for r in rows if r["id"] != before]


def list_files() -> List[Dict[str, Any]]:
    with connect() as c:
        rows = c.execute("SELECT id, name, mime, size, uploaded_by, uploaded_at FROM files"
                         " ORDER BY uploaded_at DESC").fetchall()
    return [dict(r) for r in rows]


def publish_sample(slug: str, file_id: str, title: str, teaser: str, offering: str, text: str,
                   action_id: Optional[str]) -> Dict[str, Any]:
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO samples (slug, file_id, title, teaser, offering, text, action_id, published_at,"
                  " unpublished_at, views) VALUES (?,?,?,?,?,?,?,?,NULL,COALESCE((SELECT views FROM samples WHERE slug=?),0))",
                  (slug, file_id, title, teaser, offering, text, action_id, _now(), slug))
        return dict(c.execute("SELECT * FROM samples WHERE slug=?", (slug,)).fetchone())


def list_samples(include_unpublished: bool = False) -> List[Dict[str, Any]]:
    with connect() as c:
        rows = c.execute("SELECT slug, file_id, title, teaser, offering, action_id, published_at, unpublished_at, views"
                         " FROM samples" + ("" if include_unpublished else " WHERE unpublished_at IS NULL")
                         + " ORDER BY published_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_sample(slug: str, count_view: bool = False) -> Optional[Dict[str, Any]]:
    with connect() as c:
        if count_view:
            c.execute("UPDATE samples SET views = views + 1 WHERE slug=? AND unpublished_at IS NULL", (slug,))
        r = c.execute("SELECT * FROM samples WHERE slug=? AND unpublished_at IS NULL", (slug,)).fetchone()
    return dict(r) if r else None


def unpublish_sample(slug: str) -> bool:
    with connect() as c:
        return c.execute("UPDATE samples SET unpublished_at=? WHERE slug=? AND unpublished_at IS NULL",
                         (_now(), slug)).rowcount > 0


def record_order_source(order_id: str, source: str) -> None:
    with connect() as c:
        c.execute("INSERT OR IGNORE INTO order_sources (order_id, source, at) VALUES (?,?,?)", (order_id, source, _now()))


def order_sources() -> Dict[str, str]:
    with connect() as c:
        return {r["order_id"]: r["source"] for r in c.execute("SELECT order_id, source FROM order_sources")}


def get_file(fid_or_name: str) -> Optional[Dict[str, Any]]:
    with connect() as c:
        r = c.execute("SELECT * FROM files WHERE id=? OR name=? ORDER BY uploaded_at DESC LIMIT 1",
                      (fid_or_name, fid_or_name)).fetchone()
    return dict(r) if r else None


def delete_file(fid: str) -> bool:
    with connect() as c:
        return c.execute("DELETE FROM files WHERE id=?", (fid,)).rowcount > 0


# ------------------------------------------------------------------- contacts
CONTACT_FIELDS = ("name", "role", "email", "notify_for", "near_account", "payout_chain",
                  "payout_address", "phone", "title", "department", "notes")
#: Changing one of these is changing where money goes. It is stamped, and the
#: guardian treats a recent change as a reason to ask a person.
PAYOUT_FIELDS = ("near_account", "payout_chain", "payout_address")


def list_contacts(role: Optional[str] = None) -> List[dict]:
    sql, args = "SELECT * FROM contacts WHERE active=1", []
    if role:
        sql += " AND role=?"
        args.append(role)
    with connect() as c:
        rows = c.execute(sql + " ORDER BY role, name", args).fetchall()
    return [dict(r) for r in rows]


def add_contact(name: str, role: str, email: str = "", notify_for: str = "",
                **details: Optional[str]) -> dict:
    cid = new_id("cnt")
    vals = {"name": name, "role": role, "email": (email or "").lower(), "notify_for": notify_for or ""}
    for k in CONTACT_FIELDS:
        if k not in vals:
            vals[k] = details.get(k) or None
    with connect() as c:
        c.execute("INSERT INTO contacts (id," + ",".join(CONTACT_FIELDS) + ", created_at) VALUES (?,"
                  + ",".join("?" * len(CONTACT_FIELDS)) + ",?)", (cid, *[vals[k] for k in CONTACT_FIELDS], _now()))
        return dict(c.execute("SELECT * FROM contacts WHERE id=?", (cid,)).fetchone())


def get_contact(cid: str) -> Optional[dict]:
    with connect() as c:
        r = c.execute("SELECT * FROM contacts WHERE id=? AND active=1", (cid,)).fetchone()
    return dict(r) if r else None


def find_contact(term: str) -> List[dict]:
    t = f"%{term.lower()}%"
    with connect() as c:
        rows = c.execute("SELECT * FROM contacts WHERE active=1 AND (lower(name) LIKE ? OR lower(email) LIKE ?"
                         " OR lower(COALESCE(near_account,'')) LIKE ? OR id=?) ORDER BY name LIMIT 20",
                         (t, t, t, term)).fetchall()
    return [dict(r) for r in rows]


def update_contact(cid: str, **fields: Optional[str]) -> Optional[dict]:
    """Change what is given; an empty string clears a detail."""
    sets = {k: (v.lower() if k == "email" and v else (v or None))
            for k, v in fields.items() if k in CONTACT_FIELDS and v is not None}
    if sets:
        with connect() as c:
            old = c.execute("SELECT * FROM contacts WHERE id=?", (cid,)).fetchone()
            if old is None:
                return None
            payout_changed = any(k in PAYOUT_FIELDS and (old[k] or None) != sets[k] for k in sets)
            c.execute("UPDATE contacts SET " + ", ".join(f"{k}=?" for k in sets)
                      + ", updated_at=?" + (", address_changed_at=?" if payout_changed else "")
                      + " WHERE id=? AND active=1",
                      (*sets.values(), _now(), *([_now()] if payout_changed else []), cid))
    return get_contact(cid)


def restore_contact_payout(cid: str, near_account: Optional[str], address_changed_at: Optional[str]) -> None:
    """Put a contact's payout account back exactly as it was, change stamp included.

    Only for the attack demo, which poisons a record on purpose and must leave it as it found
    it: going through update_contact would stamp the restore as a fresh address change and
    hold every real payment to that vendor for the cooldown."""
    with connect() as c:
        c.execute("UPDATE contacts SET near_account=?, address_changed_at=? WHERE id=?",
                  (near_account, address_changed_at, cid))


def notifications_to(address: str, limit: int = 20) -> List[dict]:
    with connect() as c:
        rows = c.execute("SELECT id, run_id, kind, channel, address, subject, status, attempts,"
                         " error, created_at, sent_at, attachments, action_id, reference"
                         " FROM notifications WHERE channel='email' AND address=?"
                         " ORDER BY created_at DESC LIMIT ?", (address.lower(), limit)).fetchall()
    return [_notification(r) for r in rows]


def delete_contact(cid: str) -> bool:
    with connect() as c:
        n = c.execute("UPDATE contacts SET active=0 WHERE id=?", (cid,)).rowcount
    return n > 0


# ------------------------------------------------------------------- ledger
def ledger(days: int = 30) -> Dict[str, Any]:
    """The public figures: money in, money out, splits, model spend, and how
    many decisions were the team's own versus a person's. No customer data."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect() as c:
        money = c.execute("SELECT direction, status, COALESCE(SUM(amount_usd),0) total, count(*) n"
                          " FROM payments WHERE created_at >= ? GROUP BY direction, status", (since,)).fetchall()
        model = c.execute("SELECT COALESCE(SUM(cost_usd),0) FROM runs WHERE started_at >= ?", (since,)).fetchone()[0]
        auto = c.execute("SELECT autonomous, status, count(*) n FROM actions WHERE created_at >= ?"
                         " GROUP BY autonomous, status", (since,)).fetchall()
        blocked = c.execute("SELECT count(*) FROM guardian_checks WHERE verdict='block' AND at >= ?",
                            (since,)).fetchone()[0]
        rows = c.execute("SELECT id, direction, rail, counterparty, amount_usd, token, status, tx_hash, created_at"
                         " FROM payments WHERE created_at >= ? ORDER BY created_at DESC LIMIT 200",
                         (since,)).fetchall()
    return {
        "days": days,
        "money": [dict(r) for r in money],
        "model_spend_usd": round(float(model or 0), 4),
        "decisions": [dict(r) for r in auto],
        "blocked_by_guardian": int(blocked or 0),
        "entries": [dict(r) for r in rows],
        "proofs": proof_summary(days),
    }


# ------------------------------------------------------------------ settings
def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with connect() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(key: str, value: Optional[str], by: str) -> None:
    """Write one setting. None or '' deletes it, which restores the default."""
    with connect() as c:
        if value:
            c.execute("INSERT INTO settings (key, value, updated_by, updated_at)"
                      " VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET"
                      " value=excluded.value, updated_by=excluded.updated_by,"
                      " updated_at=excluded.updated_at", (key, value, by, _now()))
        else:
            c.execute("DELETE FROM settings WHERE key=?", (key,))


# ----------------------------------------------------------- MCP servers out
def mcp_servers(include_token: bool = False) -> List[Dict[str, Any]]:
    """Every server we may call out to. The token is left out unless asked for
    by the caller that is about to use it - a list that carries credentials is
    a list that ends up in a browser."""
    with connect() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM mcp_servers ORDER BY added_at").fetchall()]
    out = []
    for r in rows:
        r["agents"] = json.loads(r.get("agents") or "[]")
        r["tools"] = json.loads(r.get("tools") or "[]")
        r["enabled"] = bool(r["enabled"])
        r["token_set"] = bool(r.get("token"))
        if not include_token:
            r.pop("token", None)
        out.append(r)
    return out


def add_mcp_server(name: str, url: str, token: Optional[str], by: str,
                   agents: Optional[List[str]] = None) -> dict:
    sid = new_id("mcp")
    with connect() as c:
        c.execute("INSERT INTO mcp_servers (id,name,url,token,enabled,agents,tools,"
                  "added_by,added_at) VALUES (?,?,?,?,1,?,'[]',?,?)",
                  (sid, name, url, token or None,
                   json.dumps(agents or []), by, _now()))
    return {"id": sid, "name": name, "url": url}


def update_mcp_server(sid: str, **fields) -> None:
    """Set only what was passed. A token of '' clears it; absent leaves it."""
    allowed = {"name", "url", "token", "enabled", "agents", "tools",
               "last_ok", "last_error"}
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("agents", "tools"):
            v = json.dumps(v)
        if k == "enabled":
            v = int(bool(v))
        if k == "token" and v == "":
            v = None
        sets.append(f"{k}=?")
        args.append(v)
    if not sets:
        return
    with connect() as c:
        c.execute(f"UPDATE mcp_servers SET {', '.join(sets)} WHERE id=?", (*args, sid))


def delete_mcp_server(sid: str) -> bool:
    with connect() as c:
        return c.execute("DELETE FROM mcp_servers WHERE id=?", (sid,)).rowcount > 0


# ------------------------------------------------------------ written skills
def stored_skills() -> List[Dict[str, Any]]:
    """Skills an operator wrote, newest last. Shape matches core.skills.Skill."""
    with connect() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM skills ORDER BY added_at").fetchall()]
    for r in rows:
        for k in ("agents", "tools", "steps"):
            r[k] = json.loads(r.get(k) or "[]")
    return rows


def add_stored_skill(name: str, title: str, description: str, agents: List[str],
                     tools: List[str], steps: List[str], by: str) -> None:
    with connect() as c:
        c.execute("INSERT INTO skills (name,title,description,agents,tools,steps,"
                  "added_by,added_at) VALUES (?,?,?,?,?,?,?,?)",
                  (name, title, description, json.dumps(agents), json.dumps(tools),
                   json.dumps(steps), by, _now()))


def delete_stored_skill(name: str) -> bool:
    with connect() as c:
        return c.execute("DELETE FROM skills WHERE name=?", (name,)).rowcount > 0


# --------------------------------------------------------------- skill usage
def record_skill_use(skill: str, agent: str, found: bool,
                     run_id: Optional[str] = None) -> None:
    """Best effort: a lost metering row must never break a skill invocation."""
    try:
        with connect() as c:
            c.execute("INSERT INTO skill_usage (skill,agent,run_id,found,at)"
                      " VALUES (?,?,?,?,?)",
                      (skill, agent, run_id, int(bool(found)), _now()))
    except Exception:                                               # noqa: BLE001
        pass


def skill_usage(days: int = 30) -> Dict[str, Dict[str, Any]]:
    """Per skill: how often, by whom, and how often it was named and missing.

    The missing count is the useful one. A model reaching for a skill that
    does not exist is a gap in the catalogue, and dropping those rows would
    hide exactly the thing worth knowing.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    with connect() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT skill, agent, found, COUNT(*) AS n FROM skill_usage"
            " WHERE at >= ? GROUP BY skill, agent, found", (since,)).fetchall()]
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        e = out.setdefault(r["skill"], {"calls": 0, "not_found": 0, "by_agent": {}})
        e["calls"] += r["n"]
        if not r["found"]:
            e["not_found"] += r["n"]
        e["by_agent"][r["agent"]] = e["by_agent"].get(r["agent"], 0) + r["n"]
    return out


# ------------------------------------------------------------- model choice
def model_choices(detail: bool = False) -> Dict[str, Any]:
    """key → model, or key → {value, updated_by, updated_at} with detail."""
    with connect() as c:
        rows = c.execute("SELECT * FROM settings WHERE key LIKE 'model.%'").fetchall()
    return {r["key"][len("model."):]: ({"value": r["value"], "updated_by": r["updated_by"],
                                        "updated_at": r["updated_at"]} if detail else r["value"])
            for r in rows}


def save_model_choices(changes: Dict[str, Optional[str]], by: str) -> None:
    """Set each key, in one transaction. None or '' clears it."""
    with connect() as c:
        for key, value in changes.items():
            if value:
                c.execute("INSERT INTO settings (key, value, updated_by, updated_at)"
                          " VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET"
                          " value=excluded.value, updated_by=excluded.updated_by,"
                          " updated_at=excluded.updated_at", (f"model.{key}", value, by, _now()))
            else:
                c.execute("DELETE FROM settings WHERE key=?", (f"model.{key}",))


# -------------------------------------------------------------- notifications
def enqueue_notification(dedup_key: str, kind: str, channel: str, address: str,
                         subject: str, body: str, run_id: Optional[str] = None,
                         attachments: Optional[List[dict]] = None,
                         action_id: Optional[str] = None) -> bool:
    """Queue one message. False when that exact message was already queued."""
    with connect() as c:
        n = c.execute(
            "INSERT OR IGNORE INTO notifications (id, dedup_key, run_id, kind, channel, address,"
            " subject, body, status, created_at, attachments, action_id)"
            " VALUES (?,?,?,?,?,?,?,?,'pending',?,?,?)",
            (new_id("ntf"), dedup_key, run_id, kind, channel, address, subject, body, _now(),
             json.dumps(attachments) if attachments else None, action_id),
        ).rowcount
    return n > 0


def _notification(r: sqlite3.Row) -> dict:
    d = dict(r)
    if "attachments" in d:
        d["attachments"] = json.loads(d["attachments"]) if d["attachments"] else []
    return d


def pending_notifications(limit: int = 50) -> List[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM notifications WHERE status='pending'"
                         " ORDER BY created_at LIMIT ?", (limit,)).fetchall()
    return [_notification(r) for r in rows]


def mark_notification(nid: str, status: str, error: Optional[str] = None,
                      reference: Optional[str] = None) -> None:
    """sent | failed | skipped, or back to pending with the error kept."""
    with connect() as c:
        c.execute("UPDATE notifications SET status=?, error=?, attempts=attempts+1,"
                  " reference=COALESCE(?, reference),"
                  " sent_at=CASE WHEN ?='sent' THEN ? ELSE sent_at END WHERE id=?",
                  (status, error, reference, status, _now(), nid))


def record_privacy_event(notification_id: Optional[str], channel: str, outcome: str, detail: str = "") -> None:
    with connect() as c:
        c.execute("INSERT INTO privacy_events (id, notification_id, channel, outcome, detail, at) VALUES (?,?,?,?,?,?)",
                  (new_id("prv"), notification_id, channel, outcome, detail[:300], _now()))


def privacy_events(limit: int = 50) -> List[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM privacy_events ORDER BY at DESC LIMIT ?", (limit,))]


def list_notifications(limit: int = 100) -> List[dict]:
    with connect() as c:
        rows = c.execute("SELECT id, run_id, kind, channel, address, subject, status, attempts,"
                         " error, created_at, sent_at, attachments, action_id, reference"
                         " FROM notifications ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_notification(r) for r in rows]


def notification_for_action(action_id: str) -> Optional[dict]:
    """The outreach message that delivers an approved action, if one was queued."""
    with connect() as c:
        r = c.execute("SELECT * FROM notifications WHERE action_id=? ORDER BY created_at DESC"
                      " LIMIT 1", (action_id,)).fetchone()
    return _notification(r) if r else None


# ----------------------------------------------------------------------- jobs
def job_states() -> Dict[str, dict]:
    with connect() as c:
        return {r["name"]: dict(r) for r in c.execute("SELECT * FROM jobs").fetchall()}


def job_started(name: str) -> None:
    with connect() as c:
        c.execute("INSERT INTO jobs (name, last_started) VALUES (?, ?) ON CONFLICT(name)"
                  " DO UPDATE SET last_started=excluded.last_started", (name, _now()))


def job_finished(name: str, ok: bool, detail: str) -> None:
    with connect() as c:
        c.execute("UPDATE jobs SET last_finished=?, last_status=?, last_detail=?, runs=runs+1,"
                  " failures=failures+? WHERE name=?",
                  (_now(), "ok" if ok else "failed", detail[:2000], 0 if ok else 1, name))


def set_job_enabled(name: str, enabled: bool) -> None:
    with connect() as c:
        c.execute("INSERT INTO jobs (name, enabled) VALUES (?, ?) ON CONFLICT(name)"
                  " DO UPDATE SET enabled=excluded.enabled", (name, int(enabled)))


# ------------------------------------------------------------- conversations
TITLE_MAX = 70


def start_conversation(agent: str, user_id: str, first_question: str) -> str:
    title = first_question.strip().replace("\n", " ")
    if len(title) > TITLE_MAX:
        title = title[: TITLE_MAX - 1].rstrip() + "…"
    cid = new_id("cnv")
    with connect() as c:
        c.execute("INSERT INTO conversations (id,agent,user_id,title,created_at,updated_at)"
                  " VALUES (?,?,?,?,?,?)", (cid, agent, user_id, title, _now(), _now()))
    return cid


def add_message(conversation_id: str, role: str, body: dict) -> None:
    """Appends. A conversation is a transcript, so nothing here is ever rewritten."""
    with connect() as c:
        seq = c.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM messages"
                        " WHERE conversation_id=?", (conversation_id,)).fetchone()["n"]
        c.execute("INSERT INTO messages (conversation_id,seq,role,body,at) VALUES (?,?,?,?,?)",
                  (conversation_id, seq, role, json.dumps(body, ensure_ascii=False), _now()))
        c.execute("UPDATE conversations SET updated_at=? WHERE id=?", (_now(), conversation_id))


def list_conversations(user_id: str, agent: Optional[str] = None,
                       limit: int = 50) -> List[dict]:
    where = "WHERE c.user_id=?" + (" AND c.agent=?" if agent else "")
    args: list = [user_id] + ([agent] if agent else []) + [limit]
    with connect() as c:
        rows = c.execute(
            "SELECT c.*,"
            " (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) AS messages,"
            " (SELECT COALESCE(SUM(json_extract(m.body, '$.tokens.total')), 0)"
            "  FROM messages m WHERE m.conversation_id=c.id AND m.role='agent') AS total_tokens,"
            " (SELECT COALESCE(SUM(json_extract(m.body, '$.cost_usd')), 0)"
            "  FROM messages m WHERE m.conversation_id=c.id AND m.role='agent') AS cost_usd"
            f" FROM conversations c {where}"
            " ORDER BY c.updated_at DESC LIMIT ?", args).fetchall()
    return [dict(r) for r in rows]


def conversation_usage_summary(user_id: str) -> Dict[str, Any]:
    """Aggregate token and cost usage across all conversations for a user, plus run costs."""
    with connect() as c:
        row = c.execute(
            "SELECT"
            " COALESCE(SUM(json_extract(m.body, '$.tokens.input')), 0) AS input_tokens,"
            " COALESCE(SUM(json_extract(m.body, '$.tokens.output')), 0) AS output_tokens,"
            " COALESCE(SUM(json_extract(m.body, '$.tokens.total')), 0) AS total_tokens,"
            " COALESCE(SUM(json_extract(m.body, '$.cost_usd')), 0) AS cost_usd,"
            " COUNT(m.id) AS replies"
            " FROM messages m"
            " JOIN conversations cv ON cv.id = m.conversation_id"
            " WHERE cv.user_id = ? AND m.role = 'agent'",
            (user_id,),
        ).fetchone()
        runs_cost = c.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM runs"
        ).fetchone()[0]
    return {
        "input_tokens": int(row["input_tokens"] or 0),
        "output_tokens": int(row["output_tokens"] or 0),
        "total_tokens": int(row["total_tokens"] or 0),
        "cost_usd": round(float(row["cost_usd"] or 0), 4),
        "replies": int(row["replies"] or 0),
        "runs_cost_usd": round(float(runs_cost or 0), 4),
    }


def get_conversation(conversation_id: str, user_id: str) -> Optional[dict]:
    """Owner-scoped on purpose: an id in a URL is not authority to read it."""
    with connect() as c:
        r = c.execute("SELECT * FROM conversations WHERE id=? AND user_id=?",
                      (conversation_id, user_id)).fetchone()
        if not r:
            return None
        rows = c.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY seq",
                         (conversation_id,)).fetchall()
    return dict(r) | {"messages": [dict(m) | {"body": json.loads(m["body"])} for m in rows]}


def delete_conversation(conversation_id: str, user_id: str) -> bool:
    with connect() as c:
        c.execute("DELETE FROM messages WHERE conversation_id IN"
                  " (SELECT id FROM conversations WHERE id=? AND user_id=?)",
                  (conversation_id, user_id))
        n = c.execute("DELETE FROM conversations WHERE id=? AND user_id=?",
                      (conversation_id, user_id)).rowcount
    return n > 0




def demo() -> None:
    """Runs against a throwaway database. The __main__ block guarantees one."""
    # A profile is versioned, and only one is in force.
    v1 = save_profile({"name": "Lumen", "offerings": []}, by="check")
    v2 = save_profile({"name": "Lumen Research", "offerings": [{"id": "brief"}]}, by="check", note="rename")
    p = active_profile()
    assert p and p["name"] == "Lumen Research" and p["_version"] == v2 > v1, p
    assert [h["active"] for h in profile_history()] == [1, 0]
    print("  business: versioned, one active ✓")

    # Agents: an edit bumps the version, a core role cannot be switched off.
    a = upsert_agent({"code": "guardian", "nickname": "Guardian", "title": "Guardian", "brief": "veto",
                      "role": "guardian", "core": True, "veto": True, "prompt": "p",
                      "capabilities": ["guardian"]}, by="check")
    assert a["version"] == 1 and a["veto"] and a["capabilities"] == ["guardian"]
    assert upsert_agent({**a, "prompt": "p"}, by="check")["version"] == 1, "no change, no bump"
    assert upsert_agent({**a, "prompt": "p2"}, by="check")["version"] == 2
    try:
        set_agent_status("guardian", "disabled", by="check")
        raise AssertionError("a core role must not be disabled")
    except ValueError:
        pass
    assert delete_agent("guardian") is False
    print("  agents: versioned ✓ · core roles locked ✓")

    # Work items deduplicate, and claiming is single-winner.
    w = record_work_item("order", "Brief for ACME", "vault", {"order_id": "o1"}, dedup_key="order:o1")
    assert w and record_work_item("order", "again", "vault", {}, dedup_key="order:o1") is None
    claimed = next_new_work_item()
    assert claimed and claimed["id"] == w and next_new_work_item() is None
    print("  work items: a paid order is worked once ✓")

    # Actions: idempotent, forward-only.
    rid = start_run(w, {"guardian": 2}, v2)
    act = record_action(rid, "pay:abc", "payment", False, {"to": "x"}, value_usd=12.5)
    assert act["status"] == "pending" and not act["repeated"]
    assert record_action(rid, "pay:abc", "payment", False, {})["repeated"]
    decide_action(act["id"], "u1", "admin", "approved")
    move_action(act["id"], "sent", reference="tx1")
    try:
        move_action(act["id"], "pending")
        raise AssertionError("status must only move forward")
    except ValueError:
        pass
    close_run(rid, "done", {"status": "done"}, cost_usd=0.0123)
    run = get_run(rid)
    assert run["status"] == "done" and run["actions"][0]["reference"] == "tx1"
    assert get_work_item(w)["status"] == "done"
    print("  actions: idempotent ✓ · forward-only ✓")

    # Money and checks reach the ledger, without customer data.
    record_check("counterparty", "evil.testnet", "block", [{"rule": "allowlist", "verdict": "block"}], run_id=rid)
    pay = record_payment("out", "vault", "vendor.testnet", 12.5, "usdc", "submitted", action_id=act["id"])
    update_payment(pay["id"], "sent", tx_hash="tx1", detail={"events": ["payment_sent"]})
    led = ledger()
    assert led["blocked_by_guardian"] == 1 and led["entries"][0]["tx_hash"] == "tx1"
    print("  ledger: payments, model spend, guardian blocks ✓")

    # A payout change is stamped.
    cn = add_contact("Vendor", "vendor", "v@example.com", near_account="vendor.testnet")
    assert cn["address_changed_at"] is None
    assert update_contact(cn["id"], notes="hi")["address_changed_at"] is None
    assert update_contact(cn["id"], near_account="other.testnet")["address_changed_at"]
    print("  contacts: a payout change is stamped ✓")

    cid = start_conversation("guardian", "usr_1", "Why did you block that?")
    add_message(cid, "person", {"text": "Why did you block that?"})
    assert get_conversation(cid, "usr_1") and get_conversation(cid, "usr_2") is None
    print("  conversations: owner-scoped ✓")
    print("store ok")


if __name__ == "__main__":
    from core.config import fixtures_only

    fixtures_only(__file__, "AERA_STORE_CHECK")
    demo()
