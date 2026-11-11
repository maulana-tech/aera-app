"""AERA HTTP service.

# ponytail: stdlib http.server, fine for a small business's traffic, zero dependencies.

    python3 api.py                 # listen on :8787
    python3 api.py --check         # the self-check, on a scratch database

Every route but /health, /login and /public/* needs a session.

The business and its team
    GET  /business                 the profile in force, its version history, problems found
    POST /business                 {profile}: save a new version (owner)
    POST /business/draft           {text}: a model's draft profile from a paragraph (not saved)
    POST /business/kill-switch     {on}: stop or resume everything (owner, approver may stop)
    GET  /team                     the team on record, with capabilities and tools
    POST /team/compose             {profile?}: the team the Composer proposes, and the diff
    POST /team/apply               {profile?}: write the proposed team (owner)
    POST /team/{code}              {prompt?, capabilities?, title?, brief?, status?} (owner)
Work
    POST /work                     {kind, title, payload}: give the team something to do
    GET  /work                     recent work items
    GET  /runs · /runs/{id} · /runs/{id}/trace · /runs/{id}/steps/{seq} · /runs/{id}/proofs
    POST /actions/{id}/decision    {decision, note}: approve or reject (limit checked from the token)
    POST /actions/{id}/outcome     {outcome, detail?}
    GET  /actions?status=pending   what waits for a person
Money and proof
    GET  /orders · POST /orders/{id}/simulate-paid (owner; demo without a vault)
    GET  /treasury                 vault policy, balance, pending payments, frozen?
    GET  /ledger                   public figures (also /public/ledger)
    GET  /guardian                 the guardian's recent rulings
    GET  /attestation/{model}      a live TEE attestation report, checked with a fresh nonce
Public
    GET  /public/offerings         what the business sells
    POST /public/checkout          {offering, inputs, email?, account?}: an order to pay
    GET  /public/orders/{id}       an order's status
    GET  /public/ledger
Agents, chat and settings
    GET  /agents · POST /agents/{code}/ask · conversations · /skills · /mcp/servers · /models ·
    /contacts · /notifications · /schedule · POST /mcp · /login · /me · /files
"""
from __future__ import annotations

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

HOST, PORT = bind_target(os.environ)


def _reasoning_workers() -> int:
    try:
        return max(1, min(8, int(os.environ.get("AERA_REASONING_WORKERS", "2"))))
    except ValueError:
        return 2


REASONING_SEMAPHORE = threading.BoundedSemaphore(_reasoning_workers())


# ------------------------------------------------------------------- handling
def _handle(run_id: str, item: dict) -> None:
    """Run the team on one work item in the background. Failures are written down."""
    seq = {"n": 0}

    def report(kind: str, d: dict) -> None:
        seq["n"] += 1
        store.save_step(run_id, {
            "seq": seq["n"],
            "stage": {"specialist_start": "DELEGATE", "specialist_done": "FINDING", "tool": "TOOL",
                      "model_call": "MODEL"}.get(kind, kind.upper()),
            "agent": d.get("agent", "supervisor"),
            "agent_name": d.get("name") or d.get("agent", "-"),
            "summary": d.get("summary") or d.get("task") or d.get("name", ""),
            "tools": [d["name"]] if kind == "tool" else [],
            "origin": d.get("origin"), "source": d.get("source"),
            "detail": d, "at": store._now(),
        })

    try:
        with REASONING_SEMAPHORE:
            import graph
            with registry.bind_run(run_id):
                result = graph.run(item, report)
        store.close_run(run_id, result.get("status", "done"), result, cost_usd=result.get("cost_usd", 0))
        _hold_undelivered_order(item)
    except Exception as e:                                           # noqa: BLE001
        if llm.is_rate_limited(e):
            store.close_run(run_id, "held", decision={"status": "held", "retryable": True,
                                                      "reason": "the model provider is rate-limiting us"})
        else:
            store.close_run(run_id, "failed", error=f"{type(e).__name__}: {e}")
            traceback.print_exc()
    _tell(run_id)


def _hold_undelivered_order(item: dict) -> None:
    """A paid order whose run ended without delivering is not done, whatever the run says:
    hold it, so it shows as waiting and "Run again" is offered."""
    oid = (item.get("payload") or {}).get("order_id") if item.get("kind") == "order" else None
    order = store.get_order(oid) if oid else None
    if order and order.get("status") == "paid":
        store.set_work_status(item["id"], "held")


SCHEDULE = None


def _tell(run_id: str) -> None:
    try:
        import notify
        if notify.queue_handling(run_id) and SCHEDULE is not None:
            SCHEDULE.run_now("notify")
    except Exception:                                                # noqa: BLE001
        traceback.print_exc()


def start_work(item: dict) -> str:
    """Open a run for a work item and set the team on it. Returns the run id."""
    from agents import roster
    from core import business
    rid = store.start_run(item["id"], roster.versions(), business.current().get("_version"))
    if CFG.model_ready:
        threading.Thread(target=_handle, args=(rid, item), daemon=True).start()
    else:
        lead = llm.spec_for_code("supervisor")
        store.close_run(rid, "held", decision={
            "status": "held",
            "reason": f"The supervisor's model {lead} cannot be called ({llm.ready(lead)[1]}). "
                      "The team cannot reason; nothing was decided."})
        _tell(rid)
    return rid


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
    from core import chain
    return 200, {
        "env": CFG.env,
        "model_ready": CFG.model_ready,
        "model": str(llm.spec_for_code("supervisor")),
        "private_mode": llm.private_mode(),
        "aux_model": str(llm.aux_spec()),
        "vault": chain.vault_id() or None,
        "network": chain.network(),
        "rail": "vault" if chain.configured() else "simulated",
    }


# ------------------------------------------------------------------- skills
@route("GET", r"/skills")
def list_skills(_m, b, h) -> Tuple[int, dict]:
    """The catalogue, with how often each has been run and by whom.

    `not_found` is the figure worth reading: a model reaching for a skill
    nobody wrote is a gap in the catalogue, and it is only visible because
    those calls are recorded rather than dropped.
    """
    from agents import roster
    ALL = roster.load()
    from core import skills
    _user(h)
    # A GET's query string arrives as its body (see the dispatcher), so the
    # window is read the same way every other GET reads its inputs.
    try:
        days = max(1, min(365, int((b or {}).get("days") or 30)))
    except (TypeError, ValueError):
        days = 30
    return 200, {"skills": skills.listing(store.skill_usage(days)), "days": days,
                 "agents": [{"code": c, "nickname": a.nickname} for c, a in ALL.items()],
                 "tools": sorted(registry.all_tools()),
                 "may_change": _user(h).role in SETTINGS_ROLES}


