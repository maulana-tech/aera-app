"""The daily model budget: what AERA may spend on models today, whoever starts the work.

Two caps hold together. The profile's own (constraints.inference_max_usd_per_day), which the business's owner
sets, and a hard one (AERA_DAILY_MODEL_CAP_USD), which hub.py sets on a business that runs on the shared AI
key and its owner cannot raise. The scheduler, a person starting work, running it again and talking to an
agent all ask here first.
"""
from __future__ import annotations

import os
from typing import Optional

from core import business, store


def hard_cap() -> float:
    """The cap the owner cannot raise; 0 when there is none."""
    try:
        return max(0.0, float(os.environ.get("AERA_DAILY_MODEL_CAP_USD", "") or 0))
    except ValueError:
        return 0.0


def refusal() -> Optional[str]:
    """Why no more model work may start today, or None."""
    caps = [c for c in (business.current()["constraints"]["inference_max_usd_per_day"], hard_cap()) if c]
    if not caps:
        return None
    cap = min(caps)
    if store.model_spend_today() >= cap:
        why = (" on the shared AI key; add your own NEAR AI key under Models to lift it"
               if hard_cap() and cap == hard_cap() else "")
        return f"today's model budget (${cap:.2f}) is used{why}. Work starts again tomorrow (UTC)"
    return None


def demo() -> None:
    store.save_profile({**business.EXAMPLE, "constraints": {**business.EXAMPLE["constraints"], "inference_max_usd_per_day": 3.0}}, by="check")
    os.environ.pop("AERA_DAILY_MODEL_CAP_USD", None)
    assert refusal() is None and hard_cap() == 0
    rid = store.start_run(store.record_work_item("request", "x", "api", {}))
    store.close_run(rid, "done", {}, cost_usd=0.6)
    assert refusal() is None, "0.60 is under the profile's 3.00"
    os.environ["AERA_DAILY_MODEL_CAP_USD"] = "0.5"
    r = refusal()
    assert r and "$0.50" in r and "own NEAR AI key" in r, r
    os.environ["AERA_DAILY_MODEL_CAP_USD"] = "nonsense"
    assert hard_cap() == 0
    os.environ.pop("AERA_DAILY_MODEL_CAP_USD", None)
    print("budget ok: profile cap ✓ · hard cap the owner cannot raise ✓ · spend counted from runs and talks ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_BUDGET_CHECK")
    demo()
