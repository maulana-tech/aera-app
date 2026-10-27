"""The report worker: one handling, assembled into a report to send or file.

The split SIGAP's law forces (and  report generator does not make):

  * The FIGURES are deterministic. The decision, the actions and their money,
    the realized-versus-predicted outcome, the provenance of what backed the
    call — all assembled here from the database, no model involved. A number in
    this report can be recomputed from the same rows by anyone.

  * The NARRATIVE is the only thing a model writes, and only the auxiliary
    model (core/aux.py), handed the figures as facts with an explicit
    instruction never to introduce a number of its own. If the aux model is not
    available, the summary is simply omitted — the deterministic report stands
    on its own. So this works with no credentials, and gets a prose summary once
    the aux model is configured, without ever letting a model near the
    arithmetic.

This is what "offload boilerplate to the aux LLM so the agents are not
burdened" means in practice: the expensive agent team already did the
reasoning; writing it up for a human is a chore, and the cheap model does it.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from core import aux, store
from engine import export

#: Jakarta. Every time this module writes is written in it, and every period it
#: is asked for is a WIB calendar period, because the people who close the month
#: close it here. The stamps in the database are UTC.
WIB = timezone(timedelta(hours=7))


def _rp(n: Optional[float]) -> str:
    return f"Rp {int(n):,}" if isinstance(n, (int, float)) else "-"


def _actual_cost(action: dict) -> Optional[float]:
    """The realized cost recorded against an action, if any — read from the
    outcome detail written by record_outcome. Never guessed.

    `cost_idr` is deliberately NOT read here, though it once was: that is the
    key the action's own PREDICTED cost uses, so a caller echoing the payload
    into the outcome detail would have its prediction read back as the realized
    figure and every delta would come out at exactly zero — the one number this
    whole section exists to produce, silently falsified.
    """
    raw = action.get("outcome_detail")
    if not raw:
        return None
    try:
        d = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:                     # noqa: BLE001
        return None
    for k in (store.REALIZED_COST_KEY, "actual_cost_idr"):
        if isinstance(d, dict) and isinstance(d.get(k), (int, float)):
            return float(d[k])
    return None


# ================================================================= the period
#
# A rollup over "everything, ever" answers a question nobody asked: this
# month's delta and last year's land in one figure and neither can be read out
# of it again. So the portfolio takes a window, and every figure it prints says
# which window produced it.
#
# The window is given in WIB calendar days. Midnight on 1 October in Jakarta is
# 17:00 on 30 September in UTC, and a window that ignored that would file the
# first seven hours of every month under the month before — quietly, and in the
# direction that makes a bad month look better.

def _day_bounds(day: str) -> Tuple[str, str]:
    """(start, end) in UTC for one WIB calendar day. The end is exclusive."""
    d = date.fromisoformat(day)
    start = datetime(d.year, d.month, d.day, tzinfo=WIB)
    return (start.astimezone(timezone.utc).isoformat(timespec="seconds"),
            (start + timedelta(days=1)).astimezone(timezone.utc).isoformat(timespec="seconds"))


def window(since: Optional[str] = None, until: Optional[str] = None,
           days: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """The period a rollup covers: UTC bounds, and a label a reader can check.

    `days` is the last N days up to now, which is what a selector on a page
    asks for. `since`/`until` are WIB calendar dates, inclusive at both ends,
    which is what a month-end close asks for. Nothing given means all time, and
    the label says so rather than leaving the reader to assume it.

    Raises ValueError on a period that cannot be read, so a mistyped date is
    refused instead of silently widening the report to everything.
    """
    if days is not None:
        n = int(days)
        if n <= 0:
            raise ValueError("a period in days must be 1 or more")
        now = datetime.now(timezone.utc)
        return {"from": (now - timedelta(days=n)).isoformat(timespec="seconds"),
                "to": None, "days": n, "since": None, "until": None,
                "label": f"the last {n} days, to {_when(now.isoformat())}"}
    if not since and not until:
        return None
    try:
        lo = _day_bounds(since)[0] if since else None
        hi = _day_bounds(until)[1] if until else None
    except ValueError as e:
        raise ValueError(f"a period is given as YYYY-MM-DD: {e}") from e
    if lo and hi and lo >= hi:
        raise ValueError(f"the period ends before it starts: {since} to {until}")
    label = (f"{since} to {until} (WIB)" if since and until
             else f"from {since} (WIB)" if since else f"up to and including {until} (WIB)")
    return {"from": lo, "to": hi, "days": None, "since": since, "until": until, "label": label}


def period_label(w: Optional[Dict[str, Any]]) -> str:
    return w["label"] if w else "every handling on record"


def _period_sql(w: Optional[Dict[str, Any]], column: str) -> Tuple[str, List[str]]:
    """The AND clause and its parameters that keep a query inside the window."""
    if not w:
        return "", []
    sql, args = "", []
    if w.get("from"):
        sql += f" AND {column} >= ?"
        args.append(w["from"])
    if w.get("to"):
        sql += f" AND {column} < ?"
        args.append(w["to"])
    return sql, args


# ====================================================== what the rules cost
#
# engine/simulate.py computes this and tools/simulation.py returns it, which
# until now meant it reached the model and stopped there. It is the figure that
# turns a veto from an assertion into a priced decision — "obeying TKDN cost
# Rp 46m, and here is the rule that cost it" — so it belongs on the record a
# manager reads, not only in the conversation the agents had.

#: The tool whose result carries it.
_COSTING_TOOL = "simulate_scenario"


def _tool_results(run: dict) -> List[Tuple[dict, str, Any]]:
    """(step, tool name, result) for every tool call in the run that returned
    something and did not fail."""
    out = []
    for s in run.get("steps") or []:
        if s.get("stage") != "TOOL":
            continue
        d = s.get("detail") or {}
        if d.get("error"):
            continue
        out.append((s, str(d.get("name") or (s.get("tools") or ["?"])[0]), d.get("result")))
    return out


def _compliance_cost(run: dict) -> Optional[dict]:
    """What obeying the rules cost on this handling, read from the record.

    The LAST costing wins: a handling may cost a scenario, learn something and
    cost it again, and the figure the decision was taken on is the final one.
    None when nothing that was struck out would have been cheaper anyway —
    which is not the same as zero, and is why this returns None.
    """
    found = None
    for step, name, result in _tool_results(run):
        if name != _COSTING_TOOL or not isinstance(result, dict):
            continue
        cc = result.get("compliance_cost")
        if isinstance(cc, dict) and isinstance(cc.get("idr"), (int, float)):
            found = dict(cc) | {"step": step.get("seq")}
    return found


def _rules_applied(run: dict) -> Optional[Dict[str, Any]]:
    """Which rules this handling actually applied, and how many of them nobody
    has checked against a source.

    Read from the steps, not from the pack as it stands today: the report says
    what was true when the decision was taken, and a pack verified next week
    does not retroactively verify last week's call. Returns None when no rule
    was read at all, which is a different state from "all of them verified".
    """
    verified: Dict[str, bool] = {}
    problems: List[str] = []
    pack: Optional[str] = None
    for _step, _name, result in _tool_results(run):
        if not isinstance(result, dict):
            continue
        for r in result.get("rules") or []:
            if isinstance(r, dict) and r.get("rule"):
                name = str(r["rule"])
                # AND across every reading: a rule read once as an assumption
                # and once as verified was an assumption when it was applied.
                verified[name] = bool(r.get("verified")) and verified.get(name, True)
        for p in result.get("problems") or []:
            if isinstance(p, str) and p not in problems:
                problems.append(p)
        if result.get("pack"):
            pack = str(result["pack"])
    if not verified:
        return None
    unverified = sorted(n for n, ok in verified.items() if not ok)
    return {"total": len(verified), "verified": len(verified) - len(unverified),
            "unverified": unverified, "problems": problems, "pack": pack}


# ================================================= evidence from outside
#
# Two tools reach the open web: Milo's `search_news` (Google News headlines,
# each with its publisher and link) and his `web_brief` (a web-search model that
# answers with the pages it read). Both already land in the workbook, because
# every tool's rows do — but the PDF carried only a count of them, and the PDF
# is what leaves the building. A reader could see that six headlines were read
# and had no way to check a single one.
#
# What goes in is the link and who published it, never the claim as fact. A
# headline is somebody else's assertion; the report cites it as reported.

def _outside_evidence(run: dict) -> List[Dict[str, Any]]:
    """Every page the handling read from the open web, with where to find it."""
    out: List[Dict[str, Any]] = []
    seen = set()
    for step, name, result in _tool_results(run):
        if not isinstance(result, dict):
            continue
        detail = step.get("detail") or {}
        when = detail.get("fetched_at") or step.get("at")
        if name == "search_news":
            for h in result.get("headlines") or []:
                if not isinstance(h, dict):
                    continue
                url = str(h.get("url") or h.get("link") or "")
                key = url or str(h.get("title") or h.get("headline"))
                if key in seen:
                    continue
                seen.add(key)
                out.append({"kind": "headline", "step": step.get("seq"),
                            "asked": result.get("query"),
                            "title": str(h.get("title") or h.get("headline") or ""),
                            "by": str(h.get("publisher") or h.get("source") or ""),
                            "when": str(h.get("published_at") or h.get("published")
                                        or h.get("time") or when or ""),
                            "url": url})
        elif name == "web_brief":
            for c in result.get("citations") or []:
                url = c if isinstance(c, str) else str((c or {}).get("url") or "")
                title = "" if isinstance(c, str) else str((c or {}).get("title") or "")
                if not url or url in seen:
                    continue
                seen.add(url)
                out.append({"kind": "citation", "step": step.get("seq"),
                            "asked": result.get("question"),
                            "title": title, "by": "cited by the web-search model",
                            "when": str(when or ""), "url": url})
    return out


def _rules_sentence(applied: Optional[Dict[str, Any]]) -> Optional[str]:
    """The rule-trust state of a decision, in words. The provenance labels say
    this per figure; a reader of the report deserves it in one line."""
    if not applied:
        return None
    if not applied["unverified"]:
        return (f"All {applied['total']} rules applied here are verified against the "
                "document they were read from.")
    return (f"{len(applied['unverified'])} of the {applied['total']} rules applied here are "
            "not verified against a source, so they are assumptions written down rather "
            "than rules: " + ", ".join(applied["unverified"])
            + (". Problems in the pack: " + "; ".join(applied["problems"])
               if applied["problems"] else ""))


def _deterministic_markdown(run: dict) -> str:
    """The report body, figures and all, assembled from the run. Pure: no model."""
    lines: List[str] = [
        f"# {run['title']}", "",
        f"Kind     : {run['kind']}",
        f"Trigger  : {run['trigger']}",
        f"Started  : {run['started_at']}",
        f"Status   : {run['status']}" + (f" ({run['mode']})" if run.get("mode") == "guided" else ""),
        "",
    ]

    decision = run.get("decision")
    if decision:
        body = decision.get("recommendation") or decision.get("reason") or "not recorded"
        lines += ["## Decision", "", body, ""]
        untrusted = decision.get("untrusted_on_board")
        if isinstance(untrusted, list) and untrusted:
            lines += [f"> Not yet trustworthy: {', '.join(untrusted)}.", ""]
        rules = _rules_sentence(_rules_applied(run))
        if rules:
            lines += [f"> {rules}", ""]

    cc = _compliance_cost(run)
    if cc:
        lines += [
            "## What the rules cost", "",
            f"Obeying the rules on this disruption cost **{_rp(cc['idr'])}**.", "",
            "| | Plan | Cost |", "|---|---|---|",
            f"| Chosen | {', '.join(cc.get('chosen') or []) or '-'} | {_rp(cc.get('chosen_cost_idr'))} |",
            f"| Cheaper, but struck out | {', '.join(cc.get('cheaper_but_blocked') or []) or '-'} "
            f"| {_rp(cc.get('cheaper_cost_idr'))} |",
            "",
        ]
        for b in cc.get("blocked_by") or []:
            lines.append(f"- **{b.get('id')}** {b.get('label') or ''} — {b.get('reason') or ''}")
        lines += ["", "> This is the price of the rule, not an overrun. It is stated so the "
                      "decision can be defended and so nobody has to re-derive it later.", ""]

    actions = run.get("actions") or []
    if actions:
        # Realized vs predicted — the half that proves the recommendation was
        # worth following. Present only when an outcome has actually been
        # recorded, never a placeholder.
        settled = [a for a in actions if a.get("outcome")]
        if settled:
            lines += ["## Outcome: realized vs predicted", "",
                      "| Action | Predicted | Actual | Delta |", "|---|---|---|---|"]
            blank = 0
            for a in settled:
                pred = a["payload"].get("cost_idr")
                act = _actual_cost(a)
                delta = (act - pred) if isinstance(pred, (int, float)) and isinstance(act, (int, float)) else None
                if delta is None:
                    blank += 1
                lines.append(f"| {a['kind']} ({a['outcome']}) | {_rp(pred)} | {_rp(act)} | {_rp(delta)} |")
            lines.append("")
            if blank:
                # A dash is honest per row, but a reader scanning the table
                # needs telling that the comparison is partial.
                lines += [f"> {blank} of {len(settled)} recorded outcome(s) carry no realized "
                          "figure, so no delta can be stated for them. A blank is "
                          "'not known', never zero.", ""]
        owed = [a for a in actions
                if not a.get("outcome") and a.get("status") in ("sent", "approved")
                and a["kind"] in store.AWAITS_OUTCOME]
        if owed:
            lines += [f"> {len(owed)} action(s) that went out still owe an outcome: "
                      + ", ".join(a["kind"] for a in owed)
                      + ". Until they are recorded the realized side of this handling is "
                        "incomplete.", ""]

        lines += ["## Actions", "", "| Action | Value | Status |", "|---|---|---|"]
        for a in actions:
            lines.append(f"| {a['kind']} | {_rp(a['payload'].get('cost_idr'))} | {a['status']} |")
        lines.append("")

    evidence = _outside_evidence(run)
    if evidence:
        lines += ["## Evidence from outside", "",
                  "What this handling read from the open web, so it can be checked rather "
                  "than taken on trust. A headline is the publisher's claim, cited here as "
                  "reported and not as fact.", ""]
        for e in evidence:
            who = f" — {e['by']}" if e["by"] else ""
            when = f" · {e['when']}" if e["when"] else ""
            lines.append(f"- {e['title'] or e['url']}{who}{when}")
            if e["url"]:
                lines.append(f"  <{e['url']}>")
        lines.append("")

    steps = run.get("steps") or []
    if steps:
        lines += ["## How the system reasoned", ""]
        for s in steps:
            origin = f" [{s['origin']}]" if s.get("origin") else ""
            lines.append(f"{s['seq']}. **{s['stage']}** · {s.get('agent_name', '-')}, "
                         f"{s.get('summary', '')}{origin}")
        lines.append("")

    approvals = run.get("approvals") or []
    if approvals:
        lines += ["## Approvals", ""]
        for p in approvals:
            lines.append(f"- {p['decision']} by {p['decided_by']} ({p['role']}) · {p['at']}")
        lines.append("")

    lines += ["---", f"Generated by SIGAP · {store._now()}"]
    return "\n".join(lines)


def _facts_digest(run: dict) -> str:
    """The factual skeleton handed to the aux model. Only facts, so the model
    has nothing to invent — it reorders and phrases, it does not compute."""
    d = run.get("decision") or {}
    actions = run.get("actions") or []
    bits = [
        f"event: {run['title']} ({run['kind']})",
        f"trigger: {run['trigger']}",
        f"status: {run['status']}",
    ]
    rec = d.get("recommendation") or d.get("reason")
    if rec:
        bits.append(f"decision: {rec[:600]}")
    for a in actions:
        pred = a["payload"].get("cost_idr")
        act = _actual_cost(a)
        tail = (f", actual {_rp(act)}" if act is not None else
                ", realized cost NOT known — do not state one" if a.get("outcome") else "")
        bits.append(f"action: {a['kind']} — {a['status']}"
                    + (f", outcome {a['outcome']}" if a.get("outcome") else "")
                    + f", predicted {_rp(pred)}{tail}")
    cc = _compliance_cost(run)
    if cc:
        bits.append(f"what the rules cost: {_rp(cc['idr'])} — "
                    f"{', '.join(cc.get('chosen') or []) or 'the chosen plan'} at "
                    f"{_rp(cc.get('chosen_cost_idr'))} instead of "
                    f"{', '.join(cc.get('cheaper_but_blocked') or []) or 'a cheaper plan'} at "
                    f"{_rp(cc.get('cheaper_cost_idr'))}, struck out by: "
                    + "; ".join(f"{b.get('id')} {b.get('reason') or ''}"
                                for b in cc.get("blocked_by") or []))
    rules = _rules_sentence(_rules_applied(run))
    if rules:
        bits.append(f"rule trust: {rules}")
    untrusted = d.get("untrusted_on_board")
    if isinstance(untrusted, list) and untrusted:
        bits.append(f"caveat: not yet trustworthy — {', '.join(untrusted)}")
    return "\n".join(bits)


_SUMMARY_SYSTEM = (
    "You write the executive summary of a supply-chain disruption report for a "
    "manager. Two or three plain sentences. Use ONLY the facts given; never "
    "introduce a number, supplier, date or claim that is not in them, and never "
    "recompute or estimate a figure. State what happened, what was decided, and "
    "the residual risk if one is noted. No preamble, no heading — just the summary."
)


def build_report(run_id: str) -> Optional[Dict[str, Any]]:
    """Assemble one run into a report. Returns None when the run does not exist.

    The body is deterministic; an executive summary is prepended only when the
    aux model writes one (fail-open — the report is complete without it)."""
    run = store.get_run(run_id)
    if not run:
        return None

    body = _deterministic_markdown(run)

    summary = _summary(run)
    if summary:
        # Insert the summary just under the title, labelled so a reader knows a
        # model phrased it (the figures below it did not come from the model).
        head, _, rest = body.partition("\n\n")
        body = f"{head}\n\n## Summary\n\n{summary}\n\n{rest}"

    applied = _rules_applied(run)
    return {
        "run_id": run_id,
        "title": run["title"],
        "markdown": body,
        "summary_by": "aux" if summary else None,
        "summary": summary or None,
        # Both of these are in the markdown already. They are returned as data
        # as well because the page lays the report out itself rather than
        # rendering the markdown, and these two must not be page-only prose.
        "compliance_cost": _compliance_cost(run),
        "rules_applied": applied,
        "rules_note": _rules_sentence(applied),
        # Every page the handling read from the open web, with its link, so the
        # page can show what the PDF now carries.
        "evidence": _outside_evidence(run),
        # What the workbook will hold, so the page can say so before the download.
        "sheets": _sheet_list(run_sheets(run)),
    }


def _sheet_list(sheets: List[export.Sheet]) -> List[Dict[str, Any]]:
    return [{"name": n, "rows": len(sh.rows)}
            for n, sh in zip(export.sheet_names([x.name for x in sheets]), sheets)]


# The summary is the one part a model writes. It is asked for once per state of
# the run (status and each action's status and outcome), not on every page view
# or download. A failed call is not remembered, so the next view tries again.
_SUMMARIES: Dict[str, str] = {}


def _summary(run: dict) -> Optional[str]:
    key = json.dumps([run["id"], run.get("status"), run.get("finished_at"),
                      [(a["id"], a.get("status"), a.get("outcome")) for a in run.get("actions") or []]])
    if key not in _SUMMARIES:
        text = aux.generate(_SUMMARY_SYSTEM, _facts_digest(run), max_tokens=256)
        if not text:
            return None
        if len(_SUMMARIES) > 256:
            _SUMMARIES.clear()
        _SUMMARIES[key] = text
    return _SUMMARIES[key]


_PORTFOLIO_SYSTEM = (
    "You write a short executive summary of a supply-chain operations report "
    "that covers many disruptions over a period, for a manager. Two or three "
    "plain sentences. Use ONLY the figures given; never introduce or recompute a "
    "number. Say how much was handled, how the realized cost compared with what "
    "was predicted, and any standing exposure noted. No heading, just the summary."
)


def portfolio_metrics(w: Optional[Dict[str, Any]] = None, *,
                      runs: Optional[List[dict]] = None,
                      actions: Optional[List[dict]] = None,
                      costs: Optional[List[dict]] = None) -> Dict[str, Any]:
    """Aggregate figures across the handlings in the window. Pure, deterministic.

    The rows can be handed in, because a report needs the same rows for its
    tables and reading them twice is how a page ends up scanning the whole
    database to print one tile.
    """
    runs = _all_runs(w) if runs is None else runs
    actions = _all_actions(w) if actions is None else actions
    costs = compliance_costs(w) if costs is None else costs

    by_status: Dict[str, int] = {}
    by_kind: Dict[str, int] = {}
    trusted = untrusted = 0
    for r in runs:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
        dec = r["decision"]
        if dec:
            try:
                parsed = json.loads(dec) if isinstance(dec, str) else dec
                u = parsed.get("untrusted_on_board")
                if isinstance(u, list) and u:
                    untrusted += 1
                else:
                    trusted += 1
            except Exception:             # noqa: BLE001
                pass

    predicted_all = 0.0
    settled_pred = settled_actual = 0.0
    settled = with_cost = awaiting = 0
    by_outcome: Dict[str, int] = {}
    for a in actions:
        try:
            p = json.loads(a["payload"]) if isinstance(a["payload"], str) else a["payload"]
        except Exception:                 # noqa: BLE001
            p = {}
        pc = p.get("cost_idr")
        if isinstance(pc, (int, float)):
            predicted_all += pc
        if a.get("outcome"):
            settled += 1
            by_outcome[a["outcome"]] = by_outcome.get(a["outcome"], 0) + 1
            act = _actual_cost(a)
            # Both halves or neither: a realized figure without its prediction
            # cannot be compared, and counting one side alone would move the
            # delta by the whole of it.
            if isinstance(pc, (int, float)) and isinstance(act, (int, float)):
                with_cost += 1
                settled_pred += pc
                settled_actual += act
        elif a.get("status") in ("sent", "approved") and a["kind"] in store.AWAITS_OUTCOME:
            # The denominator. A delta drawn from one action out of forty reads
            # as the whole truth unless the other thirty-nine are counted here.
            awaiting += 1

    kb = _rule_pack_status()
    return {
        "period": w,
        "period_label": period_label(w),
        "runs_total": len(runs),
        "by_status": by_status,
        "by_kind": by_kind,
        "decided_on_trusted": trusted,
        "decided_with_untrusted": untrusted,
        "actions_total": len(actions),
        "actions_sent": sum(1 for a in actions if a["status"] == "sent"),
        "actions_pending": sum(1 for a in actions if a["status"] == "pending"),
        "predicted_idr_total": round(predicted_all),
        # `settled_actions` counts recorded outcomes; `settled_with_cost` counts
        # the ones that can actually be compared. They are different numbers and
        # printing the first beside the delta is what made a report of three
        # outcomes with no figures announce "exactly at prediction".
        "settled_actions": settled,
        "settled_with_cost": with_cost,
        "settled_without_cost": settled - with_cost,
        "by_outcome": by_outcome,
        "awaiting_outcome": awaiting,
        "settled_predicted_idr": round(settled_pred),
        "settled_actual_idr": round(settled_actual),
        "settled_delta_idr": round(settled_actual - settled_pred),
        # What obeying the rules cost, across the window.
        "rules_cost_idr": round(sum(c["idr"] for c in costs)),
        "rules_cost_cases": len(costs),
        "knowledge_base": kb,
    }


def _rule_pack_status() -> Dict[str, Any]:
    """The knowledge base's trust state as it stands now. Imported here rather
    than at the top because a report is not part of the ruling path."""
    from tools.compliance import pack_status
    return pack_status()


def _delta_sentence(m: Dict[str, Any]) -> str:
    """The realized-versus-predicted result in one line, with the part of the
    book it was drawn from. Never asserts a comparison it cannot make."""
    if not m["settled_with_cost"]:
        if m["settled_actions"]:
            return (f"{m['settled_actions']} outcome(s) are recorded but none carries a "
                    "realized figure, so no comparison with the prediction can be made.")
        return ("No action has a recorded outcome in this period, so realized cost cannot "
                "be stated — the predicted figures stand alone.")
    delta = m["settled_delta_idr"]
    side = "under" if delta < 0 else "over" if delta > 0 else "exactly at"
    tail = ""
    if m["settled_without_cost"]:
        tail += (f" A further {m['settled_without_cost']} recorded outcome(s) carry no "
                 "figure and are not in this comparison.")
    if m["awaiting_outcome"]:
        tail += f" {m['awaiting_outcome']} action(s) that went out still owe an outcome."
    return (f"Across {m['settled_with_cost']} comparable action(s), realized cost came in "
            f"{side} prediction by {_rp(abs(delta))}." + tail)


def _portfolio_markdown(m: Dict[str, Any]) -> str:
    def _dist(d: Dict[str, int]) -> str:
        return ", ".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda x: -x[1])) or "none"
    kb = m["knowledge_base"]
    lines = [
        "# Operations report", "",
        f"Period      : {m['period_label']}",
        f"Runs        : {m['runs_total']} ({_dist(m['by_status'])})",
        f"By kind     : {_dist(m['by_kind'])}",
        f"Decisions   : {m['decided_on_trusted']} on fully-trusted evidence, "
        f"{m['decided_with_untrusted']} carried a trust caveat",
        "",
        "## Actions", "",
        f"- raised: {m['actions_total']} ({m['actions_sent']} sent, {m['actions_pending']} awaiting approval)",
        f"- committed value (predicted): {_rp(m['predicted_idr_total'])}",
        f"- outcomes recorded: {m['settled_actions']}"
        + (f" ({_dist(m['by_outcome'])})" if m["by_outcome"] else "")
        + f", still owed: {m['awaiting_outcome']}",
        "",
        "## Realized vs predicted", "",
    ]
    if m["settled_with_cost"]:
        lines += [
            "| | Predicted | Actual | Delta |", "|---|---|---|---|",
            f"| {m['settled_with_cost']} comparable action(s) | {_rp(m['settled_predicted_idr'])} "
            f"| {_rp(m['settled_actual_idr'])} | {_rp(m['settled_delta_idr'])} |",
            "",
        ]
    lines += [f"> {_delta_sentence(m)}", ""]

    lines += ["## What the rules cost", ""]
    if m["rules_cost_cases"]:
        lines += [f"Across {m['rules_cost_cases']} disruption(s) a cheaper plan was struck out "
                  f"by a rule, and taking the compliant one instead cost "
                  f"**{_rp(m['rules_cost_idr'])}**.", "",
                  "> This is the price of the rules, not an overrun. Each case names the rule "
                  "that struck the cheaper plan; see the handling's own report.", ""]
    else:
        lines += ["No disruption in this period had a cheaper plan struck out by a rule, so "
                  "obeying them cost nothing that can be measured.", ""]

    lines += ["## The rules themselves", "",
              f"{kb['verified']} of {kb['total']} rules are verified against the document they "
              "were read from"
              + (f"; assumptions: {', '.join(kb['unverified'])}" if kb["unverified"] else "")
              + ".", ""]
    if not kb["pack"]:
        lines += ["> No rule pack is installed, so every rule above is a built-in assumption "
                  "or the company's own profile figure.", ""]
    for p in kb["problems"]:
        lines.append(f"- {p}")
    if kb["problems"]:
        lines.append("")

    lines += ["---", f"Generated by SIGAP · {_when(store._now())}"]
    return "\n".join(lines)


def _portfolio_data(w: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Every row a portfolio report needs, read once.

    The page used to scan the runs and the actions to compute its figures, then
    scan both again to build the workbook — two full passes per view, on a
    route that is never cached. One pass, passed down.
    """
    runs, actions = _all_runs(w), _all_actions(w)
    costs = compliance_costs(w)
    return {"window": w, "runs": runs, "actions": actions, "costs": costs,
            "metrics": portfolio_metrics(w, runs=runs, actions=actions, costs=costs)}