@route("POST", r"/skills")
def add_skill(_m, b: dict, h) -> Tuple[int, dict]:
    """{"name","title","description"?,"agents"?,"tools"?,"steps"}.

    Validated before it is saved, with the same checks core/skills.py runs
    over the built-in catalogue. A skill that names a tool nobody wrote, or
    that restricts itself to an agent who cannot reach its own tools, is
    refused here rather than discovered in the middle of a handling.
    """
    from core import skills
    user = _user(h)
    if user.role not in SETTINGS_ROLES:
        return 403, {"error": f"role '{user.role}' may not write a skill"}
    name = str(b.get("name") or "").strip().lower()
    title = str(b.get("title") or "").strip()
    agents = [str(a) for a in (b.get("agents") or [])]
    tools = [str(t) for t in (b.get("tools") or [])]
    steps = [str(x).strip() for x in (b.get("steps") or []) if str(x).strip()]
    wrong = skills.validate(name, title, agents, tools, steps)
    if wrong:
        return 400, {"error": "; ".join(wrong), "problems": wrong}
    store.add_stored_skill(name, title, str(b.get("description") or "").strip(),
                           agents, tools, steps, user.email)
    return 200, {"skills": skills.listing(store.skill_usage(30))}


@route("POST", r"/skills/([a-z0-9_]+)/delete")
def remove_skill(m, _b, h) -> Tuple[int, dict]:
    """Only a written one. The catalogue is code and is not deleted here."""
    from core import skills
    user = _user(h)
    if user.role not in SETTINGS_ROLES:
        return 403, {"error": f"role '{user.role}' may not remove a skill"}
    name = m.group(1)
    if name in skills.BUILTIN:
        return 400, {"error": f"'{name}' is built in; it lives in core/skills.py"}
    if not store.delete_stored_skill(name):
        return 404, {"error": f"no skill called '{name}'"}
    return 200, {"skills": skills.listing(store.skill_usage(30))}


# -------------------------------------------------------------- MCP servers
def _mcp_row(r: dict) -> dict:
    """One server as a browser may see it. Never the token.

    `offered` is how many of its tools an agent can actually call, which is
    not len(tools): a writer, a tool with no usable schema, and a tool whose
    name is already one of ours are all dropped by the registry. A page that
    showed only the probed count would promise more than the system does.
    """
    offered = sum(1 for t in registry.remote_tools().values()
                  if t["server"] == r.get("name"))
    return {k: v for k, v in r.items() if k != "token"} | {"offered": offered}


@route("GET", r"/mcp/servers")
def list_mcp_servers(_m, _b, h) -> Tuple[int, dict]:
    """Servers AERA may call OUT to, plus what AERA itself serves.

    Both directions on one page on purpose: the question an operator actually
    has is "what tools exist here and who can reach them", and splitting that
    across two screens is how a tool nobody audited ends up installed.
    """
    from core import registry
    import mcp
    user = _user(h)
    tools = registry.all_tools().values()
    return 200, {
        "ours": {
            "endpoint": "/mcp",
            "protocol": mcp.PROTOCOL_VERSION,
            "tools_total": len(tools),
            "tools_writing": sum(1 for t in tools if t.writes),
            "resources": [r["uri"] for r in mcp.RESOURCES],
            "prompts": [p["name"] for p in mcp._prompt_list()],
        },
        "servers": [_mcp_row(r) for r in store.mcp_servers()],
        "may_change": user.role in SETTINGS_ROLES,
    }


@route("POST", r"/mcp/servers")
def add_mcp_server(_m, b: dict, h) -> Tuple[int, dict]:
    """{"name","url","token"?,"agents"?}. Probed before it is saved."""
    from clients import mcp_client
    user = _user(h)
    if user.role not in SETTINGS_ROLES:
        return 403, {"error": f"role '{user.role}' may not add an MCP server"}
    name = str(b.get("name") or "").strip()
    url = str(b.get("url") or "").strip()
    if not name or not url:
        return 400, {"error": "name and url are both required"}
    if not url.startswith(("http://", "https://")):
        return 400, {"error": "url must start with http:// or https://"}
    if any(r["name"] == name for r in store.mcp_servers()):
        return 409, {"error": f"a server called '{name}' is already here"}
    token = str(b.get("token") or "").strip() or None
    agents = b.get("agents") or []
    if not isinstance(agents, list):
        return 400, {"error": "agents must be a list of agent codes"}

    # Probed BEFORE it is saved. A server nobody could reach, sitting enabled
    # in the list, is a tool an agent will try and a handling will wait on.
    ok, note, tools = mcp_client.probe(url, token)
    if not ok:
        return 400, {"error": f"could not reach it: {note}"}
    row = store.add_mcp_server(name, url, token, user.email, agents)
    store.update_mcp_server(row["id"], tools=tools, last_ok=store._now(), last_error=None)
    registry.forget_remote()
    return 200, {"added": row["id"], "note": note,
                 "servers": [_mcp_row(r) for r in store.mcp_servers()]}


@route("POST", r"/mcp/servers/([A-Za-z0-9_]+)")
def change_mcp_server(m, b: dict, h) -> Tuple[int, dict]:
    """{"enabled"?,"agents"?,"token"?,"url"?}. Absent fields are left alone."""
    user = _user(h)
    if user.role not in SETTINGS_ROLES:
        return 403, {"error": f"role '{user.role}' may not change an MCP server"}
    sid = m.group(1)
    if not any(r["id"] == sid for r in store.mcp_servers()):
        return 404, {"error": f"no MCP server {sid}"}
    fields = {k: b[k] for k in ("enabled", "agents", "token", "url") if k in b}
    if not fields:
        return 400, {"error": "nothing to change"}
    store.update_mcp_server(sid, **fields)
    registry.forget_remote()
    return 200, {"servers": [_mcp_row(r) for r in store.mcp_servers()]}


@route("POST", r"/mcp/servers/([A-Za-z0-9_]+)/test")
def test_mcp_server(m, _b, h) -> Tuple[int, dict]:
    """Call it now and record what came back, so the list stops guessing."""
    from clients import mcp_client
    user = _user(h)
    if user.role not in SETTINGS_ROLES:
        return 403, {"error": f"role '{user.role}' may not test an MCP server"}
    sid = m.group(1)
    row = next((r for r in store.mcp_servers(include_token=True) if r["id"] == sid), None)
    if row is None:
        return 404, {"error": f"no MCP server {sid}"}
    ok, note, tools = mcp_client.probe(row["url"], row.get("token"))
    registry.forget_remote()
    store.update_mcp_server(sid, tools=tools if ok else row["tools"],
                            last_ok=store._now() if ok else row.get("last_ok"),
                            last_error=None if ok else note)
    return 200, {"ok": ok, "note": note, "tools": tools}


@route("POST", r"/mcp/servers/([A-Za-z0-9_]+)/delete")
def remove_mcp_server(m, _b, h) -> Tuple[int, dict]:
    user = _user(h)
    if user.role not in SETTINGS_ROLES:
        return 403, {"error": f"role '{user.role}' may not remove an MCP server"}
    registry.forget_remote()
    if not store.delete_mcp_server(m.group(1)):
        return 404, {"error": f"no MCP server {m.group(1)}"}
    return 200, {"servers": [_mcp_row(r) for r in store.mcp_servers()]}


# ---------------------------------------------------------------------- models
#: Who may change how the team runs: its models, its schedule, its alerts. A
#: model change moves spend and the quality of every recommendation after it,
#: and switching a watcher off is choosing not to hear about a typhoon, so these
#: sit with the roles that already carry the largest approval limits.
SETTINGS_ROLES = ("admin", "owner")
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
    from agents import roster
    ALL = roster.load()
    s = str(llm.parse(raw))
    env = set()
    for var in ("AERA_MODEL", "AERA_MODEL_SPECIALISTS", "AERA_MODEL_FALLBACK", "AERA_AUX_MODEL",
                *(f"AERA_MODEL_{c.upper()}" for c in ALL)):
        v = os.environ.get(var, "").strip()
        if v and v != llm.NO_FALLBACK:
            env.add(str(llm.parse(v)))
    return bool(llm.listed(s)) or s in env


