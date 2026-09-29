"""Bram's tools (Execution).

The only file that writes outward, to SAP and to the action record. Two
guards here must not be removed:

  · idempotency, identical action content yields an identical key, so a retry
    never becomes a second purchase order;
  · the autonomy limit, above Rp 50 million an action waits for a human, and
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
                      note="an identical action was already raised, so it was not sent again")

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
          "Create a DRAFT purchase order. Always waits for buyer approval, never autonomous.",
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


# ------------------------------------------------------- Prevent mode actions
# Nothing in Prevent mode is urgent, so nothing in it justifies autonomy. Both
# of these wait for a person regardless of value.

@register("create_sourcing_event", "execution",
          "Open a sourcing event to qualify a second supplier for a material. A DRAFT "
          "for procurement to approve. Never autonomous, whatever the value.",
          {"material": {"type": "string"},
           "rationale": {"type": "string",
                         "description": "the exposure this closes, in one sentence"}},
          ["material", "rationale"])
def create_sourcing_event(material: str, rationale: str) -> Result:
    return _record("create_sourcing_event", False, material=material, rationale=rationale)


@register("propose_safety_stock_change", "execution",
          "Propose a new safety stock floor for a material at a plant. This is a policy "
          "change rather than a transaction, so it always escalates. It is never sent to "
          "SAP by the sender; a person applies it.",
          {"material": {"type": "string"}, "plant": {"type": "string"},
           "new_level": {"type": "number", "description": "the proposed floor, in base units"},
           "rationale": {"type": "string"}},
          ["material", "plant", "new_level", "rationale"])
def propose_safety_stock_change(material: str, plant: str, new_level: float,
                                rationale: str) -> Result:
    return _record("propose_safety_stock_change", False, material=material, plant=plant,
                   new_level=new_level, rationale=rationale)


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

    # Neither Prevent-mode action may ever run on its own authority.
    import inspect
    for fn in (create_sourcing_event, propose_safety_stock_change):
        src = inspect.getsource(fn)
        assert "_record(" in src and ", False," in src, \
            f"{fn.__name__} must pass autonomous=False"

    print(f"execution ok, idempotency {a}")
    print("  prevent-mode actions always wait for a person")


if __name__ == "__main__":
    demo()
