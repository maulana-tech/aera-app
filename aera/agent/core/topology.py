"""The trace of one handling as a graph: who asked whom, which tool each
called, and where every figure was read from.

The steps table is a list in time order, which answers "what happened next"
and nothing else. "Which of the lead's numbers came from a fixture" or "what
did the researcher read before the writer wrote" means walking that list by
hand. This file folds it into a topology instead:

    work item -> supervisor -> specialist -> tool -> source
                                       -> action

Nodes are aggregated (one node per agent, per agent and tool, per source),
so a tool called nine times is one node with nine calls behind it; the edges
carry the count and the seqs, so every node leads back to the exact calls.
The calls themselves stay in order beside the graph, each with its full
arguments, its provenance and a preview of its result. The full result of one
call is read on demand (GET /runs/{id}/steps/{seq}); a live tenant answers a
broad question with thousands of rows and the whole trace need not carry them.

Pure: it reads a run as core/store.get_run returns it, and writes nothing.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

#: Rows of a list result carried in the trace itself. The rest is one click away.
PREVIEW_ROWS = 25
PREVIEW_CHARS = 6000

#: Origins from weakest to strongest: an edge is as good as its worst call.
_ORDER = ["missing", "modelled", "cached", "derived", "live"]

#: A compound source names several, joined by " + ". Split only where the next
#: piece is itself a source, so "Open-Meteo forecast + marine" stays one.
_JOIN = re.compile(r" \+ (?=(?:upload:|fixture:|profile\b))")


def _weakest(a: Optional[str], b: Optional[str]) -> Optional[str]:
    known = [o for o in (a, b) if o in _ORDER]
    return min(known, key=_ORDER.index) if known else (a or b)


def source_kind(src: str) -> str:
    s = src.strip()
    if s.startswith("fixture"):
        return "fixture"
    if s.startswith(("upload:", "file ", "business files", "documents")):
        return "upload"
    if s.startswith(("business profile", "profile")):
        return "profile"
    if s.startswith(("core/guardian", "guardian")):
        return "rules"
    if s.startswith(("action record", "actions", "run record", "work items", "orders", "contacts",
                     "AERA ledger", "AERA record")):
        return "record"
    if s.startswith(("vault", "near")):
        return "chain"
    if s.startswith(("engine/", "core/")) or s.endswith(".py"):
        return "engine"
    return "external"


def source_label(src: str) -> Tuple[str, str]:
    """(label, sub-label) for a source node."""
    s = src.strip()
    if s.startswith("fixture:"):
        return f"Fixture · {s[len('fixture:'):]}", "modelled sample data"
    if s.startswith("upload:"):
        return f"Upload · {s[len('upload:'):]}", "company file"
    return s, source_kind(s)


def sources_of(src: Optional[str]) -> List[str]:
    return [p.strip() for p in _JOIN.split(src or "") if p.strip()]


def preview(value: Any) -> Tuple[Any, bool]:
    """A result small enough to carry in the trace, and whether it was cut."""
    if isinstance(value, list) and len(value) > PREVIEW_ROWS:
        return value[:PREVIEW_ROWS], True
    if isinstance(value, str) and len(value) > PREVIEW_CHARS:
        return value[:PREVIEW_CHARS], True
    return value, False


_KIND = {"DELEGATE": "delegate", "TOOL": "tool", "FINDING": "finding",
         "SUMMARY": "summary", "FALLBACK": "fallback"}


def build(run: dict, agents: Optional[Dict[str, Tuple[str, ...]]] = None) -> dict:
    """The topology and the ordered calls of one run (core/store.get_run).
    `agents` is code -> (nickname, title[, brief]), for the agent nodes' labels
    and the role line in a node's detail."""
    if agents is None:
        try:
            from agents import roster
            agents = {c: (a.nickname, a.title, a.brief) for c, a in roster.load().items()}
        except Exception:                                           # noqa: BLE001
            agents = {}
    nodes: Dict[str, dict] = {}
    edges: Dict[Tuple[str, str, str], dict] = {}
    calls: List[dict] = []

    def node(nid: str, **fields) -> dict:
        n = nodes.get(nid)
        if n is None:
            if fields.get("kind") == "agent" and fields.get("agent") in agents:
                nick, title, *rest = agents[fields["agent"]]
                fields.update(label=nick, sub=title, brief=rest[0] if rest else None)
            n = nodes[nid] = {"id": nid, "calls": 0, "errors": 0, "ms": 0, **fields}
        return n

    def edge(a: str, b: str, rel: str, seq: int, origin: Optional[str] = None) -> None:
        e = edges.get((a, b, rel))
        if e is None:
            e = edges[(a, b, rel)] = {"id": f"{a}->{b}:{rel}", "from": a, "to": b, "rel": rel,
                                      "count": 0, "seqs": [], "origin": origin}
        e["count"] += 1
        e["seqs"].append(seq)
        e["origin"] = _weakest(e["origin"], origin) if origin else e["origin"]

    event = node("event", kind="event", label=run.get("title") or "work item",
                 sub=run.get("kind") or "", trigger=run.get("work_source"),
                 status=run.get("status"), started_at=run.get("started_at"))
    lead = node("agent:supervisor", kind="agent", agent="supervisor", label="Supervisor",
                sub="Supervisor", state="working")
    edge(event["id"], lead["id"], "triggers", 0)

    open_task: Dict[str, int] = {}          # agent -> seq of the delegation it is working on
    for s in run.get("steps") or []:
        d = s.get("detail") or {}
        seq = s["seq"]
        kind = _KIND.get(s["stage"], s["stage"].lower())
        agent = d.get("agent") or s.get("agent") or "supervisor"
        an = f"agent:{agent}"
        call = {"seq": seq, "kind": kind, "at": s.get("at"), "agent": agent,
                "agent_name": d.get("name") if kind != "tool" else None,
                "thinking": d.get("thinking") or None, "node_ids": [an],
                "parent_seq": open_task.get(agent)}

        if kind == "delegate":
            by = d.get("by") or "supervisor"
            a = node(an, kind="agent", agent=agent, label=d.get("name") or agent, sub=agent,
                     state="working")
            a["tasks"] = a.get("tasks", 0) + 1
            edge(f"agent:{by}", an, "delegates", seq)
            open_task[agent] = seq
            call.update(task=d.get("task"), by=by, call_id=d.get("call_id"),
                        node_ids=[f"agent:{by}", an], parent_seq=open_task.get(by))

        elif kind == "tool":
            name = d.get("name") or (s.get("tools") or ["?"])[0]
            node(an, kind="agent", agent=agent, label=agent, sub=agent, state="working")
            tn = f"tool:{agent}:{name}"
            t = node(tn, kind="tool", agent=agent, tool=name, label=name, sub=agent, origin=None)
            t["calls"] += 1
            t["ms"] += d.get("ms") or 0
            nodes[an]["calls"] += 1
            edge(an, tn, "calls", seq)
            origin, src = d.get("origin"), d.get("source")
            ids = [an, tn]
            if d.get("error"):
                t["errors"] += 1
                nodes[an]["errors"] += 1
            else:
                t["origin"] = _weakest(t["origin"], origin)
                for piece in sources_of(src):
                    sn = f"source:{piece}"
                    label, sub = source_label(piece)
                    sx = node(sn, kind="source", source=piece, source_kind=source_kind(piece),
                              label=label, sub=sub, origin=None)
                    sx["calls"] += 1
                    sx["origin"] = _weakest(sx["origin"], origin)
                    edge(tn, sn, "reads", seq, origin)
                    ids.append(sn)
            value, cut = preview(d.get("result"))
            call.update(tool=name, arguments=d.get("arguments") or {}, origin=origin,
                        source=src, note=d.get("note") or None, fetched_at=d.get("fetched_at"),
                        ms=d.get("ms"), rows=d.get("rows") if d.get("rows") is not None else
                        (len(d["result"]) if isinstance(d.get("result"), list) else None),
                        rows_shown=d.get("rows_shown"), error=d.get("error"),
                        result=value, truncated=cut, round=d.get("round"),
                        call_id=d.get("call_id"), node_ids=ids)

        elif kind in ("finding", "summary"):
            a = node(an, kind="agent", agent=agent, label=d.get("name") or agent, sub=agent)
            stats = d.get("stats") or {}
            if stats:
                a["stats"] = stats
            no_tool = kind == "finding" and d.get("tool_calls") == 0
            a["state"] = "failed" if d.get("error") else ("no tool" if no_tool else "done")
            call.update(summary=d.get("full_summary") or d.get("summary") or s.get("summary"),
                        tool_calls=d.get("tool_calls"), stats=stats or None,
                        error=bool(d.get("error")) or None)
            open_task.pop(agent, None)

        else:
            call.update(summary=d.get("summary") or s.get("summary"))
        calls.append(call)

    # Actions: joined to the call that raised them, by the action id it returned.
    raised_by = {}
    for c in calls:
        if c["kind"] == "tool" and isinstance(c.get("result"), dict) and c["result"].get("id"):
            raised_by[c["result"]["id"]] = c
    for a in run.get("actions") or []:
        payload = a.get("payload") or {}
        an = f"action:{a['id']}"
        node(an, kind="action", label=a.get("kind"), sub=a.get("status"), action_id=a["id"],
             status=a.get("status"), autonomous=bool(a.get("autonomous")),
             value_usd=a.get("value_usd"),
             title=a.get("title"), payload=payload, created_at=a.get("created_at"),
             reference=a.get("reference"),
             approvals=[{k: p.get(k) for k in ("decision", "decided_by", "role", "note", "at")}
                        for p in run.get("approvals") or [] if p.get("action_id") == a["id"]])
        c = raised_by.get(a["id"])
        if c:
            edge(f"tool:{c['agent']}:{c['tool']}", an, "raises", c["seq"])
            c["node_ids"].append(an)
        else:
            edge(lead["id"], an, "raises", 0)

    # An agent is as trustworthy as the weakest thing it read.
    for e in edges.values():
        if e["rel"] == "calls" and nodes[e["to"]].get("origin"):
            a = nodes[e["from"]]
            a["origin"] = _weakest(a.get("origin"), nodes[e["to"]]["origin"])

    status = run.get("status")
    if status in ("done", "failed", "held", "stopped"):
        for n in nodes.values():
            if n["kind"] == "agent" and n.get("state") == "working":
                n["state"] = "done" if n["id"] == lead["id"] and status == "done" else "unfinished"

    origins: Dict[str, int] = {}
    for c in calls:
        if c["kind"] == "tool":
            key = c.get("origin") or ("error" if c.get("error") else "unknown")
            origins[key] = origins.get(key, 0) + 1
    tool_calls = [c for c in calls if c["kind"] == "tool"]
    decision = run.get("decision") or {}
    return {
        "run": {k: run.get(k) for k in ("id", "title", "kind", "trigger", "status", "mode",
                                        "started_at", "finished_at", "error")}
               | {"cost_usd": run.get("cost_usd") or decision.get("cost_usd"),
                  "cost_by_model": decision.get("cost_by_model")},
        "totals": {
            "steps": len(calls),
            "tool_calls": len(tool_calls),
            "errors": sum(1 for c in tool_calls if c.get("error")),
            "agents": sum(1 for n in nodes.values() if n["kind"] == "agent"),
            "sources": sum(1 for n in nodes.values() if n["kind"] == "source"),
            "actions": sum(1 for n in nodes.values() if n["kind"] == "action"),
            "tool_ms": sum(c.get("ms") or 0 for c in tool_calls),
            "by_origin": origins,
        },
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "calls": calls,
    }


