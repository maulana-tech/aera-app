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
from datetime import datetime, timedelta, timezone
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
-- The operations report reads what the rules cost out of every costing step
-- across many runs (engine/report.py compliance_costs), which is a scan by
-- stage rather than by run.
CREATE INDEX IF NOT EXISTS idx_steps_stage ON steps(stage, run_id, seq);

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

CREATE TABLE IF NOT EXISTS reservations (
  id            TEXT PRIMARY KEY,
  run_id        TEXT NOT NULL REFERENCES runs(id),
  action_id     TEXT,                    -- set once the action exists
  material      TEXT NOT NULL,
  plant         TEXT NOT NULL,           -- the donor, the plant losing the stock
  qty           REAL NOT NULL,
  created_at    TEXT NOT NULL,
  released_at   TEXT,                    -- NULL means still held
  released_why  TEXT
);

CREATE INDEX IF NOT EXISTS reservations_open
  ON reservations (material, plant) WHERE released_at IS NULL;

CREATE TABLE IF NOT EXISTS contacts (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  role       TEXT NOT NULL,              -- planner | buyer | procurement_lead | qa | oem
  email      TEXT NOT NULL,
  notify_for TEXT NOT NULL,              -- event kinds, comma separated; * = all
  active     INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

-- Which model each role runs on, as picked on the Models page (core/llm.py,
-- choose()). Key is model.<lead|specialists|fallback|aux|agent code>. A key
-- that is absent hands that choice back to the environment.
CREATE TABLE IF NOT EXISTS settings (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Who was told what, over which channel, and whether it arrived. Written
-- before anything is sent (an outbox), so a crash between deciding to tell
-- someone and telling them leaves a row to retry, and dedup_key stops a
-- retry, or a second handling of the same run, telling them twice.
CREATE TABLE IF NOT EXISTS notifications (
  id         TEXT PRIMARY KEY,
  dedup_key  TEXT NOT NULL UNIQUE,
  run_id     TEXT,
  kind       TEXT NOT NULL,              -- handling | digest | test | report | outreach
  channel    TEXT NOT NULL,              -- email | slack | telegram | webhook
  address    TEXT NOT NULL,              -- an email, or the channel's name
  subject    TEXT NOT NULL,
  body       TEXT NOT NULL,
  status     TEXT NOT NULL,              -- pending | sent | failed | skipped
  attempts   INTEGER NOT NULL DEFAULT 0,
  error      TEXT,
  created_at TEXT NOT NULL,
  sent_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status, created_at);

-- The schedule's memory. A job's next run is worked out from when it last
-- started, so a restart does not re-run a weekly scan that ran yesterday.
CREATE TABLE IF NOT EXISTS jobs (
  name         TEXT PRIMARY KEY,
  enabled      INTEGER NOT NULL DEFAULT 1,
  last_started TEXT,
  last_finished TEXT,
  last_status  TEXT,                     -- ok | failed
  last_detail  TEXT,
  runs         INTEGER NOT NULL DEFAULT 0,
  failures     INTEGER NOT NULL DEFAULT 0
);

-- The exploration graph. A persisted, typed DAG of one event's handling: the
-- disruption, the lines of investigation it opened, the facts each one
-- surfaced (every fact keeps its origin, SIGAP's house rule), the candidate
-- options, and Kira's rulings on them. The supervisor and the specialists read
-- and write this ONE graph together, so it is the shared record of how a
-- decision was reached, not three parallel dicts that can drift.
--
-- A node's identity is (run_id, dedup_key): two specialists that surface the
-- same fact collapse to ONE node, which is what makes the multi-parent DAG hold
-- (a priced option that two leads both point at is one option, not two). The
-- whole feature is flag-gated (SIGAP_GRAPH) and written through fail-open, so a
-- graph error can never break a handling that already works without it.
CREATE TABLE IF NOT EXISTS graph_nodes (
  node_id    TEXT PRIMARY KEY,
  run_id     TEXT NOT NULL REFERENCES runs(id),
  kind       TEXT NOT NULL,            -- event | lead | fact | option | ruling
  state      TEXT,                     -- lead: open|claimed|worked|capped|blocked|stopped
  label      TEXT,
  subject    TEXT,                     -- the material / option id / supplier a node is about
  lead_key   TEXT,                     -- kind='lead' mirrors the claimable frontier key
  origin     TEXT,                     -- kind='fact' carries provenance: live|cached|derived|modelled|missing
  source     TEXT,                     -- where the fact came from ("API_MATERIAL_STOCK_SRV", "references/")
  dedup_key  TEXT NOT NULL,            -- canonical identity for multi-parent DAG dedup
  payload    TEXT,                     -- JSON: the node's value / detail
  priority   INTEGER,
  -- Claim bookkeeping so a 'lead' node can BE the atomic claimable frontier.
  -- owner = the specialist that CAS-claimed it; the counters bound the chain so
  -- a recursive spawn can never loop forever.
  owner        TEXT,
  attempts     INTEGER NOT NULL DEFAULT 0,
  dispatches   INTEGER NOT NULL DEFAULT 0,
  revived_once INTEGER NOT NULL DEFAULT 0,
  claimed_at   TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  UNIQUE(run_id, dedup_key)
);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_run ON graph_nodes(run_id, kind);
-- the atomic claim + frontier-depth queries filter by (run_id, kind, state).
CREATE INDEX IF NOT EXISTS idx_graph_nodes_claim ON graph_nodes(run_id, kind, state);

CREATE TABLE IF NOT EXISTS graph_edges (
  run_id     TEXT NOT NULL REFERENCES runs(id),
  src        TEXT NOT NULL,            -- ancestor node_id
  rel        TEXT NOT NULL,            -- spawns | derived_from | yields | rules_on | covers
  dst        TEXT NOT NULL,            -- descendant node_id
  created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, src, rel, dst)
);
CREATE INDEX IF NOT EXISTS idx_graph_edges_run ON graph_edges(run_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# Columns that arrived after a database already existed. CREATE TABLE IF NOT
# EXISTS will not add a column to a table that is already there, so each one is
# applied on connect and the duplicate error is the normal outcome.
ADDED_LATER = [
    ("uploads", "synthetic", "INTEGER NOT NULL DEFAULT 0"),
    # What actually happened after the action was sent. Without these the
    # record says what was decided and never what it cost in the end, so the
    # memory Otto reads is a memory of intentions.
    ("actions", "outcome", "TEXT"),
    ("actions", "outcome_at", "TEXT"),
    ("actions", "outcome_detail", "TEXT"),
    # What a message carries and what it answers to. Attachments are named, as
    # JSON ({"report": run_id | "portfolio", "format": "pdf"}), and rendered
    # when sent, so the outbox holds no copies of reports. action_id ties an
    # outreach message to the approved action it delivers; reference is the
    # id the mail server gave it, the proof it went.
    ("notifications", "attachments", "TEXT"),
    ("notifications", "action_id", "TEXT"),
    ("notifications", "reference", "TEXT"),
    # Who a contact is beyond an inbox: how to reach them when an alert needs
    # an answer now, and what they do. None of it is sent anywhere by SIGAP.
    ("contacts", "phone", "TEXT"),
    ("contacts", "title", "TEXT"),
    ("contacts", "department", "TEXT"),
    ("contacts", "notes", "TEXT"),
    ("contacts", "updated_at", "TEXT"),
]


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
        for table, column, decl in ADDED_LATER:
            try:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            except sqlite3.OperationalError:
                pass                      # already there, which is the usual case
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


def event_exists(title: str, trigger: str, within_days: Optional[int] = None) -> bool:
    """Has this exact signal already been recorded?

    A feed reports the same quake for hours, so a watcher that polls every few
    minutes would raise it again on every pass. Title and trigger together are
    the signal's natural identity: the trigger carries the source's own
    timestamp, so a genuinely new event never collides with an old one.
    """
    sql = "SELECT 1 FROM events WHERE title=? AND trigger=? "
    args: List[Any] = [title, trigger]
    if within_days is not None:
        # A standing risk is not news every week, but it is news again if it is
        # still there months later. Without a window a one-off suppression
        # becomes permanent silence about a problem nobody fixed.
        sql += "AND received_at >= ? "
        args.append((datetime.now(timezone.utc) - timedelta(days=within_days)).isoformat())
    with connect() as c:
        row = c.execute(sql + "LIMIT 1", args).fetchone()
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
        if status in ("failed", "held"):
            # Nothing was carried out, so nothing should stay reserved. A run
            # that ends 'done' keeps its holds: the stock really is spoken for
            # until the move is confirmed, and record_outcome lets it go.
            c.execute("UPDATE reservations SET released_at=?, released_why=?"
                      " WHERE run_id=? AND released_at IS NULL",
                      (_now(), f"run {status}", run_id))


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
                  autonomous: bool, payload: dict,
                  status: Optional[str] = None) -> Dict[str, Any]:
    """Idempotent: the same key never produces a second action.

    `status` is what it starts as. By default `pending`, waiting for a person,
    or `sent` for an autonomous record that is done once written. An
    autonomous action that still has to reach SAP starts `approved` instead
    (tools/execution.raise_action), and only SAP taking it makes it `sent`.
    """
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
             status or ("sent" if autonomous else "pending"), _now()),
        )
        row = c.execute("SELECT * FROM actions WHERE id=?", (aid,)).fetchone()
        return dict(row) | {"repeated": False}


