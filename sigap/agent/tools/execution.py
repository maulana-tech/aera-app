"""Bram's tools (Execution).

The only file that writes outward — to SAP and to the action record. Two
guards here must not be removed:

  · idempotency — identical action content yields an identical key, so a retry
    never becomes a second purchase order;
  · the autonomy limit — above Rp 50 million an action waits for a human, and
    anything waiting never touches SAP.
"""
from __future__ import annotations

import hashlib

from core.provenance import Origin, Result
from core.registry import register

AUTONOMOUS_LIMIT_IDR = 50_000_000


def idempotency_key(kind: str, **details) -> str:
    """A stable key from the action's content. The same action is never sent twice."""
    fingerprint = "|".join(f"{k}={details[k]}" for k in sorted(details))
    return f"{kind}:{hashlib.sha256(fingerprint.encode()).hexdigest()[:16]}"


def _record(kind: str, autonomous: bool, **details) -> Result:
    from clients import sap_s4
    from core import store

    key = idempotency_key(kind, **details)
    run_id = details.pop("_run_id", None) or "run_detached"
    action = store.record_action(run_id, key, kind, autonomous, details)

    if action.get("repeated"):
        return Result(action, Origin.DERIVED, "action record",
                      note="an identical action was already raised — not sent again")

    # Only autonomous actions touch SAP directly. The rest wait for approval.
    if autonomous and sap_s4.available() and kind == "stock_transfer":
        try:
            r = sap_s4.post("API_STOCK_TRANSFER_SRV", "A_StockTransfer",
                            details, idempotency_key=key)
            return Result(action | {"sap_reference": r.get("d", {}).get("MaterialDocument")},
                          Origin.LIVE, "API_STOCK_TRANSFER_SRV")
        except Exception as e:                                       # noqa: BLE001
            return Result(action, Origin.MISSING, "API_STOCK_TRANSFER_SRV",
                          note=f"failed to write to SAP: {type(e).__name__}: {e}")

    source = "action record" if sap_s4.available() else "action record (SAP not connected)"
    return Result(action, Origin.DERIVED, source)


@register("create_stock_transfer", "execution",
          "Move stock between plants. Autonomous when the cost impact is under Rp 50 million.",
          {"material": {"type": "string"}, "from_plant": {"type": "string"},
           "to_plant": {"type": "string"}, "qty": {"type": "number"},
           "cost_idr": {"type": "integer"}},
          ["material", "from_plant", "to_plant", "qty", "cost_idr"])
def create_stock_transfer(material: str, from_plant: str, to_plant: str,
                          qty: float, cost_idr: int) -> Result:
    return _record("stock_transfer", cost_idr < AUTONOMOUS_LIMIT_IDR,
                   material=material, from_plant=from_plant, to_plant=to_plant,
                   qty=qty, cost_idr=cost_idr)


@register("create_draft_po", "execution",
          "Create a DRAFT purchase order. Always waits for buyer approval — never autonomous.",
          {"supplier": {"type": "string"}, "material": {"type": "string"},
           "qty": {"type": "number"}, "needed_by": {"type": "string"},
           "cost_idr": {"type": "integer"}},
          ["supplier", "material", "qty", "needed_by", "cost_idr"])
def create_draft_po(supplier: str, material: str, qty: float,
                    needed_by: str, cost_idr: int) -> Result:
    return _record("draft_po", False, supplier=supplier, material=material,
                   qty=qty, needed_by=needed_by, cost_idr=cost_idr)


@register("notify", "execution",
          "Tell the affected roles, with the evidence that backs it.",
          {"role": {"type": "string"}, "message": {"type": "string"}},
          ["role", "message"])
def notify(role: str, message: str) -> Result:
    return _record("notify", True, role=role, message=message)


@register("monitor_shipment", "execution",
          "Watch a shipment through to receipt, then record the outcome to memory.",
          {"reference": {"type": "string"}}, ["reference"])
def monitor_shipment(reference: str) -> Result:
    return _record("monitor", True, reference=reference)


def demo() -> None:
    """The idempotency key must be stable across argument order, sensitive to content."""
    a = idempotency_key("draft_po", supplier="SUP-1", qty=85, material="M-4471")
    b = idempotency_key("draft_po", material="M-4471", qty=85, supplier="SUP-1")
    assert a == b, "argument order must not change the key"
    c = idempotency_key("draft_po", supplier="SUP-1", qty=86, material="M-4471")
    assert a != c, "a different quantity must give a different key"
    d = idempotency_key("stock_transfer", supplier="SUP-1", qty=85, material="M-4471")
    assert a != d, "a different action kind must give a different key"
    assert a.startswith("draft_po:")
    print(f"execution ok — idempotency {a}")


if __name__ == "__main__":
    demo()
