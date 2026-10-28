"""SIGAP HTTP service.

# ponytail: stdlib http.server, fine for a dozen events/day, zero dependencies.
#           Move to FastAPI + uvicorn if you need async, websockets, or >10 rps.

    python3 api.py                 # listen on :8787

Every route but /health and /login needs a session.

Endpoints
    GET  /health                   readiness, and which model each agent runs on
    POST /events                   {kind, title, trigger, payload, source} → run  (session)
    GET  /exposure                 Vega's scan and the RPT slip ranking, no model  (session)
    GET  /runs                     recent handlings
    GET  /runs/{id}                one handling: steps, actions, approvals
    POST /actions/{id}/decision    {decision, note}
    POST /actions/{id}/outcome     {outcome, detail?, actual_cost_idr?}  what happened
    POST /login                    {email, password}
    GET  /me
    GET  /agents                   team anatomy
    POST /agents/{code}/ask        {question, conversation_id?}
    GET  /agents/{code}/conversations
    GET  /conversations/{id} · POST /conversations/{id}/delete
    GET  /summary                  dashboard figures
    GET  /data/{domain}            per-domain table
    GET  /log                      every step, newest first
    GET  /runs/{id}/trace          one handling as a topology, with its calls in order
    GET  /runs/{id}/steps/{seq}    one step in full
    GET  /runs/{id}/graph          the exploration graph, empty when SIGAP_GRAPH was off
    GET  /audit                    what is wrong with the data the system can see
    GET  /uploads · POST /uploads · POST /uploads/{id}/delete
    GET  /uploads/template/{entity}   the columns an upload of that entity takes, with a sample row
    POST /mcp                      the tool registry over MCP
    GET  /reports/{run_id}         one handling written up, and the sheets its workbook holds
    GET  /reports/{run_id}.pdf · .xlsx   the same as a document, or every table it produced
    GET  /portfolio · /portfolio.pdf · /portfolio.xlsx   the handlings rolled up over a
                                   period: ?days=30, or ?since=&until= as WIB calendar dates
    POST /reports/{run_id}/send · /portfolio/send   {contacts, me?, formats, note} by email  (session)
    GET  /contacts · /contacts/{id}  (session) · POST /contacts, /contacts/{id}, /contacts/{id}/delete  (admin, lead)
    GET  /notifications            channel status and what was sent  (session)
    POST /notifications/test       a test alert to every channel set up  (admin, lead)
    POST /notifications/connect    a sign-in link for the Gmail SIGAP sends from  (admin, lead)
    POST /actions/{id}/resend      an approved outward message whose send failed  (session)
    GET  /schedule                 every job, its cadence and last result  (session)
    POST /schedule/{name}/run      run one now  (admin, lead)
    POST /schedule/{name}/enabled  {enabled}  (admin, lead)
    GET  /models                   the catalog, and which model each agent runs on  (session)
    POST /models                   {lead?, specialists?, fallback?, aux?, agents?}  (admin, lead)
    POST /models/test              {model}: one real call  (admin, lead)
"""
from __future__ import annotations

import csv
import io
import json
import os
import queue
import re
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import tools  # noqa: F401  (registers every tool)
from core import identity, llm, registry, store
from core.config import CFG, bind_target
from core.identity import NotAuthorised, User
from tools.views import VIEWS

HOST, PORT = bind_target(os.environ)


def _reasoning_workers() -> int:
    """Bound concurrent handlings so a burst cannot exhaust provider RPM/TPM."""
    try:
        return max(1, min(8, int(os.environ.get("SIGAP_REASONING_WORKERS", "1"))))
    except ValueError:
        return 1


#: Events are still recorded immediately; only their model reasoning queues.
REASONING_SEMAPHORE = threading.BoundedSemaphore(_reasoning_workers())


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
            # The provenance columns the log reads; they were left empty before.
            "origin": d.get("origin"),
            "source": d.get("source"),
            "detail": d,
            "at": store._now(),
        })

    try:
        # Runs remain visible as `running` while queued. Only the expensive
        # model work enters the bounded section, so event ingestion stays fast.
        with REASONING_SEMAPHORE:
            import graph
            # Every tool called inside this handling knows which run it belongs to,
            # so an action raised by one lands on this run rather than on nothing.
            with registry.bind_run(run_id):
                result = graph.run(event, report)
        store.close_run(run_id, "done", result, cost_idr=result.get("cost_idr", 0))
    except Exception as e:                                           # noqa: BLE001
        if llm.is_rate_limited(e):
            reason = "The Bedrock account is temporarily rate-limited after automatic retries."
            store.close_run(run_id, "held", decision={
                "status": "held", "reason": reason, "retryable": True,
            })
        else:
            store.close_run(run_id, "failed", error=f"{type(e).__name__}: {e}")
            traceback.print_exc()
    _tell(run_id)


#: The schedule, once __main__ starts it. None in a check or an import.
SCHEDULE = None


def _tell(run_id: str) -> None:
    """Queue the alerts for a finished handling, then deliver without waiting
    for the outbox's next round. Fails open: a mail server that is down must
    not turn a finished handling into a failed one; the row stays queued."""
    try:
        import notify
        if notify.queue_handling(run_id) and SCHEDULE is not None:
            SCHEDULE.run_now("notify")
    except Exception:                                                # noqa: BLE001
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
    from agents.definitions import ALL
    return 200, {
        "env": CFG.env,
        "sap_ready": CFG.sap_ready,
        "model_ready": CFG.model_ready,
        "may_use_modelled": CFG.may_use_modelled,
        # The lead's model, as before. `models` has every agent's, since they
        # no longer have to be the same one.
        "model": str(llm.spec_for(ALL["supervisor"])),
        "models": llm.describe(ALL.values()),
        "aux_model": str(llm.aux_spec()),
    }


# ---------------------------------------------------------------------- models
#: Who may change how the team runs: its models, its schedule, its alerts. A
#: model change moves spend and the quality of every recommendation after it,
#: and switching a watcher off is choosing not to hear about a typhoon, so these
#: sit with the roles that already carry the largest approval limits.
SETTINGS_ROLES = ("admin", "procurement_lead")
_CHOICE_KEYS = ("lead", "specialists", "fallback", "aux")

#: The last Test per model, for the page. In memory: a reading, not a record.
_TESTED: Dict[str, dict] = {}


def _load_model_choices() -> None:
    try:
        llm.choose(store.model_choices())
    except ValueError as e:
        print(f"  the saved model choice was not loaded ({e}); the environment's models are in force")


def _offered(raw: str) -> bool:
    """A model the page may set or test: one from the catalog, or one the
    environment already names, so going back to it never needs a shell."""
    from agents.definitions import ALL
    s = str(llm.parse(raw))
    env = set()
    for var in ("SIGAP_MODEL", "SIGAP_MODEL_SPECIALISTS", "SIGAP_MODEL_FALLBACK", "SIGAP_AUX_MODEL",
                *(f"SIGAP_MODEL_{c.upper()}" for c in ALL)):
        v = os.environ.get(var, "").strip()
        if v and v != llm.NO_FALLBACK:
            env.add(str(llm.parse(v)))
    return bool(llm.listed(s)) or s in env


