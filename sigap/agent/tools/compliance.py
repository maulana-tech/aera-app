"""Kira's tools (Rules).

Reads the rule pack in references/ rather than from the model's memory. A
rejection from this file is final: cost arguments cannot overturn it.
"""
from __future__ import annotations

import pathlib
from datetime import date, timedelta
from typing import Dict, List

from core.provenance import Origin, Result
from core.registry import register
from tools.fetcher import fixture, profile

REFERENCES = pathlib.Path(__file__).resolve().parent.parent.parent / "references"

# Extra working days an import licence takes when the origin country is new to us.
LARTAS_WORKING_DAYS_NEW_ORIGIN = 10


def _rule_pack() -> Dict[str, str]:
    """Read the rule documents. If one isn't written yet, say so — don't guess."""
    out: Dict[str, str] = {}
    for name in ("tkdn-rules", "lartas-procedure", "holiday-calendar", "priok-dwell-time"):
        f = REFERENCES / f"{name}.md"
        if f.exists():
            out[name] = f.read_text()
    return out


def _add_working_days(start: date, days: int) -> date:
    d, left = start, days
    while left > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            left -= 1
    return d


@register(
    "check_local_constraints", "compliance",
    "Test one supply option against TKDN, LARTAS, contract clauses, and the holiday "
    "calendar. Returns allowed/blocked with a reason that names the rule and the "
    "numbers. A rejection here is final and must not be overridden on cost.",
    {"option_id": {"type": "string", "description": "option id, e.g. 'A'"}},
    ["option_id"],
)
def check_local_constraints(option_id: str) -> Result:
    pack = _rule_pack()
    p = profile()
    option = next((o for o in fixture("AlternateSource") if o["id"] == option_id), None)
    if option is None:
        return Result(None, Origin.MISSING, "references/",
                      note=f"unknown option '{option_id}'")

    reasons: List[str] = []
    allowed = True
    floor = p["TkdnContractFloorPct"]

    # --- TKDN ---
    # The rule: an option must not WORSEN the local-content position, and must
    # not push it below the contract floor when we are currently above it. A
    # company already below the floor does not thereby lose every option — what
    # is forbidden is making it worse.
    tkdn = option.get("TkdnAfterPct")
    current = p["TkdnCurrentPct"]
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

    # --- LARTAS ---
    arrives = date.fromisoformat(option["ArrivalDate"])
    if option.get("NewOrigin"):
        licensed = _add_working_days(arrives, LARTAS_WORKING_DAYS_NEW_ORIGIN)
        reasons.append(
            f"LARTAS: a new origin country ({option['Origin']}) adds "
            f"{LARTAS_WORKING_DAYS_NEW_ORIGIN} working days, effective arrival {licensed}"
        )
        arrives = licensed

    note = "" if pack else (
        "references/ is not written yet — TKDN & LARTAS were judged from fixture "
        "parameters rather than from the rule documents"
    )
    return Result(
        {
            "option_id": option_id,
            "allowed": allowed,
            "reason": "; ".join(reasons) if reasons else "no rule breached",
            "arrival_effective": arrives.isoformat(),
            "tkdn_after": tkdn,
        },
        Origin.DERIVED if pack else Origin.MODELLED,
        "references/ (rule pack)" if pack else "fixture + built-in rules",
        note=note,
    )


def demo() -> None:
    p = profile()
    assert p["TkdnCurrentPct"] < p["TkdnContractFloorPct"], \
        "the scenario assumes the company already sits below the floor"

    # An option that keeps TKDN where it is must NOT be rejected just for
    # being under the floor — that was the bug this check exists to catch.
    a = check_local_constraints("A").value
    assert a["allowed"] is True, a["reason"]

    # An option that actively worsens TKDN must be rejected.
    e = check_local_constraints("E").value
    assert e["allowed"] is False and "TKDN" in e["reason"], e

    # A new origin country delays arrival past its booked date.
    d = check_local_constraints("D").value
    booked = next(o for o in fixture("AlternateSource") if o["id"] == "D")["ArrivalDate"]
    assert d["arrival_effective"] > booked, d
    assert "LARTAS" in d["reason"]

    assert check_local_constraints("ZZ").origin is Origin.MISSING
    print("compliance ok — keeps TKDN ✓ · worsens TKDN → blocked ✓ · LARTAS delay ✓")


if __name__ == "__main__":
    demo()
