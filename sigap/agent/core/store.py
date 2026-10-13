"""Persistence. SQLite, plenty for a dozen events a day, zero dependencies.

# ponytail: SQLite; move to Postgres once this is multi-tenant or needs concurrent writes

What lands here is the official record: what the agents decided, on what
evidence, who approved it, and what was actually sent to SAP. Rows in the
actions and approvals tables are NEVER updated in place, a correction is
written as a new row.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from core.config import CFG

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id            TEXT PRIMARY KEY,
  kind          TEXT NOT NULL,           -- port_closure | supplier_failure | demand_spike | ...
  title         TEXT NOT NULL,
  trigger       TEXT NOT NULL,
  payload       TEXT NOT NULL,           -- raw JSON from the signal source
  received_at   TEXT NOT NULL,
  source        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  id            TEXT PRIMARY KEY,
  event_id      TEXT NOT NULL REFERENCES events(id),
  mode          TEXT NOT NULL,           -- autonomous | guided
  status        TEXT NOT NULL,           -- running | done | held | failed
  started_at    TEXT NOT NULL,
  finished_at   TEXT,
  token_cost_idr INTEGER DEFAULT 0,
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

-- The official record. Never UPDATEd except to stamp the SAP reference.
CREATE TABLE IF NOT EXISTS actions (
  id              TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL REFERENCES runs(id),
  idempotency_key TEXT NOT NULL UNIQUE,  -- stops a retry becoming a duplicate PO
  kind            TEXT NOT NULL,
  autonomous      INTEGER NOT NULL,
  payload         TEXT NOT NULL,
  status          TEXT NOT NULL,         -- pending | approved | rejected | sent | failed
  sap_reference   TEXT,
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

CREATE TABLE IF NOT EXISTS uploads (
  id          TEXT PRIMARY KEY,
  entity      TEXT NOT NULL,             -- MaterialStock | PurchaseOrder | SalesOrder | ...
  filename    TEXT NOT NULL,
  rows        INTEGER NOT NULL,
  payload     TEXT NOT NULL,             -- JSON array
  uploaded_by TEXT NOT NULL,
  uploaded_at TEXT NOT NULL,
  -- Declared by whoever uploaded it. The system cannot tell real master data
  -- from a generated sample by looking at it, and labelling a generated file
  -- as cached would launder it into looking more trustworthy than it is.
  synthetic   INTEGER NOT NULL DEFAULT 0
);

-- A conversation with one agent. Unlike runs, this is a person talking, so it
-- belongs to whoever asked and is never shown to anyone else.
CREATE TABLE IF NOT EXISTS conversations (
  id         TEXT PRIMARY KEY,
  agent      TEXT NOT NULL,
  user_id    TEXT NOT NULL,
  title      TEXT NOT NULL,             -- the first question, trimmed
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
  body    TEXT NOT NULL,                -- JSON: the whole reply, or {"text": ...}
  at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, seq);

CREATE TABLE IF NOT EXISTS contacts (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  role       TEXT NOT NULL,              -- planner | buyer | procurement_lead | qa | oem
  email      TEXT NOT NULL,
  notify_for TEXT NOT NULL,              -- event kinds, comma separated; * = all
  active     INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


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
        # Older databases predate the synthetic flag.
        try:
            c.execute("ALTER TABLE uploads ADD COLUMN synthetic INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        yield c
        c.commit()
    finally:
        c.close()


# --------------------------------------------------------------------- events
def record_event(kind: str, title: str, trigger: str, payload: dict, source: str) -> str:
    eid = new_id("evt")
    with connect() as c:
        c.execute(
            "INSERT INTO events (id, kind, title, trigger, payload, received_at, source)"
            " VALUES (?,?,?,?,?,?,?)",
            (eid, kind, title, trigger, json.dumps(payload, ensure_ascii=False), _now(), source),
        )
    return eid


def event_exists(title: str, trigger: str) -> bool:
    """Has this exact signal already been recorded?

    A feed reports the same quake for hours, so a watcher that polls every few
    minutes would raise it again on every pass. Title and trigger together are
    the signal's natural identity: the trigger carries the source's own
    timestamp, so a genuinely new event never collides with an old one.
    """
    with connect() as c:
        row = c.execute("SELECT 1 FROM events WHERE title=? AND trigger=? LIMIT 1",
                        (title, trigger)).fetchone()
    return row is not None


# ----------------------------------------------------------------------- runs
def start_run(event_id: str, mode: str) -> str:
    rid = new_id("run")
    with connect() as c:
        c.execute("INSERT INTO runs (id, event_id, mode, status, started_at) VALUES (?,?,?,?,?)",
                  (rid, event_id, mode, "running", _now()))
    return rid


def close_run(run_id: str, status: str, decision: Optional[dict] = None,
              error: Optional[str] = None, cost_idr: int = 0) -> None:
    with connect() as c:
        c.execute(
            "UPDATE runs SET status=?, finished_at=?, decision=?, error=?, token_cost_idr=?"
            " WHERE id=?",
            (status, _now(),
             json.dumps(decision, ensure_ascii=False) if decision else None,
             error, cost_idr, run_id),
        )


def save_step(run_id: str, s: dict) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO steps (run_id, seq, stage, agent, agent_name, summary,"
            " tools, origin, source, detail, at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, s["seq"], s["stage"], s["agent"], s["agent_name"], s["summary"],
             json.dumps(s["tools"], ensure_ascii=False), s.get("origin"), s.get("source"),
             json.dumps(s.get("detail", {}), ensure_ascii=False), s["at"]),
        )


# -------------------------------------------------------------------- actions
def record_action(run_id: str, idempotency_key: str, kind: str,
                  autonomous: bool, payload: dict) -> Dict[str, Any]:
    """Idempotent: the same key never produces a second action."""
    with connect() as c:
        existing = c.execute("SELECT * FROM actions WHERE idempotency_key=?",
                             (idempotency_key,)).fetchone()
        if existing:
            return dict(existing) | {"repeated": True}
        aid = new_id("act")
        c.execute(
            "INSERT INTO actions (id, run_id, idempotency_key, kind, autonomous, payload,"
            " status, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (aid, run_id, idempotency_key, kind, int(autonomous),
             json.dumps(payload, ensure_ascii=False),
             "sent" if autonomous else "pending", _now()),
        )
        row = c.execute("SELECT * FROM actions WHERE id=?", (aid,)).fetchone()
        return dict(row) | {"repeated": False}


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
            return dict(a) | {"unchanged": True}
        c.execute("INSERT INTO approvals (action_id, decided_by, role, decision, note, at)"
                  " VALUES (?,?,?,?,?,?)", (action_id, decided_by, role, decision, note, _now()))
        c.execute("UPDATE actions SET status=? WHERE id=?", (nxt[decision], action_id))
        return dict(c.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone())


# --------------------------------------------------------------------- reads
def list_runs(limit: int = 50) -> List[dict]:
    with connect() as c:
        rows = c.execute(
            "SELECT r.*, e.title, e.kind, e.trigger FROM runs r"
            " JOIN events e ON e.id = r.event_id"
            " ORDER BY r.started_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) | {"decision": json.loads(r["decision"]) if r["decision"] else None}
            for r in rows]


def past_incidents(terms: List[str], limit: int = 5) -> tuple[List[dict], int]:
    """Handled disruptions, ranked by how many of `terms` they mention.

    Returns the matches AND the number of finished runs on record, because
    "we have never handled anything" and "we looked and nothing was
    comparable" are different answers and only the first is a gap in the data.
    The caller needs to tell them apart to label its result honestly.

    # ponytail: ranks in Python over every finished run. Fine for a dozen
    #           events a day; move to FTS5 when the table outgrows a scan.
    """
    with connect() as c:
        rows = c.execute(
            "SELECT r.id AS run_id, r.status, r.mode, r.started_at, r.finished_at,"
            "       r.token_cost_idr, r.decision, e.title, e.kind, e.trigger"
            " FROM runs r JOIN events e ON e.id = r.event_id"
            " WHERE r.finished_at IS NOT NULL"
            " ORDER BY r.finished_at DESC").fetchall()

    total = len(rows)
    scored = []
    for r in rows:
        hay = f"{r['title']} {r['kind']} {r['trigger']}".lower()
        hits = sum(1 for t in terms if t in hay)
        if hits:
            scored.append((hits, dict(r) | {
                "decision": json.loads(r["decision"]) if r["decision"] else None,
                "matched": hits,
            }))

    # Most terms matched first; the query already ordered by recency, and
    # Python's sort is stable, so equal scores keep the newest incident on top.
    scored.sort(key=lambda p: p[0], reverse=True)
    return [row for _, row in scored[:limit]], total


def get_run(run_id: str) -> Optional[dict]:
    with connect() as c:
        r = c.execute(
            "SELECT r.*, e.title, e.kind, e.trigger, e.source AS signal_source"
            " FROM runs r JOIN events e ON e.id = r.event_id WHERE r.id=?",
            (run_id,)).fetchone()
        if not r:
            return None
        steps = c.execute("SELECT * FROM steps WHERE run_id=? ORDER BY seq",
                          (run_id,)).fetchall()
        actions = c.execute("SELECT * FROM actions WHERE run_id=? ORDER BY created_at",
                            (run_id,)).fetchall()
        approvals = c.execute(
            "SELECT p.* FROM approvals p JOIN actions a ON a.id = p.action_id"
            " WHERE a.run_id=? ORDER BY p.at", (run_id,)).fetchall()
    return {
        **dict(r),
        "decision": json.loads(r["decision"]) if r["decision"] else None,
        "steps": [dict(s) | {"tools": json.loads(s["tools"]),
                             "detail": json.loads(s["detail"])} for s in steps],
        "actions": [dict(a) | {"payload": json.loads(a["payload"])} for a in actions],
        "approvals": [dict(p) for p in approvals],
    }


def get_action(action_id: str) -> Optional[dict]:
    with connect() as c:
        r = c.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
    return dict(r) | {"payload": json.loads(r["payload"])} if r else None


def mark_sent(action_id: str, sap_reference: str) -> None:
    """Called once an approved action has actually landed in SAP."""
    with connect() as c:
        c.execute("UPDATE actions SET status='sent', sap_reference=?"
                  " WHERE id=? AND status='approved'", (sap_reference, action_id))


# -------------------------------------------------------------------- uploads
def save_upload(entity: str, filename: str, payload: list, uploaded_by: str,
                synthetic: bool = False) -> dict:
    uid = new_id("upl")
    with connect() as c:
        c.execute("INSERT INTO uploads (id,entity,filename,rows,payload,uploaded_by,"
                  "uploaded_at,synthetic) VALUES (?,?,?,?,?,?,?,?)",
                  (uid, entity, filename, len(payload),
                   json.dumps(payload, ensure_ascii=False), uploaded_by, _now(),
                   int(synthetic)))
    return {"id": uid, "entity": entity, "rows": len(payload), "synthetic": synthetic}


def latest_upload(entity: str) -> Optional[dict]:
    """The most recent upload for one entity, if any."""
    with connect() as c:
        r = c.execute("SELECT * FROM uploads WHERE entity=? ORDER BY uploaded_at DESC LIMIT 1",
                      (entity,)).fetchone()
    return dict(r) | {"payload": json.loads(r["payload"])} if r else None


def list_uploads() -> List[dict]:
    with connect() as c:
        rows = c.execute("SELECT id,entity,filename,rows,uploaded_by,uploaded_at,synthetic"
                         " FROM uploads ORDER BY uploaded_at DESC LIMIT 50").fetchall()
    return [dict(r) for r in rows]


def delete_upload(uid: str) -> bool:
    with connect() as c:
        n = c.execute("DELETE FROM uploads WHERE id=?", (uid,)).rowcount
    return n > 0


# ------------------------------------------------------------------- contacts
def list_contacts() -> List[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM contacts WHERE active=1 ORDER BY role, name").fetchall()
    return [dict(r) for r in rows]


def add_contact(name: str, role: str, email: str, notify_for: str = "*") -> dict:
    cid = new_id("cnt")
    with connect() as c:
        c.execute("INSERT INTO contacts (id,name,role,email,notify_for,created_at)"
                  " VALUES (?,?,?,?,?,?)", (cid, name, role, email.lower(), notify_for, _now()))
        return dict(c.execute("SELECT * FROM contacts WHERE id=?", (cid,)).fetchone())


def delete_contact(cid: str) -> bool:
    with connect() as c:
        n = c.execute("UPDATE contacts SET active=0 WHERE id=?", (cid,)).rowcount
    return n > 0


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
            " (SELECT COALESCE(SUM(json_extract(m.body, '$.cost_idr')), 0)"
            "  FROM messages m WHERE m.conversation_id=c.id AND m.role='agent') AS cost_idr"
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
            " COALESCE(SUM(json_extract(m.body, '$.cost_idr')), 0) AS cost_idr,"
            " COUNT(m.id) AS replies"
            " FROM messages m"
            " JOIN conversations cv ON cv.id = m.conversation_id"
            " WHERE cv.user_id = ? AND m.role = 'agent'",
            (user_id,),
        ).fetchone()
        runs_cost = c.execute(
            "SELECT COALESCE(SUM(token_cost_idr), 0) FROM runs"
        ).fetchone()[0]
    return {
        "input_tokens": int(row["input_tokens"] or 0),
        "output_tokens": int(row["output_tokens"] or 0),
        "total_tokens": int(row["total_tokens"] or 0),
        "cost_idr": int(row["cost_idr"] or 0),
        "replies": int(row["replies"] or 0),
        "runs_cost_idr": int(runs_cost or 0),
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
    cid = start_conversation("demand", "usr_1", "What is daily consumption of M-4471?")
    add_message(cid, "person", {"text": "What is daily consumption of M-4471?"})
    add_message(cid, "agent", {"answer": "10.33 TON a day", "tools_used": ["forecast_demand"]})
    add_message(cid, "person", {"text": "and the other plant?"})

    c = get_conversation(cid, "usr_1")
    assert c and [m["seq"] for m in c["messages"]] == [1, 2, 3]

    # An id is not authority. Someone else's conversation is not readable and
    # not deletable, which is the whole reason these take a user_id at all.
    assert get_conversation(cid, "usr_2") is None
    assert delete_conversation(cid, "usr_2") is False

    rows = list_conversations("usr_1", "demand")
    assert len(rows) == 1 and rows[0]["messages"] == 3
    assert list_conversations("usr_1", "inventory") == []

    start_conversation("demand", "usr_1", "x" * 200)
    assert all(len(r["title"]) <= TITLE_MAX for r in list_conversations("usr_1"))

    assert delete_conversation(cid, "usr_1") is True
    with connect() as c2:
        left = c2.execute("SELECT COUNT(*) n FROM messages WHERE conversation_id=?",
                          (cid,)).fetchone()["n"]
    assert left == 0, "messages must go when the conversation goes"
    print("  conversations: owner-scoped ✓ · cascade clean ✓ · titles trimmed ✓")
    print("store ok")


if __name__ == "__main__":
    # This check writes rows, so it must never meet the real database. CFG is
    # frozen and read at import, so the only honest way to swap it is to start
    # again with SIGAP_DB pointing somewhere disposable.
    import os
    import subprocess
    import sys
    import tempfile

    if os.environ.get("SIGAP_STORE_CHECK") != "1":
        db = pathlib.Path(tempfile.mkdtemp(prefix="sigap-check-")) / "check.db"
        sys.exit(subprocess.call(
            [sys.executable, __file__],
            env={**os.environ, "SIGAP_DB": str(db), "SIGAP_STORE_CHECK": "1",
                 "PYTHONPATH": os.environ.get("PYTHONPATH", ".")}))
    demo()