# ------------------------------------------------------------- reservations
def reserve(run_id: str, material: str, plant: str, qty: float,
            action_id: Optional[str] = None) -> str:
    """Hold stock at the donor plant so a second handling cannot promise it too.

    Two disruptions running at once both read the same on-hand figure and both
    conclude SBY1 can spare 55 t. Each is right on its own and they are wrong
    together. A hold is what makes the second one see the first.
    """
    rid = new_id("res")
    with connect() as c:
        c.execute("INSERT INTO reservations (id, run_id, action_id, material, plant,"
                  " qty, created_at) VALUES (?,?,?,?,?,?,?)",
                  (rid, run_id, action_id, material, plant, float(qty), _now()))
    return rid


def reserved_qty(material: str, plant: str, excluding_run: Optional[str] = None) -> float:
    """How much of this material at this plant is already spoken for.

    `excluding_run` lets a handling see the world without its own holds, so
    re-assessing its own transfer does not subtract the stock twice.
    """
    sql = ("SELECT COALESCE(SUM(qty), 0) t FROM reservations"
           " WHERE material=? AND plant=? AND released_at IS NULL")
    args: List[Any] = [material, plant]
    if excluding_run:
        sql += " AND run_id<>?"
        args.append(excluding_run)
    with connect() as c:
        return float(c.execute(sql, args).fetchone()["t"])