def _models_payload(user: User) -> dict:
    from agents import roster
    ALL = roster.load()
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

    env = {"lead": norm(CFG.model), "specialists": norm(os.environ.get("AERA_MODEL_SPECIALISTS", "")),
           "fallback": norm(os.environ.get("AERA_MODEL_FALLBACK", "")), "aux": norm(CFG.aux_model)}
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
    from agents import roster
    ALL = roster.load()
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
    for field in ("name", "role"):
        if not b.get(field):
            return 400, {"error": f"'{field}' is required"}
    if b["role"] in ("team", "approver") and not b.get("email"):
        return 400, {"error": "a team contact needs an email"}
    bad = _contact_fields(b)
    if bad:
        return 400, {"error": bad}
    extra = [k for k in store.CONTACT_FIELDS if k not in ("name", "role", "email", "notify_for")]
    return 201, store.add_contact(b["name"].strip(), b["role"], str(b.get("email") or "").strip(),
                                  b.get("notify_for", "*" if b["role"] in ("team", "approver") else ""),
                                  **{k: str(b.get(k) or "").strip()[:1000] for k in extra})


def _contact_fields(b: dict) -> Optional[str]:
    """What is wrong with a contact as given, or None."""
    from core import chain
    if b.get("role") is not None and b["role"] not in ("customer", "vendor", "contributor", "team", "approver"):
        return "role is one of customer, vendor, contributor, team, approver"
    acct = str(b.get("near_account") or "").strip()
    if acct and not chain.valid_account(acct.lower()):
        return f"'{acct}' is not a valid NEAR account id"
    if b.get("email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",
                                                       str(b["email"]).strip()):
        return f"'{b['email']}' is not an email address"
    phone = str(b.get("phone") or "").strip()
    if phone and not re.fullmatch(r"\+?[0-9][0-9 ()\-.]{5,24}", phone):
        return f"'{phone}' is not a phone number: digits, spaces, dashes, a leading +"
    return None


