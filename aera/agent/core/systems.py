"""The Tech Lead's view: is the machinery the business runs on healthy? Computed from the record, never guessed.

  status(days)     models per agent and whether each answers in an attested TEE, how often a fallback model had to
                   step in, AI spend today against the cap, runs by outcome and how long they took, tool calls that
                   failed (by tool), outside servers and their write permissions, the vault; then the issues those
                   numbers point to, each with the figure behind it.
  incidents(days)  the runs that did not finish cleanly, with the work they were for and why.

The Tech Lead explains and recommends. It changes no setting, connects no server and allows no write: those stay
with the owner, on the pages that already ask for them.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from core import business, store


def _since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _minutes(a: str, b: str) -> float:
    try:
        return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 60
    except (TypeError, ValueError):
        return 0.0


def _models() -> List[Dict[str, Any]]:
    try:
        from agents import roster
        from core import llm
        return llm.describe(roster.load().values())
    except Exception:                                                  # noqa: BLE001
        return []


def status(days: int = 7) -> Dict[str, Any]:
    p = business.current()
    since = _since(days)
    today = datetime.now(timezone.utc).date().isoformat()
    with store.connect() as c:
        runs = [dict(r) for r in c.execute("SELECT status, started_at, finished_at, cost_usd FROM runs WHERE started_at >= ?", (since,))]
        proofs = [dict(r) for r in c.execute("SELECT model, verdict, created_at FROM tee_proofs WHERE created_at >= ?"
                                             " ORDER BY created_at", (since,))]
        tools = [dict(r) for r in c.execute("SELECT s.tools, s.detail FROM steps s JOIN runs r ON r.id = s.run_id"
                                            " WHERE s.stage='TOOL' AND r.started_at >= ?", (since,))]
        fallbacks = c.execute("SELECT COUNT(*) FROM steps s JOIN runs r ON r.id = s.run_id WHERE s.stage='FALLBACK'"
                              " AND r.started_at >= ?", (since,)).fetchone()[0]
        stopped = c.execute("SELECT COUNT(*) FROM steps s JOIN runs r ON r.id = s.run_id WHERE s.stage='FINDING'"
                            " AND json_extract(s.detail, '$.error') = 1 AND r.started_at >= ?", (since,)).fetchone()[0]
        spent_runs = c.execute("SELECT COALESCE(SUM(cost_usd),0) FROM runs WHERE started_at >= ?", (today,)).fetchone()[0]
        spent_public = c.execute("SELECT COALESCE(SUM(cost_usd),0) FROM public_chats WHERE at >= ?", (today,)).fetchone()[0]

    by_status: Dict[str, int] = {}
    for r in runs:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    finished = [_minutes(r["started_at"], r["finished_at"]) for r in runs if r.get("finished_at")]

    attest: Dict[str, Dict[str, Any]] = {}
    for pr in proofs:
        row = attest.setdefault(pr["model"], {"attested": 0, "partial": 0, "failed": 0, "pending": 0,
                                              "last_failed_at": None, "since_last_failure": 0})
        row[pr["verdict"]] = row.get(pr["verdict"], 0) + 1
        if pr["verdict"] == "failed":
            row["last_failed_at"], row["since_last_failure"] = pr["created_at"], 0
        else:
            row["since_last_failure"] += 1

    calls: Dict[str, Dict[str, Any]] = {}
    for t in tools:
        try:
            name = (json.loads(t["tools"]) or ["?"])[0]
            d = json.loads(t["detail"] or "{}")
        except ValueError:
            continue
        row = calls.setdefault(name, {"tool": name, "calls": 0, "errors": 0, "last_error": None})
        row["calls"] += 1
        if d.get("error"):
            row["errors"] += 1
            row["last_error"] = str(d["error"])[:200]
    failing = sorted((r for r in calls.values() if r["errors"]), key=lambda r: -r["errors"])

    servers = []
    for s in store.mcp_servers():
        ts = s.get("tools") or []
        ts = json.loads(ts) if isinstance(ts, str) else ts
        agents = s.get("agents") or []
        agents = json.loads(agents) if isinstance(agents, str) else agents
        servers.append({"name": s["name"], "enabled": bool(s.get("enabled")), "agents": agents, "tools": len(ts),
                        "writers_allowed": [t["name"] for t in ts if t.get("write_allowed")],
                        "last_ok": s.get("last_ok"), "last_error": s.get("last_error")})

    from core import chain
    vault: Dict[str, Any] = {"configured": chain.configured(), "readable": chain.readable()}
    if chain.readable():
        pol = chain.policy() or {}
        vault.update({"frozen": pol.get("frozen"), "answered": bool(pol)})

    cap = float(p["constraints"]["inference_max_usd_per_day"] or 0)
    spent = round(float(spent_runs) + float(spent_public), 4)
    models = _models()

    issues: List[Dict[str, str]] = []
    for m in models:
        if not m.get("ready"):
            issues.append({"tone": "bad", "text": f"{m['name']}'s model {m['model']} cannot be called: {m.get('why')}"})
    for model, v in attest.items():
        total = sum(v.get(k, 0) for k in ("attested", "partial", "failed", "pending"))
        if v.get("failed"):
            later = v["since_last_failure"]
            # A run of good proofs after the last failure means the cause is behind us (often a provider format the
            # verifier learned since); say so, so nobody swaps a model over history.
            tail = (f"; the last was {v['last_failed_at'][:16].replace('T', ' ')} UTC and the {later} calls since all passed"
                    if later >= 10 else f"; the last was {v['last_failed_at'][:16].replace('T', ' ')} UTC")
            issues.append({"tone": "info" if later >= 10 else "warn",
                           "text": f"{model}: {v['failed']} of {total} calls failed attestation in {days} days{tail}"})
        if v.get("partial") and v["partial"] + v.get("failed", 0) == total:
            issues.append({"tone": "info", "text": f"{model}: no call fully attested; passing calls are partial because the "
                                                   "provider's report carries no nonce of ours"})
    if fallbacks:
        issues.append({"tone": "warn", "text": f"A fallback model answered {fallbacks} time(s) in {days} days (the first choice timed out or failed)"})
    if stopped:
        issues.append({"tone": "warn", "text": f"An agent stopped before finishing {stopped} time(s) (tool-round limit or error)"})
    for r in failing[:3]:
        issues.append({"tone": "warn", "text": f"Tool {r['tool']} failed {r['errors']} of {r['calls']} calls; last: {r['last_error']}"})
    open_inc = [i for i in incidents(days) if not i["resolved"]]
    for i in open_inc[:3]:
        issues.append({"tone": "bad" if i["status"] == "failed" else "warn",
                       "text": f"Run {i['status']} and not redone: {i['work']}" + (f" ({i['why'][:140]})" if i["why"] else "")})
    if cap and spent >= 0.8 * cap:
        issues.append({"tone": "bad" if spent >= cap else "warn", "text": f"AI spend today ${spent:.2f} of the ${cap:.2f} daily cap"})
    for s in servers:
        if s["last_error"]:
            issues.append({"tone": "warn", "text": f"Server {s['name']}: {s['last_error'][:160]}"})
    if vault.get("frozen"):
        issues.append({"tone": "bad", "text": "The vault is frozen: no payment can leave until the owner unfreezes it"})
    if vault.get("readable") and not vault.get("answered"):
        issues.append({"tone": "warn", "text": "The vault did not answer"})

    import os
    limits = {"run_deadline_s": int(os.environ.get("AERA_RUN_SECONDS", "1200")),
              "model_timeout_s": int(os.environ.get("AERA_MODEL_TIMEOUT_S") or 300),
              "set_in": "the service environment (AERA_RUN_SECONDS, AERA_MODEL_TIMEOUT_S); a figure in an older run's "
                        "reason may be a limit that has been changed since"}
    return {
        "days": days, "models": models, "limits": limits, "attestation": attest, "fallbacks": fallbacks, "agent_stops": stopped,
        "ai_spend": {"today_usd": spent, "cap_usd": cap},
        "runs": {"total": len(runs), "by_status": by_status,
                 "avg_minutes": round(sum(finished) / len(finished), 1) if finished else None,
                 "slowest_minutes": round(max(finished), 1) if finished else None},
        "tools": {"calls": sum(r["calls"] for r in calls.values()), "failing": failing[:10]},
        "servers": servers, "vault": vault, "issues": issues,
        "summary": ("Nothing needs attention." if not issues else f"{len(issues)} thing(s) to look at."),
    }


def incidents(days: int = 7, limit: int = 20) -> List[Dict[str, Any]]:
    with store.connect() as c:
        rows = c.execute("SELECT r.id, r.status, r.started_at, r.finished_at, r.error, r.decision, w.title,"
                         " w.status AS work_status, (SELECT COUNT(*) FROM runs r2 WHERE r2.work_item_id = r.work_item_id"
                         " AND r2.status = 'done' AND r2.started_at > r.started_at) AS redone FROM runs r"
                         " JOIN work_items w ON w.id = r.work_item_id WHERE r.status IN ('failed','held','partial')"
                         " AND r.started_at >= ? ORDER BY r.started_at DESC LIMIT ?", (_since(days), limit)).fetchall()
    out = []
    for r in rows:
        try:
            decision = json.loads(r["decision"] or "{}") or {}
        except ValueError:
            decision = {}
        why = r["error"] or (decision.get("reason") if isinstance(decision, dict) else None) or ""
        out.append({"run_id": r["id"], "status": r["status"], "work": r["title"], "started_at": r["started_at"],
                    "minutes": round(_minutes(r["started_at"], r["finished_at"]), 1) if r["finished_at"] else None,
                    "why": why[:300] or None,
                    "resolved": bool(r["redone"]) or r["work_status"] == "done",
                    "work_status": r["work_status"]})
    return out


def review_markdown(st: Dict[str, Any], inc: List[Dict[str, Any]], commentary: str, name: str) -> str:
    rs = st["runs"]
    lines = [f"# Systems review — {name}", "", f"_Filed {datetime.now(timezone.utc).strftime('%d %B %Y')}. Last {st['days']} days, computed by AERA from its own record._", "",
             "## At a glance", "", "| Measure | Value |", "|---|---:|",
             f"| Runs | {rs['total']} ({', '.join(f'{v} {k}' for k, v in rs['by_status'].items()) or 'none'}) |",
             f"| Average run | {rs['avg_minutes'] if rs['avg_minutes'] is not None else '—'} min |",
             f"| Slowest run | {rs['slowest_minutes'] if rs['slowest_minutes'] is not None else '—'} min |",
             f"| Fallback model used | {st['fallbacks']} times |",
             f"| Tool calls | {st['tools']['calls']} |",
             f"| AI spend today | ${st['ai_spend']['today_usd']:.2f} of ${st['ai_spend']['cap_usd']:.2f} |", ""]
    if st["attestation"]:
        lines += ["## Models and attestation", "", "| Model | Attested | Partial | Failed |", "|---|---:|---:|---:|"]
        for m, v in st["attestation"].items():
            lines.append(f"| {m} | {v.get('attested', 0)} | {v.get('partial', 0)} | {v.get('failed', 0)} |")
        lines.append("")
    if st["tools"]["failing"]:
        lines += ["## Failing tools", "", "| Tool | Errors | Calls | Last error |", "|---|---:|---:|---|"]
        for r in st["tools"]["failing"]:
            lines.append(f"| {r['tool']} | {r['errors']} | {r['calls']} | {(r['last_error'] or '').replace('|', '/')} |")
        lines.append("")
    if st["servers"]:
        lines += ["## Outside servers", "", "| Server | Tools | Writes allowed (with approval) | Last error |", "|---|---:|---|---|"]
        for s in st["servers"]:
            lines.append(f"| {s['name']} | {s['tools']} | {', '.join(s['writers_allowed']) or 'none'} | {s['last_error'] or '—'} |")
        lines.append("")
    lines += ["## Issues", ""] + ([f"- {i['text']}" for i in st["issues"]] or ["- None."]) + [""]
    if inc:
        lines += ["## Runs that did not finish cleanly", ""]
        lines += [f"- {i['started_at'][:16].replace('T', ' ')} · {i['status']} · {i['work']}" + (f": {i['why']}" if i["why"] else "")
                  + (" (resolved: a later run finished the work)" if i["resolved"] else f" (still {i['work_status']})") for i in inc]
        lines.append("")
    if commentary.strip():
        lines += ["## Tech Lead notes", "", commentary.strip(), ""]
    lines += ["_Figures computed by AERA; the notes above are the Tech Lead's. Settings change only when the owner changes them._"]
    return "\n".join(lines)


def demo() -> None:
    store.save_profile(business.EXAMPLE, by="check")
    wid = store.record_work_item("request", "make a brief", "api", {})
    rid = store.start_run(wid)
    store.close_run(rid, "failed", error="model timed out")
    st = status()
    assert st["runs"]["total"] >= 1 and st["runs"]["by_status"].get("failed", 0) >= 1
    assert any("failed" in i["text"] for i in st["issues"]), st["issues"]
    inc = incidents()
    assert inc and inc[0]["work"] == "make a brief" and inc[0]["why"] == "model timed out" and not inc[0]["resolved"]
    store.close_run(store.start_run(wid), "done")
    assert incidents()[0]["resolved"], "a later run that finished the work resolves the incident"
    hid = store.start_run(store.record_work_item("goal", "weekly sample", "schedule", {}))
    store.close_run(hid, "held", decision={"status": "held", "reason": "model cannot be called"})
    assert next(i for i in incidents() if i["run_id"] == hid)["why"] == "model cannot be called", "reason read from the decision"
    md = review_markdown(st, inc, "Raise the run deadline.", "Lumen")
    assert "| Runs | " in md and "make a brief: model timed out" in md and "Raise the run deadline." in md
    assert not any("make a brief" in i["text"] for i in status()["issues"]), "a resolved incident is not an issue"
    print("systems ok: runs, tools, models and servers counted ✓ · issues name their figure ✓ · incidents ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_SYSTEMS_CHECK")
    demo()