def build_portfolio(since: Optional[str] = None, until: Optional[str] = None,
                    days: Optional[int] = None) -> Dict[str, Any]:
    """The portfolio report: the handlings in the period rolled up, figures
    deterministic, an aux executive summary on top when the model is available."""
    data = _portfolio_data(window(since, until, days))
    m, runs, actions, costs = data["metrics"], data["runs"], data["actions"], data["costs"]
    body = _portfolio_markdown(m)
    summary = _portfolio_summary(m)
    if summary:
        head, _, rest = body.partition("\n\n")
        body = f"{head}\n\n## Summary\n\n{summary}\n\n{rest}"
    sheets = portfolio_sheets(m, runs=runs, actions=actions, costs=costs)
    return {"title": "Operations report", "markdown": body,
            "metrics": m, "summary_by": "aux" if summary else None,
            "summary": summary or None,
            "handlings": [{k: r[k] for k in ("id", "title", "kind", "status", "mode", "started_at",
                                             "finished_at", "steps", "tools", "actions", "token_cost_idr")}
                          for r in runs],
            "actions": [{"id": a["id"], "run_id": a["run_id"], "title": a["title"], "kind": a["kind"],
                         "status": a["status"], "autonomous": bool(a.get("autonomous")),
                         "what": _payload_text(a["payload"]), "cost_idr": a["payload"].get("cost_idr"),
                         "created_at": a.get("created_at"), "outcome": a.get("outcome"),
                         "outcome_at": a.get("outcome_at"), "actual_idr": _actual_cost(a),
                         "awaiting_outcome": bool(not a.get("outcome")
                                                  and a["status"] in ("sent", "approved")
                                                  and a["kind"] in store.AWAITS_OUTCOME)}
                        for a in actions],
            "compliance_costs": costs,
            "sheets": _sheet_list(sheets)}