def _models_payload(user: User) -> dict:
    from agents.definitions import ALL
    team = llm.describe(ALL.values())
    fb = llm.fallback_for()
    aux = llm.aux_spec()
    catalog = llm.catalog()
    listed = {x["model"] for x in catalog}
    for extra in sorted({r["model"] for r in team} | {str(aux)} | ({str(fb)} if fb else set())):
        if extra not in listed:                 # named in .env, not in the catalog
            s = llm.parse(extra)
            ok, why = llm.ready(s)
            catalog.append({"model": extra, "label": s.model, "vendor": None, "note": "from .env",
                            "via": llm.route_of(s), "usd_per_mtok": list(llm.usd_per_mtok(s)),
                            "ready": ok, "why": why or None})
    def norm(raw: str) -> Any:
        raw = (raw or "").strip()
        return str(llm.parse(raw)) if raw and raw != llm.NO_FALLBACK else (raw or None)

    env = {"lead": norm(CFG.model), "specialists": norm(os.environ.get("SIGAP_MODEL_SPECIALISTS", "")),
           "fallback": norm(os.environ.get("SIGAP_MODEL_FALLBACK", "")), "aux": norm(CFG.aux_model)}
    picked = llm.chosen()
    lead = norm(picked.get("lead") or CFG.model)
    return {
        "catalog": catalog,
        "team": team,
        "fallback": str(fb) if fb else None,
        "aux": str(aux),
        # Each role's model with no per-agent setting in the way.
        "roles": {"lead": lead,
                  "specialists": norm(picked.get("specialists") or env["specialists"] or lead),
                  "fallback": str(fb) if fb else None, "aux": str(aux)},
        "chosen": store.model_choices(detail=True),
        "env": env,
        "tested": _TESTED,
        "may_change": user.role in SETTINGS_ROLES,
        "idr_per_usd": llm.IDR_PER_USD,
    }


@route("GET", r"/models")
def models(_m, _b, h) -> Tuple[int, dict]:
    return 200, _models_payload(_user(h))


@route("POST", r"/models")
def choose_models(_m, b: dict, h) -> Tuple[int, dict]:
    """{lead?, specialists?, fallback?, aux?, agents?: {code: model}}. A key
    left out is left alone; null or "" hands it back to the environment.
    Applies to every model call made after it, including the remaining rounds
    of a handling already running."""
    from agents.definitions import ALL
    user = _user(h)
    if user.role not in SETTINGS_ROLES:
        return 403, {"error": f"role '{user.role}' may not change the models "
                              f"(needs {' or '.join(SETTINGS_ROLES)})"}
    changes: Dict[str, Any] = {k: b[k] for k in _CHOICE_KEYS if k in b}
    agents = b.get("agents") or {}
    if not isinstance(agents, dict):
        return 400, {"error": "'agents' must map an agent code to a model"}
    for code, v in agents.items():
        if code not in ALL:
            return 400, {"error": f"no agent '{code}'"}
        changes[code] = v
    if not changes:
        return 400, {"error": f"nothing to change: send any of {', '.join(_CHOICE_KEYS)} or agents"}
    for key, v in list(changes.items()):
        if v is not None and not isinstance(v, str):
            return 400, {"error": f"'{key}' must be a model name, or null"}
        v = (v or "").strip()
        if not v or (key == "fallback" and v == llm.NO_FALLBACK):
            changes[key] = v or None
            continue
        try:
            if not _offered(v):
                return 400, {"error": f"'{v}' is not on the Models page; name it in .env instead"}
            s = llm.parse(v)
        except ValueError as e:
            return 400, {"error": str(e)}
        ok, why = llm.ready(s)
        if not ok:
            return 400, {"error": f"{s} cannot be called from here: {why}"}
        changes[key] = str(s)
    before = llm.chosen()
    llm.choose({**store.model_choices(), **changes})
    try:
        store.save_model_choices(changes, user.email)
    except Exception:
        llm.choose(before)                # what runs must match what is on record
        raise
    return 200, _models_payload(user)


@route("POST", r"/models/test")
def test_model(_m, b: dict, h) -> Tuple[int, dict]:
    """One tiny real call. It spends a few tokens, so it sits with the roles
    that may change the models."""
    user = _user(h)
    if user.role not in SETTINGS_ROLES:
        return 403, {"error": f"role '{user.role}' may not test models"}
    try:
        if not b.get("model") or not _offered(b["model"]):
            return 400, {"error": "name a model from the Models page"}
        s = llm.parse(b["model"])
    except ValueError as e:
        return 400, {"error": str(e)}
    ok, said, seconds = llm.ping(s)
    _TESTED[str(s)] = {"ok": ok, "said": said, "seconds": round(seconds, 1),
                       "at": store._now(), "by": user.email}
    return 200, {"model": str(s), **_TESTED[str(s)]}


def raise_event(b: dict) -> Tuple[str, str, str]:
    """Record a disruption and set the team on it. Returns (event, run, mode).

    Both the endpoint below and the BMKG watcher come through here. They used
    to be the same ten lines in two places, which is how a signal raised by a
    machine and one raised by a person drift into behaving differently.
    """
    eid = store.record_event(b["kind"], b["title"], b["trigger"],
                             b.get("payload", {}), b.get("source", "api"))
    mode = "autonomous" if CFG.model_ready else "guided"
    rid = store.start_run(eid, mode)

    event = {"id": eid, "kind": b["kind"], "title": b["title"],
             "trigger": b["trigger"], **b.get("payload", {})}

    if CFG.model_ready:
        threading.Thread(target=_handle, args=(rid, event), daemon=True).start()
    else:
        lead = llm.spec_for_code("supervisor")
        store.close_run(rid, "held", decision={
            "status": "held",
            "reason": f"The lead's model {lead} cannot be called ({llm.ready(lead)[1]}), and no "
                      "fallback can either. The agent team cannot reason. No decision was made.",
        })
        _tell(rid)
    return eid, rid, mode


@route("POST", r"/events")
def receive_event(_m, b: dict, h) -> Tuple[int, dict]:
    # A session is required. This route used to check none, so anyone who could
    # reach the host could start handlings that spend model credit. Any role
    # may raise an event: raising one decides nothing, and every action it
    # leads to still waits on someone whose limit covers it. The watchers
    # (signals/watch.py) call raise_event() in-process and never come through here.
    user = _user(h)
    for field in ("kind", "title", "trigger"):
        if not b.get(field):
            return 400, {"error": f"'{field}' is required"}

    if CFG.production and not (CFG.sap_ready and CFG.model_ready):
        return 503, {"error": "production is not ready: SAP or the model is not connected"}

    eid, rid, mode = raise_event({**b, "source": b.get("source") or f"api:{user.email}"})
    return 202, {"event_id": eid, "run_id": rid, "mode": mode}


@route("GET", r"/exposure")
def exposure(_m, _b, h) -> Tuple[int, dict]:
    """Vega's two read-only answers to "what is about to break": the exposure
    scan, and SAP RPT-1.6's ranking of open POs by how far they are likely to
    slip. Both are tools, run directly, so the answer costs no model call. The
    Joule shim's risk_scan reads this."""
    _user(h)
    scan = registry.run("scan_supply_exposure", {})
    slip = registry.run("rank_po_slip_risk", {})
    return 200, {"findings": scan.value or [], **scan.brief(),
                 "slip_ranking": {"value": slip.value or [], **slip.brief()}}


