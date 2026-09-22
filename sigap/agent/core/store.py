"""Persistence. SQLite — plenty for a dozen events a day, zero dependencies.

# ponytail: SQLite; move to Postgres once this is multi-tenant or needs concurrent writes

What lands here is the official record: what the agents decided, on what
evidence, who approved it, and what was actually sent to SAP. Rows in the
actions and approvals tables are NEVER updated in place — a correction is
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
  uploaded_at TEXT NOT NULL
);

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
def save_upload(entity: str, filename: str, payload: list, uploaded_by: str) -> dict:
    uid = new_id("upl")
    with connect() as c:
        c.execute("INSERT INTO uploads (id,entity,filename,rows,payload,uploaded_by,uploaded_at)"
                  " VALUES (?,?,?,?,?,?,?)",
                  (uid, entity, filename, len(payload),
                   json.dumps(payload, ensure_ascii=False), uploaded_by, _now()))
    return {"id": uid, "entity": entity, "rows": len(payload)}


def latest_upload(entity: str) -> Optional[dict]:
    """The most recent upload for one entity, if any."""
    with connect() as c:
        r = c.execute("SELECT * FROM uploads WHERE entity=? ORDER BY uploaded_at DESC LIMIT 1",
                      (entity,)).fetchone()
    return dict(r) | {"payload": json.loads(r["payload"])} if r else None


def list_uploads() -> List[dict]:
    with connect() as c:
        rows = c.execute("SELECT id,entity,filename,rows,uploaded_by,uploaded_at FROM uploads"
                         " ORDER BY uploaded_at DESC LIMIT 50").fetchall()
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