def _portfolio_summary(m: Dict[str, Any]) -> Optional[str]:
    """The one paragraph a model writes over these figures, asked for once per
    set of figures. It is handed facts only, and told in words when a realized
    cost does not exist, because a zero delta reads as "came in on budget"."""
    kb = m["knowledge_base"]
    facts = (f"period: {m['period_label']}; "
             f"runs: {m['runs_total']} ({m['by_status']}); kinds: {m['by_kind']}; "
             f"actions raised: {m['actions_total']}, sent {m['actions_sent']}, "
             f"pending {m['actions_pending']}; predicted total {_rp(m['predicted_idr_total'])}; "
             + (f"comparable settled actions {m['settled_with_cost']}, predicted "
                f"{_rp(m['settled_predicted_idr'])}, actual {_rp(m['settled_actual_idr'])}, "
                f"delta {_rp(m['settled_delta_idr'])}; "
                if m["settled_with_cost"] else
                # Zeros here read as "came in on budget". Nothing is comparable,
                # so the model is told not to compare.
                "NO action has both a prediction and a realized figure, so the realized "
                "cost is NOT known; do not state or compare a realized cost; ")
             + f"outcomes recorded {m['settled_actions']}, of which "
             f"{m['settled_without_cost']} carry no figure; actions still owing an outcome "
             f"{m['awaiting_outcome']}; "
             + (f"obeying the rules cost {_rp(m['rules_cost_idr'])} across "
                f"{m['rules_cost_cases']} disruption(s); " if m["rules_cost_cases"] else
                "no cheaper plan was struck out by a rule, so obeying them cost nothing "
                "measurable; ")
             + f"rules verified {kb['verified']} of {kb['total']}; "
             f"decisions on trusted evidence {m['decided_on_trusted']}, "
             f"with a caveat {m['decided_with_untrusted']}")
    if facts not in _SUMMARIES:
        text = aux.generate(_PORTFOLIO_SYSTEM, facts, max_tokens=256)
        if text:
            if len(_SUMMARIES) > 256:
                _SUMMARIES.clear()
            _SUMMARIES[facts] = text
    return _SUMMARIES.get(facts)