@route("GET", r"/contacts/([A-Za-z0-9_]+)")
def one_contact(m, _b, h) -> Tuple[int, dict]:
    """One contact, and what AERA has sent them."""
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
    fields = {k: str(b[k]).strip()[:1000] for k in store.CONTACT_FIELDS if k in b and b[k] is not None}
    if "near_account" in fields:
        fields["near_account"] = fields["near_account"].lower()
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
    """A Composio sign-in page for the Gmail mailbox AERA will send from.
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




def _remote_label(tool_name: str) -> Optional[Tuple[str, str]]:
    """(what it is, badge) for a tool on a server AERA does not operate.

    The activity feed is where a person sees what the agents did. A borrowed
    tool has to look borrowed there, or the feed quietly claims more than the
    system actually knows.
    """
    if not tool_name.startswith(registry.REMOTE_PREFIX):
        return None
    server, sep, bare = tool_name[len(registry.REMOTE_PREFIX):].partition("__")
    if not sep or not bare:
        return None
    return f"{bare.replace('_', ' ').strip()} on {server} (outside AERA)", "External"


_TOOL_BADGES = {
    "search_news": "News", "read_web_page": "Web", "get_exchange_rate": "FX", "get_public_holidays": "Calendar",
    "use_skill": "Procedure", "get_business_profile": "Profile", "write_document": "Document",
    "read_document": "Document", "read_business_file": "Files", "list_business_files": "Files",
    "find_contact": "Contacts", "save_contact": "Contacts", "search_past_work": "Memory",
    "list_orders": "Orders", "get_order": "Orders", "deliver_order": "Delivery", "draft_message": "Message",
    "check_action": "Guardian", "check_counterparty": "Guardian", "freeze_payments": "Kill switch",
    "treasury_status": "Treasury", "pay_vendor": "Payment", "propose_refund": "Refund",
    "ledger_summary": "Ledger", "get_work_item": "Work item",
}


def _nicknames() -> Dict[str, str]:
    try:
        from agents import roster
        return {c: a.nickname for c, a in roster.load().items()}
    except Exception:                                               # noqa: BLE001
        return {}


class _Nick(dict):
    def get(self, k, default=None):
        return _nicknames().get(k, default)


_AGENT_NICKNAMES = _Nick()
_TOOL_LABELS: Dict[str, str] = {}


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
            "agent_name": "Supervisor",
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
        borrowed = _remote_label(tool_name)
        tool_desc = (borrowed[0] if borrowed
                     else _TOOL_LABELS.get(tool_name, tool_name.replace("_", " ")))
        args = d.get("arguments", {})
        arg_summary = " · ".join(f"{k}: {v}" for k, v in list(args.items())[:2])
        badge = borrowed[1] if borrowed else _TOOL_BADGES.get(tool_name, "Data Check")
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
            "target_name": "Supervisor",
            "narrative": narrative,
            "badge": "Finding ›",
            "detail": f"{summary[:110]}…" if len(summary) > 110 else summary,
            "full_detail": full_summary,
            "thinking": thinking,
            "at": now,
        }
    if kind == "model_call":
        agent_code = d.get("agent", "")
        return {"seq": seq, "kind": "model_call", "agent": agent_code,
                "agent_name": d.get("name") or _AGENT_NICKNAMES.get(agent_code, agent_code),
                "narrative": d.get("summary", ""), "badge": "TEE ›" if d.get("attested") else "Model ›",
                "detail": d.get("summary", ""), "full_detail": str(d), "attested": d.get("attested"),
                "proof_id": d.get("proof_id"), "chat_id": d.get("chat_id"), "at": now}
    if kind == "summary":
        full_summary = str(d.get("full_summary") or "").strip()
        return {
            "seq": seq,
            "kind": "summary",
            "agent": "supervisor",
            "agent_name": "Supervisor",
            "narrative": "Writing the outcome",
            "badge": "Summary ›",
            "detail": "The supervisor's outcome",
            "full_detail": full_summary or "The supervisor's outcome.",
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

    from agents import roster
    ALL = roster.load()
    if code not in ALL:
        return 404, {"error": f"unknown agent '{code}'"}

    spec = llm.spec_for(ALL[code])
    if not llm.usable(spec):
        return 503, {
            "error": f"{ALL[code].nickname}'s model {spec} cannot be called: "
                     f"{llm.ready(spec)[1]}. The agent cannot reason.",
            "hint": "Set NEARAI_API_KEY (aera/ENV.md, Models) and restart the service.",
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
        "summarise what it shows, and what it means for the business."
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
                "agent_name": "Supervisor",
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
    from agents import roster
    ALL = roster.load()
    spec = llm.spec_for(ALL.get(code) or ALL["supervisor"])
    usd_in, usd_out = llm.usd_per_mtok(spec)
    return {
        **store.conversation_usage_summary(user_id),
        "cost_cap_usd": CFG.cost_cap_per_run_usd,
        "max_output_tokens": 8000,
        "context_turns": CONTEXT_TURNS,
        "max_rounds": graph.MAX_SPECIALIST_ROUNDS,
        "input_usd_per_million": usd_in,
        "output_usd_per_million": usd_out,
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
    """The tool registry over MCP, for AgentCore Gateway and other MCP clients.

    Authenticated like every other route: the client's connection is where the
    credential lives, so this staying closed is the correct default rather
    than an obstacle.
    """
    _user(h)
    import mcp
    reply = mcp.handle(b or {})
    return (204, {}) if not reply else (200, reply)




@route("POST", r"/login")
def login(_m, b: dict, _h) -> Tuple[int, dict]:
    try:
        u = identity.log_in(b.get("email", ""), b.get("password", ""))
    except NotAuthorised as e:
        return 401, {"error": str(e)}
    return 200, {"token": identity.issue_token(u),
                 "user": {"name": u.name, "email": u.email,
                          "role": u.role, "limit_usd": u.limit_usd}}


@route("GET", r"/setup")
def setup_status(_m, _b, _h) -> Tuple[int, dict]:
    """Public: whether this install still needs its first owner."""
    return 200, {"needs_owner": identity.user_count() == 0}


@route("POST", r"/setup")
def first_owner(_m, b: dict, _h) -> Tuple[int, dict]:
    """Create the FIRST account, as owner. Only while no account exists:
    after that, accounts are added by an owner (POST /users)."""
    if identity.user_count() > 0:
        return 409, {"error": "this install already has accounts; sign in"}
    email, name, pw = (str(b.get(k) or "").strip() for k in ("email", "name", "password"))
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or not name:
        return 400, {"error": "a name and a valid email are required"}
    if len(pw) < 10:
        return 400, {"error": "the password needs at least 10 characters"}
    u = identity.add_user(email, name, "owner", pw)
    return 201, {"token": identity.issue_token(u),
                 "user": {"name": u.name, "email": u.email, "role": u.role, "limit_usd": u.limit_usd}}


@route("GET", r"/users")
def users(_m, _b, h) -> Tuple[int, dict]:
    u = _user(h)
    return 200, {"users": identity.list_users(), "roles": identity.ROLE_LIMITS, "may_change": u.may_manage}


@route("POST", r"/users")
def add_user_route(_m, b: dict, h) -> Tuple[int, dict]:
    u = _user(h)
    if not u.may_manage:
        return 403, {"error": "only an owner adds accounts"}
    email, name, role, pw = (str(b.get(k) or "").strip() for k in ("email", "name", "role", "password"))
    if role not in identity.ROLE_LIMITS:
        return 400, {"error": "role is one of " + ", ".join(identity.ROLE_LIMITS)}
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or not name or len(pw) < 10:
        return 400, {"error": "name, a valid email and a password of 10+ characters are required"}
    try:
        n = identity.add_user(email, name, role, pw)
    except Exception as e:                                           # noqa: BLE001
        return 409, {"error": f"could not add: {e}"}
    return 201, {"user": {"id": n.id, "email": n.email, "name": n.name, "role": n.role, "limit_usd": n.limit_usd}}


@route("POST", r"/users/([A-Za-z0-9_]+)/delete")
def remove_user(m, _b, h) -> Tuple[int, dict]:
    u = _user(h)
    if not u.may_manage:
        return 403, {"error": "only an owner removes accounts"}
    if m.group(1) == u.id:
        return 400, {"error": "you cannot remove yourself"}
    return (200, {"removed": True}) if identity.deactivate_user(m.group(1)) else (404, {"error": "no such account"})


@route("GET", r"/me")
def me(_m, _b, h) -> Tuple[int, dict]:
    u = _user(h)
    return 200, {"name": u.name, "email": u.email, "role": u.role,
                 "limit_usd": u.limit_usd}




# ------------------------------------------------------------- the business


def _manager(h) -> User:
    u = _user(h)
    if not u.may_manage:
        raise _Refused(f"a {u.role} cannot change the business or its team (needs owner or admin)")
    return u


def _refusable(fn: Callable) -> Callable:
    def wrapped(m, b, h):
        try:
            return fn(m, b, h)
        except _Refused as e:
            return 403, {"error": str(e)}
    wrapped.__name__ = fn.__name__
    return wrapped


@route("GET", r"/business")
def get_business(_m, _b, h) -> Tuple[int, dict]:
    from core import business
    u = _user(h)
    stored = store.active_profile()
    p, problems = business.normalise(stored) if stored else (business.current(), ["not described yet"])
    return 200, {"profile": {k: v for k, v in p.items() if not k.startswith("_")},
                 "version": (stored or {}).get("_version"), "problems": problems,
                 "history": store.profile_history(), "context": business.context_block(p),
                 "may_change": u.may_manage, "example": business.EXAMPLE}


@route("POST", r"/business")
@_refusable
def save_business(_m, b: dict, h) -> Tuple[int, dict]:
    from core import business, team
    u = _manager(h)
    raw = b.get("profile")
    if not isinstance(raw, dict):
        return 400, {"error": "send {profile: {...}}"}
    p, problems = business.normalise(raw)
    if not p["name"]:
        return 400, {"error": "the business needs a name", "problems": problems}
    v = store.save_profile(p, by=u.email, note=str(b.get("note") or "")[:300])
    proposal = team.compose(p)
    diff = team.diff(proposal)
    # The first time a business is described, its team is composed with it.
    # After that a profile edit only PROPOSES a team change; a person applies it.
    first = not any(not a["core"] for a in store.list_agents(include_inactive=True))
    if first or b.get("apply_team"):
        team.apply(proposal, by=u.email)
    return 200, {"version": v, "problems": problems, "team_diff": diff, "team_applied": bool(first or b.get("apply_team"))}


@route("POST", r"/business/draft")
def draft_business(_m, b: dict, h) -> Tuple[int, dict]:
    from core import business, team
    _user(h)
    text = str(b.get("text") or "").strip()
    if len(text) < 20:
        return 400, {"error": "describe the business in a sentence or two"}
    p, problems = business.draft_from_text(text)
    if p is None:
        return 503, {"error": problems[0] if problems else "no draft"}
    return 200, {"profile": p, "problems": problems, "team": team.compose(p)}


@route("POST", r"/business/kill-switch")
def kill_switch(_m, b: dict, h) -> Tuple[int, dict]:
    """Anyone who can approve may STOP; only an owner may resume."""
    from core import business, chain
    u = _user(h)
    on = bool(b.get("on"))
    if on and u.role not in ("approver", "owner", "admin"):
        return 403, {"error": f"a {u.role} cannot pull the kill switch (approver or owner)"}
    if not on and not u.may_manage:
        return 403, {"error": "only an owner can resume the business"}
    p = business.current()
    if not p.get("name"):
        return 400, {"error": "no business to stop"}
    p["kill_switch"] = on
    store.save_profile(p, by=u.email, note=("stopped" if on else "resumed") + f" by {u.email}")
    onchain = None
    if on and chain.configured():
        try:
            onchain = chain.freeze()
        except Exception as e:                                       # noqa: BLE001
            onchain = {"error": f"{type(e).__name__}: {e}"}
    return 200, {"kill_switch": on, "vault": onchain,
                 "note": None if on or not chain.readable() else "unfreeze the vault from the owner's wallet"}


# ------------------------------------------------------------------- the team
def _agent_row(a: dict) -> dict:
    from agents import roles
    caps = roles.allowed_capabilities(a["code"], a.get("capabilities") or [])
    return {**a, "capabilities": caps,
            "tools": {c: registry.tools_of(c) for c in caps},
            "model": str(llm.spec_for_code(a["code"], a.get("veto", False)))}


@route("GET", r"/team")
def get_team(_m, _b, h) -> Tuple[int, dict]:
    from agents import roles
    from core import team
    u = _user(h)
    team.ensure_team(by=u.email)
    return 200, {"agents": [_agent_row(a) for a in store.list_agents(include_inactive=True)],
                 "capabilities": [{"name": n, "description": d, "locked_to": roles.LOCKED.get(n),
                                   "tools": registry.tools_of(n)} for n, d in roles.CAPABILITIES.items()],
                 "library": [{"key": k, **{x: r[x] for x in ("nickname", "title", "brief", "capabilities")}}
                             for k, r in roles.ROLES.items()],
                 "may_change": u.may_manage}


@route("POST", r"/team/compose")
def compose_team(_m, b: dict, h) -> Tuple[int, dict]:
    from core import business, team
    _user(h)
    p = business.normalise(b["profile"])[0] if isinstance(b.get("profile"), dict) else business.current()
    proposal = team.compose(p)
    return 200, {"team": proposal, "diff": team.diff(proposal)}


@route("POST", r"/team/apply")
@_refusable
def apply_team(_m, b: dict, h) -> Tuple[int, dict]:
    from core import business, team
    u = _manager(h)
    p = business.normalise(b["profile"])[0] if isinstance(b.get("profile"), dict) else business.current()
    team.apply(team.compose(p), by=u.email, keep_edits=not b.get("reset"))
    return 200, {"agents": [_agent_row(a) for a in store.list_agents(include_inactive=True)]}


@route("POST", r"/team/new")
@_refusable
def new_agent(_m, b: dict, h) -> Tuple[int, dict]:
    from core import team
    u = _manager(h)
    a = team._custom({"title": b.get("title"), "brief": b.get("brief"),
                      "capabilities": b.get("capabilities") or []},
                     {x["code"] for x in store.list_agents(include_inactive=True)})
    if not a:
        return 400, {"error": "give the role a new, unique title"}
    a["status"], a["origin"] = "active", "person"
    return 201, {"agent": _agent_row(store.upsert_agent(a, by=u.email))}


@route("POST", r"/team/([a-z0-9_]+)")
@_refusable
def edit_agent(m, b: dict, h) -> Tuple[int, dict]:
    from agents import roles
    u = _manager(h)
    a = store.get_agent(m.group(1))
    if not a:
        return 404, {"error": f"no agent {m.group(1)}"}
    if "status" in b:
        try:
            store.set_agent_status(a["code"], str(b["status"]), by=u.email)
        except ValueError as e:
            return 400, {"error": str(e)}
        a = store.get_agent(a["code"])
    changes = {k: b[k] for k in ("prompt", "title", "brief", "nickname", "effort") if isinstance(b.get(k), str)}
    if isinstance(b.get("capabilities"), list):
        changes["capabilities"] = roles.allowed_capabilities(a["code"], [str(x) for x in b["capabilities"]])
    if changes:
        a = store.upsert_agent({**a, **changes, "origin": "person"}, by=u.email)
    return 200, {"agent": _agent_row(a)}


@route("GET", r"/agents")
def list_agents(_m, _b, h) -> Tuple[int, dict]:
    from agents import roster
    _user(h)
    out = []
    counts: Dict[str, int] = {}
    with store.connect() as c:
        for r in c.execute("SELECT agent, count(DISTINCT run_id) n FROM steps GROUP BY agent").fetchall():
            counts[r["agent"]] = r["n"]
    for code, a in roster.load().items():
        tools_ = [{"name": t.name, "installed": True, "description": t.description}
                  for t in registry.owned_by(a.capabilities)]
        out.append({"code": code, "nickname": a.nickname, "title": a.title, "brief": a.brief,
                    "effort": a.effort, "veto": a.veto, "core": a.core, "lead": code == "supervisor",
                    "capabilities": a.capabilities, "ready": True, "tools": tools_,
                    "installed": len(tools_), "tool_count": len(tools_), "runs": counts.get(code, 0),
                    "model": str(llm.spec_for(a)), "version": a.version})
    return 200, {"agents": out}


# ----------------------------------------------------------------------- work
@route("POST", r"/work")
def new_work(_m, b: dict, h) -> Tuple[int, dict]:
    u = _user(h)
    kind = str(b.get("kind") or "request")
    if kind not in ("request", "goal", "payable", "order"):
        return 400, {"error": "kind is one of request, goal, payable, order"}
    title = str(b.get("title") or "").strip()
    if not title:
        return 400, {"error": "a title is required"}
    payload = b.get("payload") if isinstance(b.get("payload"), dict) else {"text": str(b.get("text") or "")}
    wid = store.record_work_item(kind, title[:200], "api", {**payload, "raised_by": u.email})
    item = store.get_work_item(wid)
    store.set_work_status(wid, "running")
    rid = start_work(item)
    return 201, {"work_item": wid, "run": rid}


@route("POST", r"/work/([A-Za-z0-9_]+)/retry")
def retry_work(m, _b, h) -> Tuple[int, dict]:
    """Run a held or failed work item again (e.g. after the model key was added)."""
    _user(h)
    item = store.get_work_item(m.group(1))
    if not item:
        return 404, {"error": "no such work item"}
    if item["status"] not in ("held", "failed"):
        return 409, {"error": f"the work item is {item['status']}; only held or failed work is retried"}
    if not CFG.model_ready:
        return 503, {"error": f"the supervisor's model cannot be called: {llm.ready(llm.spec_for_code('supervisor'))[1]}"}
    return 201, {"work_item": item["id"], "run": start_work(item)}


@route("GET", r"/work")
def list_work(_m, b: dict, h) -> Tuple[int, dict]:
    _user(h)
    return 200, {"items": store.list_work_items(limit=100, status=b.get("status") or None)}


@route("GET", r"/runs")
def list_runs(_m, _b, h) -> Tuple[int, dict]:
    _user(h)
    return 200, {"runs": store.list_runs(100)}


@route("GET", r"/runs/([A-Za-z0-9_]+)")
def one_run(m, _b, h) -> Tuple[int, dict]:
    _user(h)
    r = store.get_run(m.group(1))
    return (200, r) if r else (404, {"error": "no such run"})


@route("GET", r"/runs/([A-Za-z0-9_]+)/trace")
def run_trace(m, _b, h) -> Tuple[int, dict]:
    from core import topology
    _user(h)
    r = store.get_run(m.group(1))
    return (200, topology.build(r)) if r else (404, {"error": "no such run"})


@route("GET", r"/runs/([A-Za-z0-9_]+)/steps/(\d+)")
def run_step(m, _b, h) -> Tuple[int, dict]:
    _user(h)
    r = store.get_run(m.group(1))
    s = next((x for x in (r or {}).get("steps", []) if x["seq"] == int(m.group(2))), None)
    return (200, s) if s else (404, {"error": "no such step"})


@route("GET", r"/runs/([A-Za-z0-9_]+)/proofs")
def run_proofs(m, _b, h) -> Tuple[int, dict]:
    _user(h)
    proofs = store.proofs_for_run(m.group(1))
    return 200, {"proofs": proofs, "attested": sum(1 for p in proofs if p["verdict"] == "attested"),
                 "total": len(proofs)}


@route("GET", r"/log")
def raw_log(_m, _b, h) -> Tuple[int, dict]:
    _user(h)
    with store.connect() as c:
        steps = c.execute("SELECT s.*, w.title, w.kind AS work_kind FROM steps s JOIN runs r ON r.id = s.run_id"
                          " JOIN work_items w ON w.id = r.work_item_id ORDER BY s.id DESC LIMIT 300").fetchall()
    out = []
    for r in steps:
        d = json.loads(r["detail"])
        if isinstance(d.get("result"), list):
            d["rows"] = d.get("rows") or len(d["result"])
            d.pop("result")
        out.append(dict(r) | {"tools": json.loads(r["tools"]), "detail": d})
    return 200, {"steps": out, "actions": store.list_actions(limit=100)}


# -------------------------------------------------------------------- actions
@route("GET", r"/actions")
def list_actions(_m, b: dict, h) -> Tuple[int, dict]:
    _user(h)
    return 200, {"actions": store.list_actions(status=b.get("status") or None, kind=b.get("kind") or None)}


@route("POST", r"/actions/([A-Za-z0-9_]+)/decision")
def decide(m, b: dict, h) -> Tuple[int, dict]:
    u = _user(h)
    a = store.get_action(m.group(1))
    if not a:
        return 404, {"error": "no such action"}
    decision = str(b.get("decision") or "")
    if decision not in ("approved", "rejected", "escalated"):
        return 400, {"error": "decision is approved, rejected or escalated"}
    if u.limit_usd <= 0:
        return 403, {"error": f"a {u.role} cannot decide on actions"}
    if a["status"] == "blocked":
        return 409, {"error": "the guardian blocked this action; a block is final and cannot be approved"}
    if decision == "approved" and not u.may_approve(a["value_usd"]):
        art = "an" if u.role[:1] in "aeiou" else "a"
        return 403, {"error": f"{art} {u.role} may approve up to ${u.limit_usd:,.2f}; this is ${a['value_usd']:,.2f}"}
    from core import business
    if decision == "approved" and business.current().get("kill_switch"):
        return 409, {"error": "the kill switch is on; resume the business before approving anything"}
    d = store.decide_action(a["id"], u.email, u.role, decision, str(b.get("note") or "")[:500])
    out: Dict[str, Any] = {"action": d}
    if d.get("status") == "approved" and not d.get("unchanged"):
        import settle
        out["executed"] = settle.execute(a["id"])
        out["action"] = store.get_action(a["id"])
    return 200, out


@route("POST", r"/actions/([A-Za-z0-9_]+)/outcome")
def record_outcome(m, b: dict, h) -> Tuple[int, dict]:
    _user(h)
    try:
        a = store.record_outcome(m.group(1), str(b.get("outcome") or "")[:40] or "noted",
                                 {"detail": str(b.get("detail") or "")[:2000]})
    except KeyError:
        return 404, {"error": "no such action"}
    return 200, {"action": a}


# ------------------------------------------------------------- money & proof
@route("GET", r"/orders")
def list_orders(_m, b: dict, h) -> Tuple[int, dict]:
    _user(h)
    return 200, {"orders": store.list_orders(status=b.get("status") or None)}


@route("POST", r"/orders/([A-Za-z0-9_\-]+)/simulate-paid")
@_refusable
def simulate_paid(m, _b, h) -> Tuple[int, dict]:
    """Mark an order paid WITHOUT a chain, for a demo with no vault. Labelled
    `simulated` in the ledger and on the order, everywhere it is shown."""
    import settle
    from core import chain
    _manager(h)
    if chain.configured():
        return 409, {"error": "a vault is configured: pay it for real (ft_transfer_call)"}
    o = store.get_order(m.group(1))
    if not o:
        return 404, {"error": "no such order"}
    w = settle.order_paid(o["id"], payer=o.get("customer"), amount_usd=o["amount_usd"], offering=o["offering"],
                          tx=None, rail="simulated")
    return 200, {"order": store.get_order(o["id"]), "work_items": w}


@route("GET", r"/treasury")
def treasury(_m, _b, h) -> Tuple[int, dict]:
    from core import business, chain
    _user(h)
    p = business.current()
    out: Dict[str, Any] = {
        "network": chain.network(), "vault": chain.vault_id() or None, "agent": chain.agent_id() or None,
        "token": chain.token_id(), "rail": "vault" if chain.configured() else "simulated",
        "caps": business.spend_caps(p), "paid_today_usd": round(store.spent_today_usd(), 2),
        "kill_switch": p.get("kill_switch"),
        "pending_actions": store.list_actions(status="pending"),
        "pending_onchain": store.list_payments(status="pending_onchain"),
        "approved_refunds": store.list_actions(status="approved", kind="refund"),
        "payments": store.list_payments(limit=50),
    }
    if chain.readable():
        out["policy"] = chain.policy()
        out["balance_usd"] = chain.vault_balance()
        pol = out["policy"] or {}
        if pol:
            caps = out["caps"]
            onchain = {"per_payment": chain.from_base(pol.get("per_tx_cap", 0)),
                       "per_day": chain.from_base(pol.get("daily_cap", 0))}
            drift = any(abs(onchain[k] - caps[k]) >= 0.01 for k in ("per_payment", "per_day"))
            # The profile and the vault must agree. When they do not, the owner signs
            # set_policy with these exact arguments from their wallet.
            out["policy_drift"] = {"drift": drift, "vault": onchain, "profile": caps,
                                   "set_policy": {"per_tx_cap": chain.to_base(caps["per_payment"]),
                                                  "daily_cap": chain.to_base(caps["per_day"])}}
        out["explorer"] = (("https://testnet.nearblocks.io" if chain.network() == "testnet"
                            else "https://nearblocks.io") + f"/address/{chain.vault_id()}")
    return 200, out


@route("POST", r"/treasury/sync")
def treasury_sync(_m, _b, h) -> Tuple[int, dict]:
    """Run settlement now: after an approver signed in their wallet, the record
    catches up without waiting for the next pass."""
    import settle
    _user(h)
    return 200, {"done": settle.run_once()}


@route("GET", r"/ledger")
def ledger(_m, b: dict, h) -> Tuple[int, dict]:
    _user(h)
    return 200, store.ledger(int(b.get("days") or 30))


@route("GET", r"/guardian")
def guardian_log(_m, b: dict, h) -> Tuple[int, dict]:
    _user(h)
    return 200, {"checks": store.list_checks(limit=100, verdict=b.get("verdict") or None)}


@route("GET", r"/attestation/([A-Za-z0-9_.:\-/]+)")
def attestation(m, _b, h) -> Tuple[int, dict]:
    """A fresh report for one model, checked with a nonce made now."""
    from core import attest
    _user(h)
    model = m.group(1)
    if model.startswith("nearai:"):
        model = model[len("nearai:"):]
    try:
        nonce = attest.new_nonce()
        rep = attest.fetch_report(model, nonce=nonce, use_cache=False) \
            if "use_cache" in attest.fetch_report.__code__.co_varnames else attest.fetch_report(model, nonce=nonce)
        checks = attest.check_report(rep, rep.get("_aera", {}).get("nonce", nonce), model)
    except Exception as e:                                           # noqa: BLE001
        return 502, {"model": model, "error": f"{type(e).__name__}: {e}"}
    return 200, {"model": model, "nonce": nonce, "checks": checks, "verdict": attest.verdict(checks)}


@route("GET", r"/proofs")
def proofs(_m, _b, h) -> Tuple[int, dict]:
    _user(h)
    with store.connect() as c:
        rows = c.execute("SELECT * FROM tee_proofs ORDER BY created_at DESC LIMIT 100").fetchall()
    return 200, {"proofs": [dict(r) | {"checks": json.loads(r["checks"] or "[]")} for r in rows],
                 "summary": store.proof_summary(30)}


# ---------------------------------------------------------------------- files
@route("GET", r"/documents")
def list_documents(_m, b: dict, h) -> Tuple[int, dict]:
    """The team's own documents (deliverables and drafts), newest first; ?order_id= filters."""
    _user(h)
    out = []
    for f in store.list_files():
        if not f["name"].startswith("doc:"):
            continue
        full = store.get_file(f["id"]) or {}
        meta = json.loads(full.get("mime", "").split(";", 1)[1]) if ";" in full.get("mime", "") else {}
        if b.get("order_id") and meta.get("order_id") != b["order_id"]:
            continue
        if b.get("run_id") and meta.get("run_id") != b["run_id"]:
            continue
        out.append({**f, "title": meta.get("title") or f["name"][4:], "format": meta.get("format"),
                    "order_id": meta.get("order_id"), "run_id": meta.get("run_id")})
    return 200, {"documents": out}


