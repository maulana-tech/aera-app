"""What the team is doing and has done, as one feed a person can read (GET /activity).

The team works without being asked: an order is paid on chain, the Supervisor hands it out, the
specialists research and write, the Guardian rules, the Treasurer pays. All of that is already in
the record (steps, work_items, runs, actions, approvals, payments, guardian_checks, business
versions); this module only reads it back in plain words, newest first, each event linking to its
evidence. Nothing here is generated or summarised by a model.

    feed(limit, category)   events: {at, category, tone, agent, title, detail, run_id, order_id, tx}
    now()                   runs in progress: who is working on what, and the latest step
    since(ts)               what changed since a moment: orders, money, work done, held, blocked
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core import store

CATEGORIES = ("team", "money", "guardian", "work")

#: Tool calls worth a line in the feed. Searches and reads are many and small; they show on the run.
NOTABLE_TOOLS = {
    "write_document": "wrote a document",
    "deliver_order": "delivered an order to the customer",
    "draft_message": "drafted a message",
    "pay_vendor": "asked the vault to pay a vendor",
    "propose_refund": "proposed a refund",
    "freeze_payments": "froze payments",
    "save_contact": "saved a contact",
    "quote_cross_chain_payment": "priced a payment to another chain",
}
CORE_NAMES = {"supervisor": "Supervisor", "guardian": "Guardian", "treasurer": "Treasurer"}
KIND_WORD = {"order": "order", "request": "request", "goal": "goal", "payable": "bill"}


def _j(text: Optional[str], default: Any) -> Any:
    try:
        return json.loads(text) if text else default
    except (TypeError, ValueError):
        return default


_MD = re.compile(r"(\*\*|__|`+|^#{1,6}\s*|\s#{1,6}\s|\[(?=[^\]]*\]\()|\]\([^)]*\))", re.M)


def _short(s: Any, n: int = 160) -> str:
    """One readable line: an agent's hand-back is markdown, and a feed line is not the place for it."""
    s = _MD.sub(" ", str(s or "")).replace("✅", "").replace("❌", "")
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _name(agent: str, agent_name: str = "") -> str:
    return CORE_NAMES.get(agent) or agent_name or agent.replace("_", " ").title()


def _ev(at: str, category: str, tone: str, agent: str, title: str, detail: str = "", **links: Any) -> Dict[str, Any]:
    return {"at": at, "category": category, "tone": tone, "agent": agent, "title": title,
            "detail": _short(detail, 220), **{k: v for k, v in links.items() if v}}


# ------------------------------------------------------------------- sources
def _work(c, limit: int) -> List[dict]:
    out = []
    for r in c.execute("SELECT id, kind, title, source, received_at FROM work_items ORDER BY received_at DESC LIMIT ?", (limit,)):
        word = KIND_WORD.get(r["kind"], r["kind"])
        src = {"vault": "paid on chain", "schedule": "from a standing goal", "chat": "from chat",
               "api": "from the Work page"}.get(r["source"], r["source"])
        out.append(_ev(r["received_at"], "work", "info", "Team", f"New {word}: {_short(r['title'], 90)}", src,
                       work_item_id=r["id"]))
    for r in c.execute("SELECT r.id, r.status, r.finished_at, r.cost_usd, w.title FROM runs r JOIN work_items w ON w.id=r.work_item_id"
                       " WHERE r.finished_at IS NOT NULL ORDER BY r.finished_at DESC LIMIT ?", (limit,)):
        tone, verb = {"done": ("ok", "finished"), "partial": ("warn", "stopped early on"), "held": ("warn", "is holding"),
                      "failed": ("bad", "failed on")}.get(r["status"], ("info", r["status"]))
        cost = f"model cost ${r['cost_usd']:.2f}" if r["cost_usd"] else ""
        out.append(_ev(r["finished_at"], "work", tone, "Team", f"The team {verb} {_short(r['title'], 80)}", cost, run_id=r["id"]))
    return out


def _roster(c) -> Dict[str, str]:
    """Agent code -> the name the team page shows. A TOOL step's agent_name is the tool, not the agent."""
    try:
        return {r["code"]: r["nickname"] for r in c.execute("SELECT code, nickname FROM agents")}
    except Exception:                                                  # noqa: BLE001
        return {}