# ===================================================== files to take away
#
# The same record, as a PDF to read or send and a workbook to work in. Both are
# built from the run itself (never from the page), so a download says exactly
# what the log says. The workbook carries every table the handling produced:
# the actions, the steps, any table in the decision, and every row each tool
# read, one sheet per tool.

_STAGE = {"DELEGATE": "Delegation", "TOOL": "Data check", "FINDING": "Finding",
          "SUMMARY": "Answer", "FALLBACK": "Fallback", "START": "Trigger", "DONE": "Completed"}


def _when(t: Optional[str]) -> str:
    """A stored UTC time, as Jakarta reads it."""
    if not t:
        return ""
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(WIB).strftime("%d %b %Y %H:%M WIB")
    except ValueError:
        return t


def _nicknames() -> Dict[str, str]:
    from agents.definitions import ALL
    return {code: a.nickname for code, a in ALL.items()}


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:80] or "report"


def _args(d: dict) -> str:
    return ", ".join(f"{k}={v if isinstance(v, str) else json.dumps(v, default=str)}"
                     for k, v in (d.get("arguments") or {}).items())


def _what(s: dict) -> str:
    """One step, in a sentence: the call it made, the task it got, what it found."""
    d = s.get("detail") or {}
    if s["stage"] == "TOOL":
        name = d.get("name") or (s.get("tools") or ["?"])[0]
        tail = f" -> error: {d['error']}" if d.get("error") else ""
        return f"{name}({_args(d)}){tail}"
    if s["stage"] == "DELEGATE":
        return d.get("task") or s.get("summary") or ""
    return d.get("full_summary") or d.get("summary") or s.get("summary") or ""


def _excerpt(text: str) -> str:
    """A model's markdown as one run of plain text, for a table cell."""
    out = []
    for line in (text or "").split("\n"):
        line = line.strip()
        if not line or re.match(r"^(-{3,}|\*{3,}|_{3,}|\|?\s*:?-{2,}.*)$", line):
            continue
        line = re.sub(r"^#+\s*|^>\s*|^[-*+]\s+|\*\*|__|`", "", line).replace("|", " ").strip()
        if line:
            out.append(line if line[-1] in ".:;!?" else line + ".")
    return re.sub(r"\s+", " ", " ".join(out))


def _payload_text(p: dict) -> str:
    """An action's payload as a reader would say it."""
    bits = []
    if p.get("material"):
        bits.append(str(p["material"]))
    if p.get("from_plant") or p.get("to_plant"):
        bits.append(f"{p.get('from_plant', '?')} -> {p.get('to_plant', '?')}")
    if p.get("supplier"):
        bits.append(f"supplier {p['supplier']}")
    if isinstance(p.get("qty"), (int, float)):
        bits.append(f"qty {p['qty']:,}")
    if p.get("needed_by"):
        bits.append(f"by {p['needed_by']}")
    if p.get("role"):
        bits.append(f"to {p['role']}")
    text = " · ".join(bits)
    for k in ("message", "rationale"):
        if p.get(k):
            text += (": " if text else "") + str(p[k])
            break
    return text


def _rows_of(result: Any) -> List[dict]:
    """A tool's result as table rows: a list of records as they are, one record
    as one row, a record holding a list of records as that list (with the
    record's own plain fields on every row). Anything else is not a table."""
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)]
    if not isinstance(result, dict) or "idempotency_key" in result:   # an action record
        return []
    lists = [(k, v) for k, v in result.items()
             if isinstance(v, list) and v and all(isinstance(x, dict) for x in v)]
    plain = {k: v for k, v in result.items() if not isinstance(v, (list, dict))}
    if lists:
        _, longest = max(lists, key=lambda kv: len(kv[1]))
        return [{**plain, **row} for row in longest]
    return [result]


def _cell(v: Any) -> Any:
    return v if v is None or isinstance(v, (str, int, float, bool)) else json.dumps(v, default=str, ensure_ascii=False)


def data_tables(run: dict) -> List[Tuple[str, List[str], List[List[Any]]]]:
    """Every row every tool read during the handling, one table per tool, each
    row saying which step read it, with what arguments, from where."""
    names = _nicknames()
    by_tool: Dict[str, List[dict]] = {}
    for s in run.get("steps") or []:
        if s["stage"] != "TOOL":
            continue
        d = s.get("detail") or {}
        rows = _rows_of(d.get("result"))
        if not rows or d.get("error"):
            continue
        tool = d.get("name") or (s.get("tools") or ["?"])[0]
        lead = {"Step": s["seq"], "Agent": names.get(s.get("agent"), s.get("agent")), "Arguments": _args(d)}
        tail = {"Origin": d.get("origin") or s.get("origin"), "Source": d.get("source") or s.get("source")}
        by_tool.setdefault(tool, []).extend({**lead, **r, **tail} for r in rows)
    out = []
    for tool, rows in by_tool.items():
        cols: List[str] = []
        for r in rows:
            cols += [k for k in r if k not in cols and k not in ("Origin", "Source")]
        cols += ["Origin", "Source"]
        out.append((tool, cols, [[_cell(r.get(c)) for c in cols] for r in rows]))
    return out


