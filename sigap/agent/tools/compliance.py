"""Kira's tools (Rules).

Rules from the rule pack (sigap/references/README.md), not from the model's
memory. A rejection from this file is final: cost arguments cannot overturn it.

The pack is a file a person writes and signs off: each rule carries its value,
the document it was read from, and whether someone checked it against that
document. Where the pack states no rule, the built-in value below applies and
the ruling says so, labelled modelled, because an assumption is not a rule.
The contract floor and the company's current position fall back to the
company profile, which is the installation's own master data.

    rule pack   references/rule-pack.json, or SIGAP_RULE_PACK
    holidays    Indonesian public holidays from Nager.Date, live, plus the
                collective leave (cuti bersama) the pack lists, which no
                public calendar carries
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.config import CFG
from core.provenance import Origin, Result, weakest
from core.registry import register
from tools.fetcher import as_of, fixture, profile, read

REFERENCES = pathlib.Path(__file__).resolve().parent.parent.parent / "references"

#: Rules the code carries for when the pack states none. Each is an assumption
#: until a pack entry with a source replaces it.
BUILT_IN: Dict[str, Tuple[Any, str]] = {
    "lartas_new_origin_working_days": (
        10, "built-in assumption: working days an import licence takes for an origin "
            "country new to the company"),
    "default_port_dwell_days": (
        4, "built-in assumption: days from discharge to release when no customs "
           "history is on record"),
}

#: Rules that are the company's own figures, read from its profile.
FROM_PROFILE = {"tkdn_contract_floor_pct": "TkdnContractFloorPct",
                "tkdn_current_pct": "TkdnCurrentPct"}


@dataclass
class Rule:
    name: str
    value: Any
    source: str
    verified: bool
    origin: Origin

    def as_dict(self) -> dict:
        return {"rule": self.name, "value": self.value, "source": self.source,
                "verified": self.verified, "origin": self.origin.value}


#: Where the pack is read from when not CFG.rule_pack. The self-check points
#: it at a scratch file, so it reads the same on any installation.
_pack_file: Optional[pathlib.Path] = None


def pack_path() -> pathlib.Path:
    return _pack_file or pathlib.Path(CFG.rule_pack)


def pack_source() -> str:
    """How a result read from the pack names its source."""
    return f"rule pack {pack_path().name}"


def load_pack() -> Optional[dict]:
    """The installed rule pack, or None when there is none.

    A pack that does not parse is not quietly treated as absent: a person
    wrote it to be applied, so it raises and the ruling fails out loud.
    """
    f = pack_path()
    if not f.exists():
        return None
    try:
        pack = json.loads(f.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"the rule pack at {f} is not valid JSON: {e}") from e
    if not isinstance(pack, dict):
        raise ValueError(f"the rule pack at {f} must be a JSON object")
    return pack


def rule(name: str, pack: Optional[dict] = None) -> Rule:
    """One rule, from the pack where it states it, else profile or built-in.

    Verified with a source is the only state that counts as derived. A pack
    entry nobody checked is still somebody's assumption, written down.
    """
    entry = ((pack or {}).get("rules") or {}).get(name)
    if isinstance(entry, dict) and entry.get("value") is not None:
        source = str(entry.get("source") or "").strip()
        verified = bool(entry.get("verified")) and bool(source)
        return Rule(name, entry["value"], source or "rule pack, no source given", verified,
                    Origin.DERIVED if verified else Origin.MODELLED)
    if name in FROM_PROFILE:
        return Rule(name, profile()[FROM_PROFILE[name]], "company profile", False,
                    Origin.MODELLED)
    value, why = BUILT_IN[name]
    return Rule(name, value, why, False, Origin.MODELLED)


def collective_leave(pack: Optional[dict]) -> Dict[date, str]:
    """Cuti bersama the pack lists. No public calendar carries them."""
    out: Dict[date, str] = {}
    for d in (pack or {}).get("collective_leave") or []:
        try:
            out[date.fromisoformat(str(d["date"]))] = str(d.get("name") or "collective leave")
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _public_holidays(first: date, last: date) -> Result:
    """Indonesian public holidays between two dates. Its own function so the
    self-check can stand in for the network."""
    from clients.web_data import public_holidays
    return public_holidays("ID", first.isoformat(), last.isoformat())


def closed_days(first: date, last: date, pack: Optional[dict]) -> Tuple[Dict[date, str], Result]:
    """Days customs and licensing do not work, beyond weekends: national
    holidays and the pack's collective leave, with the holiday read's Result
    so the caller can say when the calendar could not be read."""
    r = _public_holidays(first, last)
    days: Dict[date, str] = {}
    for h in (r.value or {}).get("holidays") or []:
        try:
            day = date.fromisoformat(h["date"])
        except (KeyError, TypeError, ValueError):
            continue
        days[day] = h.get("name") or "public holiday"
    for d, name in collective_leave(pack).items():
        if first <= d <= last:
            days.setdefault(d, name)
    return days, r


def _add_working_days(start: date, days: int, closed: Optional[Set[date]] = None) -> date:
    d, left = start, days
    while left > 0:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in (closed or set()):
            left -= 1
    return d


@register(
    "check_local_constraints", "compliance",
    "Test one supply option against TKDN, LARTAS and the holiday calendar. Returns "
    "allowed/blocked with a reason that names the rule and the numbers, the rules it "
    "applied and where each came from. A rejection here is final and must not be "
    "overridden on cost.",
    {"option_id": {"type": "string", "description": "option id, e.g. 'A'"}},
    ["option_id"],
)
def check_local_constraints(option_id: str) -> Result:
    pack = load_pack()
    # The options Clint offered, from wherever he read them: SAP, an upload, the fixture.
    options = read("AlternateSource", ids=[option_id])
    option = next(iter(options.value or []), None)
    if option is None:
        # Name the ids that do exist. A caller reaches here mainly one way: the
        # options were listed by one agent, renumbered in the hand-off, and
        # ruled on by another under the new numbers, so every call misses and
        # nothing is ever cleared. Refusing without saying what the real ids
        # are costs a whole handling; saying so lets the next call be right.
        known = [str(o.get("id")) for o in (read("AlternateSource").value or []) if o.get("id")]
        hint = ""
        if known:
            shown = ", ".join(known[:10])
            hint = (f". The options on record are: {shown}"
                    + (f" and {len(known) - 10} more" if len(known) > 10 else "")
                    + ". Use the id exactly as find_alternate_sources returned it, not a "
                      "number assigned to it afterwards")
        return Result(None, Origin.MISSING, "rule pack",
                      note=f"unknown option '{option_id}'{hint}")

    reasons: List[str] = []
    unknown: List[str] = []
    allowed = True
    floor_rule, current_rule = rule("tkdn_contract_floor_pct", pack), rule("tkdn_current_pct", pack)
    floor, current = float(floor_rule.value), float(current_rule.value)
    used = [floor_rule, current_rule]

    # --- TKDN ---
    # The rule: an option must not WORSEN the local-content position, and must
    # not push it below the contract floor when we are currently above it. A
    # company already below the floor does not thereby lose every option, what
    # is forbidden is making it worse.
    tkdn = option.get("TkdnAfterPct")
    if tkdn is not None:
        if tkdn < current - 0.05:                       # rounding tolerance
            allowed = False
            reasons.append(
                f"TKDN falls from {current}% to {tkdn}%"
                + (f", further below the {floor}% contract floor" if tkdn < floor
                   else f", breaching the {floor}% contract floor")
            )
        elif tkdn < floor <= current:
            allowed = False
            reasons.append(f"TKDN drops to {tkdn}%, contract floor {floor}%")
        elif tkdn >= floor > current:
            reasons.append(f"TKDN rises to {tkdn}%, back above the {floor}% floor")
    elif option.get("Supplier") != "INTERNAL":
        # Moving our own stock leaves the position where it is. Buying from
        # anyone else changes it by an amount nobody has stated, and an option
        # whose effect cannot be checked has not passed the check.
        allowed = False
        unknown.append("TkdnAfterPct")
        reasons.append(
            "not cleared: the TKDN position after this option is not known. SAP holds no "
            "local-content figure; upload AlternateSource with TkdnAfterPct for it")

    # --- LARTAS ---
    arrives = date.fromisoformat(option["ArrivalDate"]) if option.get("ArrivalDate") else None
    new_origin = option.get("NewOrigin")
    calendar: Optional[Result] = None
    if new_origin is None and (option.get("Origin") or "ID") != "ID":
        # Unknown is taken as new: the delay is the cautious side of the guess.
        unknown.append("NewOrigin")
        new_origin = True
        reasons.append(f"whether {option['Origin']} is a new origin is not recorded, so "
                       "it is treated as one")
    if arrives is None:
        unknown.append("ArrivalDate")
        reasons.append("no arrival date: the source records no delivery time")
    elif new_origin:
        lartas = rule("lartas_new_origin_working_days", pack)
        used.append(lartas)
        days = int(lartas.value)
        # Licensing offices close on holidays as well as weekends. The window
        # read is generous: ten working days never span more than five weeks.
        closed, calendar = closed_days(arrives, arrives + timedelta(days=7 * (days // 5 + 3)),
                                       pack)
        licensed = _add_working_days(arrives, days, set(closed))
        skipped = sorted(d for d in closed if arrives < d <= licensed and d.weekday() < 5)
        reasons.append(
            f"LARTAS: a new origin country ({option['Origin']}) adds {days} working days, "
            f"effective arrival {licensed}"
            + (", counting past " + ", ".join(f"{closed[d]} ({d})" for d in skipped)
               if skipped else "")
        )
        if calendar.value is None:
            unknown.append("holiday calendar")
            reasons.append(f"the holiday calendar could not be read ({calendar.note}), so "
                           "only weekends were skipped")
        arrives = licensed

    origins = [options.origin, Origin.DERIVED, *(r.origin for r in used)]
    if calendar is not None and calendar.value is None:
        origins.append(Origin.MODELLED)
    assumed = [r for r in used if not r.verified]
    note = ("" if not assumed else
            "not from a verified rule pack: " + "; ".join(
                f"{r.name} {r.value} ({r.source})" for r in assumed))
    return Result(
        {
            "option_id": option_id,
            "allowed": allowed,
            "reason": "; ".join(reasons) if reasons else "no rule breached",
            "arrival_effective": arrives.isoformat() if arrives else None,
            "tkdn_after": tkdn,
            "rules": [r.as_dict() for r in used],
            **({"unknown": unknown} if unknown else {}),
        },
        weakest(*origins),
        pack_source() if pack else "built-in rules + company profile",
        note=note,
    )


def _import_origins() -> set:
    """Countries the company has already imported from, from its own orders.

    A new origin is the thing LARTAS charges for, and whether a country is new
    is a fact about this company's history, not a judgement. Derived from the
    purchase order book and the supplier master rather than asked of anyone.
    """
    suppliers = {str(s.get("Supplier")): str(s.get("Country") or "")
                 for s in (read("Supplier").value or [])}
    seen = set()
    for o in read("PurchaseOrder").value or []:
        c = suppliers.get(str(o.get("Supplier")))
        if c:
            seen.add(c)
    return seen


@register(
    "check_supplier_constraints", "compliance",
    "Test one SUPPLIER against TKDN and LARTAS, for a purchase that comes from a "
    "quotation rather than from a costed supply option. Returns allowed/blocked with a "
    "reason that names the rule and the numbers, the rules it applied and where each "
    "came from. A rejection here is final and must not be overridden on price. Use it "
    "before drafting a purchase order; use check_local_constraints for an option the "
    "sourcing search returned.",
    {"supplier": {"type": "string", "description": "a supplier id, e.g. SUP-4417"}},
    ["supplier"],
)
def check_supplier_constraints(supplier: str) -> Result:
    """Kira, on a supplier.

    check_local_constraints rules an AlternateSource option, which carries the
    local-content position the company would be left with. A quotation carries
    no such figure, so until now the whole procurement path reached a draft
    purchase order without a ruling at all: the veto had a back door, and price
    walked through it.

    What can honestly be said about a supplier, and nothing more:

      * A domestic supplier contributes local content. Without a certified
        percentage on record there is nothing to check, and an effect that
        cannot be checked has not passed the check - the same discipline
        check_local_constraints applies to an unknown TkdnAfterPct.
      * A foreign supplier contributes none. It therefore cannot improve the
        position, and when the company already sits below its contract floor
        the rule "must not worsen" is breached by definition.
      * A country the company has never imported from is a new origin, and
        LARTAS charges working days for it.
      * A certificate that has lapsed takes its local content with it.

    What is deliberately NOT claimed: the position this company would be left
    with after the order. That depends on volume and mix, a quotation states
    neither, and inventing it would be exactly the confident unlabelled number
    this file exists to refuse.
    """
    sid = (supplier or "").strip()
    found = read("Supplier", ids=[sid])
    firm = next(iter(found.value or []), None)
    if firm is None:
        known = sorted({str(s.get("Supplier")) for s in (read("Supplier").value or [])})[:10]
        return Result(None, Origin.MISSING, "supplier master",
                      note=f"unknown supplier '{sid}'"
                           + (f". On the approved list: {', '.join(known)}" if known else ""))

    pack = load_pack()
    floor_rule, current_rule = rule("tkdn_contract_floor_pct", pack), rule("tkdn_current_pct", pack)
    floor, current = float(floor_rule.value), float(current_rule.value)
    used = [floor_rule, current_rule]
    reasons: List[str] = []
    unknown: List[str] = []
    allowed = True

    country = str(firm.get("Country") or "").strip().upper()
    certified = firm.get("TkdnCertifiedPct")

    # --- TKDN ---
    if country == "ID":
        if certified is None:
            allowed = False
            unknown.append("TkdnCertifiedPct")
            reasons.append(
                f"not cleared: {sid} is domestic but carries no certified local-content "
                "figure, so its effect on TKDN cannot be checked. Upload Supplier with "
                "TkdnCertifiedPct, or add the certificate to the rule pack")
        elif float(certified) < current - 0.05:
            allowed = False
            reasons.append(
                f"TKDN: {sid} is certified at {certified}%, below the company's current "
                f"{current}%, so buying here moves the position down")
        else:
            reasons.append(f"TKDN: {sid} is certified at {certified}%, at or above the "
                           f"company's current {current}%")
    else:
        if current < floor:
            allowed = False
            reasons.append(
                f"TKDN: {country or 'a foreign'} supply carries no local content, and the "
                f"company is already at {current}% against a {floor}% contract floor. An "
                "order here cannot improve the position and the rule is that it must not "
                "worsen")
        else:
            reasons.append(
                f"TKDN: {country or 'foreign'} supply adds no local content. The company is "
                f"at {current}% against a {floor}% floor, and how far this order would "
                "dilute it depends on volume, which a quotation does not state")

    # --- certificates ---
    today = as_of()
    for c in (pack or {}).get("certificates") or []:
        if str(c.get("supplier")) != sid:
            continue
        until = str(c.get("valid_until") or "")
        try:
            left = (date.fromisoformat(until) - today).days if until else None
        except ValueError:
            left = None
        if left is not None and left < 0:
            allowed = False
            reasons.append(f"certificate {c.get('certificate')} lapsed on {until}, "
                           f"{-left} day(s) ago, so the local content behind it is gone")
        elif left is not None:
            reasons.append(f"certificate {c.get('certificate')} is valid for another "
                           f"{left} day(s), to {until}")

    # --- LARTAS ---
    licensed_from = None
    if country and country != "ID":
        history = _import_origins()
        if country not in history:
            lartas = rule("lartas_new_origin_working_days", pack)
            used.append(lartas)
            days = int(lartas.value)
            closed, calendar = closed_days(today, today + timedelta(days=7 * (days // 5 + 3)), pack)
            licensed_from = _add_working_days(today, days, set(closed))
            reasons.append(
                f"LARTAS: the company has not imported from {country} before, so an import "
                f"licence adds {days} working days; nothing from {sid} clears customs before "
                f"{licensed_from}")
            if calendar.value is None:
                unknown.append("holiday calendar")
                reasons.append(f"the holiday calendar could not be read ({calendar.note}), so "
                               "only weekends were skipped")
        else:
            reasons.append(f"LARTAS: the company already imports from {country}, so no new "
                           "origin licence is needed")

    assumed = [r for r in used if not r.verified]
    return Result(
        {
            "supplier": sid,
            "supplier_name": firm.get("SupplierName"),
            "country": country or None,
            "allowed": allowed,
            "reason": "; ".join(reasons) if reasons else "no rule breached",
            "tkdn_certified_pct": certified,
            "tkdn_current_pct": current,
            "tkdn_contract_floor_pct": floor,
            "earliest_customs_clearance": licensed_from.isoformat() if licensed_from else None,
            "rules": [r.as_dict() for r in used],
            **({"unknown": unknown} if unknown else {}),
        },
        weakest(found.origin, Origin.DERIVED, *(r.origin for r in used)),
        pack_source() if pack else "built-in rules + company profile",
        note=("" if not assumed else
              "not from a verified rule pack: " + "; ".join(
                  f"{r.name} {r.value} ({r.source})" for r in assumed)),
    )


#: Every rule name the pack may state. Anything else is a typo, and a typo is
#: the dangerous case: `rule()` falls back to the profile or the built-in and
#: the ruling reads as if the pack had simply stayed silent.
KNOWN_RULES = (*FROM_PROFILE, *BUILT_IN)


def validate_pack(pack: Optional[dict]) -> List[str]:
    """Problems with an installed rule pack, named. Deterministic.

    Returns a list of human-readable problems, empty when the pack is sound (or
    absent, which is a normal state). This never raises and is never fatal: a
    company whose pack has a typo still gets its handling, it just gets told.
    """
    if not pack:
        return []
    problems: List[str] = []
    rules = pack.get("rules")
    if rules is not None and not isinstance(rules, dict):
        return ["'rules' must be an object of rule name -> {value, source, verified}"]
    for name, entry in (rules or {}).items():
        if name not in KNOWN_RULES:
            problems.append(
                f"unknown rule '{name}' — it is ignored, and the ruling will use the "
                f"built-in or the company profile instead. One of: {', '.join(KNOWN_RULES)}")
            continue
        if not isinstance(entry, dict) or entry.get("value") is None:
            problems.append(f"rule '{name}' has no value, so it is ignored")
            continue
        if not isinstance(entry["value"], (int, float)) or isinstance(entry["value"], bool):
            problems.append(f"rule '{name}' value must be a number, not {entry['value']!r}")
        if entry.get("verified") and not str(entry.get("source") or "").strip():
            problems.append(
                f"rule '{name}' is marked verified but names no source; it will be "
                "treated as an assumption until it cites the document it was read from")
    for i, d in enumerate((pack.get("collective_leave") or []), start=1):
        if not isinstance(d, dict) or not str(d.get("date") or "").strip():
            problems.append(f"collective_leave entry {i} has no date, so it is ignored")
            continue
        try:
            date.fromisoformat(str(d["date"]))
        except ValueError:
            problems.append(f"collective_leave entry {i}: '{d['date']}' is not YYYY-MM-DD")
    for i, cert in enumerate((pack.get("certificates") or []), start=1):
        if not isinstance(cert, dict) or not str(cert.get("supplier") or "").strip():
            problems.append(f"certificate entry {i} names no supplier, so it is ignored")
    return problems


def pack_status() -> Dict[str, Any]:
    """How much of the knowledge base is verified, and what is wrong with it.

    Reads the pack file and nothing else: no profile, no SAP, no holiday
    calendar. A report states the trust level of the rules it rests on, and it
    must be able to do that for the price of reading one file rather than the
    price of a ruling. The same figures `get_rule_pack` returns, which is the
    agent's way in; this is the record's way in.

    A rule counts as verified only where the pack states it, gives a value,
    marks it verified AND cites a source — the same test `rule()` applies, so
    the two can never disagree about what is trusted.
    """
    try:
        pack = load_pack()
    except ValueError as e:
        # A pack that does not parse is not a pack with no rules: nothing in it
        # is trusted, and the reason is the first thing to show.
        return {"pack": str(pack_path()), "total": len(KNOWN_RULES), "verified": 0,
                "unverified": list(KNOWN_RULES), "problems": [str(e)]}
    rules = (pack or {}).get("rules")
    if not isinstance(rules, dict):
        rules = {}
    verified = {n for n in KNOWN_RULES
                if isinstance(rules.get(n), dict)
                and rules[n].get("value") is not None
                and rules[n].get("verified")
                and str(rules[n].get("source") or "").strip()}
    return {"pack": str(pack_path()) if pack else None,
            "total": len(KNOWN_RULES), "verified": len(verified),
            "unverified": [n for n in KNOWN_RULES if n not in verified],
            "problems": validate_pack(pack)}


@register(
    "get_rule_pack", "compliance",
    "The rules check_local_constraints applies, each with its value, the document it "
    "was read from and whether a person verified it there: the TKDN contract floor and "
    "the current position, the LARTAS licensing delay for a new origin country, the "
    "default port dwell, the collective leave on file and how many TKDN certificates "
    "are held. Read it to cite a rule, or to say plainly that one is an assumption.",
    {}, [],
)
def get_rule_pack() -> Result:
    pack = load_pack()
    rules = [rule(n, pack) for n in (*FROM_PROFILE, *BUILT_IN)]
    leave = collective_leave(pack)
    unverified = [r.name for r in rules if not r.verified]
    value = {
        "pack": str(pack_path()) if pack else None,
        "version": (pack or {}).get("version"),
        "rules": [r.as_dict() for r in rules],
        "collective_leave": [{"date": d.isoformat(), "name": n} for d, n in sorted(leave.items())],
        "certificates": len((pack or {}).get("certificates") or []),
        # The trust state of the knowledge base, as a figure, so a reader does
        # not have to count booleans to learn how much of this is assumption.
        "verified_rules": len(rules) - len(unverified),
        "total_rules": len(rules),
        "unverified": unverified,
        "problems": validate_pack(pack),
    }
    if pack is None:
        return Result(value, Origin.MODELLED, "built-in rules + company profile",
                      note="no rule pack is installed, so every rule is the built-in "
                           "assumption or the company profile; no collective leave and no "
                           "certificate is on file")
    note = (("not verified against a source: " + ", ".join(unverified))
            if unverified else "every rule verified against its source")
    if value["problems"]:
        # A malformed pack is said out loud rather than silently ignored: the
        # quiet failure is a misspelled rule reading exactly like no rule.
        note += ". Problems in the pack: " + "; ".join(value["problems"])
    return Result(value, Origin.MODELLED if unverified else Origin.DERIVED, pack_source(),
                  note=note)


def demo() -> None:
    import tempfile

    p = profile()
    assert p["TkdnCurrentPct"] < p["TkdnContractFloorPct"], \
        "the scenario assumes the company already sits below the floor"

    # The network stands aside: a fixed calendar with one weekday holiday. And
    # an installed pack stands aside too, so the check reads the same anywhere.
    global _public_holidays, _pack_file
    real_holidays = _public_holidays
    scratch = tempfile.TemporaryDirectory()
    absent = pathlib.Path(scratch.name) / "absent.json"
    _pack_file = absent
    # The shape clients/web_data.public_holidays returns, so the check reads
    # what the live calendar hands over and not a shape of its own.
    _public_holidays = lambda first, last: Result(          # noqa: E731
        {"country": "ID", "from": first.isoformat(), "to": last.isoformat(),
         "holidays": [{"date": "2026-09-30", "name": "Test Day"}]}, Origin.LIVE, "Nager.Date")
    try:
        # No pack installed: every rule is an assumption and the ruling says so.
        assert load_pack() is None
        a = check_local_constraints("A")
        # An option that keeps TKDN where it is must NOT be rejected just for
        # being under the floor, that was the bug this check exists to catch.
        assert a.value["allowed"] is True, a.value["reason"]
        assert a.origin is Origin.MODELLED and "not from a verified rule pack" in a.note, a.note

        # An option that actively worsens TKDN must be rejected.
        e = check_local_constraints("E").value
        assert e["allowed"] is False and "TKDN" in e["reason"], e

        # A new origin country delays arrival past its booked date, and the
        # count of working days steps over the holiday in the window.
        d = check_local_constraints("D").value
        booked = next(o for o in fixture("AlternateSource") if o["id"] == "D")["ArrivalDate"]
        assert d["arrival_effective"] > booked, d
        assert "LARTAS" in d["reason"] and "Test Day" in d["reason"], d["reason"]
        weekends_only = _add_working_days(date.fromisoformat(booked), 10)
        assert date.fromisoformat(d["arrival_effective"]) > weekends_only, d

        assert check_local_constraints("ZZ").origin is Origin.MISSING

        # An option read from SAP carries no TKDN figure: it is not cleared, and says why.
        global read
        real = read
        sap_row = [{"id": "IR1-1710", "label": "SAP info record", "Supplier": "17300001",
                    "Material": "M-4471", "ArrivalDate": "2026-09-20", "Origin": "CN",
                    "TkdnAfterPct": None, "NewOrigin": None}]
        read = lambda entity, **kw: Result(sap_row, Origin.LIVE, "test")   # noqa: E731
        try:
            u = check_local_constraints("IR1-1710")
        finally:
            read = real
        assert u.value["allowed"] is False and set(u.value["unknown"]) == {"TkdnAfterPct", "NewOrigin"}
        assert u.value["arrival_effective"] > "2026-09-20", "an unknown origin is treated as new"
        # Live option, built-in rules: the ruling is no stronger than its weakest rule.
        assert u.origin is Origin.MODELLED, u.origin

        # A pack with verified rules is what makes a ruling derived. Written to a
        # scratch file, read through the same path an installation uses.
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / "rule-pack.json"
            src = "test contract, clause 1"
            f.write_text(json.dumps({
                "version": "test",
                "rules": {n: {"value": v, "source": src, "verified": True} for n, v in (
                    ("tkdn_contract_floor_pct", 40.0), ("tkdn_current_pct", 38.2),
                    ("lartas_new_origin_working_days", 10), ("default_port_dwell_days", 4))},
                "collective_leave": [{"date": "2026-10-01", "name": "Test Leave"}],
            }))
            _pack_file = f
            try:
                read = lambda entity, **kw: Result(           # noqa: E731
                    [dict(sap_row[0], TkdnAfterPct=38.2, NewOrigin=True)], Origin.LIVE, "test")
                try:
                    v = check_local_constraints("IR1-1710")
                finally:
                    read = real
                assert v.origin is Origin.DERIVED and not v.note, (v.origin, v.note)
                assert "Test Leave" in v.value["reason"], v.value["reason"]
                pack = get_rule_pack()
                assert pack.origin is Origin.DERIVED and pack.value["collective_leave"], pack.brief()
                # The same trust state, for the price of reading one file: this
                # is what a report states, and it must agree with the tool.
                st = pack_status()
                assert st["verified"] == st["total"] == pack.value["total_rules"], st
                assert st["unverified"] == [] and st["problems"] == [], st

                # A rule written down but not checked is still an assumption.
                f.write_text(json.dumps({"rules": {"lartas_new_origin_working_days":
                                                   {"value": 12, "verified": True}}}))
                r = rule("lartas_new_origin_working_days", load_pack())
                assert r.value == 12 and not r.verified and r.origin is Origin.MODELLED, r
                # Marked verified with no source: said out loud, not ignored.
                assert any("names no source" in p for p in validate_pack(load_pack()))

                # A misspelled rule name is the dangerous case: `rule()` falls
                # back to the profile, so the pack reads exactly as if it had
                # stayed silent. It must be named rather than swallowed.
                f.write_text(json.dumps({"rules": {
                    "tkdn_floor_pct": {"value": 40.0, "source": "x", "verified": True},
                    "default_port_dwell_days": {"value": "four", "source": "x"},
                }, "collective_leave": [{"date": "not-a-date"}]}))
                problems = validate_pack(load_pack())
                assert any("unknown rule 'tkdn_floor_pct'" in p for p in problems), problems
                assert any("must be a number" in p for p in problems), problems
                assert any("not YYYY-MM-DD" in p for p in problems), problems
                # The tool reports them instead of failing the handling.
                reported = get_rule_pack()
                assert reported.value["problems"] == problems
                assert "Problems in the pack" in reported.note
                assert reported.value["total_rules"] == 4

                # And the cheap read agrees that nothing here is trusted.
                st = pack_status()
                assert st["verified"] == 0 and st["problems"] == problems, st

                f.write_text("{not json")
                try:
                    load_pack()
                    raise AssertionError("a broken pack must fail out loud")
                except ValueError:
                    pass
                # A pack that will not parse is not a pack with no rules: a
                # report must be able to say why nothing in it is trusted
                # rather than raise in the middle of being assembled.
                broken = pack_status()
                assert broken["verified"] == 0 and broken["problems"], broken
                assert "not valid JSON" in broken["problems"][0], broken
            finally:
                _pack_file = absent
        assert get_rule_pack().origin is Origin.MODELLED
    finally:
        _public_holidays, _pack_file = real_holidays, None
        scratch.cleanup()

    print("compliance ok, keeps TKDN ✓ · worsens TKDN → blocked ✓ · LARTAS delay over "
          "holidays ✓ · unknown TKDN → not cleared ✓")
    print("  no pack → modelled, named ✓ · verified pack → derived ✓ · unsourced rule "
          "stays an assumption ✓ · broken pack fails ✓ · pack_status agrees with the tool ✓")
    # ---- Kira on a supplier, which is the path a quotation takes ----
    # check_local_constraints rules an option; a purchase order comes from a
    # quotation, which is not one. Without this the veto had a back door.
    from tools.fetcher import read as _read
    firms = {str(s.get("Supplier")): s for s in (_read("Supplier").value or [])}
    dom = next(s for s in firms.values()
               if s.get("Country") == "ID" and s.get("TkdnCertifiedPct") is not None)
    foreign = next(s for s in firms.values() if s.get("Country") not in ("ID", None))

    # The company sits below its contract floor in this fixture, so foreign
    # supply cannot help and the rule "must not worsen" is breached outright.
    assert p["TkdnCurrentPct"] < p["TkdnContractFloorPct"]
    bad = check_supplier_constraints(str(foreign["Supplier"]))
    assert bad.value["allowed"] is False, bad.value
    assert "carries no local content" in bad.value["reason"], bad.value["reason"]
    assert "must not worsen" in bad.value["reason"]

    good = check_supplier_constraints(str(dom["Supplier"]))
    assert good.value["allowed"] is True, good.value["reason"]
    assert "certified at" in good.value["reason"], good.value["reason"]

    # A domestic firm with no certified figure is NOT cleared. An effect that
    # cannot be checked has not passed the check, exactly as an unknown
    # TkdnAfterPct is treated above.
    blind = {s for s in firms.values()
             if s.get("Country") == "ID" and s.get("TkdnCertifiedPct") is None}
    if blind:
        r = check_supplier_constraints(str(next(iter(blind))["Supplier"]))
        assert r.value["allowed"] is False and "cannot be checked" in r.value["reason"], r.value

    assert check_supplier_constraints("SUP-NOBODY").value is None
    assert "unknown supplier" in check_supplier_constraints("SUP-NOBODY").note

    # LARTAS on a country the company has never bought from. The fixture has
    # imported from every country its suppliers sit in, so the history is stood
    # aside to reach the branch rather than left untested.
    global _import_origins
    real_origins = _import_origins
    _import_origins = lambda: {"ID"}                      # noqa: E731
    try:
        fresh = check_supplier_constraints(str(foreign["Supplier"]))
        assert "has not imported from" in fresh.value["reason"], fresh.value["reason"]
        assert fresh.value["earliest_customs_clearance"], fresh.value
        assert fresh.value["earliest_customs_clearance"] > str(as_of()), fresh.value
    finally:
        _import_origins = real_origins
    print("  Kira rules a supplier too: foreign supply below the floor blocked ✓ · "
          "unknown local content not cleared ✓ · a new origin costs LARTAS days ✓")

    print("  a misspelled rule is named, not swallowed ✓ · pack problems reported without "
          "failing the handling ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_COMPLIANCE_CHECK")
    demo()