def release_reservations(why: str, run_id: Optional[str] = None,
                         action_id: Optional[str] = None) -> int:
    """Let held stock go. Returns how many holds were lifted."""
    if not (run_id or action_id):
        raise ValueError("release what? pass run_id or action_id")
    sql = "UPDATE reservations SET released_at=?, released_why=? WHERE released_at IS NULL"
    args: List[Any] = [_now(), why]
    if action_id:
        sql += " AND action_id=?"
        args.append(action_id)
    else:
        sql += " AND run_id=?"
        args.append(run_id)
    with connect() as c:
        return c.execute(sql, args).rowcount


def open_reservations(material: Optional[str] = None) -> List[dict]:
    sql = "SELECT * FROM reservations WHERE released_at IS NULL"
    args: List[Any] = []
    if material:
        sql += " AND material=?"
        args.append(material)
    with connect() as c:
        return [dict(r) for r in c.execute(sql + " ORDER BY created_at", args)]


OUTCOMES = ("delivered", "late", "short", "failed", "cancelled")

#: The one key engine/report.py reads as the realized cost. Declared here so the
#: agent tool and the HTTP route cannot each invent their own spelling.
REALIZED_COST_KEY = "actual_idr"

#: Action kinds that have a real-world result worth asking about. `notify` is
#: deliberately absent: an internal message has no realized cost, and chasing
#: one would teach people to ignore the chase.
AWAITS_OUTCOME = ("stock_transfer", "draft_po", "monitor",
                  "customer_notice", "supplier_request")