@route("GET", r"/documents/([A-Za-z0-9_]+)")
def one_document(m, _b, h) -> Tuple[int, dict]:
    _user(h)
    f = store.get_file(m.group(1))
    if not f or not f["name"].startswith("doc:"):
        return 404, {"error": "no such document"}
    meta = json.loads(f["mime"].split(";", 1)[1]) if ";" in f["mime"] else {}
    import hashlib
    import settle
    pdf = settle.render_document(f)
    return 200, {"id": f["id"], "title": meta.get("title") or f["name"][4:], "format": meta.get("format"),
                 "order_id": meta.get("order_id"), "run_id": meta.get("run_id"), "markdown": f["text"], "uploaded_by": f["uploaded_by"],
                 "uploaded_at": f["uploaded_at"], "pdf_sha256": hashlib.sha256(pdf).hexdigest()}


@route("GET", r"/documents/([A-Za-z0-9_]+)\.pdf")
def document_pdf(m, _b, h):
    """The document as the customer receives it. Its sha256 is what deliver_receipt writes on chain."""
    _user(h)
    f = store.get_file(m.group(1))
    if not f or not f["name"].startswith("doc:"):
        return 404, {"error": "no such document"}
    import settle
    title = f["name"][4:] or "document"
    return 200, Download(settle.render_document(f), f"{title[:60]}.pdf", "application/pdf")


