"""Data origin labelling.

The house rule: every tool returns a Result, never a bare value. If an input
on a critical path is not LIVE/CACHED/DERIVED, the calculator must not emit a
rupiah figure at all (see engine/simulate.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Origin(str, Enum):
    LIVE = "live"          # straight from SAP / an official API
    CACHED = "cached"      # was live once, carries its timestamp
    DERIVED = "derived"    # computed from something live
    MODELLED = "modelled"  # company profile / fixture — labelled in the open
    MISSING = "missing"    # the lead stops here rather than guessing


#: Origins that may back a rupiah figure shown to a user.
TRUSTED = frozenset({Origin.LIVE, Origin.CACHED, Origin.DERIVED})


@dataclass
class Result:
    value: Any
    origin: Origin
    source: str                      # "API_MATERIAL_STOCK_SRV" / "TKDN register"
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    note: str = ""

    @property
    def trusted(self) -> bool:
        return self.origin in TRUSTED

    def brief(self) -> dict:
        return {
            "origin": self.origin.value,
            "source": self.source,
            "fetched_at": self.fetched_at.isoformat(timespec="seconds"),
            "note": self.note,
        }


def demo() -> None:
    live = Result({"material": "M-4471", "qty": 84.0}, Origin.LIVE, "API_MATERIAL_STOCK_SRV")
    assert live.trusted and live.value["qty"] == 84.0

    failed = Result(None, Origin.MISSING, "API_MATERIAL_STOCK_SRV",
                    note="ConnectionError: no API key")
    assert not failed.trusted
    assert failed.value is None, "a failure must never invent a value"

    modelled = Result({"qty": 84.0}, Origin.MODELLED, "fixture")
    assert not modelled.trusted, "modelled data must never count as trusted"

    assert {o.value for o in Origin} == {"live", "cached", "derived", "modelled", "missing"}
    print("provenance ok")


if __name__ == "__main__":
    demo()