def run_sheets(run: dict, include_data: bool = True) -> List[export.Sheet]:
    """The handling as a workbook.

    `include_data` carries the per-tool sheets: every row every tool read,
    supplier prices among them. That is exactly what an auditor sitting inside
    the company wants and exactly what should not leave it by accident, so a
    report that is emailed out is built without them (notify.files_for) unless
    the installation says otherwise.
    """
    names = _nicknames()
    d = run.get("decision") or {}
    actions = run.get("actions") or []
    steps = run.get("steps") or []
    tools = [s for s in steps if s["stage"] == "TOOL"]
    summary = [
        ["Handling", run["title"]], ["Run", run["id"]], ["Kind", run["kind"]],
        ["Trigger", run.get("trigger")], ["Status", run["status"]], ["Mode", run.get("mode")],
        ["Started", _when(run.get("started_at"))], ["Finished", _when(run.get("finished_at"))],
        ["Steps", len(steps)], ["Tool calls", len(tools)], ["Actions", len(actions)],
        ["Model cost (IDR)", run.get("token_cost_idr") or 0],
        ["Decision", d.get("recommendation") or d.get("reason") or "not recorded"],
    ]
    if isinstance(d.get("untrusted_on_board"), list) and d["untrusted_on_board"]:
        summary.append(["Not yet trustworthy", ", ".join(d["untrusted_on_board"])])
    applied = _rules_applied(run)
    if applied:
        summary.append(["Rules verified", f"{applied['verified']} of {applied['total']}"])
        if applied["unverified"]:
            summary.append(["Rules assumed", ", ".join(applied["unverified"])])
    cc = _compliance_cost(run)
    if cc:
        summary.append(["What the rules cost (IDR)", cc["idr"]])
    sheets = [export.Sheet("Summary", ["Field", "Value"], summary, pairs=True)]

    if cc:
        sheets.append(export.Sheet("Compliance cost", ["Field", "Value"], [
            ["Chosen plan", ", ".join(cc.get("chosen") or [])],
            ["Chosen cost (IDR)", cc.get("chosen_cost_idr")],
            ["Cheaper plan, struck out", ", ".join(cc.get("cheaper_but_blocked") or [])],
            ["Cheaper cost (IDR)", cc.get("cheaper_cost_idr")],
            ["What the rules cost (IDR)", cc["idr"]],
            *[[f"Struck out: {b.get('id')} {b.get('label') or ''}".strip(), b.get("reason")]
              for b in cc.get("blocked_by") or []],
        ], pairs=True))

    if actions:
        keys: List[str] = []
        for a in actions:
            keys += [k for k in a["payload"] if k not in keys and not k.startswith("_")]
        cols = ["Action ID", "Action", "Status", "Autonomous"] + keys + \
               ["Created", "SAP reference", "Outcome", "Actual IDR"]
        sheets.append(export.Sheet("Actions", cols, [
            [a["id"], a["kind"], a["status"], bool(a.get("autonomous"))]
            + [_cell(a["payload"].get(k)) for k in keys]
            + [_when(a.get("created_at")), a.get("sap_reference"), a.get("outcome"), _actual_cost(a)]
            for a in actions]))
    approvals = run.get("approvals") or []
    if approvals:
        sheets.append(export.Sheet("Approvals", ["Action ID", "Decision", "By", "Role", "Note", "At"], [
            [p.get("action_id"), p["decision"], p["decided_by"], p["role"], p.get("note"), _when(p["at"])]
            for p in approvals]))
    if steps:
        sheets.append(export.Sheet("Steps", ["#", "At", "Stage", "Agent", "What", "Rows", "Origin", "Source"], [
            [s["seq"], _when(s.get("at")), _STAGE.get(s["stage"], s["stage"].title()),
             names.get(s.get("agent"), s.get("agent")), _what(s),
             (s.get("detail") or {}).get("rows") if s["stage"] == "TOOL" else None,
             s.get("origin") or (s.get("detail") or {}).get("origin"),
             s.get("source") or (s.get("detail") or {}).get("source")]
            for s in steps]))
    evidence = _outside_evidence(run)
    if evidence:
        sheets.append(export.Sheet("Evidence from outside", [
            "Step", "Kind", "Asked", "What was read", "Published by", "When", "Where"], [
            [e["step"], e["kind"], e["asked"], e["title"], e["by"], e["when"], e["url"]]
            for e in evidence]))
    for i, (heading, cols, rows) in enumerate(export.md_tables(d.get("recommendation") or ""), start=1):
        sheets.append(export.Sheet(f"Decision - {heading or f'table {i}'}", cols, rows))
    if include_data:
        for tool, cols, rows in data_tables(run):
            sheets.append(export.Sheet(tool, cols, rows))
    return sheets


def run_pdf(run: dict) -> bytes:
    names = _nicknames()
    d = run.get("decision") or {}
    actions = run.get("actions") or []
    steps = run.get("steps") or []
    tools = [s for s in steps if s["stage"] == "TOOL"]
    status = run["status"] + (" (guided)" if run.get("mode") == "guided" else "")

    doc = export.Doc(run["title"], kicker="SIGAP · Disruption report", subtitle=run.get("trigger") or "",
                     footer=f"SIGAP · {run['title']} · {run['id']}")
    doc.facts([("Kind", run["kind"]), ("Status", status), ("Model cost", _rp(run.get("token_cost_idr") or 0)),
               ("Started", _when(run.get("started_at"))),
               ("Finished", _when(run.get("finished_at")) or "still running"),
               ("Steps · tool calls", f"{len(steps)} · {len(tools)}")])

    summary = _summary(run)
    if summary:
        doc.h2("Summary").md(summary)
        doc.p("Phrased by the auxiliary model from the figures below; it was given no number to invent.",
              size=7.5, muted=True)
    doc.h2("Decision").md(d.get("recommendation") or d.get("reason") or "No decision was recorded.")
    if isinstance(d.get("untrusted_on_board"), list) and d["untrusted_on_board"]:
        doc.note("Not yet trustworthy: " + ", ".join(d["untrusted_on_board"]))
    rules_note = _rules_sentence(_rules_applied(run))
    if rules_note:
        doc.note(rules_note)

    cc = _compliance_cost(run)
    if cc:
        doc.h2("What the rules cost")
        doc.p(f"Obeying the rules on this disruption cost {_rp(cc['idr'])}: the plan that was "
              "chosen, set against the cheaper one a rule struck out.", size=8.5)
        doc.table(["", "Plan", "Cost"], [
            ["Chosen", ", ".join(cc.get("chosen") or []) or "-", _rp(cc.get("chosen_cost_idr"))],
            ["Cheaper, struck out", ", ".join(cc.get("cheaper_but_blocked") or []) or "-",
             _rp(cc.get("cheaper_cost_idr"))],
            ["Difference", "what the rules cost", _rp(cc["idr"])],
        ], align=["l", "l", "r"], widths=[1.6, 3.4, 1.4])
        if cc.get("blocked_by"):
            doc.table(["Struck out", "Why"], [
                [f"{b.get('id')} {b.get('label') or ''}".strip(), b.get("reason") or ""]
                for b in cc["blocked_by"]], align=["l", "l"], widths=[1.6, 4.8], size=8)
        doc.p("This is the price of the rule, not an overrun. It is on the record so the "
              "decision can be defended without re-deriving it.", size=7.5, muted=True)

    settled = [a for a in actions if a.get("outcome")]
    if settled:
        doc.h2("Outcome: realized vs predicted")
        rows = []
        blank = 0
        for a in settled:
            pred, act = a["payload"].get("cost_idr"), _actual_cost(a)
            delta = act - pred if isinstance(pred, (int, float)) and isinstance(act, (int, float)) else None
            if delta is None:
                blank += 1
            rows.append([f"{a['kind']} ({a['outcome']})", _rp(pred), _rp(act), _rp(delta)])
        doc.table(["Action", "Predicted", "Actual", "Delta"], rows, align=["l", "r", "r", "r"])
        if blank:
            doc.p(f"{blank} of {len(settled)} recorded outcome(s) carry no realized figure, so "
                  "no delta is stated for them. A dash is 'not known', never zero.",
                  size=7.5, muted=True)
    owed = [a for a in actions
            if not a.get("outcome") and a.get("status") in ("sent", "approved")
            and a["kind"] in store.AWAITS_OUTCOME]
    if owed:
        doc.note(f"{len(owed)} action(s) that went out still owe an outcome "
                 f"({', '.join(a['kind'] for a in owed)}). Until those are recorded the "
                 "realized side of this handling is incomplete.")

    doc.h2(f"Actions ({len(actions)})")
    if actions:
        doc.table(["Action", "What it does", "Value", "Status", "Authority"], [
            [a["kind"], _payload_text(a["payload"]), _rp(a["payload"].get("cost_idr")), a["status"],
             "own authority" if a.get("autonomous") else "needs approval"] for a in actions],
            align=["l", "l", "r", "l", "l"], widths=[1.3, 3.2, 1.2, 0.9, 1.2])
    else:
        doc.p("None were raised.", muted=True)

    approvals = run.get("approvals") or []
    if approvals:
        doc.h2(f"Approvals ({len(approvals)})")
        doc.table(["Decision", "By", "Role", "At", "Note"], [
            [p["decision"], p["decided_by"], p["role"], _when(p["at"]), p.get("note") or ""] for p in approvals])

    evidence = _outside_evidence(run)
    if evidence:
        doc.h2(f"Evidence from outside ({len(evidence)})")
        doc.p("What this handling read from the open web. A headline is the publisher's claim, "
              "cited as reported and not as fact — the link is here so it can be checked.",
              size=8.5)
        doc.table(["What was read", "Published by", "When", "Where"], [
            [e["title"] or e["url"], e["by"], e["when"], e["url"]] for e in evidence],
            align=["l", "l", "l", "l"], widths=[2.8, 1.4, 1.1, 2.9], size=7.5, max_lines=3)

    read = data_tables(run)
    by_tool: Dict[str, dict] = {}
    for s in tools:
        dd = s.get("detail") or {}
        name = dd.get("name") or (s.get("tools") or ["?"])[0]
        t = by_tool.setdefault(name, {"agent": names.get(s.get("agent"), s.get("agent")), "calls": 0,
                                      "failed": 0, "rows": 0, "origins": set(), "sources": set()})
        t["calls"] += 1
        t["failed"] += 1 if dd.get("error") else 0
        t["rows"] += dd.get("rows") if isinstance(dd.get("rows"), int) else len(_rows_of(dd.get("result")))
        if dd.get("origin") or s.get("origin"):
            t["origins"].add(dd.get("origin") or s.get("origin"))
        if dd.get("source") or s.get("source"):
            t["sources"].add(dd.get("source") or s.get("source"))
    if by_tool:
        doc.h2("What the decision rests on")
        doc.p("Every tool the team called, how much it read and where from. The rows themselves are in "
              f"the Excel download, one sheet per tool ({len(read)} with rows).", size=8.5, muted=True)
        doc.table(["Tool", "Agent", "Calls", "Rows", "Origin", "Source"], [
            [k, v["agent"], v["calls"] - v["failed"] if not v["failed"] else f"{v['calls']} ({v['failed']} failed)",
             v["rows"], ", ".join(sorted(v["origins"])), "; ".join(sorted(v["sources"]))]
            for k, v in by_tool.items()],
            align=["l", "l", "r", "r", "l", "l"], widths=[2.2, 0.9, 0.8, 0.7, 1.0, 2.6])

    if steps:
        doc.h2(f"How the system reasoned ({len(steps)} steps)")
        rows = []
        for s in steps:
            what = _what(s)
            if s["stage"] in ("FINDING", "SUMMARY"):
                plain = _excerpt(what)
                what = plain[:260].rstrip() + "... (in full below)" if len(plain) > 280 else plain
            rows.append([s["seq"], _STAGE.get(s["stage"], s["stage"].title()),
                         names.get(s.get("agent"), s.get("agent")), what,
                         s.get("origin") or (s.get("detail") or {}).get("origin") or ""])
        doc.table(["#", "Stage", "Agent", "What", "Origin"], rows, align=["r", "l", "l", "l", "l"],
                  widths=[0.4, 0.9, 0.8, 5.0, 0.9], size=7.5, max_lines=8)

    findings = [s for s in steps if s["stage"] in ("FINDING", "SUMMARY")
                and ((s.get("detail") or {}).get("full_summary") or (s.get("detail") or {}).get("summary"))]
    if findings:
        doc.h2("Findings in full")
        for s in findings:
            dd = s.get("detail") or {}
            who = names.get(s.get("agent"), s.get("agent"))
            doc.h3(f"{who} · {_STAGE.get(s['stage'], s['stage'].title())} #{s['seq']}")
            doc.md(dd.get("full_summary") or dd.get("summary"))

    doc.rule().p("Assembled from the stored record, not re-summarised by a model, so it says exactly "
                 f"what the log says. Generated by SIGAP on {_when(store._now())}.", size=7.5, muted=True)
    return doc.render()