@route("GET", r"/summary")
def summary(_m, b, h) -> Tuple[int, dict]:
    """The dashboard figures, over a period: ?days=30, or ?since=&until= (WIB).

    Two kinds of figure live here and they are NOT both period figures, so the
    reply keeps them apart rather than letting a date range quietly change the
    meaning of half the page:

      * a FLOW is what happened between two dates - how much was handled, what
        it was predicted to cost, what obeying the rules cost, what the models
        cost. A period makes these comparable month to month.
      * a STATE is what is true right now - what waits on a person, what still
        owes an outcome, how much of the rule pack anybody has verified.
        Filtering a state by last month would answer a question nobody asked
        and hide the approval that is late today.
    """
    _user(h)
    from engine import report, triage
    from tools.compliance import pack_status
    try:
        w = report.window(**_period(b))
    except ValueError as e:
        return 400, {"error": str(e)}
    clause, args = report.period_sql(w, "r.started_at")

    with store.connect() as c:
        runs = c.execute("SELECT r.status, COUNT(*) n FROM runs r WHERE 1=1"
                         + clause + " GROUP BY r.status", args).fetchall()
        actions = c.execute(
            "SELECT a.status, COUNT(*) n FROM actions a JOIN runs r ON r.id = a.run_id"
            " WHERE 1=1" + clause + " GROUP BY a.status", args).fetchall()
        approved = c.execute(
            "SELECT COALESCE(SUM(json_extract(a.payload,'$.cost_idr')),0) FROM actions a"
            " JOIN runs r ON r.id = a.run_id WHERE a.status IN ('approved','sent')"
            + clause, args).fetchone()[0]
        pending = c.execute(
            "SELECT COALESCE(SUM(json_extract(a.payload,'$.cost_idr')),0) FROM actions a"
            " JOIN runs r ON r.id = a.run_id WHERE a.status='pending'" + clause, args).fetchone()[0]
        model_cost = c.execute("SELECT COALESCE(SUM(r.token_cost_idr),0) FROM runs r"
                               " WHERE 1=1" + clause, args).fetchone()[0]
        autonomous = c.execute(
            "SELECT COUNT(*) FROM actions a JOIN runs r ON r.id = a.run_id"
            " WHERE a.autonomous=1 AND a.status IN ('approved','sent')" + clause, args).fetchone()[0]
        recent = c.execute(
            "SELECT e.title, r.status, r.started_at FROM runs r"
            " JOIN events e ON e.id=r.event_id WHERE 1=1" + clause
            + " ORDER BY r.started_at DESC LIMIT 5", args).fetchall()

    stock = VIEWS["inventory"]()
    critical = [x for x in stock["rows"] if (x.get("days_left") or 999) < 14]

    # Flow: what the rules cost between those dates.
    costs = report.compliance_costs(w)
    # State: what is true now. Deliberately not filtered by the period - an
    # approval that is late today is late whatever month the reader picked.
    board = triage.summarise([triage.Verdict(**r["verdict"]) for r in triage.queue()])
    owed = store.actions_awaiting_outcome()

    return 200, {
        "period": w,
        "period_label": report.period_label(w),
        # ---- flow, inside the period
        "runs": {r["status"]: r["n"] for r in runs},
        "actions": {r["status"]: r["n"] for r in actions},
        "approved_value_idr": approved,
        "pending_value_idr": pending,
        "model_cost_idr": model_cost,
        "autonomous_actions": autonomous,
        "rules_cost_idr": sum(int(c["idr"]) for c in costs),
        "rules_cost_cases": len(costs),
        "recent": [dict(r) for r in recent],
        # ---- state, right now, whatever period is selected
        "board": board,
        "outcomes_owed": len(owed),
        "oldest_owed_days": max((o["days_waiting"] or 0 for o in owed), default=0),
        "knowledge_base": pack_status(),
        "critical_stock": critical[:5],
        "sap_ready": CFG.sap_ready,
        "model_ready": CFG.model_ready,
    }


@route("GET", r"/data/([a-z]+)")
def domain_view(m, _b, h) -> Tuple[int, dict]:
    _user(h)
    name = m.group(1)
    if name not in VIEWS:
        return 404, {"error": f"unknown domain '{name}'", "available": list(VIEWS)}
    # the domain name is the code of the agent that owns it
    return 200, {"domain": name, "agent": name, **VIEWS[name]()}


@route("GET", r"/audit")
def audit(_m, _b, h) -> Tuple[int, dict]:
    """Read everything the system can see and report what is wrong with it."""
    _user(h)
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
def list_uploads(_m, _b, h) -> Tuple[int, dict]:
    _user(h)
    return 200, {"uploads": store.list_uploads()}


@route("POST", r"/uploads")
def upload(_m, b: dict, h) -> Tuple[int, dict]:
    """Accept the company's own data as CSV.

    This layers over the modelled data: once uploaded, the tools use it and the
    origin label becomes 'cached' rather than 'modelled'.
    """
    from core import schema
    u = _user(h)
    entity = b.get("entity")
    filename = b.get("filename", "untitled.csv")
    body = b.get("csv", "")
    if entity not in schema.ENTITIES:
        return 400, {"error": f"entity must be one of {schema.entity_names()}"}
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

    # Validate before storing. SIGAP refuses to keep data it cannot stand
    # behind: a missing column or a non-numeric quantity is reported with the
    # row, and the file is rejected, rather than sitting as plausible-looking
    # rows that break three agents downstream.
    check = schema.validate(entity, rows)
    if not check["ok"]:
        return 422, {"error": "the file does not match the " + entity + " schema",
                     "problems": check["errors"], "rows": check["row_problems"],
                     "template": schema.template(entity)}

    # The uploader says whether this is real master data or a generated sample.
    # Nothing in the file itself can tell us, and guessing would mean labelling
    # generated rows as cached, which is exactly the laundering this system
    # exists to prevent.
    return 201, store.save_upload(entity, filename, rows, u.email,
                                  synthetic=bool(b.get("synthetic")))


@route("GET", r"/uploads/([A-Za-z0-9_]+)/rows")
def upload_rows(m, _b, h) -> Tuple[int, dict]:
    """One upload's own rows, so a person can see what they actually gave the
    system rather than trusting a row count. Capped; the reply says when it is."""
    _user(h)
    u = store.get_upload(m.group(1))
    return (200, u) if u else (404, {"error": "not found"})


@route("GET", r"/uploads/template/([A-Za-z]+)")
def upload_template(m, _b, h) -> Tuple[int, dict]:
    """The expected columns (and a one-row sample) for an entity, so a company
    knows exactly what to upload."""
    _user(h)
    from core import schema
    entity = m.group(1)
    if entity not in schema.ENTITIES:
        return 404, {"error": f"unknown entity; one of {schema.entity_names()}"}
    return 200, schema.template(entity)


@route("POST", r"/uploads/([A-Za-z0-9_]+)/delete")
def remove_upload(m, _b, h) -> Tuple[int, dict]:
    _user(h)
    return (200, {"deleted": True}) if store.delete_upload(m.group(1)) \
        else (404, {"error": "not found"})


def _period(b: dict) -> dict:
    """The period a rollup is asked for: ?days=30, or ?since=&until= as WIB
    calendar dates. Nothing given means every handling on record."""
    days = b.get("days")
    return {"since": str(b["since"]) if b.get("since") else None,
            "until": str(b["until"]) if b.get("until") else None,
            "days": int(days) if days not in (None, "") else None}


@route("GET", r"/portfolio")
def portfolio_report(_m, b, h) -> Tuple[int, dict]:
    """The operations rollup over a period: counts, committed value, what the
    rules cost, realized-vs-predicted. Figures deterministic; aux adds a summary
    when able. ?days=30, or ?since=2026-10-01&until=2026-10-31 (WIB)."""
    _user(h)
    from engine import report
    try:
        return 200, report.build_portfolio(**_period(b))
    except ValueError as e:
        return 400, {"error": str(e)}


@route("GET", r"/reports/([A-Za-z0-9_]+)")
def report_for_run(m, _b, h) -> Tuple[int, dict]:
    """Assemble one handling into a report, ready to copy or send. The figures
    are deterministic; the aux model adds an executive summary when available
    (engine/report.py), and the report is complete without it."""
    _user(h)
    from engine import report
    rep = report.build_report(m.group(1))
    return (200, rep) if rep else (404, {"error": "not found"})


@route("GET", r"/reports/([A-Za-z0-9_]+)\.(pdf|xlsx)")
def report_file(m, _b, h) -> Tuple[int, Any]:
    """One handling as a file: a PDF to read or send on, or a workbook with
    every table it produced (actions, steps, and each tool's rows)."""
    _user(h)
    from engine import report
    f = report.run_file(m.group(1), m.group(2))
    return (200, Download(*f)) if f else (404, {"error": "not found"})


@route("GET", r"/portfolio\.(pdf|xlsx)")
def portfolio_file(m, b, h) -> Tuple[int, Any]:
    """The operations report as a file, over the same period as the page."""
    _user(h)
    from engine import report
    try:
        return 200, Download(*report.portfolio_file(m.group(1), **_period(b)))
    except ValueError as e:
        return 400, {"error": str(e)}


