"""The three things Joule may ask SIGAP, and how each answer is written.

  investigate_disruption   raise an event, answer AT ONCE with the run id
  disruption_status        read a run: status, who worked, the recommendation
  risk_scan                Vega's exposure scan and the RPT-1.6 slip ranking

Nothing here can approve, and no fourth skill is reachable. Joule carries no
user identity (the destination is `NoAuthentication`), so an approval sent
through it would be an approval with no approver. Every answer that touches an
action says where it is approved: on SIGAP web, by a signed-in person.

Joule picks a scenario by matching the user's words against the scenario
descriptions, then sends the user's message, and only the message, to this
agent. All three scenarios reach the same agent, so the skill is decided again
here, from the same words. A JSON message `{"skill": ..., "text": ...,
"run_id": ...}` names it outright, which is what the A2A Editor is for.

Why investigate returns immediately: Joule waits 60 seconds for a synchronous
answer, and a handling may run to `MAX_SECONDS_PER_EVENT` (600 s). So the
investigation is a raise-and-link, and following it is the status skill.

A message that names none of the three gets the help text, not an event. A
misread question must cost nothing, and raising an event spends model credit.

Standard library only (Python 3.9+), so this file self-checks without the
A2A SDK installed.
"""
from __future__ import annotations

import json
import re
import threading
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Tuple

SKILLS = ("investigate_disruption", "disruption_status", "risk_scan")

NAMES = {"supervisor": "Arya", "impact": "Elsa", "demand": "Dara", "inventory": "Iris",
         "sourcing": "Clint", "procurement": "Prita", "logistics": "Milo",
         "compliance": "Kira", "simulation": "Tara", "precedent": "Otto",
         "execution": "Bram", "exposure": "Vega"}

#: UN/LOCODEs for the ports the records mention, so "Ningbo" in a message
#: becomes the `port` the agents look the purchase orders up by.
PORTS = {"ningbo": "CNNGB", "shanghai": "CNSHA", "busan": "KRPUS", "pusan": "KRPUS",
         "laem chabang": "THLCH", "ho chi minh": "VNSGN", "saigon": "VNSGN",
         "cat lai": "VNSGN", "tanjung priok": "IDTPP", "priok": "IDTPP",
         "yokohama": "JPYOK", "port klang": "MYPKG", "klang": "MYPKG",
         "singapore": "SGSIN", "tanjung perak": "IDSUB"}

RUN_ID = re.compile(r"\brun_[0-9a-f]{6,}\b")
LOCODE = re.compile(r"\b([A-Z]{2}[A-Z2-9]{3})\b")
MATERIAL = re.compile(r"\bM-\d{3,}\b")
SUPPLIER = re.compile(r"\bSUP-\d{3,}\b")
DAYS = re.compile(r"\b(\d{1,3})\s*(?:days?|hari)\b", re.I)

# English and Indonesian, because the people typing into Joule here use both.
_STATUS = re.compile(r"\b(status|progress|progres|how is|how's|how are|update on|"
                     r"what happened|result|outcome|recommendation|rekomendasi|"
                     r"bagaimana|gimana|sudah sampai mana|follow)\b", re.I)
_RISK = re.compile(r"\b(risk|risks|risiko|resiko|exposure|exposed|scan|about to break|"
                   r"single[- ]source|single[- ]sourced|concentrat\w*|slip|slipping|"
                   r"likely to be late|prevent|rawan|akan telat)\b", re.I)
_DISRUPTION = re.compile(r"\b(investigat\w*|selidik\w*|closed|closure|close|shut|tutup|"
                         r"delay\w*|late|terlambat|telat|strike|mogok|typhoon|topan|"
                         r"storm|badai|flood|banjir|quake|earthquake|gempa|customs|"
                         r"bea cukai|held|hold|ditahan|stuck|tertahan|shortage|"
                         r"kekurangan|disrupt\w*|gangguan|missed|cancel\w*|batal|"
                         r"bankrupt\w*|failed|gagal|recall|reject\w*)\b", re.I)
_AGAIN = re.compile(r"\b(again|new|re-?run|fresh|lagi|ulang|baru)\b", re.I)

HELP = (
    "I can do three things with SIGAP, the supply disruption assistant:\n\n"
    "1. **Investigate a disruption**: *\"Investigate: Ningbo port closed for 6 days\"*\n"
    "2. **Check an investigation**: *\"What is the status of run_1a2b3c4d5e6f?\"*\n"
    "3. **Scan for risk**: *\"What is about to break this week?\"*\n\n"
    "Approvals are not done here. Joule carries no identity, so an approval "
    "happens on SIGAP web, by a signed-in person with the authority for it."
)