def _steps(c, limit: int) -> List[dict]:
    out = []
    names = _roster(c)
    rows = c.execute("SELECT run_id, stage, agent, agent_name, summary, tools, detail, at FROM steps"
                     " WHERE stage IN ('DELEGATE','FINDING','TOOL','FALLBACK') ORDER BY id DESC LIMIT ?", (limit * 6,))
    for r in rows:
        who = names.get(r["agent"]) or _name(r["agent"], "" if r["stage"] == "TOOL" else r["agent_name"])
        if r["stage"] == "DELEGATE":
            out.append(_ev(r["at"], "team", "info", who, f"{who} took on a task", r["summary"], run_id=r["run_id"]))
        elif r["stage"] == "FINDING":
            stopped = "stopped" in (r["summary"] or "").lower()[:40]
            out.append(_ev(r["at"], "team", "warn" if stopped else "ok", who,
                           f"{who} {'stopped before finishing' if stopped else 'handed back its work'}", r["summary"], run_id=r["run_id"]))
        elif r["stage"] == "FALLBACK":
            out.append(_ev(r["at"], "team", "warn", who, f"{who}'s model was slow; a fallback model answered", r["summary"],
                           run_id=r["run_id"]))
        else:
            tool = (_j(r["tools"], []) or [""])[0]
            if tool in NOTABLE_TOOLS:
                out.append(_ev(r["at"], "team", "info", who, f"{who} {NOTABLE_TOOLS[tool]}", "", run_id=r["run_id"]))
        if len(out) >= limit:
            break
    return out


def _money(c, limit: int) -> List[dict]:
    out = []
    for r in c.execute("SELECT direction, rail, counterparty, amount_usd, status, tx_hash, detail, created_at FROM payments"
                       " ORDER BY created_at DESC LIMIT ?", (limit,)):
        d = _j(r["detail"], {})
        sim = " (simulated)" if r["rail"] == "simulated" else ""
        amount = f"${r['amount_usd']:,.2f}"
        if r["direction"] == "in":
            title = f"{amount} received{sim}" + (f" for order {d['order_id']}" if d.get("order_id") else "")
            tone, agent = "ok", "Vault"
        elif r["direction"] == "refund":
            title, tone, agent = f"{amount} refunded to {r['counterparty']}{sim}", "warn", "Treasurer"
        elif r["direction"] == "split":
            title, tone, agent = f"{amount} revenue share paid to {r['counterparty']}{sim}", "ok", "Vault"
        else:
            verb = {"sent": "paid", "pending_onchain": "held by the vault for an approver", "failed": "failed to pay",
                    "submitted": "is paying", "rejected": "was refused paying"}.get(r["status"], r["status"])
            title = f"Treasurer {verb} {amount} to {r['counterparty']}{sim}"
            tone, agent = ("ok" if r["status"] == "sent" else "bad" if r["status"] in ("failed", "rejected") else "warn"), "Treasurer"
        out.append(_ev(r["created_at"], "money", tone, agent, title, "", tx=r["tx_hash"], order_id=d.get("order_id")))
    for r in c.execute("SELECT id, run_id, kind, status, value_usd, reason, created_at FROM actions ORDER BY created_at DESC LIMIT ?", (limit,)):
        if r["status"] == "pending":
            val = f" (${r['value_usd']:,.2f})" if r["value_usd"] else ""
            out.append(_ev(r["created_at"], "money", "warn", "Team", f"Waiting for you: {r['kind'].replace('_', ' ')}{val}",
                           r["reason"] or "", run_id=r["run_id"], action_id=r["id"]))
    for r in c.execute("SELECT a.action_id, a.decided_by, a.decision, a.note, a.at, x.kind, x.run_id FROM approvals a"
                       " JOIN actions x ON x.id=a.action_id ORDER BY a.at DESC LIMIT ?", (limit,)):
        tone = {"approved": "ok", "rejected": "bad"}.get(r["decision"], "info")
        out.append(_ev(r["at"], "money", tone, r["decided_by"], f"{r['decided_by']} {r['decision']} a {r['kind'].replace('_', ' ')}",
                       r["note"] or "", run_id=r["run_id"], action_id=r["action_id"]))
    return out