def run_file(run_id: str, fmt: str,
             include_data: bool = True) -> Optional[Tuple[bytes, str, str]]:
    """(content, filename, media type) for one handling as a PDF or a workbook."""
    run = store.get_run(run_id)
    if not run:
        return None
    name = f"sigap-{slug(run['title'])}-{run_id[-6:]}"
    if fmt == "xlsx":
        return (export.xlsx(run_sheets(run, include_data), title=run["title"]),
                f"{name}.xlsx", export.XLSX_MIME)
    return run_pdf(run), f"{name}.pdf", export.PDF_MIME


# The period filters on the HANDLING's start, for the actions as well as the
# runs. An action belongs to the disruption it was raised for, so a report of
# October's disruptions holds October's actions even where one was approved on
# the 2nd of November — and the counts in it reconcile with each other.
def _all_runs(w: Optional[Dict[str, Any]] = None) -> List[dict]:
    clause, args = _period_sql(w, "r.started_at")
    with store.connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT r.id, r.status, r.mode, r.started_at, r.finished_at, r.token_cost_idr, r.decision,"
            "       e.title, e.kind, e.trigger,"
            " (SELECT count(*) FROM steps s WHERE s.run_id = r.id) AS steps,"
            " (SELECT count(*) FROM steps s WHERE s.run_id = r.id AND s.stage = 'TOOL') AS tools,"
            " (SELECT count(*) FROM actions a WHERE a.run_id = r.id) AS actions"
            " FROM runs r JOIN events e ON e.id = r.event_id"
            " WHERE 1=1" + clause + " ORDER BY r.started_at DESC", args)]


def _all_actions(w: Optional[Dict[str, Any]] = None) -> List[dict]:
    clause, args = _period_sql(w, "r.started_at")
    with store.connect() as c:
        rows = [dict(a) for a in c.execute(
            "SELECT a.*, e.title FROM actions a JOIN runs r ON r.id = a.run_id"
            " JOIN events e ON e.id = r.event_id"
            " WHERE 1=1" + clause + " ORDER BY a.created_at DESC", args)]
    for a in rows:
        try:
            a["payload"] = json.loads(a["payload"]) if isinstance(a["payload"], str) else a["payload"]
        except Exception:                 # noqa: BLE001
            a["payload"] = {}
        try:
            a["outcome_detail"] = (json.loads(a["outcome_detail"])
                                   if isinstance(a.get("outcome_detail"), str)
                                   else a.get("outcome_detail"))
        except Exception:                 # noqa: BLE001
            a["outcome_detail"] = None
    return rows


def compliance_costs(w: Optional[Dict[str, Any]] = None) -> List[dict]:
    """What obeying the rules cost, one row per handling that priced it.

    Read out of the costing step already on the record rather than kept in a
    column of its own: a second copy of a figure is a second thing that can
    disagree with the first. The LIKE narrows the scan to the few steps that
    could carry one; the parse decides whether it does.
    """
    clause, args = _period_sql(w, "r.started_at")
    with store.connect() as c:
        rows = c.execute(
            "SELECT s.run_id, s.seq, s.detail, e.title, r.started_at"
            " FROM steps s JOIN runs r ON r.id = s.run_id"
            " JOIN events e ON e.id = r.event_id"
            " WHERE s.stage = 'TOOL' AND s.detail LIKE '%compliance_cost%'"
            + clause + " ORDER BY s.run_id, s.seq", args).fetchall()
    found: Dict[str, dict] = {}
    for r in rows:
        try:
            d = json.loads(r["detail"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(d, dict) or d.get("error"):
            continue
        result = d.get("result")
        cc = result.get("compliance_cost") if isinstance(result, dict) else None
        if not isinstance(cc, dict) or not isinstance(cc.get("idr"), (int, float)):
            continue
        # Ordered by seq, so the last costing in a run — the one its decision
        # was taken on — is the one left standing.
        found[r["run_id"]] = dict(cc) | {"run_id": r["run_id"], "title": r["title"],
                                         "step": r["seq"], "started_at": r["started_at"]}
    return sorted(found.values(), key=lambda x: x["started_at"], reverse=True)


def _decision_line(raw: Optional[str]) -> str:
    try:
        d = json.loads(raw) if raw else {}
    except Exception:                     # noqa: BLE001
        return ""
    text = d.get("recommendation") or d.get("reason") or ""
    for line in text.split("\n"):
        line = re.sub(r"[#*_>`|]", "", line).strip()
        if len(line) > 30:
            return line[:300]
    return text[:300]


def portfolio_sheets(m: Optional[Dict[str, Any]] = None, *,
                     runs: Optional[List[dict]] = None,
                     actions: Optional[List[dict]] = None,
                     costs: Optional[List[dict]] = None) -> List[export.Sheet]:
    w = (m or {}).get("period")
    runs = _all_runs(w) if runs is None else runs
    actions = _all_actions(w) if actions is None else actions
    costs = compliance_costs(w) if costs is None else costs
    m = m or portfolio_metrics(w, runs=runs, actions=actions, costs=costs)
    kb = m["knowledge_base"]
    dist = lambda d: ", ".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda x: -x[1]))  # noqa: E731
    sheets = [export.Sheet("Summary", ["Figure", "Value"], [
        ["Period", m["period_label"]],
        ["Handlings", m["runs_total"]], ["By status", dist(m["by_status"])], ["By kind", dist(m["by_kind"])],
        ["Decided on fully-trusted evidence", m["decided_on_trusted"]],
        ["Decided with a trust caveat", m["decided_with_untrusted"]],
        ["Actions raised", m["actions_total"]], ["Actions sent", m["actions_sent"]],
        ["Actions awaiting approval", m["actions_pending"]],
        ["Committed value, predicted (IDR)", m["predicted_idr_total"]],
        ["Outcomes recorded", m["settled_actions"]],
        ["Outcomes by kind", dist(m["by_outcome"])],
        ["Outcomes with no realized figure", m["settled_without_cost"]],
        ["Actions still owing an outcome", m["awaiting_outcome"]],
        ["Comparable actions", m["settled_with_cost"]],
        ["Comparable, predicted (IDR)", m["settled_predicted_idr"]],
        ["Comparable, actual (IDR)", m["settled_actual_idr"]],
        ["Comparable, delta (IDR)", m["settled_delta_idr"]],
        ["What the rules cost (IDR)", m["rules_cost_idr"]],
        ["Disruptions where a rule struck out a cheaper plan", m["rules_cost_cases"]],
        ["Rules verified against a source", f"{kb['verified']} of {kb['total']}"],
        ["Rules that are assumptions", ", ".join(kb["unverified"]) or "none"],
        ["Rule pack", kb["pack"] or "none installed"],
        ["Generated", _when(store._now())],
    ], pairs=True)]
    if costs:
        sheets.append(export.Sheet("Compliance cost", [
            "Handling", "Run ID", "Chosen", "Chosen IDR", "Cheaper but struck out",
            "Cheaper IDR", "What the rules cost IDR", "Struck out by"], [
            [c["title"], c["run_id"], ", ".join(c.get("chosen") or []),
             c.get("chosen_cost_idr"), ", ".join(c.get("cheaper_but_blocked") or []),
             c.get("cheaper_cost_idr"), c["idr"],
             "; ".join(f"{b.get('id')}: {b.get('reason') or ''}" for b in c.get("blocked_by") or [])]
            for c in costs]))
    if runs:
        sheets.append(export.Sheet("Handlings", [
            "Run ID", "Handling", "Kind", "Status", "Mode", "Started", "Finished", "Steps", "Tool calls",
            "Actions", "Model cost IDR", "Decision"], [
            [r["id"], r["title"], r["kind"], r["status"], r["mode"], _when(r["started_at"]),
             _when(r["finished_at"]), r["steps"], r["tools"], r["actions"], r["token_cost_idr"] or 0,
             _decision_line(r["decision"])] for r in runs]))
    if actions:
        keys: List[str] = []
        for a in actions:
            keys += [k for k in a["payload"] if k not in keys and not k.startswith("_")]
        sheets.append(export.Sheet("Actions", [
            "Run ID", "Handling", "Action ID", "Action", "Status", "Autonomous"] + keys
            + ["Created", "Outcome", "Recorded", "Actual IDR", "Owes an outcome"], [
            [a["run_id"], a["title"], a["id"], a["kind"], a["status"], bool(a.get("autonomous"))]
            + [_cell(a["payload"].get(k)) for k in keys]
            + [_when(a.get("created_at")), a.get("outcome"), _when(a.get("outcome_at")),
               _actual_cost(a),
               bool(not a.get("outcome") and a["status"] in ("sent", "approved")
                    and a["kind"] in store.AWAITS_OUTCOME)] for a in actions]))
    return sheets