@route("GET", r"/files")
def list_files(_m, _b, h) -> Tuple[int, dict]:
    _user(h)
    return 200, {"files": store.list_files()}


@route("POST", r"/files")
def upload_file(_m, b: dict, h) -> Tuple[int, dict]:
    u = _user(h)
    name, text = str(b.get("name") or "").strip(), str(b.get("text") or "")
    if not name or not text.strip():
        return 400, {"error": "send {name, text}"}
    if name.startswith("doc:"):
        return 400, {"error": "'doc:' names are reserved for the team's own documents"}
    return 201, store.save_file(name[:120], str(b.get("mime") or "text/plain")[:60], text, by=u.email)


@route("POST", r"/files/([A-Za-z0-9_]+)/delete")
def delete_file(m, _b, h) -> Tuple[int, dict]:
    if not _user(h).may_manage:
        return 403, {"error": "only an owner removes business files"}
    return (200, {"deleted": True}) if store.delete_file(m.group(1)) else (404, {"error": "no such file"})


# --------------------------------------------------------------------- public
@route("GET", r"/public/offerings")
def public_offerings(_m, _b, _h) -> Tuple[int, dict]:
    from core import business, chain
    p = business.current()
    return 200, {"business": p.get("name"), "mission": p.get("mission"),
                 "open": bool(p.get("name")) and not p.get("kill_switch"),
                 "offerings": p.get("offerings", []), "vault": chain.vault_id() or None,
                 "token": chain.token_id(), "network": chain.network()}