def _send_report(target: str, b: dict, h) -> Tuple[int, dict]:
    """A report to the people on the Contacts page, by email, with the files
    asked for. Only to contacts (or to the sender): a report carries what was
    decided and what it is worth, and the contact list is where an admin or a
    procurement lead has chosen who may read that."""
    import notify
    from clients import channels
    u = _user(h)
    wanted = {str(x) for x in b.get("contacts") or []}
    known = {c["id"]: c["email"] for c in store.list_contacts()}
    unknown = sorted(wanted - set(known))
    if unknown:
        return 400, {"error": f"not on the Contacts page: {', '.join(unknown)}"}
    emails = [known[i] for i in wanted] + ([u.email] if b.get("me") else [])
    if not emails:
        return 400, {"error": "choose at least one contact, or yourself"}
    gaps = channels.missing("email")
    if gaps:
        return 409, {"error": "email is not set up: " + "; ".join(gaps)}
    try:
        n = notify.queue_report(target, list(b.get("formats") or ["pdf"]), emails, u.email,
                                str(b.get("note") or "")[:2000],
                                period=_period(b) if target == "portfolio" else None)
    except LookupError as e:
        return 404, {"error": str(e)}
    return 200, {"queued": n, "to": emails, "delivery": notify.deliver_summary()}


@route("POST", r"/reports/([A-Za-z0-9_]+)/send")
def send_report(m, b: dict, h) -> Tuple[int, dict]:
    return _send_report(m.group(1), b, h)


@route("POST", r"/portfolio/send")
def send_portfolio(_m, b: dict, h) -> Tuple[int, dict]:
    return _send_report("portfolio", b, h)


@route("GET", r"/contacts")
def list_contacts(_m, _b, h) -> Tuple[int, dict]:
    _user(h)
    return 200, {"contacts": store.list_contacts()}


def _settings_user(h) -> User:
    user = _user(h)
    if user.role not in SETTINGS_ROLES:
        raise _Refused(f"a {user.role} cannot change this (needs {' or '.join(SETTINGS_ROLES)})")
    return user


class _Refused(Exception):
    pass


@route("POST", r"/contacts")
def create_contact(_m, b: dict, h) -> Tuple[int, dict]:
    # A contact receives the record by email: what was decided, what it is
    # worth, who must approve it. Adding one is choosing who reads that, so it
    # sits with the same roles as the rest of the settings.
    try:
        _settings_user(h)
    except _Refused as e:
        return 403, {"error": str(e)}
    for field in ("name", "role", "email"):
        if not b.get(field):
            return 400, {"error": f"'{field}' is required"}
    bad = _contact_fields(b)
    if bad:
        return 400, {"error": bad}
    return 201, store.add_contact(b["name"].strip(), b["role"], b["email"].strip(),
                                  b.get("notify_for", "*"),
                                  **{k: str(b.get(k) or "").strip()[:1000] for k in store.CONTACT_DETAILS})


def _contact_fields(b: dict) -> Optional[str]:
    """What is wrong with a contact as given, or None."""
    if b.get("email") is not None and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",
                                                       str(b["email"]).strip()):
        return f"'{b['email']}' is not an email address"
    phone = str(b.get("phone") or "").strip()
    if phone and not re.fullmatch(r"\+?[0-9][0-9 ()\-.]{5,24}", phone):
        return f"'{phone}' is not a phone number: digits, spaces, dashes, a leading +"
    return None


@route("GET", r"/contacts/([A-Za-z0-9_]+)")
def one_contact(m, _b, h) -> Tuple[int, dict]:
    """One contact, and what SIGAP has sent them."""
    _user(h)
    c = store.get_contact(m.group(1))
    if not c:
        return 404, {"error": "not found"}
    return 200, {"contact": c, "sent": store.notifications_to(c["email"], 20)}


@route("POST", r"/contacts/([A-Za-z0-9_]+)")
def change_contact(m, b: dict, h) -> Tuple[int, dict]:
    try:
        _settings_user(h)
    except _Refused as e:
        return 403, {"error": str(e)}
    for field in ("name", "role", "email"):
        if field in b and not str(b[field] or "").strip():
            return 400, {"error": f"'{field}' cannot be empty"}
    bad = _contact_fields(b)
    if bad:
        return 400, {"error": bad}
    fields = {k: str(b[k]).strip()[:1000] for k in ("name", "role", "email", "notify_for",
                                                     *store.CONTACT_DETAILS) if k in b and b[k] is not None}
    c = store.update_contact(m.group(1), **fields)
    return (200, c) if c else (404, {"error": "not found"})


@route("POST", r"/contacts/([A-Za-z0-9_]+)/delete")
def remove_contact(m, _b, h) -> Tuple[int, dict]:
    try:
        _settings_user(h)
    except _Refused as e:
        return 403, {"error": str(e)}
    return (200, {"deleted": True}) if store.delete_contact(m.group(1)) \
        else (404, {"error": "not found"})


# -------------------------------------------------------------------- alerts
@route("GET", r"/notifications")
def notifications(_m, _b, h) -> Tuple[int, dict]:
    """What was sent, to whom, and whether it arrived; and which channels are
    set up (by variable name, never value)."""
    from clients import channels
    user = _user(h)
    return 200, {"channels": channels.status(), "recent": store.list_notifications(50),
                 "web_url": CFG.web_url, "may_change": user.role in SETTINGS_ROLES}


@route("POST", r"/notifications/test")
def notifications_test(_m, _b, h) -> Tuple[int, dict]:
    import notify
    try:
        user = _settings_user(h)
    except _Refused as e:
        return 403, {"error": str(e)}
    queued = notify.queue_test(user.email)
    if not queued:
        return 400, {"error": "no channel is set up: see ENV.md, Alerts"}
    return 200, {"queued": queued, "delivery": notify.deliver_summary()}


@route("POST", r"/notifications/connect")
def notifications_connect(_m, _b, h) -> Tuple[int, dict]:
    """A Composio sign-in page for the Gmail mailbox SIGAP will send from.
    Whoever signs in there is the mailbox, so the link goes back only to the
    admin or lead who asked for it."""
    from clients import composio
    try:
        _settings_user(h)
    except _Refused as e:
        return 403, {"error": str(e)}
    if not composio.configured():
        return 409, {"error": "COMPOSIO_API_KEY is not set (.secrets/notify.env)"}
    try:
        return 200, composio.connect_link("gmail", f"{CFG.web_url}/contacts")
    except composio.NotConnected as e:
        return 409, {"error": str(e)}
    except composio.Failed as e:
        return 502, {"error": str(e)}


# ------------------------------------------------------------------ schedule
@route("GET", r"/schedule")
def schedule(_m, _b, h) -> Tuple[int, dict]:
    user = _user(h)
    if SCHEDULE is None:
        return 503, {"error": "the schedule is not running in this process"}
    return 200, {"jobs": SCHEDULE.describe(), "enabled": SCHEDULE.enabled,
                 "watch": SCHEDULE.watch, "may_change": user.role in SETTINGS_ROLES}


@route("POST", r"/schedule/([a-z_]+)/run")
def schedule_run(m, _b, h) -> Tuple[int, dict]:
    # Running a watcher by hand can raise events, and an event spends model
    # credit, so this is a settings action rather than anyone's button.
    try:
        user = _settings_user(h)
    except _Refused as e:
        return 403, {"error": str(e)}
    if SCHEDULE is None:
        return 503, {"error": "the schedule is not running in this process"}
    if m.group(1) not in SCHEDULE.jobs:
        return 404, {"error": f"no job '{m.group(1)}'"}
    started = SCHEDULE.run_now(m.group(1))
    print(f"  schedule: {m.group(1)} run by hand by {user.email}", flush=True)
    return (202, {"started": True}) if started else (409, {"error": "it is already running"})


