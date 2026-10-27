"""Bram's tools (Execution).

The action record lives here. What reaches SAP goes through sender.py: an
action SIGAP may take on its own authority the moment it is raised, an approved
one on the schedule's next pass. Three guards here must not be removed:

  · idempotency, identical action content yields an identical key, so a retry
    never becomes a second purchase order;
  · the autonomy limit (SIGAP_AUTONOMOUS_LIMIT_IDR, Rp 50 million unless set):
    at or above it an action waits for a human, and anything waiting never
    touches SAP;
  · no run, no row, because an action nobody can trace back to a handling is
    an action nobody can approve or refuse.

Recording an action is shared through `raise_action` rather than duplicated,
because a draft does not have to be raised by the agent that sends it onward.
Prita picks the supplier and raises the purchase order; Bram is the one who
takes an approved action to SAP. Both write the same record.

Anything said to someone outside the company, a customer told their order is
late or a supplier asked for a new date, is drafted here and never sent from
here. The draft is the email itself, subject, body and the address read from
the record (the business partner in SAP), so the person who approves it sees
exactly what will go and to whom; only then does outreach.py send it, as
written. It always waits for that person: a message cannot be taken back once
it is read.
"""
from __future__ import annotations

import hashlib

from typing import Optional, Tuple

from core.config import CFG
from core.provenance import Origin, Result
from core.registry import register
from tools.fetcher import read

AUTONOMOUS_LIMIT_IDR = CFG.autonomous_limit_idr
LIMIT = CFG.autonomous_limit_text

# Absence of precedent is not weak evidence about the material, it is the
# system's own youth. Everything else on the board describes the situation
# being acted on, and an untrusted figure there is a reason to ask a person.
NOT_EVIDENCE = {"precedent.search_past_incidents"}


def autonomy_check(cost_idr: int) -> tuple[bool, str]:
    """May this be done without a person? Returns the verdict and the reason.

    Value alone was the whole test, and value is a number the model hands in:
    nothing stopped it from declaring a Rp 200 million transfer as Rp 1 million
    and granting itself the authority to execute. So the figure has to be
    corroborated by evidence the model did not author.

    The board is that evidence. Every specialist writes its findings there with
    the origin they came from, so "is anything under this decision modelled,
    or missing" is already a question the board can answer. If it can be
    answered yes, the action waits for a person however cheap it claims to be.
    """
    from core import registry

    if cost_idr >= AUTONOMOUS_LIMIT_IDR:
        return False, f"Rp {cost_idr:,} is at or over the {LIMIT} limit"

    board = registry.current_board()
    if board is None:
        # A tool called outside a handling has no evidence behind it at all.
        # That is the weakest case, not the strongest, so it never goes alone.
        return False, "no evidence on record: this was not raised from a handling"

    weak = [k for k in board.untrusted_keys() if k not in NOT_EVIDENCE]
    if weak:
        return False, ("the figures under this are not all trusted: "
                       + ", ".join(sorted(weak)))

    if not [k for k in board.origin if k not in NOT_EVIDENCE]:
        return False, "nothing was read before deciding"

    return True, f"Rp {cost_idr:,} is under the limit and every figure under it is trusted"


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

    from sender import TARGETS

    key = idempotency_key(kind, **details)
    # An autonomous action that lands in SAP starts approved, the autonomy
    # limit standing in for the approver, and is `sent` only once SAP has taken
    # it. Recorded as sent before the write, a failed write would read as done
    # and never be tried again.
    status = "approved" if autonomous and kind in TARGETS else None
    action = store.record_action(run_id, key, kind, autonomous, details, status=status)
    if action.get("repeated"):
        return Result(action, Origin.DERIVED, "action record",
                      note="an identical action was already raised, so it was not sent again")
    return Result(action, Origin.DERIVED, "action record")


def _record(kind: str, autonomous: bool, **details) -> Result:
    import sender
    from clients import sap_s4

    r = raise_action(kind, autonomous, **details)
    if r.value is None or r.value.get("repeated"):
        return r
    action = r.value

    # Only an autonomous action goes to SAP from here, and through the same
    # sender an approved one takes. The rest wait for approval.
    if autonomous and kind in sender.TARGETS:
        service = sender.TARGETS[kind][0]
        sent = sender.send_one(action["id"])
        if sent["sent"]:
            return Result(action | {"status": "sent", "sap_reference": sent["reference"]},
                          Origin.LIVE, service)
        if not sap_s4.available():
            return Result(action, Origin.DERIVED, "action record (SAP not connected)",
                          note="approved on SIGAP's own authority, not in SAP yet: SAP is "
                               "not connected, and sender.py posts it once it is")
        return Result(action, Origin.MISSING, service,
                      note=f"approved on SIGAP's own authority, but the write to SAP failed "
                           f"({sent['why']}); it stays approved and sender.py tries again")

    source = "action record" if sap_s4.available() else "action record (SAP not connected)"
    return Result(action, Origin.DERIVED, source)


