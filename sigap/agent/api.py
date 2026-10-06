"""SIGAP HTTP service.

# ponytail: stdlib http.server, fine for a dozen events/day, zero dependencies.
#           Move to FastAPI + uvicorn if you need async, websockets, or >10 rps.

    python3 api.py                 # listen on :8787

Endpoints
    GET  /health
    POST /events                   {kind, title, trigger, payload, source} → run
    GET  /runs                     recent handlings
    GET  /runs/{id}                one handling: steps, actions, approvals
    POST /actions/{id}/decision    {decision, note}
    POST /login                    {email, password}
    GET  /me
    GET  /agents                   team anatomy
    POST /agents/{code}/ask        {question, conversation_id?}
    GET  /agents/{code}/conversations
    GET  /conversations/{id} · POST /conversations/{id}/delete
    GET  /summary                  dashboard figures
    GET  /data/{domain}            per-domain table
    GET  /log                      every step, newest first
    GET  /uploads · POST /uploads
    POST /mcp                      the tool registry over MCP\n    GET  /reports/{run_id}
    GET  /contacts · POST /contacts
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Tuple
from urllib.parse import urlparse

import tools  # noqa: F401  (registers every tool)
from core import identity, store
from core.config import CFG, bind_target
from core.identity import NotAuthorised, User
from tools.views import VIEWS

HOST, PORT = bind_target(os.environ)


# ------------------------------------------------------------------- handling
def _handle(run_id: str, event: dict) -> None:
    """Run the agent team in the background. Failures are written down, not swallowed."""
    seq = {"n": 0}

    def report(kind: str, d: dict) -> None:
        seq["n"] += 1
        name = d.get("name") or d.get("agent", "-")
        store.save_step(run_id, {
            "seq": seq["n"],
            "stage": {"specialist_start": "DELEGATE", "specialist_done": "FINDING",
                      "tool": "TOOL"}.get(kind, kind.upper()),
            "agent": d.get("agent", "supervisor"),
            "agent_name": name,
            "summary": d.get("summary") or d.get("task") or d.get("name", ""),
            "tools": [d["name"]] if kind == "tool" else [],
            "detail": d,
            "at": store._now(),
        })

    try:
        import graph
        result = graph.run(event, report)
        store.close_run(run_id, "done", result, cost_idr=result.get("cost_idr", 0))
    except Exception as e:                                           # noqa: BLE001
        store.close_run(run_id, "failed", error=f"{type(e).__name__}: {e}")
        traceback.print_exc()


# -------------------------------------------------------------------- routing
ROUTES: list = []


def _user(headers) -> User:
    """Identity comes ONLY from the token. Never from the request body."""
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise NotAuthorised("a session token is required")
    return identity.from_token(auth[7:])


def route(method: str, pattern: str) -> Callable:
    r = re.compile("^" + pattern + "$")

    def wrap(fn: Callable) -> Callable:
        ROUTES.append((method, r, fn))
        return fn
    return wrap


@route("GET", r"/health")
def health(_m, _b, _h) -> Tuple[int, dict]:
    return 200, {
        "env": CFG.env,
        "sap_ready": CFG.sap_ready,
        "model_ready": CFG.model_ready,
        "may_use_modelled": CFG.may_use_modelled,
        "model": CFG.model,
    }


@route("POST", r"/events")
def receive_event(_m, b: dict, _h) -> Tuple[int, dict]:
    for field in ("kind", "title", "trigger"):
        if not b.get(field):
            return 400, {"error": f"'{field}' is required"}

    if CFG.production and not (CFG.sap_ready and CFG.model_ready):
        return 503, {"error": "production is not ready: SAP or the model is not connected"}

    eid = store.record_event(b["kind"], b["title"], b["trigger"],
                             b.get("payload", {}), b.get("source", "api"))
    mode = "autonomous" if CFG.model_ready else "guided"
    rid = store.start_run(eid, mode)

    event = {"id": eid, "kind": b["kind"], "title": b["title"],
             "trigger": b["trigger"], **b.get("payload", {})}

    if CFG.model_ready:
        threading.Thread(target=_handle, args=(rid, event), daemon=True).start()
    else:
        store.close_run(rid, "held", decision={
            "status": "held",
            "reason": "AWS_REGION is not set. The agent team cannot reason. "
                      "No decision was made.",
        })

    return 202, {"event_id": eid, "run_id": rid, "mode": mode}


@route("GET", r"/summary")
def summary(_m, _b, _h) -> Tuple[int, dict]:
    """The dashboard figures."""
    with store.connect() as c:
        runs = c.execute("SELECT status, COUNT(*) n FROM runs GROUP BY status").fetchall()
        actions = c.execute("SELECT status, COUNT(*) n FROM actions GROUP BY status").fetchall()
        approved = c.execute(
            "SELECT COALESCE(SUM(json_extract(payload,'$.cost_idr')),0) FROM actions"
            " WHERE status IN ('approved','sent')").fetchone()[0]
        pending = c.execute(
            "SELECT COALESCE(SUM(json_extract(payload,'$.cost_idr')),0) FROM actions"
            " WHERE status='pending'").fetchone()[0]
        model_cost = c.execute("SELECT COALESCE(SUM(token_cost_idr),0) FROM runs").fetchone()[0]
        recent = c.execute(
            "SELECT e.title, r.status, r.started_at FROM runs r"
            " JOIN events e ON e.id=r.event_id ORDER BY r.started_at DESC LIMIT 5").fetchall()

    stock = VIEWS["inventory"]()
    critical = [x for x in stock["rows"] if (x.get("days_left") or 999) < 14]

    return 200, {
        "runs": {r["status"]: r["n"] for r in runs},
        "actions": {r["status"]: r["n"] for r in actions},
        "approved_value_idr": approved,
        "pending_value_idr": pending,
        "model_cost_idr": model_cost,
        "critical_stock": critical[:5],
        "recent": [dict(r) for r in recent],
        "sap_ready": CFG.sap_ready,
        "model_ready": CFG.model_ready,
    }


@route("GET", r"/data/([a-z]+)")
def domain_view(m, _b, _h) -> Tuple[int, dict]:
    name = m.group(1)
    if name not in VIEWS:
        return 404, {"error": f"unknown domain '{name}'", "available": list(VIEWS)}
    # the domain name is the code of the agent that owns it
    return 200, {"domain": name, "agent": name, **VIEWS[name]()}


@route("GET", r"/audit")
def audit(_m, _b, _h) -> Tuple[int, dict]:
    """Read everything the system can see and report what is wrong with it."""
    from engine import audit as engine_audit
    from tools.fetcher import current_dataset, profile

    data, origins = current_dataset()
    if not data.get("MaterialStock"):
        return 200, {"findings": [], "counts": {}, "coverage": {},
                     "origins": origins,
                     "note": "no material stock is readable, so there is nothing to audit"}

    result = engine_audit.run(data, profile())
    weakest = sorted({o["origin"] for o in origins.values()},
                     key=["missing", "modelled", "cached", "derived", "live"].index)
    return 200, {
        **result.as_dict(),
        "origins": origins,
        "weakest_origin": weakest[0] if weakest else "missing",
        "note": "Every finding is computed from the rows named beside it. No model was "
                "involved, so any of it can be recomputed from the same file.",
    }


@route("GET", r"/uploads")
def list_uploads(_m, _b, _h) -> Tuple[int, dict]:
    return 200, {"uploads": store.list_uploads()}


@route("POST", r"/uploads")
def upload(_m, b: dict, h) -> Tuple[int, dict]:
    """Accept the company's own data as CSV.

    This layers over the modelled data: once uploaded, the tools use it and the
    origin label becomes 'cached' rather than 'modelled'.
    """
    u = _user(h)
    entity = b.get("entity")
    filename = b.get("filename", "untitled.csv")
    body = b.get("csv", "")
    allowed = {"MaterialStock", "PurchaseOrder", "SalesOrder",
               "BillOfMaterial", "AlternateSource"}
    if entity not in allowed:
        return 400, {"error": f"entity must be one of {sorted(allowed)}"}
    if not body.strip():
        return 400, {"error": "the CSV body is empty"}
    try:
        rows = [dict(r) for r in csv.DictReader(io.StringIO(body))]
    except Exception as e:                                          # noqa: BLE001
        return 400, {"error": f"could not read the CSV: {e}"}
    if not rows:
        return 400, {"error": "the CSV has no data rows"}

    # numbers come back as numbers; CSV sends everything as text
    for r in rows:
        for k, v in list(r.items()):
            if isinstance(v, str) and v.strip():
                try:
                    r[k] = float(v) if "." in v else int(v)
                except ValueError:
                    pass
    # The uploader says whether this is real master data or a generated sample.
    # Nothing in the file itself can tell us, and guessing would mean labelling
    # generated rows as cached, which is exactly the laundering this system
    # exists to prevent.
    return 201, store.save_upload(entity, filename, rows, u.email,
                                  synthetic=bool(b.get("synthetic")))


@route("POST", r"/uploads/([A-Za-z0-9_]+)/delete")
def remove_upload(m, _b, h) -> Tuple[int, dict]:
    _user(h)
    return (200, {"deleted": True}) if store.delete_upload(m.group(1)) \
        else (404, {"error": "not found"})


@route("GET", r"/reports/([A-Za-z0-9_]+)")
def report_for_run(m, _b, _h) -> Tuple[int, dict]:
    """Assemble one handling into a report, ready to copy or send."""
    d = store.get_run(m.group(1))
    if not d:
        return 404, {"error": "not found"}

    lines: List[str] = [
        f"# {d['title']}", "",
        f"Kind     : {d['kind']}",
        f"Trigger  : {d['trigger']}",
        f"Started  : {d['started_at']}",
        f"Status   : {d['status']}" + (f" ({d['mode']})" if d["mode"] == "guided" else ""),
        "",
    ]
    if d["decision"]:
        k = d["decision"]
        lines += ["## Decision", "", k.get("recommendation") or k.get("reason") or "not recorded", ""]
    if d["steps"]:
        lines += ["## Reasoning", ""]
        for s in d["steps"]:
            origin = f" [{s['origin']}]" if s.get("origin") else ""
            lines.append(f"{s['seq']}. **{s['stage']}** · {s['agent_name']}, "
                         f"{s['summary']}{origin}")
        lines.append("")
    if d["actions"]:
        lines += ["## Actions", "", "| Action | Value | Status |", "|---|---|---|"]
        for a in d["actions"]:
            n = a["payload"].get("cost_idr")
            lines.append(f"| {a['kind']} | {('Rp ' + format(n, ',')) if n else '-'} "
                         f"| {a['status']} |")
        lines.append("")
    if d["approvals"]:
        lines += ["## Approvals", ""]
        for p in d["approvals"]:
            lines.append(f"- {p['decision']} by {p['decided_by']} ({p['role']}) · {p['at']}")
        lines.append("")
    lines += ["---", f"Generated by SIGAP · {store._now()}"]

    return 200, {"run_id": d["id"], "title": d["title"], "markdown": "\n".join(lines)}


@route("GET", r"/contacts")
def list_contacts(_m, _b, _h) -> Tuple[int, dict]:
    return 200, {"contacts": store.list_contacts()}


@route("POST", r"/contacts")
def create_contact(_m, b: dict, h) -> Tuple[int, dict]:
    _user(h)
    for field in ("name", "role", "email"):
        if not b.get(field):
            return 400, {"error": f"'{field}' is required"}
    return 201, store.add_contact(b["name"], b["role"], b["email"],
                                  b.get("notify_for", "*"))


@route("POST", r"/contacts/([A-Za-z0-9_]+)/delete")
def remove_contact(m, _b, h) -> Tuple[int, dict]:
    _user(h)
    return (200, {"deleted": True}) if store.delete_contact(m.group(1)) \
        else (404, {"error": "not found"})


@route("GET", r"/agents")
def list_agents(_m, _b, _h) -> Tuple[int, dict]:
    """Team anatomy: who exists, what tools they hold, what is actually wired up."""
    from agents.definitions import ALL
    from core import registry

    registered = registry.all_tools()
    out = []
    for code, a in ALL.items():
        tools = [{
            "name": name,
            "installed": name in registered,
            "description": registered[name].description if name in registered else None,
        } for name in a.tools]
        out.append({
            "code": code, "nickname": a.nickname, "title": a.title, "brief": a.brief,
            "effort": a.effort, "veto": a.veto,
            "lead": code == "supervisor",
            "ready": a.ready,
            "tools": tools,
            "installed": sum(1 for t in tools if t["installed"]),
            "tool_count": len(tools),
        })

    # how many events actually invoked each agent
    with store.connect() as c:
        used = dict(c.execute(
            "SELECT agent, COUNT(DISTINCT run_id) FROM steps GROUP BY agent").fetchall())
    for a in out:
        a["used_in"] = used.get(a["code"], 0)

    return 200, {
        "agents": out,
        "summary": {
            "agent_count": len(out),
            "tools_installed": sum(a["installed"] for a in out),
            "tools_total": sum(a["tool_count"] for a in out),
            "prompts_written": sum(1 for a in out if a["ready"]),
            "model_ready": CFG.model_ready,
            "sap_ready": CFG.sap_ready,
        },
    }


@route("POST", r"/agents/([a-z_]+)/ask")
def ask_agent(m, b: dict, h) -> Tuple[int, dict]:
    """A direct conversation with one specialist."""
    user = _user(h)                                # identity comes from the token
    code, question = m.group(1), (b.get("question") or "").strip()
    if not question:
        return 400, {"error": "'question' is required"}

    from agents.definitions import ALL
    if code not in ALL:
        return 404, {"error": f"unknown agent '{code}'"}

    if not CFG.model_ready:
        return 503, {
            "error": "AWS_REGION is not set. The agent cannot reason.",
            "hint": "Set AWS_REGION in sigap/agent/.env to a region that offers Claude "
                    "on Bedrock, then restart the service.",
        }
    # An existing conversation is only continued if this user owns it. An id in
    # a request body is a claim, not proof.
    cid = (b.get("conversation_id") or "").strip() or None
    prior = store.get_conversation(cid, user.id) if cid else None
    if cid and not prior:
        return 404, {"error": "no such conversation"}

    try:
        import graph
        reply = graph.ask_specialist(code, question, history=_as_turns(prior))
    except Exception as e:                                          # noqa: BLE001
        traceback.print_exc()
        return 500, {"error": f"{type(e).__name__}: {e}"}

    # Written down only once there is something to write down, so a failed ask
    # does not leave an empty conversation in the list.
    if not cid:
        cid = store.start_conversation(code, user.id, question)
    store.add_message(cid, "person", {"text": question})
    store.add_message(cid, "agent", reply)
    return 200, reply | {"conversation_id": cid}


# How many earlier messages the agent is shown. Far enough back to follow a
# thread, near enough that an old conversation cannot run the bill up.
CONTEXT_TURNS = 12


def _as_turns(conversation: dict | None) -> List[dict] | None:
    """Stored messages as model turns. Errors are dropped: they are not answers."""
    if not conversation:
        return None
    turns = []
    for m in conversation["messages"]:
        if m["role"] == "person":
            turns.append({"role": "user", "content": m["body"]["text"]})
        elif m["role"] == "agent":
            turns.append({"role": "assistant", "content": m["body"]["answer"]})
    return turns[-CONTEXT_TURNS:] or None


@route("GET", r"/agents/([a-z_]+)/conversations")
def agent_conversations(m, _b, h) -> Tuple[int, dict]:
    user = _user(h)
    return 200, {"conversations": store.list_conversations(user.id, m.group(1))}


@route("GET", r"/conversations/([A-Za-z0-9_]+)")
def read_conversation(m, _b, h) -> Tuple[int, dict]:
    user = _user(h)
    c = store.get_conversation(m.group(1), user.id)
    if not c:
        return 404, {"error": "no such conversation"}
    return 200, c


@route("POST", r"/conversations/([A-Za-z0-9_]+)/delete")
def remove_conversation(m, _b, h) -> Tuple[int, dict]:
    user = _user(h)
    if not store.delete_conversation(m.group(1), user.id):
        return 404, {"error": "no such conversation"}
    return 200, {"deleted": True}


@route("POST", r"/mcp")
def mcp_endpoint(_m, b: dict, h) -> Tuple[int, dict]:
    """The tool registry over MCP, for AgentCore Gateway and for SAP Joule.

    Authenticated like every other route. Joule reaches an MCP server through a
    BTP destination, and the destination is where the credential lives, so this
    staying closed is the correct default rather than an obstacle.
    """
    _user(h)
    import mcp
    reply = mcp.handle(b or {})
    return (204, {}) if not reply else (200, reply)


@route("GET", r"/log")
def raw_log(_m, _b, _h) -> Tuple[int, dict]:
    """Every step from every handling, newest first."""
    with store.connect() as c:
        steps = c.execute(
            "SELECT s.*, e.title, e.kind AS event_kind FROM steps s"
            " JOIN runs r ON r.id = s.run_id"
            " JOIN events e ON e.id = r.event_id"
            " ORDER BY s.id DESC LIMIT 300").fetchall()
        actions = c.execute(
            "SELECT a.*, e.title FROM actions a"
            " JOIN runs r ON r.id = a.run_id"
            " JOIN events e ON e.id = r.event_id"
            " ORDER BY a.created_at DESC LIMIT 100").fetchall()
        approvals = c.execute(
            "SELECT p.*, a.kind AS action_kind, a.run_id FROM approvals p"
            " JOIN actions a ON a.id = p.action_id ORDER BY p.id DESC LIMIT 100").fetchall()
    return 200, {
        "steps": [dict(r) | {"tools": json.loads(r["tools"]),
                             "detail": json.loads(r["detail"])} for r in steps],
        "actions": [dict(r) | {"payload": json.loads(r["payload"])} for r in actions],
        "approvals": [dict(r) for r in approvals],
    }


@route("POST", r"/login")
def login(_m, b: dict, _h) -> Tuple[int, dict]:
    try:
        u = identity.log_in(b.get("email", ""), b.get("password", ""))
    except NotAuthorised as e:
        return 401, {"error": str(e)}
    return 200, {"token": identity.issue_token(u),
                 "user": {"name": u.name, "email": u.email,
                          "role": u.role, "limit_idr": u.limit_idr}}


@route("GET", r"/me")
def me(_m, _b, h) -> Tuple[int, dict]:
    u = _user(h)
    return 200, {"name": u.name, "email": u.email, "role": u.role,
                 "limit_idr": u.limit_idr}


@route("GET", r"/runs")
def list_runs(_m, _b, _h) -> Tuple[int, dict]:
    return 200, {"runs": store.list_runs()}


@route("GET", r"/runs/([A-Za-z0-9_]+)")
def one_run(m, _b, _h) -> Tuple[int, dict]:
    d = store.get_run(m.group(1))
    return (200, d) if d else (404, {"error": "not found"})


@route("POST", r"/actions/([A-Za-z0-9_]+)/decision")
def decide(m, b: dict, h) -> Tuple[int, dict]:
    u = _user(h)                       # identity from the token, not the body
    if not b.get("decision"):
        return 400, {"error": "'decision' is required"}

    action_id = m.group(1)
    d = store.get_action(action_id)
    if not d:
        return 404, {"error": "action not found"}

    value = int(d["payload"].get("cost_idr", 0))
    if b["decision"] == "approved" and not u.may_approve(value):
        return 403, {
            "error": f"role '{u.role}' may not approve Rp {value:,}",
            "limit_idr": u.limit_idr,
            "hint": "escalate to procurement_lead",
        }
    try:
        return 200, store.decide_action(action_id, u.email, u.role,
                                        b["decision"], b.get("note", ""))
    except ValueError as e:
        return 400, {"error": str(e)}


# --------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type,authorization")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:          # noqa: N802
        self._send(204, {})

    def _dispatch(self, method: str) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/health"
        body: Dict[str, Any] = {}
        if method == "POST":
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                try:
                    body = json.loads(self.rfile.read(n))
                except json.JSONDecodeError:
                    return self._send(400, {"error": "the body is not valid JSON"})
        for m, pattern, fn in ROUTES:
            if m != method:
                continue
            found = pattern.match(path)
            if found:
                try:
                    code, data = fn(found, body, self.headers)
                except NotAuthorised as e:
                    return self._send(401, {"error": str(e)})
                except Exception as e:                               # noqa: BLE001
                    traceback.print_exc()
                    return self._send(500, {"error": f"{type(e).__name__}: {e}"})
                return self._send(code, data)
        self._send(404, {"error": f"unknown route: {method} {path}"})

    def do_GET(self) -> None:              # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:             # noqa: N802
        self._dispatch("POST")

    def log_message(self, fmt: str, *a) -> None:
        print(f"  {self.command} {self.path} → {a[1] if len(a) > 1 else ''}")


if __name__ == "__main__":
    print(f"SIGAP API · env={CFG.env} · sap={'ready' if CFG.sap_ready else 'no'} "
          f"· model={'ready' if CFG.model_ready else 'no'}")
    print(f"listening on http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
