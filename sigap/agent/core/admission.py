"""Fair admission: a bound on how many specialists run at once.

Ported from  fair-admission.ts, kept to the half SIGAP's scale needs.

SmartX gates concurrent workers with a global cap, a per-operator cap, and
weight units (a heavy worker costs several, a light one costs one), so that on
one box ten operators cannot each spawn enough heavy workers to melt it, and no
one operator can starve the rest. SIGAP will need exactly this the day it goes
multi-tenant (its own roadmap note: "move to Postgres once this is
multi-tenant"). The elaborate parts of  version — dynamic fair-share
and waiter-priority aging — solve a many-operators-contending-for-one-box
problem SIGAP does not have yet, so they are deliberately left out. If that day
comes, they port the same way.

Two differences from SmartX, both because SIGAP is Python threads, not a Bun
event loop:
  * a lock guards acquire/release (a single-threaded event loop needs none);
  * the async dispatcher (engine/dispatch.py) runs specialists on a thread
    pool, so the contention this bounds is real within one process.

Flag-gated (SIGAP_FAIR_ADMISSION, default on) with generous defaults, so for a
single operator it does not gate a normal handling — it only bites under
genuine concurrency. Non-blocking: tryAcquire only gates; a caller refused does
not wait, it retries on a later dispatch pass, exactly as  does.
"""
from __future__ import annotations

import os
import threading
from typing import Dict, Optional


def _clamp_int(v: Optional[str], default: int, lo: int, hi: int) -> int:
    """Parse an env knob, clamp to [lo, hi]. A blank/unset/non-numeric value
    falls back to `default`, never the floor — a blank .env line must not
    silently collapse the cap to 1 ( clampInt, same reasoning)."""
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return max(lo, min(hi, default))
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def _clamp_weight(w) -> int:
    """A weight is a whole number >= 1. A bad caller (0, negative, fractional)
    falls back to 1 so the accounting can never be corrupted: 0 would admit an
    unbounded number against a finite budget, a negative would inflate it on
    release."""
    try:
        n = int(float(w))
    except (TypeError, ValueError):
        return 1
    return n if n >= 1 else 1


ANON = "_anon"


class FairAdmission:
    """Global + per-operator weighted admission. Thread-safe. Non-blocking."""

    def __init__(self, global_slots: Optional[int] = None,
                 per_operator: Optional[int] = None,
                 enabled: Optional[bool] = None):
        self._on = (os.environ.get("SIGAP_FAIR_ADMISSION", "1") != "0"
                    if enabled is None else enabled)
        self._global = _clamp_int(
            str(global_slots) if global_slots is not None
            else os.environ.get("SIGAP_GLOBAL_SLOTS"), 8, 1, 256)
        self._per_op = _clamp_int(
            str(per_operator) if per_operator is not None
            else os.environ.get("SIGAP_PER_OPERATOR_SLOTS"), 4, 1, self._global)
        self._active: Dict[str, int] = {}
        self._total = 0
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._on

    def try_acquire(self, operator_id: str, weight: int = 1) -> bool:
        """Admit `weight` units for `operator_id` if they fit BOTH budgets.
        All-or-nothing. Returns False (taking nothing) when refused. When the
        feature is off, always admits but still counts, so release() balances."""
        w = _clamp_weight(weight)
        k = operator_id or ANON
        with self._lock:
            held = self._active.get(k, 0)
            if self._on and (self._total + w > self._global or held + w > self._per_op):
                return False
            self._total += w
            self._active[k] = held + w
            return True

    def release(self, operator_id: str, weight: int = 1) -> None:
        """Give back the EXACT weight acquired. Over-release is a no-op and can
        never drive a bucket or the total negative ( rule: release what
        was acquired, never recompute — the slot-leak class they fixed)."""
        w = _clamp_weight(weight)
        k = operator_id or ANON
        with self._lock:
            cur = self._active.get(k, 0)
            if cur <= 0:
                return
            removed = min(w, cur)
            nxt = cur - removed
            if nxt == 0:
                self._active.pop(k, None)
            else:
                self._active[k] = nxt
            self._total = max(0, self._total - removed)

    def active_for(self, operator_id: str) -> int:
        with self._lock:
            return self._active.get(operator_id or ANON, 0)

    def total_active(self) -> int:
        with self._lock:
            return self._total

    def stats(self) -> dict:
        with self._lock:
            return {"total": self._total, "per_operator": dict(self._active),
                    "global": self._global, "per_op_cap": self._per_op,
                    "enabled": self._on}


#: One process-global instance shared by every handling, like
#: globalSwarmAdmission. The dispatcher acquires from it before running a
#: specialist and releases when that specialist reaches a terminal state.
GLOBAL = FairAdmission()


def demo() -> None:
    fa = FairAdmission(global_slots=4, per_operator=2, enabled=True)

    # Per-operator cap: one operator may hold at most 2.
    assert fa.try_acquire("alice") and fa.try_acquire("alice")
    assert not fa.try_acquire("alice"), "per-operator cap of 2 must refuse the 3rd"
    assert fa.active_for("alice") == 2 and fa.total_active() == 2

    # A second operator is not starved by the first.
    assert fa.try_acquire("bob") and fa.try_acquire("bob")
    assert fa.total_active() == 4
    # Global cap of 4 is now full: a fresh operator is refused.
    assert not fa.try_acquire("carol"), "global cap of 4 must refuse past 4"

    # Release gives the slot back, exactly.
    fa.release("alice")
    assert fa.active_for("alice") == 1 and fa.total_active() == 3
    assert fa.try_acquire("carol"), "a freed global slot admits the newcomer"

    # Weighted: a heavy worker (weight 2) is all-or-nothing.
    fa2 = FairAdmission(global_slots=4, per_operator=3, enabled=True)
    assert fa2.try_acquire("h", weight=2)
    assert not fa2.try_acquire("h", weight=2), "2+2 > per-op cap 3 → refused whole"
    assert fa2.try_acquire("h", weight=1), "weight 1 still fits"
    fa2.release("h", weight=2)
    assert fa2.active_for("h") == 1, "release returns the exact weight acquired"

    # Over-release never goes negative.
    fa2.release("h", weight=99)
    assert fa2.active_for("h") == 0 and fa2.total_active() == 0

    # Disabled: always admits, still balances.
    off = FairAdmission(global_slots=1, per_operator=1, enabled=False)
    assert off.try_acquire("x") and off.try_acquire("x"), "off ⇒ never gates"
    off.release("x"); off.release("x")
    assert off.total_active() == 0

    # Clamp: a blank knob falls back to the default, not the floor.
    assert _clamp_int("", 8, 1, 256) == 8
    assert _clamp_int(None, 8, 1, 256) == 8
    assert _clamp_int("garbage", 8, 1, 256) == 8
    assert _clamp_int("500", 8, 1, 256) == 256
    assert _clamp_weight(0) == 1 and _clamp_weight(-3) == 1 and _clamp_weight(2) == 2

    print("admission ok, per-operator cap ✓ · global cap ✓ · no-starve ✓ "
          "· weighted all-or-nothing ✓ · exact release ✓ · clamps ✓")


if __name__ == "__main__":
    demo()