@register("create_stock_transfer", "execution",
          f"Move stock between plants. Autonomous only when the cost impact is under {LIMIT} "
          "AND every figure the decision rests on is trusted. A modelled or "
          "missing figure anywhere under it sends this to a person however cheap it is.",
          {"material": {"type": "string"}, "from_plant": {"type": "string"},
           "to_plant": {"type": "string"}, "qty": {"type": "number"},
           "cost_idr": {"type": "integer"}},
          ["material", "from_plant", "to_plant", "qty", "cost_idr"])
def create_stock_transfer(material: str, from_plant: str, to_plant: str,
                          qty: float, cost_idr: int) -> Result:
    alone, why = autonomy_check(cost_idr)
    r = _record("stock_transfer", alone,
                material=material, from_plant=from_plant, to_plant=to_plant,
                qty=qty, cost_idr=cost_idr)

    # Hold the donor's stock the moment the move is raised, not when it is
    # approved. The window between raising and approving is exactly when a
    # second handling would otherwise promise the same tonnes.
    from core import registry, store

    run_id = registry.current_run()
    if run_id and isinstance(r.value, dict) and not r.value.get("repeated"):
        store.reserve(run_id, material, from_plant, qty, action_id=r.value.get("id"))
    # The reason travels with the action. A planner asking why this one waited
    # and that one did not should not have to read the code to find out.
    if isinstance(r.value, dict):
        r.value["autonomy"] = {"autonomous": alone, "reason": why}
    return r


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
          "Tell an affected role inside the company (planner, buyer, procurement_lead, qa), "
          "with the evidence that backs it. Internal only: a customer or a supplier is told "
          "through draft_customer_notice or request_supplier_update.",
          {"role": {"type": "string"}, "message": {"type": "string"}},
          ["role", "message"])
def notify(role: str, message: str) -> Result:
    return _record("notify", True, role=role, message=message)


@register("monitor_shipment", "execution",
          "File a watch on a shipment so its outcome is owed and asked for. SIGAP does not "
          "poll the carrier: this records that this reference still needs a result, and a "
          "person, or you, closes it with record_outcome once receipt is actually known. "
          "Nothing here observes an arrival, so nothing here can invent one.",
          {"reference": {"type": "string"}}, ["reference"])
def monitor_shipment(reference: str) -> Result:
    return _record("monitor", True, reference=reference)


@register("record_outcome", "execution",
          "Close the loop on an action that was sent: what actually happened, and when. "
          "Writes it to the record so the next incident can learn from this one.",
          {"action_id": {"type": "string"},
           "outcome": {"type": "string",
                       "description": "delivered | late | short | failed | cancelled"},
           "detail": {"type": "string",
                      "description": "what was actually seen: real arrival date, real "
                                     "quantity. Plain text."},
           "actual_cost_idr": {"type": ["number", "null"],
                               "description": "what it actually cost, in rupiah, as a "
                                              "number you were given — off an invoice, a "
                                              "goods receipt, or from a person. Never "
                                              "compute it, never convert it, never round a "
                                              "range into it. Omit it unless you have the "
                                              "figure: a cost written into `detail` is "
                                              "prose and is never read as money."}},
          ["action_id", "outcome"])
def record_outcome(action_id: str, outcome: str, detail: str = "",
                   actual_cost_idr: Optional[float] = None) -> Result:
    """Record what happened. The realized cost travels as its own number.

    `detail` is prose and stays prose: nothing mines a rupiah figure out of it,
    because a number parsed out of a sentence is the model's guess about money,
    which is the one thing this system will not do. A caller who knows the real
    cost passes `actual_cost_idr`; one who does not passes nothing, and the
    report says the realized cost is not known rather than showing a zero.
    """
    from core import store

    try:
        detail_doc = store.outcome_detail(
            detail, actual_cost_idr,
            recorded_by="agent:execution.record_outcome")
        row = store.record_outcome(action_id, outcome, detail_doc)
    except KeyError:
        return Result(None, Origin.MISSING, "actions table",
                      note=f"no action {action_id}")
    except ValueError as e:
        return Result(None, Origin.MISSING, "actions table", note=str(e))

    if row.get("repeated"):
        return Result(row, Origin.DERIVED, "action record",
                      note="an outcome was already recorded; it was not overwritten")
    # Say out loud whether a figure was recorded, so the transcript shows the
    # model leaving it blank rather than quietly omitting it.
    said = (f"realized cost recorded: Rp {int(actual_cost_idr):,}"
            if actual_cost_idr is not None else
            "no realized cost was given, so the report will not state one")
    return Result(row, Origin.DERIVED, "action record", note=said)


