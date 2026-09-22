"""Data fetcher: try SAP first, fall back to fixtures when there's no key.

The point: falling back is NOT hidden. The origin becomes MODELLED, and that
shows up both in the UI and in the calculator's own trust check.
"""
from __future__ import annotations

import json
import pathlib
from typing import Callable, Dict, List, Optional

from clients import sap_s4
from core.provenance import Origin, Result

_FIXTURE = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "ningbo_scenario.json"
_cache: Optional[dict] = None


def fixture(entity: str) -> List[dict]:
    global _cache
    if _cache is None:
        _cache = json.loads(_FIXTURE.read_text())
    return _cache[entity]


def profile() -> dict:
    return fixture("Profile")  # type: ignore[return-value]


def pull(
    fixture_entity: str,
    sap_service: str,
    sap_entity: str,
    params: Optional[Dict] = None,
    keep: Optional[Callable[[dict], bool]] = None,
) -> Result:
    """One read path shared by every read tool."""
    if sap_s4.available():
        try:
            data = sap_s4.rows(sap_s4.get(sap_service, sap_entity, params))
            if keep:
                data = [r for r in data if keep(r)]
            return Result(data, Origin.LIVE, sap_service)
        except Exception as e:                                   # noqa: BLE001
            return Result(None, Origin.MISSING, sap_service, note=f"{type(e).__name__}: {e}")

    # Data the user uploaded outranks a fixture: it is the company's real data,
    # just not pulled live. Hence CACHED rather than MODELLED.
    try:
        from core import store
        u = store.latest_upload(fixture_entity)
    except Exception:                                            # noqa: BLE001
        u = None
    if u:
        data = u["payload"]
        if keep:
            data = [r for r in data if keep(r)]
        return Result(data, Origin.CACHED, f"upload:{u['filename']}",
                      note=f"uploaded {u['uploaded_at']}")

    data = fixture(fixture_entity)
    if keep:
        data = [r for r in data if keep(r)]
    return Result(
        data, Origin.MODELLED, f"fixture:{fixture_entity}",
        note="SAP_API_KEY is not set — using modelled data",
    )