def outcome_detail(note: str = "", actual_cost_idr: Optional[float] = None,
                   recorded_by: str = "") -> Optional[Dict[str, Any]]:
    """Build the `detail` document for `record_outcome`. Deterministic.

    The realized cost travels as a number or not at all. A string raises here
    rather than being coerced, and `note` is never scanned for a figure: in
    Indonesian "Rp 24,5 jt" and "24.500.000" put the same digits a thousand
    apart, so any parser would have to guess a scale, and a guessed rupiah
    figure that reaches a portfolio tile is indistinguishable from a read one.
    That is the single thing this system refuses to do.

    `recorded_by` says who read reality, which is what makes the figure
    admissible as a reading rather than as somebody's arithmetic.
    """
    doc: Dict[str, Any] = {}
    if note:
        doc["note"] = note
    if actual_cost_idr is not None:
        # bool is an int in Python; True is not a cost.
        if isinstance(actual_cost_idr, bool) or not isinstance(actual_cost_idr, (int, float)):
            raise ValueError(
                f"a realized cost must be a number, not {actual_cost_idr!r}. "
                "Pass the figure itself, or leave it out and the report will say "
                "the realized cost is not known.")
        if actual_cost_idr < 0:
            raise ValueError(f"a realized cost cannot be negative: {actual_cost_idr!r}")
        doc[REALIZED_COST_KEY] = float(actual_cost_idr)
    if recorded_by:
        doc["recorded_by"] = recorded_by
    return doc or None


def record_outcome(action_id: str, outcome: str, detail: Optional[dict] = None) -> Dict[str, Any]:
    """What actually happened after the action was sent.

    This is the half of the record that was missing. Everything else here says
    what was decided and on what evidence; without this nothing says whether
    the decision worked, so the system could run for a year and learn nothing.

    Written once, like an approval. A correction is a new reading of reality,
    not an edit of the old one, so a second call is refused rather than
    silently overwriting what the first one saw.
    """
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {', '.join(OUTCOMES)}, not {outcome!r}")
    with connect() as c:
        row = c.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        if not row:
            raise KeyError(action_id)
        if row["outcome"]:
            return dict(row) | {"repeated": True}
        if row["status"] not in ("sent", "approved"):
            raise ValueError(f"action {action_id} is {row['status']}: "
                             "nothing was sent, so nothing can have happened to it")
        c.execute("UPDATE actions SET outcome=?, outcome_at=?, outcome_detail=? WHERE id=?",
                  (outcome, _now(), json.dumps(detail or {}, ensure_ascii=False), action_id))
        # The move has now either happened or not. Either way SAP's own numbers
        # are the truth from here, so the hold has nothing left to protect.
        c.execute("UPDATE reservations SET released_at=?, released_why=?"
                  " WHERE action_id=? AND released_at IS NULL",
                  (_now(), f"outcome {outcome}", action_id))
        return dict(c.execute("SELECT * FROM actions WHERE id=?",
                              (action_id,)).fetchone()) | {"repeated": False}