# ------------------------------------------------------------ outside parties
# Drafts for a person to approve and send. The party comes from the record, not
# from the model: a notice is attached to an order that exists, addressed to
# whoever that order names, at the address the record holds for them.

def partner_address(partner: Optional[str]) -> Result:
    """Where a message to a supplier or a customer goes: the email on its
    business partner in SAP, else an uploaded PartnerContact list (the fixture
    offline), else nowhere. Never an address the model wrote."""
    from clients import sap_s4
    from tools.fetcher import read_extra

    if not partner:
        return Result(None, Origin.MISSING, "business partner", note="the order names no partner")
    tried = []
    if sap_s4.available():
        from clients import sap_map
        try:
            r = sap_map.partner_email(str(partner))
        except Exception as e:                                       # noqa: BLE001
            r = Result(None, Origin.MISSING, "API_BUSINESS_PARTNER", note=f"{type(e).__name__}: {e}")
        if r.value:
            return r
        tried.append(r)
    listed = read_extra("PartnerContact", lambda x: str(x.get("Partner")) == str(partner))
    row = next((x for x in listed.value or [] if str(x.get("Email") or "").strip()), None)
    if row:
        return Result(str(row["Email"]).strip(), listed.origin, listed.source,
                      note=f"the {row.get('Role') or 'partner'} contact on file for {partner}")
    tried.append(listed)
    return Result(None, Origin.MISSING, " + ".join(t.source for t in tried),
                  note=f"no email on record for {partner}: "
                       + "; ".join(t.note for t in tried if t.note))


def _addressed(to: Result) -> dict:
    return {"to": to.value, "to_source": to.source, "to_origin": to.origin.value}


def _send_note(to: Result, who: str) -> str:
    if to.value:
        return (f"a draft for {who} to approve; once approved SIGAP sends it as written to "
                f"{to.value} ({to.source})")
    return (f"a draft for {who} to approve; {to.note}, so SIGAP cannot send it and a person "
            "must, or the address must be added to the business partner")

def _sales_order(number: str) -> Tuple[Optional[dict], Result]:
    """The order, and the read it came from: an order not found where the orders
    could not be read is a hole, not a missing order."""
    r = read("SalesOrder")
    return next((x for x in r.value or [] if str(x.get("SalesOrder")) == number
                 or str(x.get("SalesOrder")).split("-")[0] == number), None), r


@register("draft_customer_notice", "execution",
          "Draft a notice to a customer that their order will be late, or short, and what "
          "is being done about it. The customer and their email address are read from the "
          "order and the business partner record, never typed in. A DRAFT: it always waits "
          "for a procurement lead to approve it, whatever it says; once approved SIGAP "
          "emails it exactly as written, so write it as the finished message.",
          {"sales_order": {"type": "string", "description": "the customer order it is about"},
           "message": {"type": "string",
                       "description": "the notice as the customer will read it, plain text"},
           "new_date": {"type": ["string", "null"],
                        "description": "the delivery date now expected, YYYY-MM-DD, if known"}},
          ["sales_order", "message"])
def draft_customer_notice(sales_order: str, message: str,
                          new_date: Optional[str] = None) -> Result:
    order, orders = _sales_order(sales_order)
    if order is None:
        why = (f"the customer orders could not be read ({orders.note})" if orders.value is None
               else f"no open customer order {sales_order} on record")
        return Result(None, Origin.MISSING, orders.source,
                      note=why + ", so there is nobody to address a notice to")
    so = str(order["SalesOrder"])
    to = partner_address(order.get("Customer"))
    facts = [f"Order: {so}", f"Product: {order.get('Material')}",
             f"Requested delivery: {order.get('RequestedDeliveryDate')}"]
    if new_date:
        facts.append(f"Expected delivery: {new_date}")
    r = _record("customer_notice", False,
                sales_order=so, customer=order.get("Customer"),
                customer_name=order.get("CustomerName"), finished_good=order.get("Material"),
                requested_date=order.get("RequestedDeliveryDate"), new_date=new_date,
                message=message, **_addressed(to),
                subject=f"Your order {so}: delivery update",
                body=message.strip() + "\n\n" + "\n".join(facts))
    if isinstance(r.value, dict):
        r.note = "; ".join(x for x in (r.note, _send_note(to, "a procurement lead")) if x)
    return r