@route("POST", r"/schedule/([a-z_]+)/enabled")
def schedule_switch(m, b: dict, h) -> Tuple[int, dict]:
    try:
        user = _settings_user(h)
    except _Refused as e:
        return 403, {"error": str(e)}
    if SCHEDULE is None:
        return 503, {"error": "the schedule is not running in this process"}
    if m.group(1) not in SCHEDULE.jobs:
        return 404, {"error": f"no job '{m.group(1)}'"}
    if not isinstance(b.get("enabled"), bool):
        return 400, {"error": "'enabled' must be true or false"}
    store.set_job_enabled(m.group(1), b["enabled"])
    print(f"  schedule: {m.group(1)} switched {'on' if b['enabled'] else 'off'} by {user.email}",
          flush=True)
    return 200, {"jobs": SCHEDULE.describe()}


@route("GET", r"/agents")
def list_agents(_m, _b, h) -> Tuple[int, dict]:
    """Team anatomy: who exists, what tools they hold, what is actually wired up."""
    _user(h)
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


_AGENT_NICKNAMES = {
    "supervisor": "Arya", "impact": "Elsa", "demand": "Dara", "inventory": "Iris",
    "sourcing": "Clint", "procurement": "Prita", "logistics": "Milo", "compliance": "Kira",
    "simulation": "Tara", "precedent": "Otto", "execution": "Bram", "exposure": "Vega",
}

_TOOL_LABELS = {
    "scan_live_hazards": "live hazards near ports and plants",
    "get_port_conditions": "port weather and hazards",
    "search_news": "news headlines",
    "get_public_holidays": "public holiday calendar",
    "web_brief": "web search brief",
    "get_exchange_rate": "ECB exchange rate",
    "get_materials": "material master records",
    "get_open_purchase_orders": "open purchase orders",
    "get_material_stock": "plant stock availability",
    "get_bom_explosion": "bill of materials (BOM)",
    "get_sales_order_commitments": "customer order commitments",
    "get_demand_signal": "demand signals",
    "get_production_schedule": "production schedule",
    "forecast_demand": "material demand forecast",
    "get_quality_holds": "stock quality holds",
    "get_safety_stock_policy": "safety stock policy",
    "assess_transfer": "stock transfer feasibility",
    "find_alternate_sources": "alternative suppliers",
    "find_internal_transfers": "stock at alternative plants",
    "get_supplier_master": "supplier master records",
    "get_supplier_performance": "supplier performance history",
    "get_quotations": "supplier quotations",
    "compare_quotations": "quotation comparisons",
    "propose_purchase_order": "purchase order proposal",
    "get_shipment_status": "shipment tracking status",
    "estimate_eta": "estimated arrival dates (ETA)",
    "check_local_constraints": "compliance and regulatory constraints",
    "check_supplier_constraints": "whether the rules clear this supplier",
    "simulate_scenario": "scenario mitigation costs",
    "search_past_incidents": "similar past incident records",
    "create_stock_transfer": "stock transfer request",
    "create_draft_po": "draft purchase order creation",
    "notify": "notification dispatch",
    "draft_customer_notice": "customer delay notice (draft)",
    "request_supplier_update": "supplier date request (draft)",
    "monitor_shipment": "shipment watch",
    "record_outcome": "action outcome record",
    "create_sourcing_event": "sourcing event (draft)",
    "propose_safety_stock_change": "safety stock change (proposal)",
    "get_customs_status": "customs declaration status",
    "find_substitute_materials": "substitute materials and approvals",
    "allocate_short_supply": "allocation of short supply to customer orders",
    "get_rule_pack": "rule pack in force",
    "scan_supply_exposure": "supply exposure scan",
    "get_supplier_certifications": "supplier TKDN certificates",
    "rank_po_slip_risk": "purchase order slip risk",
    "detect_disruption": "disruption signal detection",
}

_TOOL_BADGES = {
    "scan_live_hazards": "Hazards",
    "get_port_conditions": "Weather",
    "search_news": "News",
    "get_public_holidays": "Calendar",
    "web_brief": "Web",
    "get_exchange_rate": "FX",
    "get_material_stock": "Stock Check",
    "get_open_purchase_orders": "Orders",
    "get_sales_order_commitments": "Sales",
    "forecast_demand": "Demand",
    "check_local_constraints": "Compliance",
    "check_supplier_constraints": "Compliance",
    "simulate_scenario": "Simulation",
    "find_alternate_sources": "Sourcing",
    "find_internal_transfers": "Transfers",
    "get_shipment_status": "Logistics",
    "get_customs_status": "Customs",
    "find_substitute_materials": "Substitutes",
    "allocate_short_supply": "Allocation",
    "get_rule_pack": "Rules",
    "draft_customer_notice": "Customer",
    "request_supplier_update": "Supplier",
    "detect_disruption": "Trigger",
}


def format_orchestration_step(kind: str, d: dict, seq: int) -> dict:
    now = store._now()
    thinking = str(d.get("thinking") or "").strip() or None
    if kind == "specialist_start":
        target_code = d.get("agent", "")
        target_name = d.get("name") or _AGENT_NICKNAMES.get(target_code, target_code.title())
        task = str(d.get("task", "")).strip()
        first_clause = task.split(".")[0].strip() if task else ""
        narrative = f"Delegating to {target_name}: {first_clause}" if first_clause else f"Delegating analysis to {target_name}"
        return {
            "seq": seq,
            "kind": "specialist_start",
            "agent": "supervisor",
            "agent_name": "Arya",
            "target_agent": target_code,
            "target_name": target_name,
            "narrative": narrative,
            "badge": f"{target_name} ›",
            "detail": f"{task[:110]}…" if len(task) > 110 else (task or f"Delegating to {target_name}"),
            "full_detail": task or f"Delegating analysis to {target_name}",
            "thinking": thinking,
            "at": now,
        }
    if kind == "tool":
        agent_code = d.get("agent", "")
        agent_name = _AGENT_NICKNAMES.get(agent_code, d.get("name", agent_code.title()))
        tool_name = d.get("name", "")
        tool_desc = _TOOL_LABELS.get(tool_name, tool_name.replace("_", " "))
        args = d.get("arguments", {})
        arg_summary = " · ".join(f"{k}: {v}" for k, v in list(args.items())[:2])
        badge = _TOOL_BADGES.get(tool_name, "Data Check")
        narrative = f"{agent_name} checking {tool_desc}"
        detail = f"{tool_name}{f' ({arg_summary})' if arg_summary else ''} ›"
        return {
            "seq": seq,
            "kind": "tool",
            "agent": agent_code,
            "agent_name": agent_name,
            "narrative": narrative,
            "badge": f"{badge} ›",
            "detail": detail,
            "tool_name": tool_name,
            "tool_label": tool_desc,
            "arguments": args,
            "result": d.get("result"),
            "origin": d.get("origin"),
            "source": d.get("source"),
            "error": d.get("error"),
            "thinking": thinking,
            "at": now,
        }
    if kind == "specialist_done":
        agent_code = d.get("agent", "")
        agent_name = d.get("name") or _AGENT_NICKNAMES.get(agent_code, agent_code.title())
        summary = str(d.get("summary", "")).strip()
        full_summary = str(d.get("full_summary") or summary).strip()
        first_line = summary.split("\n")[0].split(".")[0].strip()
        narrative = f"{agent_name} reported: {first_line}" if first_line else f"{agent_name} completed findings"
        return {
            "seq": seq,
            "kind": "specialist_done",
            "agent": agent_code,
            "agent_name": agent_name,
            "target_agent": "supervisor",
            "target_name": "Arya",
            "narrative": narrative,
            "badge": "Finding ›",
            "detail": f"{summary[:110]}…" if len(summary) > 110 else summary,
            "full_detail": full_summary,
            "thinking": thinking,
            "at": now,
        }
    if kind == "summary":
        full_summary = str(d.get("full_summary") or "").strip()
        return {
            "seq": seq,
            "kind": "summary",
            "agent": "supervisor",
            "agent_name": "Arya",
            "narrative": "Formulating final mitigation recommendation",
            "badge": "Summary ›",
            "detail": "Synthesizing findings for user",
            "full_detail": full_summary or "Synthesizing specialist findings into final mitigation recommendation.",
            "thinking": thinking,
            "at": now,
        }
    return {
        "seq": seq,
        "kind": kind,
        "agent": d.get("agent", "-"),
        "agent_name": d.get("name", "-"),
        "narrative": d.get("summary", ""),
        "badge": "Activity ›",
        "detail": str(d)[:80],
        "full_detail": str(d),
        "thinking": thinking,
        "at": now,
    }