# --------------------------------------------------------------- intent
def classify(text: str) -> Tuple[str, Dict[str, Any]]:
    """The skill a message asks for, and what it says. ('help', {}) when none."""
    raw = (text or "").strip()
    args: Dict[str, Any] = {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        parsed = None
    if isinstance(parsed, dict):
        raw = str(parsed.get("text") or parsed.get("user_request") or parsed.get("question") or "")
        if parsed.get("run_id"):
            args["run_id"] = str(parsed["run_id"])
        if parsed.get("skill") in SKILLS:
            return parsed["skill"], {**args, "text": raw}
    args["text"] = raw

    run = RUN_ID.search(raw)
    if run:
        args.setdefault("run_id", run.group(0))
        return "disruption_status", args
    if _STATUS.search(raw) and not _AGAIN.search(raw):
        return "disruption_status", args
    if _RISK.search(raw) and not _DISRUPTION.search(raw):
        return "risk_scan", args
    if _DISRUPTION.search(raw):
        return "investigate_disruption", args
    if _RISK.search(raw):
        return "risk_scan", args
    return "help", args


def event_from_text(text: str) -> dict:
    """The POST /events body for a disruption described in words.

    Only what the words actually say goes into the payload: a port that is
    named, materials and suppliers by their codes, a duration in days. The
    agents read the records for everything else; nothing is filled in here.
    """
    low = text.lower()
    if re.search(r"customs|bea cukai|ditahan|tertahan|held at|clearance", low):
        kind = "customs_hold"
    elif re.search(r"quality|qc|reject|recall|defect|cacat", low):
        kind = "quality_hold"
    elif re.search(r"supplier|vendor|pemasok|bankrupt|missed|cancel|batal|gagal kirim", low):
        kind = "supplier_failure"
    elif re.search(r"quake|gempa", low):
        kind = "seismic"
    elif re.search(r"port|pelabuhan|closed|closure|tutup|typhoon|topan|storm|badai|strike|mogok", low):
        kind = "port_closure"
    else:
        kind = "other"

    payload: Dict[str, Any] = {"reported_via": "joule", "text": text[:1000]}
    ports = [code for name, code in PORTS.items() if name in low]
    ports += [m for m in LOCODE.findall(text) if m in PORTS.values()]
    if ports:
        payload["port"] = ports[0]
    materials = sorted(set(MATERIAL.findall(text)))
    if materials:
        payload["materials"] = materials
    suppliers = sorted(set(SUPPLIER.findall(text)))
    if suppliers:
        payload["supplier"] = suppliers[0]
    days = DAYS.search(text)
    if days:
        payload["days"] = int(days.group(1))

    title = re.sub(r"^\s*(please\s+)?(investigate|selidiki|check)\s*[:,-]?\s*", "", text,
                   flags=re.I).strip() or text.strip()
    title = title[:1].upper() + title[1:]
    return {"kind": kind, "title": title[:120], "trigger": "Joule: reported in chat",
            "payload": payload, "source": "joule"}


# ----------------------------------------------------------- formatting
def _link(web: Optional[str], run_id: str) -> str:
    return f"[{run_id}]({web}/disruptions/{run_id})" if web else f"`{run_id}`"


def _rp(v: Any) -> str:
    try:
        return f"Rp {int(round(float(v))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "-"


def _origin(o: Any) -> str:
    return str(o or "missing").upper()


def _cell(v: Any) -> str:
    return str(v if v not in (None, "") else "-").replace("|", "/").replace("\n", " ")


NO_APPROVAL = ("Approvals happen on SIGAP web only. Joule carries no identity, so it "
               "cannot approve anything.")


def render_investigation(resp: dict, event: dict, web: Optional[str]) -> str:
    rid = resp.get("run_id", "?")
    lines = ["**Investigation started.** SIGAP's agent team is on it.", "",
             "| | |", "|---|---|",
             f"| Disruption | {_cell(event.get('title'))} |",
             f"| Kind | {_cell(event.get('kind'))} |",
             f"| Run | {_link(web, rid)} |"]
    p = event.get("payload") or {}
    if p.get("port"):
        lines.append(f"| Port | {p['port']} |")
    if p.get("materials"):
        lines.append(f"| Materials | {', '.join(p['materials'])} |")
    lines.append("")
    if resp.get("mode") == "guided":
        lines.append("⚠️ The agent team's model is not connected, so this run is **held**: "
                     "the event is recorded, and no decision was made.")
    else:
        lines.append(f"The team can take up to ten minutes. Ask **\"status of {rid}\"** "
                     "to follow it" + (", or open the run on SIGAP web." if web else "."))
    lines += ["", NO_APPROVAL]
    return "\n".join(lines)


def render_duplicate(run: dict, web: Optional[str]) -> str:
    return (f"This looks like a disruption SIGAP is already handling: "
            f"**{_cell(run.get('title'))}** ({_link(web, run.get('id', '?'))}, "
            f"{run.get('status', '?')}). I did not raise it again. Say *\"investigate "
            f"again: ...\"* if it is a new event.\n\n" + render_status(run, web))


def render_status(run: dict, web: Optional[str]) -> str:
    rid = run.get("id", "?")
    status = run.get("status", "?")
    d = run.get("decision") or {}
    lines = [f"**{_cell(run.get('title'))}**", "",
             "| | |", "|---|---|",
             f"| Run | {_link(web, rid)} |",
             f"| Status | **{status}**" + (f" ({d.get('status')})" if d.get("status")
                                          and d.get("status") != status else "") + " |",
             f"| Started | {_cell(run.get('started_at'))} |"]
    if run.get("finished_at"):
        lines.append(f"| Finished | {run['finished_at']} |")
    called = d.get("agents_called") or []
    if called:
        lines.append("| Agents | " + ", ".join(NAMES.get(c, c) for c in dict.fromkeys(called)) + " |")
    cost = d.get("cost_idr", run.get("token_cost_idr"))
    if cost:
        lines.append(f"| Model spend | {_rp(cost)} |")
    lines.append("")

    if status == "running":
        steps = [s for s in (run.get("steps") or []) if s.get("summary")][-4:]
        if steps:
            lines.append("**Latest steps**")
            for s in steps:
                lines.append(f"- {s.get('agent_name') or s.get('agent', '-')}: "
                             f"{str(s['summary'])[:200]}")
            lines.append("")
    if status == "held" and d.get("reason"):
        lines += [f"**Held:** {d['reason']}", ""]
    if status == "failed" and run.get("error"):
        lines += [f"**Failed:** {str(run['error'])[:400]}", ""]
    if d.get("status") == "partial" and d.get("reason"):
        lines += [f"**Stopped early:** {d['reason']}. What was established is below, "
                  "labelled by how far it can be trusted.", ""]
    if d.get("recommendation"):
        text = str(d["recommendation"]).strip()
        if len(text) > 2500:
            text = text[:2500].rsplit("\n", 1)[0] + "\n\n*(cut short here, the full text is on SIGAP web)*"
        lines += ["**Recommendation**", "", text, ""]
    untrusted = d.get("untrusted_on_board") or []
    if untrusted:
        lines += ["**Not yet trusted** (modelled or missing, so the calculator will not "
                  "price figures resting on them): " + ", ".join(f"`{k}`" for k in untrusted), ""]

    waiting = [a for a in (run.get("actions") or []) if a.get("status") == "pending"]
    if waiting:
        lines += ["**Waiting for approval**", "", "| Action | What | Value |", "|---|---|---|"]
        for a in waiting:
            p = a.get("payload") or {}
            parts = [str(p[k]) for k in ("material", "supplier") if p.get(k)]
            if p.get("from_plant") or p.get("to_plant"):
                parts.append(f"{p.get('from_plant', '?')} → {p.get('to_plant', '?')}")
            if p.get("qty") is not None:
                parts.append(f"qty {p['qty']:g}" if isinstance(p["qty"], (int, float)) else f"qty {p['qty']}")
            what = ", ".join(parts)
            lines.append(f"| {_cell(a.get('kind'))} | {_cell(what)} | {_rp(p.get('cost_idr'))} |")
        lines += ["", ("Approve or reject on SIGAP web: " + _link(web, rid)) if web
                  else "Approve or reject on SIGAP web."]
    lines += ["", NO_APPROVAL]
    return "\n".join(lines)


def render_risk(exp: dict, web: Optional[str], top: int = 5) -> str:
    lines = ["**What is about to break**", ""]
    findings = sorted(exp.get("findings") or [], key=lambda f: f.get("value_idr") or 0,
                      reverse=True)
    if findings:
        lines += [f"Vega's exposure scan, origin **{_origin(exp.get('origin'))}**. "
                  "Deterministic: arithmetic over the records, no model.", "",
                  "| Risk | Material | Plant | Value behind it |", "|---|---|---|---|"]
        for f in findings[:top]:
            lines.append(f"| {_cell(f.get('pattern'))} | {_cell(f.get('material'))} | "
                         f"{_cell(f.get('plant'))} | {_rp(f.get('value_idr'))} |")
        if len(findings) > top:
            lines.append(f"\n{len(findings) - top} more on SIGAP web.")
    else:
        lines.append("The exposure scan found nothing" + (f": {exp['note']}" if exp.get("note") else "."))
    lines.append("")

    slip = exp.get("slip_ranking") or {}
    ranked = slip.get("value") or []
    if ranked:
        lines += [f"**Purchase orders likely to slip**, origin **{_origin(slip.get('origin'))}**. "
                  "A ranking signal from SAP RPT-1.6, never a priced input.", "",
                  "| PO | Material | Supplier | Port | Slip (days) | Range |",
                  "|---|---|---|---|---|---|"]
        for r in ranked[:top]:
            iv = r.get("interval") or []
            rng = f"{iv[0]:g} to {iv[1]:g}" if len(iv) == 2 else "-"
            try:
                days = f"{float(r.get('predicted_slip_days')):.1f}"
            except (TypeError, ValueError):
                days = "-"
            lines.append(f"| {_cell(r.get('purchase_order'))} | {_cell(r.get('material'))} | "
                         f"{_cell(r.get('supplier'))} | {_cell(r.get('loading_port'))} | "
                         f"{days} | {rng} |")
        if slip.get("note"):
            lines += ["", f"*{slip['note']}*"]
    elif slip:
        lines.append(f"Slip ranking unavailable ({_origin(slip.get('origin'))})"
                     + (f": {slip['note']}" if slip.get("note") else "."))
    lines += ["", "To act on a risk, open it on SIGAP web" + (f": {web}" if web else ".")]
    return "\n".join(lines)


# ----------------------------------------------------------- the guards
class RateLimit:
    """At most `n` investigations an hour. The shim's URL is public by
    construction (NoAuthentication), and each event spends model credit."""

    def __init__(self, n: int, window_s: float = 3600.0, clock: Callable[[], float] = time.monotonic):
        self.n, self.window, self.clock = n, window_s, clock
        self._at: deque = deque()
        self._lock = threading.Lock()

    def take(self) -> bool:
        with self._lock:
            now = self.clock()
            while self._at and now - self._at[0] > self.window:
                self._at.popleft()
            if len(self._at) >= self.n:
                return False
            self._at.append(now)
            return True


def find_duplicate(event: dict, runs: List[dict], within_s: float = 24 * 3600,
                   now: Optional[float] = None) -> Optional[dict]:
    """A recent run about the same disruption: same title, or the same port and
    kind. Checked before raising, so a question asked twice is one handling."""
    from datetime import datetime, timezone
    now = now if now is not None else time.time()
    port = (event.get("payload") or {}).get("port")
    for r in runs:
        try:
            started = datetime.fromisoformat(str(r.get("started_at")).replace("Z", "+00:00"))
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if now - started.timestamp() > within_s:
                continue
        except ValueError:
            continue
        title = str(r.get("title", "")).strip().lower()
        if title == event["title"].strip().lower():
            return r
        if port and r.get("kind") == event["kind"] and _mentions_port(title, port):
            return r
    return None


def _mentions_port(text_lower: str, port: str) -> bool:
    return port.lower() in text_lower or any(
        name in text_lower for name, code in PORTS.items() if code == port)


def pick_run(text: str, runs: List[dict]) -> Optional[dict]:
    """The run a status question is about: the newest one sharing a material
    code or a port with the question, else simply the newest."""
    if not runs:
        return None
    low = (text or "").lower()
    materials = {m.lower() for m in MATERIAL.findall(text or "")}
    ports = {code for name, code in PORTS.items() if name in low}
    for r in runs:                                   # GET /runs is newest first
        title = str(r.get("title", "")).lower()
        if any(m in title for m in materials) or any(_mentions_port(title, p) for p in ports):
            return r
    return runs[0]


# ------------------------------------------------------------- dispatch
def answer(text: str, client, web: Optional[str], limiter: RateLimit) -> str:
    """One message in, one markdown answer out. `client` is a SigapClient."""
    from sigap_client import NotConfigured, SigapError, SigapUnreachable

    skill, args = classify(text)
    try:
        if skill == "disruption_status":
            rid = args.get("run_id")
            if not rid:
                picked = pick_run(args.get("text") or "", client.runs())
                if not picked:
                    return "SIGAP has no investigations on record yet.\n\n" + HELP
                rid = picked["id"]
            return render_status(client.run(rid), web)

        if skill == "risk_scan":
            return render_risk(client.exposure(), web)

        if skill == "investigate_disruption":
            event = event_from_text(args.get("text") or text)
            if not _AGAIN.search(args.get("text") or ""):
                dup = find_duplicate(event, client.runs())
                if dup:
                    return render_duplicate(client.run(dup["id"]), web)
            if not limiter.take():
                return ("SIGAP has already been asked to investigate as many disruptions as "
                        "this channel allows in an hour. Raise this one on SIGAP web, or "
                        "try again later.")
            return render_investigation(client.raise_event(event), event, web)
    except SigapError as e:
        if e.status == 404:
            return f"SIGAP has no run `{args.get('run_id', '')}`. Check the id, or ask for the latest status."
        return f"SIGAP refused the request ({e.status}): {e.detail[:200] or 'no detail'}"
    except SigapUnreachable:
        return "SIGAP is not answering right now. Nothing was raised. Try again in a minute."
    except NotConfigured as e:
        return f"The SIGAP connection is not configured on this agent: {e}."
    return HELP


def demo() -> None:
    assert classify("Investigate: Ningbo port closed for 6 days")[0] == "investigate_disruption"
    assert classify("What is about to break this week?")[0] == "risk_scan"
    assert classify("status of run_1a2b3c4d5e6f")[1]["run_id"] == "run_1a2b3c4d5e6f"
    assert classify("How is the Ningbo investigation going?")[0] == "disruption_status"
    assert classify("Pelabuhan Ningbo tutup 6 hari, tolong selidiki")[0] == "investigate_disruption"
    assert classify("Which suppliers are single-sourced?")[0] == "risk_scan"
    assert classify("hello there")[0] == "help", "a greeting must raise nothing"
    assert classify('{"skill": "risk_scan"}')[0] == "risk_scan"
    assert classify('{"skill": "approve_action"}')[0] == "help", "no fourth skill exists"

    e = event_from_text("Investigate: Ningbo port closed for 6 days, M-4471 at risk")
    assert e["kind"] == "port_closure" and e["payload"]["port"] == "CNNGB", e
    assert e["payload"]["days"] == 6 and e["payload"]["materials"] == ["M-4471"], e
    assert e["title"].startswith("Ningbo port closed"), e["title"]
    assert event_from_text("Shipment held at customs in Priok")["kind"] == "customs_hold"
    assert event_from_text("SUP-2207 missed its shipment")["payload"]["supplier"] == "SUP-2207"

    t = [0.0]
    rl = RateLimit(2, 10, clock=lambda: t[0])
    assert rl.take() and rl.take() and not rl.take()
    t[0] = 11
    assert rl.take(), "the window slides"

    from datetime import datetime, timezone
    now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc).timestamp()
    runs = [{"id": "run_a", "title": "Ningbo port closed for 6 days, M-4471 at risk",
             "kind": "port_closure", "started_at": "2026-10-24T10:00:00+00:00"}]
    assert find_duplicate(e, runs, now=now)["id"] == "run_a"
    old = [{**runs[0], "started_at": "2026-10-20T10:00:00+00:00"}]
    assert find_duplicate(e, old, now=now) is None, "a week-old run is not this disruption"
    other = event_from_text("Investigate: Busan port closed")
    assert find_duplicate(other, runs, now=now) is None, "another port is another disruption"

    many = [{"id": "run_new", "title": "Customs hold at Priok"}, *runs]
    assert pick_run("How is the Ningbo one going?", many)["id"] == "run_a"
    assert pick_run("status please", many)["id"] == "run_new", "no clue → the newest"

    md = render_status({"id": "run_a", "title": "x", "status": "done",
                        "decision": {"agents_called": ["impact", "compliance"],
                                     "recommendation": "Recommend B.",
                                     "untrusted_on_board": ["impact.get_material_stock"]},
                        "actions": [{"kind": "draft_po", "status": "pending",
                                     "payload": {"material": "M-4471", "cost_idr": 94000000}}]},
                       "https://sigap.example.org")
    assert "Elsa, Kira" in md and "Rp 94.000.000" in md and "get_material_stock" in md
    assert "/disruptions/run_a" in md and NO_APPROVAL in md
    print("skills ok, intent ✓ · help instead of a guess ✓ · event from words ✓ "
          "· rate limit ✓ · duplicate held back ✓ · status keeps origin labels ✓")


if __name__ == "__main__":
    demo()