def _guardian(c, limit: int) -> List[dict]:
    out = []
    for r in c.execute("SELECT run_id, kind, subject, verdict, reasons, at FROM guardian_checks WHERE verdict IN ('block','warn')"
                       " ORDER BY at DESC LIMIT ?", (limit,)):
        hits = [x for x in _j(r["reasons"], []) if x.get("verdict") in ("block", "warn")]
        why = "; ".join(_short(x.get("detail"), 90) for x in hits[:2])
        verb = "blocked" if r["verdict"] == "block" else "held for you"
        what = "a payment to" if r["kind"] == "counterparty" else "an action for"
        out.append(_ev(r["at"], "guardian", "bad" if r["verdict"] == "block" else "warn", "Guardian",
                       f"Guardian {verb} {what} {_short(r['subject'], 50)}", why, run_id=r["run_id"]))
    return out


def _visitors(c, limit: int) -> List[dict]:
    """Sales answering visitors on the public checkout page (core/public_chat.py)."""
    out = []
    try:
        rows = c.execute("SELECT s.session, s.offering, s.note, s.at, (SELECT v.text FROM public_chats v WHERE v.session=s.session"
                         " AND v.role='visitor' AND v.at <= s.at ORDER BY v.at DESC LIMIT 1) q FROM public_chats s"
                         " WHERE s.role='sales' ORDER BY s.at DESC LIMIT ?", (limit,)).fetchall()
    except Exception:                                                  # noqa: BLE001
        return out
    for r in rows:
        where = f"/buy/{r['offering']}" if r["offering"] else "the checkout"
        note = r["note"] or ""
        if note.startswith("withheld"):
            out.append(_ev(r["at"], "guardian", "bad", "Guardian", f"A reply to a visitor on {where} was withheld", note))
        elif note.startswith("model unavailable"):
            out.append(_ev(r["at"], "team", "warn", "Sales", f"Sales could not answer a visitor on {where}", note))
        else:
            title = f"Sales answered a visitor on {where}" + (" and filled in the checkout" if "checkout" in note else "")
            out.append(_ev(r["at"], "team", "ok", "Sales", title, f"Asked: {r['q'] or ''}"))
    return out


def _switch(c) -> List[dict]:
    out, last = [], None
    names = _roster(c)
    for r in c.execute("SELECT profile, changed_by, note, at FROM business ORDER BY version"):
        on = bool(_j(r["profile"], {}).get("kill_switch"))
        if last is not None and on != last:
            by = r["changed_by"] or ""
            # an agent ("agent:guardian"), a person (an email), or a tool run by hand ("attack-demo")
            actor = names.get(by[6:], by[6:].title()) if by.startswith("agent:") else by if "@" in by else "Team"
            out.append(_ev(r["at"], "guardian", "bad" if on else "ok", actor,
                           "The kill switch stopped the team" if on else "The team was resumed", r["note"] or ""))
        last = on
    return out


# -------------------------------------------------------------------- public
def feed(limit: int = 50, category: Optional[str] = None) -> List[Dict[str, Any]]:
    with store.connect() as c:
        events = _work(c, limit) + _steps(c, limit) + _money(c, limit) + _guardian(c, limit) + _visitors(c, limit) + _switch(c)
    if category in CATEGORIES:
        events = [e for e in events if e["category"] == category]
    events.sort(key=lambda e: e["at"], reverse=True)
    return events[:limit]


def now() -> List[Dict[str, Any]]:
    """Runs in progress, with who is working and the latest thing they did."""
    out = []
    with store.connect() as c:
        runs = c.execute("SELECT r.id, r.started_at, w.title, w.kind FROM runs r JOIN work_items w ON w.id=r.work_item_id"
                         " WHERE r.status='running' ORDER BY r.started_at DESC LIMIT 10").fetchall()
        for r in runs:
            steps = c.execute("SELECT stage, agent, agent_name, summary, tools, at FROM steps WHERE run_id=? ORDER BY id DESC LIMIT 40",
                              (r["id"],)).fetchall()
            last = steps[0] if steps else None
            active = None
            for s in steps:                     # the specialist most recently handed a task and not yet back
                if s["stage"] == "FINDING":
                    break
                if s["stage"] == "DELEGATE":
                    active = s
                    break
            working = active or last
            roster = _roster(c)
            agents = sorted({s["agent"] for s in steps})
            doing = ""
            if last:
                tool = (_j(last["tools"], []) or [""])[0]
                doing = (NOTABLE_TOOLS.get(tool) or tool.replace("_", " ")) if last["stage"] == "TOOL" else \
                    "thinking" if last["stage"] == "MODEL" else _short(last["summary"], 120)
            n = c.execute("SELECT count(*) n FROM steps WHERE run_id=?", (r["id"],)).fetchone()["n"]
            out.append({"run_id": r["id"], "title": r["title"], "kind": r["kind"], "started_at": r["started_at"],
                        "agent": working["agent"] if working else "supervisor",
                        "agent_name": (roster.get(working["agent"]) or _name(working["agent"], working["agent_name"] if working["stage"] != "TOOL" else ""))
                        if working else "Supervisor",
                        "doing": doing, "last_at": last["at"] if last else r["started_at"],
                        "agents": agents, "steps": n})
    return out