@route("POST", r"/public/checkout")
def public_checkout(_m, b: dict, _h) -> Tuple[int, dict]:
    """An order to pay. With a vault: the exact ft_transfer_call to sign in a
    wallet. Without one: the order waits, and an owner can mark it paid
    (simulated) from the Orders page."""
    import secrets as _s
    from core import business, chain
    p = business.current()
    if not p.get("name") or p.get("kill_switch"):
        return 409, {"error": "the business is not taking orders right now"}
    o = business.offering(str(b.get("offering") or ""), p)
    if not o:
        return 404, {"error": "no such offering"}
    raw_inputs = b.get("inputs") if isinstance(b.get("inputs"), dict) else {}
    inputs = {k: str(raw_inputs.get(k) or "")[:500] for k in o["inputs"]}
    missing = [k for k, v in inputs.items() if not v.strip()]
    if missing:
        return 400, {"error": "missing: " + ", ".join(missing)}
    email = str(b.get("email") or "").strip().lower()[:200]
    account = str(b.get("account") or "").strip().lower()[:64]
    customer = None
    if email:
        found = [c for c in store.find_contact(email) if c["email"] == email]
        customer = (found[0] if found else store.add_contact(email.split("@")[0], "customer", email,
                                                             near_account=account or None))["id"]
    order_id = "ord_" + _s.token_hex(6)
    order = store.create_order(order_id, o["id"], o["price_usd"], inputs, customer=customer or account or None)
    pay: Dict[str, Any] = {"amount_usd": o["price_usd"], "token": chain.token_id()}
    if chain.readable():
        pay["ft_transfer_call"] = {"receiver_id": chain.vault_id(), "amount": chain.to_base(o["price_usd"]),
                                   "msg": json.dumps({"order_id": order_id, "offering": o["id"]})}
    else:
        pay["simulated"] = True
    return 201, {"order": order, "pay": pay}


@route("GET", r"/public/orders/([A-Za-z0-9_\-]+)")
def public_order(m, _b, _h) -> Tuple[int, dict]:
    o = store.get_order(m.group(1))
    if not o:
        return 404, {"error": "no such order"}
    return 200, {k: o[k] for k in ("id", "offering", "status", "amount_usd", "created_at", "updated_at")}


@route("GET", r"/public/ledger")
def public_ledger(_m, _b, _h) -> Tuple[int, dict]:
    led = store.ledger(30)
    return 200, {**led, "entries": [{k: e[k] for k in ("direction", "rail", "amount_usd", "token", "status",
                                                      "tx_hash", "created_at")} for e in led["entries"]]}


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


#: Routes that may be reached without a session token.
PUBLIC_PREFIX = "/public/"
PUBLIC = {("GET", "/health"), ("POST", "/login"), ("GET", "/setup"), ("POST", "/setup")}