def step(run: dict, seq: int) -> Optional[dict]:
    """One step of a run in full, result and all."""
    return next((s for s in run.get("steps") or [] if s["seq"] == seq), None)


def demo() -> None:
    rows = [{"title": f"headline {i}", "publisher": "Reuters"} for i in range(60)]
    run = {
        "id": "run_x", "title": "Order ord_1: brief", "kind": "order", "status": "done",
        "steps": [
            {"seq": 1, "stage": "DELEGATE", "agent": "researcher",
             "detail": {"agent": "researcher", "name": "Researcher", "task": "research it", "by": "supervisor"}},
            {"seq": 2, "stage": "TOOL", "agent": "researcher", "tools": ["search_news"],
             "detail": {"agent": "researcher", "name": "search_news", "arguments": {"query": "coffee"},
                        "result": rows, "origin": "live", "source": "Google News + fixture:Sample", "ms": 900}},
            {"seq": 3, "stage": "TOOL", "agent": "researcher", "tools": ["read_web_page"],
             "detail": {"agent": "researcher", "name": "read_web_page", "arguments": {},
                        "result": [], "origin": "missing", "source": "example.com"}},
            {"seq": 4, "stage": "TOOL", "agent": "researcher", "tools": ["read_web_page"],
             "detail": {"agent": "researcher", "name": "read_web_page", "arguments": {}, "error": "URLError"}},
            {"seq": 5, "stage": "FINDING", "agent": "researcher",
             "detail": {"agent": "researcher", "name": "Researcher", "summary": "3 facts", "tool_calls": 3}},
            {"seq": 6, "stage": "DELEGATE", "agent": "treasurer",
             "detail": {"agent": "treasurer", "name": "Treasurer", "task": "pay the data vendor"}},
            {"seq": 7, "stage": "TOOL", "agent": "treasurer", "tools": ["pay_vendor"],
             "detail": {"agent": "treasurer", "name": "pay_vendor", "arguments": {},
                        "result": {"id": "act_1", "kind": "payment"}, "origin": "derived", "source": "action record"}},
            {"seq": 8, "stage": "FINDING", "agent": "treasurer",
             "detail": {"agent": "treasurer", "name": "Treasurer", "summary": "waiting", "tool_calls": 0}},
        ],
        "actions": [{"id": "act_1", "kind": "payment", "status": "pending", "value_usd": 40.0, "payload": {}}],
        "approvals": [{"action_id": "act_1", "decision": "escalated", "decided_by": "a@b", "role": "operator", "at": "t"}],
    }
    t = build(run, {"researcher": ("Researcher", "Researcher", "Finds facts.")})
    ids = {n["id"]: n for n in t["nodes"]}
    e = {(x["from"], x["to"], x["rel"]): x for x in t["edges"]}
    assert ("event", "agent:supervisor", "triggers") in e
    assert e[("agent:supervisor", "agent:researcher", "delegates")]["seqs"] == [1]
    page = ids["tool:researcher:read_web_page"]
    assert page["calls"] == 2 and page["errors"] == 1, "one node per agent and tool"
    assert {"source:Google News", "source:fixture:Sample"} <= set(ids), "a compound source names both"
    assert e[("tool:treasurer:pay_vendor", "action:act_1", "raises")]["seqs"] == [7]
    assert ids["action:act_1"]["value_usd"] == 40.0
    assert ids["agent:researcher"]["brief"] == "Finds facts."
    news = next(c for c in t["calls"] if c["seq"] == 2)
    assert news["truncated"] and len(news["result"]) == PREVIEW_ROWS and news["rows"] == 60
    assert source_kind("vault") == "chain" and source_kind("core/guardian.py") == "rules"
    print(f"topology ok, {len(t['nodes'])} nodes · {len(t['edges'])} edges")


if __name__ == "__main__":
    demo()