def since(ts: Optional[str]) -> Dict[str, Any]:
    """What changed since `ts` (ISO time). The waiting count is now, not since: it is what needs you."""
    ts = ts or "1970-01-01T00:00:00+00:00"
    with store.connect() as c:
        one = lambda sql, *a: c.execute(sql, a).fetchone()[0] or 0  # noqa: E731
        out = {
            "since": ts,
            "orders_paid": one("SELECT count(*) FROM payments WHERE direction='in' AND created_at > ?", ts),
            "revenue_usd": round(one("SELECT sum(amount_usd) FROM payments WHERE direction='in' AND created_at > ?", ts), 2),
            "paid_out_usd": round(one("SELECT sum(amount_usd) FROM payments WHERE direction='out' AND status='sent' AND created_at > ?", ts), 2),
            "work_done": one("SELECT count(*) FROM runs WHERE status='done' AND finished_at > ?", ts),
            "held": one("SELECT count(*) FROM runs WHERE status IN ('held','partial','failed') AND finished_at > ?", ts),
            "guardian_stops": one("SELECT count(*) FROM guardian_checks WHERE verdict IN ('block','warn') AND at > ?", ts),
            "model_cost_usd": round(one("SELECT sum(cost_usd) FROM runs WHERE finished_at > ?", ts), 2),
            "waiting_now": one("SELECT count(*) FROM actions WHERE status='pending'"),
            "running_now": one("SELECT count(*) FROM runs WHERE status='running'"),
        }
    return out


def summary(limit: int = 50, category: Optional[str] = None, ts: Optional[str] = None) -> Dict[str, Any]:
    return {"now": now(), "since": since(ts), "events": feed(limit, category),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def demo() -> None:
    from core import business
    store.save_profile(business.EXAMPLE, by="check")
    wid = store.record_work_item("order", "Order ord_1: brief", "vault", {"order_id": "ord_1"})
    rid = store.start_run(wid)
    store.save_step(rid, {"seq": 1, "stage": "DELEGATE", "agent": "researcher", "agent_name": "Researcher",
                          "summary": "Find market size signals", "tools": [], "detail": {}, "at": store._now()})
    store.save_step(rid, {"seq": 2, "stage": "TOOL", "agent": "researcher", "agent_name": "Researcher",
                          "summary": "search_news", "tools": ["search_news"], "detail": {}, "at": store._now()})
    live = now()
    assert live and live[0]["agent_name"] == "Researcher" and live[0]["doing"] == "search news", live
    store.save_step(rid, {"seq": 3, "stage": "TOOL", "agent": "writer", "agent_name": "Writer",
                          "summary": "write_document", "tools": ["write_document"], "detail": {}, "at": store._now()})
    store.record_payment("in", "simulated", "ana.testnet", 15, "usdc", "sent", detail={"order_id": "ord_1"})
    store.record_check("counterparty", "attacker.testnet", "block", [{"rule": "blocklist", "verdict": "block", "detail": "on the blocklist"}])
    store.close_run(rid, "done", {"status": "done"}, cost_usd=0.06)
    ev = feed()
    titles = [e["title"] for e in ev]
    assert any(t.startswith("New order") for t in titles), titles
    assert "Researcher took on a task" in titles and "Writer wrote a document" in titles
    assert not any("search news" in t for t in titles), "small reads stay off the feed"
    assert any(t.startswith("$15.00 received") for t in titles) and any(t.startswith("Guardian blocked") for t in titles)
    assert all(e["category"] == "guardian" for e in feed(category="guardian"))
    s = since("1970-01-01T00:00:00+00:00")
    assert s["orders_paid"] == 1 and s["revenue_usd"] == 15 and s["work_done"] == 1 and s["guardian_stops"] == 1
    assert not now()
    json.dumps(summary())
    print("activity ok: live run and active agent ✓ · feed in plain words, small reads left out ✓ · since-summary ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_ACTIVITY_CHECK")
    demo()