@route("POST", r"/agents/([a-z_]+)/ask")
def ask_agent(m, b: dict, h):
    """A direct conversation with one specialist."""
    user = _user(h)                                # identity comes from the token
    code = m.group(1)
    question = (b.get("question") or "").strip()
    raw_attachments = b.get("attachments") or []
    attachments = [a for a in raw_attachments if isinstance(a, dict)] if isinstance(raw_attachments, list) else []

    if not question and not attachments:
        return 400, {"error": "'question' or an attachment is required"}

    from agents.definitions import ALL
    if code not in ALL:
        return 404, {"error": f"unknown agent '{code}'"}

    spec = llm.spec_for(ALL[code])
    if not llm.usable(spec):
        return 503, {
            "error": f"{ALL[code].nickname}'s model {spec} cannot be called: "
                     f"{llm.ready(spec)[1]}. The agent cannot reason.",
            "hint": "ENV.md, under Models, has the setup. Restart the service after "
                    "changing sigap/agent/.env.",
        }
    # An existing conversation is only continued if this user owns it. An id in
    # a request body is a claim, not proof.
    cid = (b.get("conversation_id") or "").strip() or None
    prior = store.get_conversation(cid, user.id) if cid else None
    if cid and not prior:
        return 404, {"error": "no such conversation"}

    effective_question = question or (
        "The user uploaded the attached image/file without a caption: "
        + ", ".join(str(a.get("name") or "attachment") for a in attachments)
        + ". Read all visible text, numbers, and visual context in the attachment carefully, "
        "summarise what it shows, and explain the supply-chain impact or next steps."
    )

    wants_stream = "text/event-stream" in (h.get("Accept") or "") or bool(b.get("stream"))

    stored_attachments = [
        {
            "name": str(a.get("name") or "attachment"),
            "mime_type": str(a.get("mime_type") or ""),
            "size": int(a.get("size") or 0),
            "kind": "image" if str(a.get("mime_type") or "").startswith("image/") else "file",
            "preview_url": a.get("preview_url") if str(a.get("mime_type") or "").startswith("image/") else None,
            "text_content": (str(a.get("text_content"))[:10000] if a.get("text_content") else None),
        }
        for a in attachments
    ]
    person_body: Dict[str, Any] = {"text": question}
    if stored_attachments:
        person_body["attachments"] = stored_attachments

    title_seed = question or (str(attachments[0].get("name") or "Attachment") if attachments else "Conversation")
    if not cid:
        cid = store.start_conversation(code, user.id, title_seed)
    store.add_message(cid, "person", person_body)

    if wants_stream:
        def sse_generator():
            q: queue.Queue = queue.Queue()
            sentinel = object()
            result_holder = {}
            error_holder = {}
            seq_counter = {"n": 0}

            steps_all: list = []

            def capture_report(kind: str, d: dict) -> None:
                seq_counter["n"] += 1
                step = format_orchestration_step(kind, d, seq_counter["n"])
                steps_all.append(step)
                q.put(("step", step))

            def worker() -> None:
                try:
                    import graph
                    res = graph.ask_specialist(
                        code,
                        effective_question,
                        report=capture_report,
                        history=_as_turns(prior),
                        attachments=attachments or None,
                    )
                    res["steps"] = list(steps_all)
                    # Persist the reply HERE, in the worker, the moment it is
                    # produced — not in the generator after the final yield. If
                    # the client navigates away or drops the connection
                    # mid-stream, the generator stops being read and any save
                    # placed after its yields would never run; the turn would be
                    # lost. The worker runs to completion regardless of the
                    # client, so the answer is written down either way.
                    try:
                        store.add_message(cid, "agent", res)
                    except Exception:                               # noqa: BLE001
                        traceback.print_exc()
                    result_holder["res"] = res
                except Exception as e:
                    traceback.print_exc()
                    error_holder["err"] = e
                finally:
                    q.put(sentinel)

            threading.Thread(target=worker, daemon=True).start()

            init_step = {
                "seq": 0,
                "kind": "init",
                "agent": "supervisor",
                "agent_name": "Arya",
                "conversation_id": cid,
                "narrative": "Analyzing request and mapping specialist delegations",
                "badge": "Analysis ›",
                "detail": "Orchestrating agent team...",
                "at": store._now(),
            }
            yield f"event: step\ndata: {json.dumps(init_step, ensure_ascii=False)}\n\n"

            while True:
                try:
                    item = q.get(timeout=2.0)
                except queue.Empty:
                    # Heartbeat prevents TCP/proxy idle timeouts while agent models think
                    yield ": ping\n\n"
                    continue

                if item is sentinel:
                    break
                _, step_data = item
                yield f"event: step\ndata: {json.dumps(step_data, ensure_ascii=False)}\n\n"

            if "err" in error_holder:
                err = error_holder["err"]
                yield f"event: error\ndata: {json.dumps({'error': f'{type(err).__name__}: {err}'})}\n\n"
                return

            # The worker already persisted the reply (see above); the generator
            # only streams it to a client still listening.
            reply = result_holder["res"]
            done_payload = reply | {"conversation_id": cid, "usage": _usage_payload(user.id, code)}
            yield f"event: done\ndata: {json.dumps(done_payload, ensure_ascii=False, default=str)}\n\n"

        return sse_generator()

    # Non-streaming fallback
    steps_collected = []
    seq_counter = {"n": 0}

    def capture_report(kind: str, d: dict) -> None:
        seq_counter["n"] += 1
        steps_collected.append(format_orchestration_step(kind, d, seq_counter["n"]))

    try:
        import graph
        reply = graph.ask_specialist(
            code,
            effective_question,
            report=capture_report,
            history=_as_turns(prior),
            attachments=attachments or None,
        )
    except Exception as e:                                          # noqa: BLE001
        traceback.print_exc()
        return 500, {"error": f"{type(e).__name__}: {e}"}

    reply["steps"] = steps_collected
    store.add_message(cid, "agent", reply)
    return 200, reply | {"conversation_id": cid, "usage": _usage_payload(user.id, code)}


# How many earlier messages the agent is shown. Far enough back to follow a
# thread, near enough that an old conversation cannot run the bill up.
CONTEXT_TURNS = 12


def _usage_payload(user_id: str, code: str = "supervisor") -> dict:
    """The figures beside a conversation, at the rate of the model the agent
    being talked to runs on."""
    import graph
    from agents.definitions import ALL
    spec = llm.spec_for(ALL.get(code) or ALL["supervisor"])
    usd_in, usd_out = llm.usd_per_mtok(spec)
    return {
        **store.conversation_usage_summary(user_id),
        "cost_cap_idr": CFG.cost_cap_per_event_idr,
        "max_output_tokens": 8000,
        "context_turns": CONTEXT_TURNS,
        "max_rounds": graph.MAX_SPECIALIST_ROUNDS,
        "input_idr_per_million": round(usd_in * llm.IDR_PER_USD),
        "output_idr_per_million": round(usd_out * llm.IDR_PER_USD),
        "model": str(spec),
    }


