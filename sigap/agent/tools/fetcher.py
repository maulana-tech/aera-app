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

    # Real company data that was uploaded rather than pulled outranks a fixture:
    # it is genuine, just not live. Hence CACHED. A file the uploader declared
    # as generated stays MODELLED, because calling it cached would launder it.
    try:
        from core import store
        u = store.latest_upload(fixture_entity)
    except Exception:                                            # noqa: BLE001
        u = None
    if u:
        data = u["payload"]
        if keep:
            data = [r for r in data if keep(r)]
        generated = bool(u.get("synthetic"))
        return Result(
            data,
            Origin.MODELLED if generated else Origin.CACHED,
            f"upload:{u['filename']}",
            note=(f"uploaded {u['uploaded_at']}"
                  + (", declared as generated sample data" if generated else "")),
        )

    data = fixture(fixture_entity)
    if keep:
        data = [r for r in data if keep(r)]
    return Result(
        data, Origin.MODELLED, f"fixture:{fixture_entity}",
        note="SAP_API_KEY is not set. Using modelled data",
    )


#: Every entity the audit reads, with the SAP service it would come from live.
ENTITIES = {
    "MaterialStock": ("API_MATERIAL_STOCK_SRV", "A_MatlStkInAcctMod"),
    "PurchaseOrder": ("API_PURCHASEORDER_PROCESS_SRV", "A_PurchaseOrder"),
    "BillOfMaterial": ("API_BILL_OF_MATERIAL_SRV", "A_BillOfMaterial"),
    "SalesOrder": ("API_SALES_ORDER_SRV", "A_SalesOrder"),
    "AlternateSource": ("API_PURCHASING_INFO_RECORD_SRV", "A_PurchasingInfoRecord"),
    "Supplier": ("API_BUSINESS_PARTNER", "A_Supplier"),
}


def current_dataset() -> tuple[dict, dict]:
    """Everything the system can currently see, by the same path the tools use.

    Returns the rows and, separately, where each entity came from. An audit that
    does not say which of its inputs were modelled is an audit of nothing.
    """
    data: Dict[str, list] = {}
    origins: Dict[str, dict] = {}
    for entity, (service, sap_entity) in ENTITIES.items():
        try:
            r = pull(entity, service, sap_entity, {"$top": "500"})
        except KeyError:
            # Not every entity exists in the fixture; Supplier is newer than it.
            continue
        data[entity] = r.value or []
        origins[entity] = {"origin": r.origin.value, "source": r.source, "note": r.note}
    return data, origins