def portfolio_pdf(data: Optional[Dict[str, Any]] = None) -> bytes:
    data = data if data is not None else _portfolio_data()
    m, runs, actions, costs = data["metrics"], data["runs"], data["actions"], data["costs"]
    kb = m["knowledge_base"]
    summary = _portfolio_summary(m)
    doc = export.Doc("Operations report", kicker="SIGAP · Every handling rolled up",
                     subtitle=f"{m['period_label']}. How much was handled, what it was predicted "
                              "to cost and, once outcomes are recorded, what it actually cost.",
                     footer="SIGAP · Operations report")
    doc.facts([
        ("Period", m["period_label"]),
        ("Handlings", f"{m['runs_total']}  ({', '.join(f'{v} {k}' for k, v in m['by_status'].items())})"),
        ("Actions raised", f"{m['actions_total']}  ({m['actions_sent']} sent, {m['actions_pending']} awaiting)"),
        ("Committed (predicted)", _rp(m["predicted_idr_total"])),
        # The delta is drawn from the comparable actions only, and says so: the
        # count beside it used to be every recorded outcome, which made a
        # delta of nothing look like a book that came in on budget.
        ("Realized vs predicted", (("+" if m["settled_delta_idr"] > 0 else "") + _rp(m["settled_delta_idr"])
                                   + f"  ({m['settled_with_cost']} comparable)") if m["settled_with_cost"]
         else "no realized figure recorded"),
        ("Outcomes still owed", m["awaiting_outcome"]),
        ("What the rules cost", _rp(m["rules_cost_idr"]) if m["rules_cost_cases"] else "nothing measurable"),
        ("Rules verified", f"{kb['verified']} of {kb['total']}"),
        ("Decided on trusted evidence", m["decided_on_trusted"]),
        ("Decided with a caveat", m["decided_with_untrusted"]),
    ])
    if summary:
        doc.h2("Summary").md(summary)
    doc.h2(f"Handlings ({len(runs)})")
    if runs:
        doc.table(["Handling", "Kind", "Status", "Started", "Steps", "Actions", "Model cost"], [
            [r["title"], r["kind"], r["status"], _when(r["started_at"]), r["steps"], r["actions"],
             _rp(r["token_cost_idr"] or 0)] for r in runs],
            align=["l", "l", "l", "l", "r", "r", "r"], widths=[3.2, 1.3, 0.8, 1.6, 0.6, 0.7, 1.1])
    else:
        doc.p("No handling on record.", muted=True)
    doc.h2(f"Actions ({len(actions)})")
    if actions:
        doc.table(["Handling", "Action", "What it does", "Value", "Status"], [
            [a["title"], a["kind"], _payload_text(a["payload"]), _rp(a["payload"].get("cost_idr")), a["status"]]
            for a in actions], align=["l", "l", "l", "r", "l"], widths=[2.2, 1.2, 3.0, 1.2, 0.9])
    else:
        doc.p("No action has been raised.", muted=True)
    doc.h2("Realized vs predicted")
    if m["settled_with_cost"]:
        doc.table(["", "Predicted", "Actual", "Delta"], [[
            f"{m['settled_with_cost']} comparable action(s)", _rp(m["settled_predicted_idr"]),
            _rp(m["settled_actual_idr"]), _rp(m["settled_delta_idr"])]], align=["l", "r", "r", "r"])
    doc.p(_delta_sentence(m), size=8.5, muted=not m["settled_with_cost"])

    doc.h2("What the rules cost")
    if costs:
        doc.p(f"Across {len(costs)} disruption(s) a rule struck out a cheaper plan. Taking the "
              f"compliant one instead cost {_rp(m['rules_cost_idr'])}. This is the price of the "
              "rules, not an overrun.", size=8.5)
        doc.table(["Handling", "Chosen", "Cheaper, struck out", "Cost of the rule", "Struck out by"], [
            [c["title"], ", ".join(c.get("chosen") or []) or "-",
             ", ".join(c.get("cheaper_but_blocked") or []) or "-", _rp(c["idr"]),
             "; ".join(str(b.get("id")) for b in c.get("blocked_by") or [])]
            for c in costs], align=["l", "l", "l", "r", "l"],
            widths=[2.4, 1.1, 1.3, 1.2, 1.4], size=8)
    else:
        doc.p("No disruption in this period had a cheaper plan struck out by a rule, so obeying "
              "them cost nothing that can be measured.", muted=True)

    doc.h2("The rules themselves")
    doc.p(f"{kb['verified']} of {kb['total']} rules are verified against the document they were "
          "read from"
          + (f". Assumptions: {', '.join(kb['unverified'])}" if kb["unverified"] else "")
          + ("" if kb["pack"] else ". No rule pack is installed, so every rule is a built-in "
                                  "assumption or the company's own profile figure") + ".",
          size=8.5)
    for p in kb["problems"]:
        doc.note(p)

    doc.rule().p(f"Computed from the record. Generated by SIGAP on {_when(store._now())}.", size=7.5, muted=True)
    return doc.render()


def _file_stamp(w: Optional[Dict[str, Any]]) -> str:
    """The period in a filename, so two downloads of different periods do not
    arrive under the same name."""
    if not w:
        return datetime.now(WIB).strftime("%Y-%m-%d") + "-all"
    if w.get("days"):
        return f"{datetime.now(WIB).strftime('%Y-%m-%d')}-last{w['days']}d"
    return f"{w.get('since') or 'start'}_to_{w.get('until') or 'now'}"


def portfolio_file(fmt: str, since: Optional[str] = None, until: Optional[str] = None,
                   days: Optional[int] = None) -> Tuple[bytes, str, str]:
    w = window(since, until, days)
    data = _portfolio_data(w)
    name = f"sigap-operations-report-{_file_stamp(w)}"
    if fmt == "xlsx":
        return (export.xlsx(portfolio_sheets(data["metrics"], runs=data["runs"],
                                             actions=data["actions"], costs=data["costs"]),
                            title="Operations report"),
                f"{name}.xlsx", export.XLSX_MIME)
    return portfolio_pdf(data), f"{name}.pdf", export.PDF_MIME