def _as_turns(conversation: dict | None) -> List[dict] | None:
    """Stored messages as model turns. Errors are dropped: they are not answers."""
    if not conversation:
        return None
    turns = []
    for m in conversation["messages"]:
        if m["role"] == "person":
            text = str(m["body"].get("text") or "")
            atts = m["body"].get("attachments") or []
            if atts:
                notes = []
                for a in atts:
                    name = a.get("name", "attachment")
                    txt = a.get("text_content")
                    if txt:
                        notes.append(f"[Attached file '{name}']:\n{txt[:4000]}")
                    else:
                        notes.append(f"[Attached {a.get('kind', 'file')}: {name}]")
                text = ("\n\n".join(notes) + ("\n\n" + text if text else "")).strip()
            if text:
                turns.append({"role": "user", "content": text})
        elif m["role"] == "agent":
            turns.append({"role": "assistant", "content": m["body"]["answer"]})
    return turns[-CONTEXT_TURNS:] or None


@route("GET", r"/agents/([a-z_]+)/conversations")
def agent_conversations(m, _b, h) -> Tuple[int, dict]:
    user = _user(h)
    return 200, {
        "conversations": store.list_conversations(user.id, m.group(1)),
        "usage": _usage_payload(user.id, m.group(1)),
    }


@route("GET", r"/conversations/([A-Za-z0-9_]+)")
def read_conversation(m, _b, h) -> Tuple[int, dict]:
    user = _user(h)
    c = store.get_conversation(m.group(1), user.id)
    if not c:
        return 404, {"error": "no such conversation"}
    return 200, c | {"usage": _usage_payload(user.id, c.get("agent") or "supervisor")}


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
def raw_log(_m, _b, h) -> Tuple[int, dict]:
    """Every step from every handling, newest first."""
    _user(h)
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
    def light(detail: str) -> dict:
        # The log lists; it does not need every row a tool returned. The full
        # step is at /runs/{id}/steps/{seq}.
        d = json.loads(detail)
        if isinstance(d.get("result"), list):
            d["rows"] = d.get("rows") or len(d["result"])
            d.pop("result")
        return d

    return 200, {
        "steps": [dict(r) | {"tools": json.loads(r["tools"]),
                             "detail": light(r["detail"])} for r in steps],
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
def list_runs(_m, _b, h) -> Tuple[int, dict]:
    """The board, most owed first, each handling carrying its verdict.

    The verdict is computed from the record (engine/triage.py), never asked of
    a model: a severity nobody can recompute is the kind of confident unlabelled
    claim this system exists to refuse."""
    _user(h)
    from engine import triage
    runs = triage.queue()
    return 200, {"runs": runs,
                 "board": triage.summarise([triage.Verdict(**r["verdict"]) for r in runs])}


@route("GET", r"/runs/([A-Za-z0-9_]+)")
def one_run(m, _b, h) -> Tuple[int, dict]:
    _user(h)
    d = store.get_run(m.group(1))
    if d:
        import outreach
        # An outward message shows where it goes, or went, beside the draft.
        for a in d.get("actions", []):
            delivery = outreach.state(a)
            if delivery:
                a["delivery"] = delivery
    return (200, d) if d else (404, {"error": "not found"})


@route("GET", r"/runs/([A-Za-z0-9_]+)/trace")
def run_trace(m, _b, h) -> Tuple[int, dict]:
    """One handling as a topology (event, lead, specialists, tools, sources,
    actions) beside its calls in order, each with a preview of its result."""
    _user(h)
    from agents.definitions import ALL
    from core import topology
    d = store.get_run(m.group(1))
    names = {code: (a.nickname, a.title, a.brief) for code, a in ALL.items()}
    return (200, topology.build(d, names)) if d else (404, {"error": "not found"})


@route("GET", r"/runs/([A-Za-z0-9_]+)/steps/(\d+)")
def run_step(m, _b, h) -> Tuple[int, dict]:
    """One step in full: every row of its result, not the trace's preview."""
    _user(h)
    from core import topology
    d = store.get_run(m.group(1))
    s = topology.step(d, int(m.group(2))) if d else None
    return (200, s) if s else (404, {"error": "not found"})


@route("GET", r"/runs/([A-Za-z0-9_]+)/graph")
def run_graph(m, _b, h) -> Tuple[int, dict]:
    """The exploration graph for one run: its typed nodes and edges, for the
    DAG view. Empty when SIGAP_GRAPH was off for the handling (nothing was
    mirrored), which the UI shows as 'the graph was not recorded'."""
    _user(h)
    from core import exploration as ex
    with store.connect() as c:
        return 200, ex.get_graph(c, m.group(1))


@route("POST", r"/actions/([A-Za-z0-9_]+)/outcome")
def record_outcome(m, b: dict, h) -> Tuple[int, dict]:
    """What actually happened. The half of the record that closes the loop.

    `actual_cost_idr` is taken as a number at the top level, not dug out of
    `detail`: a client that sends "24,500,000" gets a 400 rather than having a
    scale guessed for it. Structured `detail` still passes through as given.
    """
    u = _user(h)                       # a reading of reality is still attributable
    if not b.get("outcome"):
        return 400, {"error": f"'outcome' is required, one of {', '.join(store.OUTCOMES)}"}
    try:
        given = b.get("detail")
        if given is not None and not isinstance(given, dict):
            given = {"note": str(given)}       # a plain string is a note, not a shape error
        detail = (given or {}) | (
            store.outcome_detail("", b.get("actual_cost_idr"), recorded_by=u.email) or {})
        return 200, store.record_outcome(m.group(1), b["outcome"], detail or None)
    except KeyError:
        return 404, {"error": "action not found"}
    except ValueError as e:
        return 400, {"error": str(e)}


@route("POST", r"/actions/([A-Za-z0-9_]+)/decision")
def decide(m, b: dict, h) -> Tuple[int, dict]:
    u = _user(h)                       # identity from the token, not the body
    if not b.get("decision"):
        return 400, {"error": "'decision' is required"}

    action_id = m.group(1)
    d = store.get_action(action_id)
    if not d:
        return 404, {"error": "action not found"}

    import outreach
    value = int(d["payload"].get("cost_idr", 0))
    if b["decision"] == "approved" and not u.may_approve(value):
        return 403, {
            "error": f"role '{u.role}' may not approve Rp {value:,}",
            "limit_idr": u.limit_idr,
            "hint": "escalate to procurement_lead",
        }
    # A message to a customer or a supplier costs nothing and still commits
    # the company, so who may send it is its own rule, not the money limit.
    why = outreach.refusal(d["kind"], u.role) if b["decision"] == "approved" else None
    if why:
        return 403, {"error": why, "hint": f"escalate to {outreach.APPROVERS[d['kind']][0]}"}
    try:
        decided = store.decide_action(action_id, u.email, u.role,
                                      b["decision"], b.get("note", ""))
    except ValueError as e:
        return 400, {"error": str(e)}
    if decided.get("status") == "approved" and d["kind"] in outreach.KINDS:
        decided["delivery"] = outreach.queue(action_id)
        if decided["delivery"].get("queued") and SCHEDULE is not None:
            SCHEDULE.run_now("notify")
    return 200, decided


@route("POST", r"/actions/([A-Za-z0-9_]+)/resend")
def resend(m, _b, h) -> Tuple[int, dict]:
    """Send an approved outward message again after its send failed. Who may
    approve it may resend it; nothing about it changes."""
    import outreach
    u = _user(h)
    d = store.get_action(m.group(1))
    if not d or d["kind"] not in outreach.KINDS:
        return 404, {"error": "no outward message by that id"}
    why = outreach.refusal(d["kind"], u.role)
    if why:
        return 403, {"error": why}
    r = outreach.queue(d["id"], again=True)
    if r.get("queued") and SCHEDULE is not None:
        SCHEDULE.run_now("notify")
    return (200 if r.get("queued") else 409), r


# --------------------------------------------------------------------- server
class Download:
    """A route's answer that is a file, not JSON: a report as a PDF or a workbook."""

    def __init__(self, body: bytes, filename: str, media: str):
        self.body, self.filename, self.media = body, filename, media


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send_file(self, code: int, f: Download) -> None:
        from urllib.parse import quote
        ascii_name = f.filename.encode("ascii", "replace").decode().replace('"', "")
        self.send_response(code)
        self.send_header("Content-Type", f.media)
        self.send_header("Content-Length", str(len(f.body)))
        self.send_header("Content-Disposition",
                         f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(f.filename)}")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(f.body)

    def _send(self, code: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type,authorization,accept")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:          # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type,authorization,accept")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def _dispatch(self, method: str) -> None:
        parts = urlparse(self.path)
        path = parts.path.rstrip("/") or "/health"
        # A GET has no body, so its query string is its inputs and a handler
        # reads them the same way: b.get("since"). First value wins; a repeated
        # parameter is a caller mistake, not two answers.
        body: Dict[str, Any] = {k: v[0] for k, v in parse_qs(parts.query).items()}
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
                    res = fn(found, body, self.headers)
                    if hasattr(res, "__iter__") and not isinstance(res, (tuple, list, dict, str, bytes)):
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                        self.send_header("Cache-Control", "no-cache, no-transform")
                        self.send_header("X-Accel-Buffering", "no")
                        self.send_header("Connection", "close")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Access-Control-Allow-Headers", "content-type,authorization,accept")
                        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                        self.end_headers()
                        try:
                            for chunk in res:
                                self.wfile.write(chunk.encode("utf-8") if isinstance(chunk, str) else chunk)
                                self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            pass
                        finally:
                            self.close_connection = True
                        return
                    code, data = res
                except NotAuthorised as e:
                    return self._send(401, {"error": str(e)})
                except Exception as e:                               # noqa: BLE001
                    traceback.print_exc()
                    return self._send(500, {"error": f"{type(e).__name__}: {e}"})
                if isinstance(data, Download):
                    return self._send_file(code, data)
                return self._send(code, data)
        self._send(404, {"error": f"unknown route: {method} {path}"})

    def do_GET(self) -> None:              # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:             # noqa: N802
        self._dispatch("POST")

    def log_message(self, fmt: str, *a) -> None:
        print(f"  {self.command} {self.path} → {a[1] if len(a) > 1 else ''}")


#: The only two routes that may be reached without a session token. /health is
#: what a load balancer polls, and /login is where a token comes from. Every
#: other route handles one company's disruptions, costs and suppliers.
PUBLIC = {("GET", "/health"), ("POST", "/login")}

#: One sample value per group shape a pattern uses, so a route can be called
#: without naming all 48 by hand. A new shape fails the check rather than
#: quietly skipping the route that uses it.
_SAMPLES = ((r"([A-Za-z0-9_]+)", "x1"), (r"([A-Za-z]+)", "Supplier"),
            (r"([a-z_]+)", "digest"), (r"([a-z]+)", "impact"),
            (r"(\d+)", "0"), (r"(pdf|xlsx)", "pdf"))


def _sample_path(pattern) -> str:
    path = pattern.pattern.lstrip("^").rstrip("$")
    for group, value in _SAMPLES:
        path = path.replace(group, value)
    return path.replace("\\.", ".")


def demo() -> None:
    """What is checked here is the door, not the rooms.

    Every route but two handles one company's disruptions, costs and suppliers.
    A route added without `_user(h)` is an open door, and nothing else in the
    suite would notice: it would answer 200 to anyone who could reach the port.
    So each one is called with no token and has to refuse. Grepping for
    `_user(` would not do - several routes are guarded inside a shared helper -
    so they are called for real.
    """
    from core import identity

    assert len(ROUTES) >= 40, f"only {len(ROUTES)} routes registered; did an import fail?"

    # A shadowed route never runs, and the one that wins is whichever was
    # imported first - which is not a thing anyone chooses on purpose.
    seen = [(m, r.pattern) for m, r, _ in ROUTES]
    duplicates = sorted({x for x in seen if seen.count(x) > 1})
    assert not duplicates, f"two handlers for the same route: {duplicates}"

    public, guarded, unmatched = [], [], []
    for method, pattern, fn in ROUTES:
        path = _sample_path(pattern)
        found = pattern.match(path)
        if found is None:
            unmatched.append(pattern.pattern)
            continue
        key = (method, path)
        try:
            fn(found, {}, {})
        except NotAuthorised:
            guarded.append(key)
            continue
        except Exception:                                            # noqa: BLE001
            # It got past the door on its own business and then failed on a
            # made-up id. That is a route serving an anonymous caller.
            pass
        public.append(key)

    assert not unmatched, f"no sample path for: {unmatched}; add its shape to _SAMPLES"
    extra = sorted(set(public) - PUBLIC)
    assert not extra, f"reachable without a token: {extra}"
    missing = sorted(PUBLIC - set(public))
    assert not missing, f"meant to be public but refused anonymously: {missing}"
    assert len(guarded) == len(ROUTES) - len(PUBLIC)

    # Identity comes from the token and from nowhere else. A body naming
    # another user is a request, not a fact.
    identity.prepare()
    u = identity.add_user("buyer@example.com", "A Buyer", "buyer", "pw-for-the-check")
    code, out = login(None, {"email": "buyer@example.com", "password": "pw-for-the-check"}, {})
    assert code == 200 and out["token"], out
    token = out["token"]
    assert out["user"]["role"] == "buyer" and out["user"]["limit_idr"] == 500_000_000, out

    headers = {"Authorization": f"Bearer {token}"}
    code, who = me(None, {"email": "admin@example.com", "role": "admin"}, headers)
    assert code == 200 and who["email"] == u.email, who
    assert who["role"] == "buyer", "a body claiming admin must not become one"
    assert who["limit_idr"] == 500_000_000, who

    for bad in ("", "Bearer", "Bearer not-a-token", "Basic abc", f"Bearer {token}x"):
        try:
            me(None, {}, {"Authorization": bad})
            raise AssertionError(f"{bad!r} must not authenticate")
        except NotAuthorised:
            pass

    # The one route a load balancer polls says what it can see, without a token.
    code, health_out = health(None, {}, {})
    assert code == 200 and "sap_ready" in health_out and "models" in health_out

    print(f"  {len(ROUTES)} routes · {len(guarded)} refuse an anonymous caller ✓")
    print(f"  public by design: {', '.join(f'{m} {p}' for m, p in sorted(PUBLIC))} ✓")
    print("  no route shadows another ✓ · identity comes from the token, never the body ✓")
    print("api ok")


if __name__ == "__main__":
    if "--check" in sys.argv:
        # Calling 48 handlers writes and reads; never against a real database.
        from core.config import fixtures_only

        fixtures_only(__file__, "SIGAP_API_CHECK")
        demo()
        raise SystemExit(0)

    _load_model_choices()
    print(f"SIGAP API · env={CFG.env} · sap={'ready' if CFG.sap_ready else 'no'} "
          f"· model={'ready' if CFG.model_ready else 'no'}")
    # Bind before watching. The watchers write real events into the record, and
    # a second copy of the service that cannot take the port must not spend its
    # last moments raising disruptions nobody is serving.
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"listening on http://{HOST}:{PORT}")

    # Watching is what separates this from an inbox: one eye on what happened,
    # one on what has not happened yet, and the outbox that tells people. The
    # whole list, with cadences, is jobs.py. SIGAP_WATCH=0 keeps the watchers
    # off (somewhere that should not reach out to a feed); SIGAP_SCHEDULE=0
    # keeps everything off.
    import jobs
    SCHEDULE = jobs.scheduler(lambda body: raise_event(body)[0])
    SCHEDULE.start()

    server.serve_forever()