def actions_awaiting_outcome(older_than_days: int = 0) -> List[Dict[str, Any]]:
    """Actions that went out and whose real result nobody has written down yet.

    The loop that makes this system learn is closed by hand: nothing here polls
    SAP or a carrier to discover a receipt, and inventing one would be worse
    than an empty column. So the open half of the record is made visible
    instead, and the daily digest asks for it. Oldest first, because the one
    sent three weeks ago is the one whose outcome is about to be forgotten.

    The `status IN ('sent','approved') AND outcome IS NULL` test is a literal
    mirror of the guard inside `record_outcome`. If the two drift, this offers
    a thing the store would then refuse. The kind filter is narrower on purpose
    (see AWAITS_OUTCOME), so the two rules sit next to each other here.
    """
    cutoff = ""
    if older_than_days > 0:
        cutoff = (datetime.now(timezone.utc)
                  - timedelta(days=older_than_days)).isoformat(timespec="seconds")
    marks = ",".join("?" * len(AWAITS_OUTCOME))
    with connect() as c:
        rows = c.execute(
            "SELECT a.id, a.run_id, a.kind, a.payload, a.status, a.sap_reference,"
            "       a.created_at, e.title, e.kind AS event_kind"
            " FROM actions a JOIN runs r ON r.id = a.run_id"
            " JOIN events e ON e.id = r.event_id"
            " WHERE a.status IN ('sent','approved') AND a.outcome IS NULL"
            f" AND a.kind IN ({marks})"
            + (" AND a.created_at <= ?" if cutoff else "")
            + " ORDER BY a.created_at",
            AWAITS_OUTCOME + ((cutoff,) if cutoff else ())).fetchall()

    now = datetime.now(timezone.utc)
    out = []
    for r in rows:
        waiting = None
        try:
            waiting = (now - datetime.fromisoformat(r["created_at"])).days
        except (TypeError, ValueError):       # a stamp we cannot read is not a crash
            pass
        out.append(dict(r) | {"payload": json.loads(r["payload"]),
                              "days_waiting": waiting})
    return out


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
        if decision == "rejected":
            # The move is not happening, so the donor's stock belongs to
            # whoever needs it next. Held inside this transaction so a
            # rejection never leaves tonnes locked by an action that died.
            c.execute("UPDATE reservations SET released_at=?, released_why=?"
                      " WHERE action_id=? AND released_at IS NULL",
                      (_now(), "action rejected", action_id))
        return dict(c.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone())


# --------------------------------------------------------------------- reads
def list_runs(limit: int = 50) -> List[dict]:
    with connect() as c:
        rows = c.execute(
            "SELECT r.*, e.title, e.kind, e.trigger,"
            " (SELECT count(*) FROM steps s WHERE s.run_id = r.id) AS step_count,"
            " (SELECT count(*) FROM steps s WHERE s.run_id = r.id AND s.stage = 'TOOL') AS tool_count,"
            " (SELECT count(*) FROM actions a WHERE a.run_id = r.id) AS action_count"
            " FROM runs r JOIN events e ON e.id = r.event_id"
            " ORDER BY r.started_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) | {"decision": json.loads(r["decision"]) if r["decision"] else None}
            for r in rows]


