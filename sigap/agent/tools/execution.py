"""Bram's tools (Execution).

The action record lives here, and this is the only file that writes outward to
SAP. Three guards here must not be removed:

  · idempotency, identical action content yields an identical key, so a retry
    never becomes a second purchase order;
  · the autonomy limit, above Rp 50 million an action waits for a human, and
    anything waiting never touches SAP;
  · no run, no row, because an action nobody can trace back to a handling is
    an action nobody can approve or refuse.

Recording an action is shared through `raise_action` rather than duplicated,
because a draft does not have to be raised by the agent that sends it onward.
Prita picks the supplier and raises the purchase order; Bram is the one who
takes an approved action to SAP. Both write the same record.
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


def raise_action(kind: str, autonomous: bool, **details) -> Result:
    """Key an action, attach it to the run in force, write it down.

    Returns a value of None when no run is open. That is a refusal, not a
    failure: actions.run_id references runs(id), and an id invented here would
    either fail that reference or leave a row nothing could be traced to.

    The run comes from the context rather than an argument, because it cannot
    come from an argument: the tool schema is shown to the model as it stands
    and additionalProperties is false, so there is no spare parameter to carry it.
    """
    from core import registry, store

    run_id = registry.current_run()
    if not run_id:
        return Result(None, Origin.MISSING, "runs table",
                      note=("no run is open, so this action has nothing to attach "
                            "to. Raise it from a signal rather than from a question."))

    key = idempotency_key(kind, **details)
    action = store.record_action(run_id, key, kind, autonomous, details)
    if action.get("repeated"):
        return Result(action, Origin.DERIVED, "action record",
                      note="an identical action was already raised, so it was not sent again")
    return Result(action, Origin.DERIVED, "action record")


def _record(kind: str, autonomous: bool, **details) -> Result:
    from clients import sap_s4

    r = raise_action(kind, autonomous, **details)
    if r.value is None or r.value.get("repeated"):
        return r
    action = r.value
    key = idempotency_key(kind, **details)

    # Only autonomous actions touch SAP directly. The rest wait for approval.
    if autonomous and sap_s4.available() and kind == "stock_transfer":
        try:
            posted = sap_s4.post("API_STOCK_TRANSFER_SRV", "A_StockTransfer",
                                 details, idempotency_key=key)
            return Result(action | {"sap_reference": posted.get("d", {}).get("MaterialDocument")},
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

    # Outside a handling no run is open, and an action is refused rather than
    # written down where nothing could be traced to it. This writes no row.
    from core import registry
    refused = raise_action("draft_po", False, supplier="SUP-1", material="M-4471",
                           qty=85, needed_by="2026-09-20", cost_idr=1)
    assert registry.current_run() is None, "a run must not outlive its handling"
    assert refused.value is None and refused.origin is Origin.MISSING, refused.note

    print(f"execution ok, idempotency {a}")
    print("  prevent-mode actions always wait for a person")
    print("  no run open, so an action is refused rather than written")


if __name__ == "__main__":
    demo()