_SAMPLES = ((r"([A-Za-z0-9_]+)", "x1"), (r"([A-Za-z]+)", "Thing"), (r"([a-z0-9_]+)", "a_skill"),
            (r"([a-z_]+)", "digest"), (r"([a-z]+)", "impact"), (r"(\d+)", "0"), (r"(pdf|xlsx)", "pdf"),
            (r"([A-Za-z0-9_\-]+)", "ord_x"), (r"([A-Za-z0-9_]+)\.pdf", "x1.pdf"), (r"([A-Za-z0-9_.:\-/]+)", "z-ai/glm-5.3"))


def _sample_path(pattern) -> str:
    path = pattern.pattern.lstrip("^").rstrip("$")
    for group, value in _SAMPLES:
        path = path.replace(group, value)
    return path.replace("\\.", ".")


def demo() -> None:
    """The door, not the rooms: every route but the public ones refuses an
    anonymous caller. Each is called for real with no token."""
    import secrets

    if not identity.SECRET:
        os.environ.setdefault("AERA_SECRET", secrets.token_hex(16))
        identity.SECRET = os.environ["AERA_SECRET"]
    os.environ["AERA_ATTEST_OFFLINE"] = "1"

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
        if path.startswith("/attestation/"):
            guarded.append((method, path))          # network call; guarded by _user before it
            continue
        try:
            fn(found, {}, {})
        except NotAuthorised:
            guarded.append((method, path))
            continue
        except Exception:                                            # noqa: BLE001
            pass
        public.append((method, path))
    assert not unmatched, f"no sample path for: {unmatched}"
    extra = sorted(x for x in set(public) - PUBLIC if not x[1].startswith(PUBLIC_PREFIX))
    assert not extra, f"reachable without a token: {extra}"

    from core import business
    identity.prepare()
    identity.add_user("owner@lumen.example", "Owner", "owner", "pw-for-the-check")
    identity.add_user("op@lumen.example", "Op", "operator", "pw-for-the-check")
    tok = login(None, {"email": "owner@lumen.example", "password": "pw-for-the-check"}, {})[1]["token"]
    op = login(None, {"email": "op@lumen.example", "password": "pw-for-the-check"}, {})[1]["token"]
    H, O = {"Authorization": f"Bearer {tok}"}, {"Authorization": f"Bearer {op}"}

    assert first_owner(None, {"email": "x@y.example", "name": "X", "password": "0123456789"}, {})[0] == 409, \
        "the first-owner door closes once an account exists"
    assert setup_status(None, {}, {})[1]["needs_owner"] is False
    code, out = save_business(None, {"profile": business.EXAMPLE}, O)
    assert code == 403, "an operator cannot rewrite the business"
    code, out = save_business(None, {"profile": business.EXAMPLE}, H)
    assert code == 200 and out["version"], out
    code, t = get_team(None, {}, H)
    codes = {a["code"] for a in t["agents"]}
    assert {"supervisor", "guardian", "treasurer", "researcher", "writer"} <= codes, codes
    tre = next(a for a in t["agents"] if a["code"] == "treasurer")
    assert "pay_vendor" in tre["tools"]["treasury"]
    code, e = edit_agent(re.match(r"(.*)", "writer"), {"capabilities": ["documents", "treasury"]}, H)
    assert code == 200 and "treasury" not in e["agent"]["capabilities"], "the lock holds through the API"
    print(f"  business saved ✓ · team composed ({len(codes)} agents) ✓ · treasury stays locked ✓")

    code, co = public_checkout(None, {"offering": "brief", "inputs": {"industry": "coffee", "country": "VN"},
                                      "email": "ana@client.example"}, {})
    assert code == 201 and co["pay"].get("simulated"), co
    oid = co["order"]["id"]
    code, paid = simulate_paid(re.match(r"(.*)", oid), {}, H)
    assert code == 200 and paid["order"]["status"] == "paid" and paid["work_items"], paid
    assert public_order(re.match(r"(.*)", oid), {}, {})[1]["status"] == "paid"
    print("  checkout → simulated payment → a work item for the team ✓")

    # Approval limits come from the token; a blocked action can never be approved.
    from core.actions import raise_action
    wid = store.record_work_item("request", "x", "api", {})
    rid = store.start_run(wid)
    with registry.bind_run(rid):
        big = raise_action("payment", {"receiver": "v.testnet", "amount_usd": 400}, {"verdict": "warn", "reasons": []},
                           value_usd=400, execute=False).value
        bad = raise_action("payment", {"receiver": "e.testnet", "amount_usd": 1}, {"verdict": "block", "reasons": []},
                           value_usd=1, execute=False).value
    assert decide(re.match(r"(.*)", big["id"]), {"decision": "approved"}, O)[0] == 403
    assert decide(re.match(r"(.*)", bad["id"]), {"decision": "approved"}, H)[0] == 409
    code, d = decide(re.match(r"(.*)", big["id"]), {"decision": "approved"}, H)
    assert code == 200 and d["action"]["status"] == "sent", d
    print("  approval: role limit from the token ✓ · blocked is final ✓ · approved executes ✓")

    assert kill_switch(None, {"on": True}, O)[0] == 403, "an operator cannot stop the business"
    assert kill_switch(None, {"on": True}, H)[0] == 200
    identity.add_user("ap@lumen.example", "Ap", "approver", "pw-for-the-check")
    ap = login(None, {"email": "ap@lumen.example", "password": "pw-for-the-check"}, {})[1]["token"]
    assert kill_switch(None, {"on": False}, {"Authorization": f"Bearer {ap}"})[0] == 403, "only an owner resumes"
    assert create_contact(None, {"name": "V", "role": "vendor", "near_account": "Bad Acct"}, H)[0] == 400
    code, cv = create_contact(None, {"name": "V", "role": "vendor", "near_account": "vendor.testnet"}, H)
    assert code == 201 and cv["near_account"] == "vendor.testnet", cv
    assert create_contact(None, {"name": "V", "role": "vendor", "near_account": "v2.testnet"}, O)[0] == 403
    assert public_checkout(None, {"offering": "brief", "inputs": {"industry": "x", "country": "y"}}, {})[0] == 409
    assert kill_switch(None, {"on": False}, H)[0] == 200
    print("  kill switch: approvers and owners stop, only an owner resumes ✓ · contacts validated ✓")
    print(f"  {len(ROUTES)} routes · {len(guarded)} refuse an anonymous caller ✓")
    print("api ok")


if __name__ == "__main__":
    if "--check" in sys.argv:
        from core.config import fixtures_only

        fixtures_only(__file__, "AERA_API_CHECK")
        demo()
        raise SystemExit(0)

    _load_model_choices()
    llm.refresh_attested()
    print(f"AERA API · env={CFG.env} · model={'ready' if CFG.model_ready else 'no'} "
          f"· private={'on' if llm.private_mode() else 'off'}")
    class _Server(ThreadingHTTPServer):
        # A page fans out a dozen requests at once; the default backlog of 5
        # resets some of them.
        request_queue_size = 128
        daemon_threads = True

    server = _Server((HOST, PORT), Handler)
    print(f"listening on http://{HOST}:{PORT}")
    import jobs
    SCHEDULE = jobs.scheduler(start_work)
    SCHEDULE.start()
    server.serve_forever()