@register("request_supplier_update", "execution",
          "Draft a request to a supplier about one of its purchase orders: confirm the "
          "date, give a revised one, say what has shipped. The supplier and its email "
          "address are read from the order and the business partner record, never typed "
          "in. A DRAFT: it waits for a buyer to approve it; once approved SIGAP emails it "
          "exactly as written, so write it as the finished message. The answer, once it "
          "comes, is recorded with record_outcome.",
          {"purchase_order": {"type": "string"},
           "question": {"type": "string", "description": "what is asked, plain text"}},
          ["purchase_order", "question"])
def request_supplier_update(purchase_order: str, question: str) -> Result:
    found = read("PurchaseOrder", numbers=[purchase_order], open_only=False)
    lines = found.value or []
    if not lines:
        return Result(None, Origin.MISSING, found.source,
                      note=f"the purchase orders could not be read ({found.note})"
                      if found.value is None else f"no purchase order {purchase_order} on record")
    po = lines[0]
    number = str(po["PurchaseOrder"])
    to = partner_address(po.get("Supplier"))
    facts = [f"Purchase order: {number}", f"Material: {po.get('Material')}",
             f"Delivery date on the order: {po.get('DeliveryDate')}"]
    if po.get("RevisedDeliveryDate"):
        facts.append(f"Revised delivery date on record: {po.get('RevisedDeliveryDate')}")
    r = _record("supplier_request", False,
                purchase_order=number, supplier=po.get("Supplier"),
                material=po.get("Material"), delivery_date=po.get("DeliveryDate"),
                revised_date=po.get("RevisedDeliveryDate"), question=question,
                **_addressed(to), subject=f"Purchase order {number}: request for an update",
                body=question.strip() + "\n\n" + "\n".join(facts))
    if isinstance(r.value, dict):
        r.note = "; ".join(x for x in (r.note, _send_note(to, "a buyer")) if x)
    return r


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

    # Neither Prevent-mode action, and nothing said outside the company, may
    # ever run on its own authority.
    import inspect
    for fn in (create_sourcing_event, propose_safety_stock_change,
               draft_customer_notice, request_supplier_update):
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

    # The autonomy gate. The point is that value alone can be forged by the
    # caller, so a cheap claim must still be backed by trusted evidence.
    from core import registry

    class FakeBoard:
        def __init__(self, origins):
            self.origin = origins

        def untrusted_keys(self):
            return [k for k, o in self.origin.items()
                    if o not in ("live", "cached", "derived")]

    cheap = 1_000_000
    alone, why = autonomy_check(cheap)
    assert not alone and "not raised from a handling" in why, why

    trusted = FakeBoard({"impact.get_material_stock": "live",
                         "simulation.simulate_scenario": "derived"})
    with registry.bind_board(trusted):
        alone, why = autonomy_check(cheap)
        assert alone, why
        over, why_over = autonomy_check(AUTONOMOUS_LIMIT_IDR)
        assert not over and "limit" in why_over, why_over

    # The forgery this closes: a model declaring a huge move as a small one.
    # It is under the limit, so the old gate would have let it execute alone.
    modelled = FakeBoard({"impact.get_material_stock": "modelled",
                          "simulation.simulate_scenario": "derived"})
    with registry.bind_board(modelled):
        alone, why = autonomy_check(cheap)
        assert not alone, "a modelled figure under the decision must stop autonomy"
        assert "impact.get_material_stock" in why, why

    # Having no precedent is the system being young, not the evidence being
    # weak, so it must not be what blocks a well-evidenced action.
    young = FakeBoard({"impact.get_material_stock": "live",
                       "precedent.search_past_incidents": "missing"})
    with registry.bind_board(young):
        alone, why = autonomy_check(cheap)
        assert alone, f"an empty memory must not block a trusted decision: {why}"

    with registry.bind_board(FakeBoard({})):
        alone, why = autonomy_check(cheap)
        assert not alone and "nothing was read" in why, why

    print("  autonomy needs a trusted board, not just a small number")
    print("  a modelled figure anywhere under the decision sends it to a person")

    # Outward drafts: the party comes from the record, and the draft waits.
    import json
    from core import store
    eid = store.record_event("supplier_failure", "Qingdao Baowu misses a shipment", "check",
                             {"supplier": "SUP-2209"}, "execution-check")
    rid = store.start_run(eid, "guided")
    with registry.bind_run(rid):
        n = draft_customer_notice("0000104411", "Your FG-1120 order will ship on 3 Oct.",
                                  "2026-10-03")
        sent_to = json.loads(n.value["payload"])
        assert n.value["status"] == "pending" and not n.value["autonomous"], n.value
        assert sent_to["customer"] == "CUS-1001", "the customer is read from the order"
        assert sent_to["to"] == "purchasing@cus-1001.example", "and the address from the record"
        assert sent_to["body"].startswith("Your FG-1120 order") and "Expected delivery: 2026-10-03" \
            in sent_to["body"] and "0000104411" in sent_to["subject"], sent_to
        assert draft_customer_notice("0000999999", "x").origin is Origin.MISSING
        q = request_supplier_update("4500018876", "Please confirm the revised date.")
        asked = json.loads(q.value["payload"])
        assert q.value["status"] == "pending" and asked["supplier"] == "SUP-2209", asked
        assert asked["to"] == "sales@sup-2209.example" and "4500018876" in asked["body"], asked
        assert request_supplier_update("4599999999", "x").origin is Origin.MISSING
        assert partner_address("SUP-0000").value is None and "no email" in partner_address("SUP-0000").note

        # On its own authority: a transfer is not done until SAP has it. With
        # SAP not connected it stays approved for sender.py, never `sent`.
        t = _record("stock_transfer", True, material="M-4471", from_plant="SBY1",
                    to_plant="KRW1", qty=22.0, cost_idr=cheap)
        assert t.value["status"] == "approved" and not t.value["sap_reference"], t.value
        assert "not connected" in t.note, t.note
        told = _record("notify", True, role="buyer", message="Hold 55 t at SBY1.")
        assert told.value["status"] == "sent", "a record that never goes to SAP is done once written"

        # A filed watch is owed a result. The description must keep saying so:
        # it used to promise it would observe the arrival, which it never did.
        from core import registry as _reg
        assert "does not poll" in _reg.get("monitor_shipment").description
        watch = monitor_shipment("SHP-1")
        assert watch.value["status"] == "sent"
        assert watch.value["id"] in {a["id"] for a in store.actions_awaiting_outcome()}

        # ---- the loop closes, with a figure that survives to the report ----
        from engine.report import _actual_cost
        schema = _reg.get("record_outcome").schema
        assert schema["additionalProperties"] is False
        assert "actual_cost_idr" in schema["properties"]
        assert "actual_cost_idr" not in schema["required"], "the figure is optional"

        done = record_outcome(t.value["id"], "delivered", detail="arrived 3 Oct",
                              actual_cost_idr=24_500_000)
        assert done.origin is Origin.DERIVED and "24,500,000" in done.note, done.note
        # THE assertion: the realized figure recorded through the agent's own
        # tool reaches the report. This is the link that used to be broken, so
        # every realized column read "-" however carefully it was filled in.
        assert _actual_cost(store.get_action(t.value["id"])) == 24_500_000

        # A cost mentioned only in prose stays prose.
        prose = record_outcome(watch.value["id"], "late",
                               detail="it cost about Rp 24,5 jt more")
        assert prose.origin is Origin.DERIVED and "no realized cost" in prose.note
        assert _actual_cost(store.get_action(watch.value["id"])) is None

        # A figure sent as text is refused, not coerced into some scale.
        refused = record_outcome(told.value["id"], "delivered", actual_cost_idr="24500000")
        assert refused.origin is Origin.MISSING and "must be a number" in refused.note
        assert store.get_action(told.value["id"])["outcome"] is None
    store.close_run(rid, "done", decision={"status": "done"})
    print("  a customer notice and a supplier request are drafts, addressed from the record, "
          "written as the email that will go")
    print("  an autonomous transfer is approved until SAP has it, so a failed write is retried")
    print("  the loop closes: a realized figure reaches the report ✓ · prose never becomes "
          "money ✓ · a watch is owed a result ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_EXECUTION_CHECK")
    demo()