def demo() -> None:
    """Build a report from a scratch run and prove the things a report can get
    wrong: the figures are deterministic, a delta is only claimed where both
    halves exist, what the rules cost reaches the page, the period actually
    filters, and with no aux model the report is still complete."""
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_REPORT_SELFCHECK")

    from tools.execution import idempotency_key

    eid = store.record_event("port_closure", "Typhoon closes Ningbo",
                             "Maritime advisory", {"port": "CNNGB"}, "demo")
    rid = store.start_run(eid, "autonomous")
    store.save_step(rid, {"seq": 1, "stage": "FINDING", "agent": "compliance",
                          "agent_name": "Kira", "summary": "Option E blocked on TKDN",
                          "tools": [], "origin": "modelled", "source": "fixture",
                          "detail": {}, "at": store._now()})
    # The costing step, as tools/simulation.py records it. This is where what
    # the rules cost lives, and the report has to read it back out.
    store.save_step(rid, {
        "seq": 2, "stage": "TOOL", "agent": "simulation", "agent_name": "Tara",
        "summary": "simulate_scenario", "tools": ["simulate_scenario"],
        "origin": "derived", "source": "engine/simulate.py", "at": store._now(),
        "detail": {"name": "simulate_scenario", "rows": 1, "result": {
            "chosen": {"combination": ["B", "C"]},
            # the rule pack as it was read at the time: one assumption, one verified
            "rules": [{"rule": "tkdn_contract_floor_pct", "value": 40.0, "verified": True,
                       "source": "contract KPN-2024", "origin": "derived"},
                      {"rule": "tkdn_current_pct", "value": 38.2, "verified": False,
                       "source": "company profile", "origin": "modelled"}],
            "compliance_cost": {
                "idr": 46_000_000, "chosen": ["B"], "chosen_cost_idr": 94_000_000,
                "cheaper_but_blocked": ["E"], "cheaper_cost_idr": 48_000_000,
                "blocked_by": [{"id": "E", "label": "China spot",
                                "reason": "TKDN falls from 38.2% to 34.8%"}]}}}})
    # What Milo read from the open web. It is the one kind of evidence a reader
    # can check for themselves, so the report has to carry the link, not a count.
    store.save_step(rid, {
        "seq": 3, "stage": "TOOL", "agent": "logistics", "agent_name": "Milo",
        "summary": "search_news", "tools": ["search_news"], "origin": "live",
        "source": "Google News", "at": store._now(),
        "detail": {"name": "search_news", "rows": 2, "fetched_at": "2026-09-04T01:00:00Z",
                   "result": {"query": "Ningbo port typhoon", "days": 7, "headlines": [
                       {"title": "Ningbo-Zhoushan halts operations as typhoon nears",
                        "publisher": "Reuters", "publisher_site": "https://reuters.com",
                        "published_at": "2026-09-03T02:00+00:00",
                        "url": "https://example.com/reuters/ningbo-halt"},
                       {"title": "Carriers omit Ningbo calls this week",
                        "publisher": "Lloyd's List", "publisher_site": None,
                        "published_at": "2026-09-04T06:30+00:00",
                        "url": "https://example.com/lloyds/omissions"}]}}})
    store.save_step(rid, {
        "seq": 4, "stage": "TOOL", "agent": "logistics", "agent_name": "Milo",
        "summary": "web_brief", "tools": ["web_brief"], "origin": "derived",
        "source": "sonar on SAP AI Core", "at": store._now(),
        "detail": {"name": "web_brief", "rows": 1, "result": {
            "question": "Is Ningbo port operating?", "answer": "Operations are suspended.",
            "citations": [{"url": "https://example.com/portauthority/notice",
                           "title": "Port authority notice"}]}}})
    body = {"material": "M-4471", "from_plant": "SBY1", "to_plant": "KRW1",
            "qty": 22.0, "cost_idr": 22_000_000}
    action = store.record_action(rid, idempotency_key("stock_transfer", **body),
                                 "stock_transfer", True, body)
    # A second action that will be settled with NO figure, and a third that goes
    # out and is never settled: between them they are every state the realized
    # side can be in, and the report has to tell them apart.
    nofig = {"material": "M-4471", "supplier": "SUP-4417", "qty": 30.0, "cost_idr": 61_000_000}
    second = store.record_action(rid, idempotency_key("draft_po", **nofig),
                                 "draft_po", True, nofig)
    owed_body = {"material": "M-4471", "from_plant": "KRW1", "to_plant": "SBY1", "qty": 5.0}
    store.record_action(rid, idempotency_key("stock_transfer", **owed_body),
                        "stock_transfer", True, owed_body, status="sent")
    store.close_run(rid, "done", {"recommendation": "Recommend B+C; E blocked on TKDN.",
                                  "untrusted_on_board": ["compliance.check_local_constraints"]})
    # a recorded outcome: it actually cost a little more than predicted
    # Built through the one helper that produces this key, so the whole tree
    # has a single place where a realized figure is spelled.
    store.record_outcome(action["id"], "delivered",
                         store.outcome_detail("", 24_500_000, "demo@x"))
    store.record_outcome(second["id"], "late", store.outcome_detail("arrived 9 Oct", None, "demo@x"))

    rep = build_report(rid)
    assert rep and rep["run_id"] == rid
    md = rep["markdown"]
    assert "# Typhoon closes Ningbo" in md
    assert "## Decision" in md and "Recommend B+C" in md
    assert "## Outcome: realized vs predicted" in md, md
    assert "Rp 22,000,000" in md and "Rp 24,500,000" in md, "predicted and actual must both show"
    assert "Rp 2,500,000" in md, "the delta must be computed deterministically"
    assert "## How the system reasoned" in md and "Kira" in md
    assert "not yet trustworthy" in md.lower()
    # the outcome with no figure must be counted and said, not averaged in
    assert "1 of 2 recorded outcome(s) carry no realized figure" in md, md
    # and the action that went out and owes an outcome must be chased here too
    assert "still owe an outcome" in md, md

    # What the rules cost: read out of the costing step, priced, with the rule
    # that struck the cheaper plan named.
    cc = rep["compliance_cost"]
    assert cc and cc["idr"] == 46_000_000 and cc["step"] == 2, cc
    assert "## What the rules cost" in md and "Rp 46,000,000" in md, md
    assert "TKDN falls from 38.2% to 34.8%" in md, "the rule that struck it must be named"

    # Rule trust, as it was when the decision was taken: one of the two rules
    # the handling applied was an assumption.
    applied = rep["rules_applied"]
    assert applied and applied["total"] == 2 and applied["verified"] == 1, applied
    assert applied["unverified"] == ["tkdn_current_pct"], applied
    assert "tkdn_current_pct" in (rep["rules_note"] or ""), rep["rules_note"]

    # Evidence from outside: the link travels, not just a count of links.
    ev = rep["evidence"]
    assert len(ev) == 3, ev
    assert {e["kind"] for e in ev} == {"headline", "citation"}, ev
    assert all(e["url"].startswith("https://") for e in ev), ev
    assert "## Evidence from outside" in md, md
    assert "https://example.com/reuters/ningbo-halt" in md, "the link itself must be in the report"
    assert "Reuters" in md and "Lloyd's List" in md
    assert "cited here as reported and not as fact" in md, "a headline is not a fact"

    # aux unavailable in the self-check env → no model summary, report still whole
    if not aux.ready():
        assert rep["summary_by"] is None
        assert "## Summary" not in md

    # Portfolio rollup: one comparable action (22m predicted, 24.5m actual), one
    # recorded outcome with no figure, one action still owing one.
    port = build_portfolio()
    pm = port["metrics"]
    assert pm["runs_total"] == 1 and pm["settled_actions"] == 2, pm
    assert pm["settled_with_cost"] == 1 and pm["settled_without_cost"] == 1, pm
    assert pm["settled_delta_idr"] == 2_500_000, pm
    assert pm["awaiting_outcome"] == 1, pm
    assert pm["by_outcome"] == {"delivered": 1, "late": 1}, pm
    assert pm["rules_cost_idr"] == 46_000_000 and pm["rules_cost_cases"] == 1, pm
    assert pm["knowledge_base"]["total"] >= 1, pm["knowledge_base"]
    assert "# Operations report" in port["markdown"]
    assert "Realized vs predicted" in port["markdown"]
    assert "1 comparable action(s)" in port["markdown"], port["markdown"]
    assert "What the rules cost" in port["markdown"] and "Rp 46,000,000" in port["markdown"]
    if not aux.ready():
        assert port["summary_by"] is None and "## Summary" not in port["markdown"]

    # The bug this section exists to prevent: an outcome with no figure must
    # never be reported as a cost that landed on prediction.
    settled_no_figure = dict(pm) | {"settled_with_cost": 0, "settled_actions": 2,
                                    "settled_without_cost": 2, "settled_delta_idr": 0}
    said = _delta_sentence(settled_no_figure)
    assert "no comparison" in said and "exactly at" not in said, said
    assert "exactly at prediction" not in _portfolio_markdown(settled_no_figure)

    # The period: a window that ends before this run started holds nothing, and
    # says so instead of quietly widening to everything.
    empty = build_portfolio(since="2000-01-01", until="2000-01-02")
    assert empty["metrics"]["runs_total"] == 0, empty["metrics"]
    assert empty["metrics"]["rules_cost_cases"] == 0
    assert "2000-01-01 to 2000-01-02 (WIB)" in empty["markdown"], empty["markdown"]
    assert build_portfolio(days=1)["metrics"]["runs_total"] == 1
    # WIB, not UTC: a day begins at 17:00 UTC the day before, and a window that
    # forgot it would file the first seven hours of a month in the month before.
    assert _day_bounds("2026-10-01")[0] == "2026-09-30T17:00:00+00:00"

    # The files: a PDF that opens, a workbook whose sheets carry the action and the steps.
    pdf, name, mime = run_file(rid, "pdf")
    assert pdf.startswith(b"%PDF") and name.endswith(".pdf") and mime == export.PDF_MIME
    book, name, _ = run_file(rid, "xlsx")
    assert book[:2] == b"PK" and name.endswith(".xlsx")
    sheets = {s["name"]: s["rows"] for s in rep["sheets"]}
    assert sheets.get("Actions") == 3 and sheets.get("Steps") == 4, sheets
    assert "Compliance cost" in sheets, sheets
    assert sheets.get("Evidence from outside") == 3, sheets
    # A workbook that leaves by email carries the record, not the rows each tool
    # read. Same record, fewer sheets, and nothing silently dropped from it.
    full = [s.name for s in run_sheets(store.get_run(rid), include_data=True)]
    trimmed = [s.name for s in run_sheets(store.get_run(rid), include_data=False)]
    assert "simulate_scenario" in full and "simulate_scenario" not in trimmed, (full, trimmed)
    assert set(trimmed) < set(full) and "Compliance cost" in trimmed
    assert portfolio_file("pdf")[0].startswith(b"%PDF") and portfolio_file("xlsx")[0][:2] == b"PK"
    assert "last1d" in portfolio_file("pdf", days=1)[1], portfolio_file("pdf", days=1)[1]
    assert _rows_of({"query": "q", "headlines": [{"t": 1}, {"t": 2}]}) == [{"query": "q", "t": 1}, {"query": "q", "t": 2}]
    assert _rows_of({"id": "act", "idempotency_key": "k"}) == [], "an action record is not data read"

    with store.connect() as c:
        c.execute("DELETE FROM approvals WHERE action_id IN (SELECT id FROM actions WHERE run_id=?)", (rid,))
        c.execute("DELETE FROM actions WHERE run_id=?", (rid,))
        c.execute("DELETE FROM steps WHERE run_id=?", (rid,))
        c.execute("DELETE FROM runs WHERE id=?", (rid,))
        c.execute("DELETE FROM events WHERE id=?", (eid,))

    print("report ok, figures deterministic ✓ · realized-vs-predicted ✓ · delta only where "
          "comparable ✓ · outcomes owed counted ✓ · what the rules cost ✓ · rule trust ✓ "
          "· period in WIB ✓ · evidence from the open web carries its link ✓ · aux summary "
          "fail-open ✓ · pdf + xlsx ✓ · email workbook without the raw rows ✓")


if __name__ == "__main__":
    demo()