def past_incidents(terms: List[str], limit: int = 5) -> tuple[List[dict], int]:
    """Handled disruptions, ranked by how many of `terms` they mention.

    Returns the matches AND the number of finished runs on record, because
    "we have never handled anything" and "we looked and nothing was
    comparable" are different answers and only the first is a gap in the data.
    The caller needs to tell them apart to label its result honestly.

    What is searched includes how the handling ENDED, not only how it was
    titled: the lead's recommendation and each action's outcome. An incident is
    most worth finding for what came of it ("late", "short"), and that is
    exactly the part a title never says.

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
        # One query for every action, grouped here: the haystack now needs the
        # outcomes before anything is scored, and asking per run would be a
        # query per finished run.
        by_run: Dict[str, List[dict]] = {}
        for a in c.execute(
                "SELECT run_id, kind, payload, status, outcome, outcome_at, outcome_detail"
                " FROM actions ORDER BY created_at").fetchall():
            by_run.setdefault(a["run_id"], []).append({
                "kind": a["kind"],
                "payload": json.loads(a["payload"]),
                "status": a["status"],
                "outcome": a["outcome"],
                "outcome_at": a["outcome_at"],
                "outcome_detail": json.loads(a["outcome_detail"]) if a["outcome_detail"] else None,
            })

    total = len(rows)
    scored = []
    for r in rows:
        # What was done, and what came of it. A precedent without its outcome
        # only says what somebody decided, which is the part the system already
        # knows it decided.
        acts = by_run.get(r["run_id"], [])
        decision = json.loads(r["decision"]) if r["decision"] else None
        # Only the prose is searched, never the JSON around it: matching on the
        # raw document would make every incident a hit for "recommendation".
        said = " ".join(str(decision.get(k) or "") for k in ("recommendation", "reason")
                        ) if isinstance(decision, dict) else ""
        happened = " ".join(
            f"{a['kind']} {a['outcome'] or ''} "
            f"{(a['outcome_detail'] or {}).get('note') or ''}" for a in acts)
        hay = f"{r['title']} {r['kind']} {r['trigger']} {said} {happened}".lower()
        hits = sum(1 for t in terms if t in hay)
        if not hits:
            continue
        scored.append((hits, dict(r) | {
            "decision": decision,
            "matched": hits,
            "actions": acts,
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
        "actions": [dict(a) | {
            "payload": json.loads(a["payload"]),
            # Parsed here like `payload`, so a reader never has to know that one
            # JSON column arrives decoded and the next one as a string.
            "outcome_detail": json.loads(a["outcome_detail"]) if a["outcome_detail"] else None,
        } for a in actions],
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


#: How many rows of an upload a reader is handed at once. A file of 1,395
#: quotations is normal, and sending all of it to a browser to fill a drawer
#: nobody scrolls is a cost paid on every open.
PREVIEW_ROWS = 200


def get_upload(uid: str, limit: int = PREVIEW_ROWS) -> Optional[dict]:
    """One upload with the first `limit` of its rows, for looking at.

    The row count stays the file's own, not the number returned, so a reader
    can tell a short file from a long one that was cut — a preview that quietly
    renamed 1,395 rows to 200 would be the kind of small lie this system is
    built to avoid.
    """
    with connect() as c:
        r = c.execute("SELECT * FROM uploads WHERE id=?", (uid,)).fetchone()
    if not r:
        return None
    rows = json.loads(r["payload"])
    shown = rows[:limit] if limit else rows
    return {k: r[k] for k in ("id", "entity", "filename", "rows", "uploaded_by",
                              "uploaded_at", "synthetic")} | {
        "columns": list(shown[0]) if shown else [],
        "preview": shown,
        "shown": len(shown),
        "truncated": len(shown) < len(rows),
    }


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


#: What a contact carries besides name, role, email and the kinds they follow.
CONTACT_DETAILS = ("phone", "title", "department", "notes")


def add_contact(name: str, role: str, email: str, notify_for: str = "*",
                **details: Optional[str]) -> dict:
    cid = new_id("cnt")
    extra = [details.get(k) or None for k in CONTACT_DETAILS]
    with connect() as c:
        c.execute("INSERT INTO contacts (id,name,role,email,notify_for,created_at,"
                  + ",".join(CONTACT_DETAILS) + ") VALUES (?,?,?,?,?,?,"
                  + ",".join("?" * len(CONTACT_DETAILS)) + ")",
                  (cid, name, role, email.lower(), notify_for, _now(), *extra))
        return dict(c.execute("SELECT * FROM contacts WHERE id=?", (cid,)).fetchone())


def get_contact(cid: str) -> Optional[dict]:
    with connect() as c:
        r = c.execute("SELECT * FROM contacts WHERE id=? AND active=1", (cid,)).fetchone()
    return dict(r) if r else None


def update_contact(cid: str, **fields: Optional[str]) -> Optional[dict]:
    """Change what is given; an empty string clears a detail."""
    allowed = ("name", "role", "email", "notify_for") + CONTACT_DETAILS
    sets = {k: (v.lower() if k == "email" and v else (v or None))
            for k, v in fields.items() if k in allowed and v is not None}
    if sets:
        with connect() as c:
            c.execute("UPDATE contacts SET " + ", ".join(f"{k}=?" for k in sets)
                      + ", updated_at=? WHERE id=? AND active=1", (*sets.values(), _now(), cid))
    return get_contact(cid)


def notifications_to(address: str, limit: int = 20) -> List[dict]:
    """What was sent to one email address, newest first."""
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
    # ---------------------------------------------------------- reservations
    # Two handlings read the same on-hand figure at the same moment. Each
    # concludes SBY1 can spare 55 t. Each is right alone; together they promise
    # 110 t that does not exist. The hold is what makes the second one see the
    # first.
    e1 = record_event("port_closure", "Ningbo closes", "test", {}, "check")
    e2 = record_event("supplier_failure", "Supplier stops", "test", {}, "check")
    r1, r2 = start_run(e1, "guided"), start_run(e2, "guided")

    assert reserved_qty("M-4471", "SBY1") == 0
    reserve(r1, "M-4471", "SBY1", 55)
    assert reserved_qty("M-4471", "SBY1") == 55
    # The run that placed the hold must not be charged for its own tonnes.
    assert reserved_qty("M-4471", "SBY1", excluding_run=r1) == 0
    assert reserved_qty("M-4471", "SBY1", excluding_run=r2) == 55
    assert reserved_qty("M-4471", "KRW1") == 0, "a hold is per plant"

    reserve(r2, "M-4471", "SBY1", 20)
    assert reserved_qty("M-4471", "SBY1") == 75

    freed = release_reservations("run failed", run_id=r1)
    assert freed == 1 and reserved_qty("M-4471", "SBY1") == 20, reserved_qty("M-4471", "SBY1")

    # A run that ends without carrying anything out must not keep the stock.
    close_run(r2, "failed", error="boom")
    assert reserved_qty("M-4471", "SBY1") == 0, "a failed run left stock held"
    assert not open_reservations("M-4471")
    print("  reservations: donor stock cannot be promised twice ✓ · freed on failure ✓")

    # ---- the realized figure, and what is still owed one -------------------
    # A cost is a number or it is nothing. These are the assertions that keep
    # prose from ever becoming money.
    assert outcome_detail() is None
    assert outcome_detail("arrived late") == {"note": "arrived late"}, "prose only"
    assert REALIZED_COST_KEY not in outcome_detail("it cost about Rp 24,5 jt")
    assert outcome_detail("", 24_500_000, "rina@x") == {
        REALIZED_COST_KEY: 24_500_000.0, "recorded_by": "rina@x"}
    for bad in ("24,500,000", "24500000", True, -1):
        try:
            outcome_detail("", bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"a realized cost of {bad!r} was accepted")

    r3 = start_run(e1, "guided")
    moved = record_action(r3, "k-move", "stock_transfer", True,
                          {"material": "M-4471", "cost_idr": 22_000_000})
    told = record_action(r3, "k-told", "notify", True, {"role": "buyer"})
    reserve(r3, "M-4471", "SBY1", 10, action_id=moved["id"])

    owed = {a["id"]: a for a in actions_awaiting_outcome()}
    assert moved["id"] in owed, "a sent transfer is owed an outcome"
    assert told["id"] not in owed, "an internal message is not chased for an outcome"
    assert owed[moved["id"]]["title"] == "Ningbo closes"
    assert owed[moved["id"]]["days_waiting"] == 0

    # An outcome recorded by hand releases the hold in the same transaction.
    record_outcome(moved["id"], "late", outcome_detail("3 days late", 24_500_000, "rina@x"))
    assert moved["id"] not in {a["id"] for a in actions_awaiting_outcome()}
    assert reserved_qty("M-4471", "SBY1") == 0, "the outcome left stock held"
    again = record_outcome(moved["id"], "delivered")
    assert again["repeated"] and again["outcome"] == "late", "an outcome was overwritten"

    # Nothing was sent, so nothing can have happened to it — and the store's
    # refusal must agree with what actions_awaiting_outcome() offers.
    waiting = record_action(r3, "k-po", "draft_po", False, {"cost_idr": 94_000_000})
    assert waiting["id"] not in {a["id"] for a in actions_awaiting_outcome()}
    try:
        record_outcome(waiting["id"], "delivered")
    except ValueError:
        pass
    else:
        raise AssertionError("an outcome was recorded against a pending action")
    print("  outcomes: a figure is a number or nothing, never read out of prose ✓ "
          "· written once ✓ · the hold is released ✓ · what is still owed one ✓")

    save_model_choices({"lead": "aicore:gpt-5.4", "specialists": "deepseek.v3.2"}, "a@x")
    save_model_choices({"specialists": "zai.glm-5", "lead": None}, "b@x")
    assert model_choices() == {"specialists": "zai.glm-5"}, model_choices()
    assert model_choices(detail=True)["specialists"]["updated_by"] == "b@x"
    print("  model choice: set, replaced, cleared back to the environment ✓")

    assert enqueue_notification("run:r1:done:a@x", "handling", "email", "a@x", "s", "b", "r1")
    assert not enqueue_notification("run:r1:done:a@x", "handling", "email", "a@x", "s", "b", "r1"), \
        "the same message is queued once, however many times it is asked for"
    (n,) = pending_notifications()
    mark_notification(n["id"], "sent")
    assert not pending_notifications() and list_notifications()[0]["status"] == "sent"
    print("  notifications: queued once ✓ · marked sent ✓")

    k = add_contact("Rina", "buyer", "Rina@X", "*", phone="+62 812 0000 1111", title="Buyer, steel")
    assert k["email"] == "rina@x" and k["phone"] == "+62 812 0000 1111" and k["notes"] is None
    k = update_contact(k["id"], department="Procurement", phone="", notes="Mornings only")
    assert k["department"] == "Procurement" and k["phone"] is None and k["notes"] == "Mornings only"
    assert k["updated_at"] and update_contact(k["id"], role=None)["role"] == "buyer", "None keeps"
    assert enqueue_notification("to:rina", "test", "email", "rina@x", "hello", "b")
    assert [n["subject"] for n in notifications_to("Rina@x")] == ["hello"]
    assert delete_contact(k["id"]) and get_contact(k["id"]) is None
    print("  contacts: phone, title, department, notes kept and cleared ✓ · what was sent to them ✓")

    job_started("probe")
    job_finished("probe", False, "boom")
    set_job_enabled("probe", False)
    j = job_states()["probe"]
    assert (j["runs"], j["failures"], j["last_status"], j["enabled"]) == (1, 1, "failed", 0)
    print("  jobs: a run, a failure and a switch-off are remembered ✓")

    # An upload read back for looking at. The count a reader is shown must stay
    # the file's own even when the rows handed over are cut, because a preview
    # that renamed 7 rows to 3 would be a quiet lie about what was stored.
    big = [{"Supplier": f"SUP-{i}", "TkdnCertifiedPct": float(i)} for i in range(7)]
    up = save_upload("Supplier", "suppliers.csv", big, "rina@x")
    whole = get_upload(up["id"])
    assert whole and whole["rows"] == 7 and whole["shown"] == 7 and not whole["truncated"]
    assert whole["columns"] == ["Supplier", "TkdnCertifiedPct"], whole["columns"]
    cut = get_upload(up["id"], limit=3)
    assert cut["shown"] == 3 and cut["truncated"] and cut["rows"] == 7, cut
    assert cut["preview"][0]["Supplier"] == "SUP-0"
    assert get_upload("upl_nope") is None, "an unknown id is not found, not an empty file"
    assert delete_upload(up["id"]) and get_upload(up["id"]) is None
    print("  uploads: read back whole, cut rows say so, the row count stays the file's ✓")

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
