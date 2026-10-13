"""Prita's tools (Procurement).

The supplier book, and the quotations against it. Nothing else in the system
reads the `Supplier` entity: Sourcing reads AlternateSource, which is the
options for one material, Impact reads PurchaseOrder, which is the lines to
trace through a bill of materials, and Vega counts single sources rather than
suppliers. None of them can answer who the company buys from as a portfolio,
whether those suppliers kept the date on their own orders, or what they are
quoting for the next order — and those three questions are procurement's alone.

The quotation file is the only place a price exists anywhere in this system.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional

from core.provenance import Origin, Result
from core.registry import register
from tools.execution import raise_action
from tools.fetcher import profile, pull

#: Words that are legal form rather than identity. "PT Logam Andalan" and
#: "PT Logam Andalan Tbk" are one company carrying two supplier codes, and every
#: count that does not look for the difference reports them as two suppliers.
LEGAL_FORM = {
    "pt", "persero", "cv", "koperasi", "tbk", "perusahaan", "co", "company",
    "ltd", "limited", "inc", "llc", "gmbh", "pte", "plc", "ag", "sa",
}


def _identity(name: str) -> str:
    """The company behind a supplier name, stripped of how it is incorporated."""
    words = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower()).split()
    return " ".join(w for w in words if w not in LEGAL_FORM)


def _book() -> Result:
    """Every purchase order line — the denominator of every share in this file."""
    return pull(
        "PurchaseOrder", "API_PURCHASEORDER_PROCESS_SRV", "A_PurchaseOrder",
        {"$top": "500"},
    )


def _slip(order: dict) -> Optional[int]:
    """The revised delivery date minus the date on the order, in days.

    Read from the two dates rather than from `Status`, because status says where
    a shipment is and not whether it met the date it was given: a supplier that
    moves its own date forward is late while the status still reads in transit.

    None when either date is missing. Missing is not the same as on time, and a
    silent zero here would quietly improve every supplier that has one.
    """
    try:
        booked = date.fromisoformat(str(order["DeliveryDate"])[:10])
        revised = date.fromisoformat(str(order["RevisedDeliveryDate"])[:10])
    except (KeyError, TypeError, ValueError):
        return None
    return (revised - booked).days


def _master() -> Dict[str, dict]:
    """Supplier id -> supplier record, so two tools cannot disagree on identity."""
    rows = pull("Supplier", "API_BUSINESS_PARTNER", "A_Supplier", {"$top": "500"}).value or []
    return {str(s.get("Supplier")): s for s in rows}


@register(
    "get_supplier_master", "procurement",
    "The supplier book: every supplier on the approved list, with its country and its "
    "certified local-content percentage, plus how many purchase orders reach it and "
    "what share of the total volume that is. The suppliers holding no orders come "
    "back too, because qualified capacity nobody is using is a finding rather than a "
    "hole in the data. Records naming the same company twice are reported through "
    "duplicate_of rather than merged, since merging them would be a guess.",
    {},
    [],
)
def get_supplier_master() -> Result:
    suppliers = pull("Supplier", "API_BUSINESS_PARTNER", "A_Supplier", {"$top": "500"})
    if not suppliers.value:
        return Result(None, suppliers.origin, suppliers.source,
                      note=suppliers.note or "no supplier master to read")

    book = _book().value or []
    total = sum(float(o.get("OrderQuantity") or 0) for o in book)

    # Report the duplicate, do not resolve it. The two codes may exist for a
    # reason only SAP knows, and a portfolio that silently halves a supplier is
    # a portfolio nobody can argue with.
    first_seen: Dict[str, str] = {}
    duplicate_of: Dict[str, str] = {}
    for s in suppliers.value:
        sid, key = str(s.get("Supplier")), _identity(s.get("SupplierName"))
        if not key:
            continue
        if key in first_seen:
            duplicate_of[sid] = first_seen[key]
        else:
            first_seen[key] = sid

    rows: List[dict] = []
    for s in suppliers.value:
        sid = str(s.get("Supplier"))
        mine = [o for o in book if str(o.get("Supplier")) == sid]
        qty = sum(float(o.get("OrderQuantity") or 0) for o in mine)
        rows.append({
            "supplier": sid,
            "name": s.get("SupplierName"),
            "country": s.get("Country"),
            "tkdn_certified_pct": s.get("TkdnCertifiedPct"),
            "orders": len(mine),
            "volume": round(qty, 1),
            "unit": mine[0].get("BaseUnit") if mine else None,
            "share_pct": round(100 * qty / total, 2) if total else 0.0,
            "duplicate_of": duplicate_of.get(sid),
        })

    # Sorted by the share each row carries, so the chart, the table and any
    # answer drawn from them all read in the same order.
    rows.sort(key=lambda r: (-r["share_pct"], r["supplier"]))
    unit = next((r["unit"] for r in rows if r["unit"]), None)
    unused = sum(1 for r in rows if not r["orders"])
    dups = sum(1 for r in rows if r["duplicate_of"])
    note = f"{len(rows)} suppliers on the approved list, {unused} of them holding no orders"
    if dups:
        note += (f"; {dups} record repeats a company already on the list"
                 if dups == 1 else
                 f"; {dups} records repeat a company already on the list")
    if unit:
        note += f". Volume in {unit}"
    return Result(rows, suppliers.origin, suppliers.source, note=note)


@register(
    "get_supplier_performance", "procurement",
    "How each supplier kept the delivery date on its own purchase orders: how many "
    "slipped, the average and the worst slip, what share of the book it carries, and "
    "the order it was worst on. Slip is the revised date minus the date on the order, "
    "so a supplier that renegotiates its own date forward is late even while the "
    "status still reads in transit. Pass a supplier id to ask about one supplier.",
    {"supplier": {"type": "string",
                  "description": "a supplier id such as SUP-8815. Omit it for the whole book."}},
    [],
)
def get_supplier_performance(supplier: Optional[str] = None) -> Result:
    wanted = (supplier or "").strip() or None
    book = _book()
    all_orders = book.value or []
    if not all_orders:
        return Result(None, book.origin, book.source,
                      note=book.note or "no purchase orders to judge anyone against")

    # Share is always a share of the whole book, even when one supplier was
    # asked for, so a filtered answer cannot make a supplier look bigger than
    # it is by removing everyone else.
    total = sum(float(o.get("OrderQuantity") or 0) for o in all_orders)
    rows_all = [o for o in all_orders
                if wanted is None or str(o.get("Supplier")) == wanted]
    if not rows_all:
        return Result([], book.origin, book.source,
                      note=f"{wanted} holds no purchase orders")

    names = _master()
    by: Dict[str, List[dict]] = {}
    for o in rows_all:
        by.setdefault(str(o.get("Supplier")), []).append(o)

    rows: List[dict] = []
    for sid, mine in by.items():
        slips = [s for s in (_slip(o) for o in mine) if s is not None]
        late = [s for s in slips if s > 0]
        qty = sum(float(o.get("OrderQuantity") or 0) for o in mine)
        dated = [o for o in mine if _slip(o) is not None]
        worst = max(dated, key=lambda o: abs(_slip(o) or 0)) if dated else None
        who = names.get(sid) or {}
        rows.append({
            "supplier": sid,
            "name": who.get("SupplierName"),
            "country": who.get("Country"),
            "orders": len(mine),
            "late": len(late),
            "on_time_pct": round(100 * (len(mine) - len(late)) / len(mine), 1),
            "avg_slip_days": round(sum(slips) / len(slips), 2) if slips else 0.0,
            "max_slip_days": max(slips) if slips else 0,
            "worst_po": worst.get("PurchaseOrder") if worst else None,
            "worst_slip_days": _slip(worst) if worst else None,
            "share_pct": round(100 * qty / total, 2) if total else 0.0,
        })

    # Worst average slip first, then the bigger supplier among equals. One order
    # that arrived eight days late outranks nothing, which is why the order
    # count travels with every row.
    rows.sort(key=lambda r: (-r["avg_slip_days"], -r["orders"], r["supplier"]))
    slipped = sum(1 for r in rows if r["late"])
    one = len(rows) == 1
    return Result(
        rows, book.origin, book.source,
        note=(f"{len(rows)} supplier{'s' if not one else ''} holding orders, {slipped} "
              f"of them with at least one late line; slip is the revised date minus "
              f"the booked date"),
    )


# ---------------------------------------------------------------- quotations
# The only entity in the system that carries a price. AlternateSource carries
# ExtraCost, which is what an option costs over the baseline rather than what a
# firm charges for a tonne of it, and there is no price list to fall back on.
# "Cheapest" had no answer until this file existed.

def _quotes(material: Optional[str] = None) -> Result:
    return pull(
        "Quotation", "API_QTN_PROCESS_SRV", "A_SupplierQuotation", {"$top": "500"},
        keep=(lambda r: r.get("Material") == material) if material else None,
    )


def _unit_price(q: dict) -> float:
    """What one base unit costs.

    SAP prices per PriceUnit, and for pieces that unit is a hundred rather than
    one, so NetPrice on its own is a figure that cannot be set beside another
    firm's without being divided first.
    """
    try:
        return float(q.get("NetPrice") or 0) / max(float(q.get("PriceUnit") or 1), 1.0)
    except (TypeError, ValueError):
        return 0.0


def _valid_to(q: dict) -> Optional[date]:
    try:
        return date.fromisoformat(str(q.get("QuotationValidityEndDate"))[:10])
    except (TypeError, ValueError):
        return None


def _as_of() -> date:
    """The day the system believes it is.

    An offer's validity is judged here rather than against today's calendar, so
    a fixture dated 4 September 2026 is not read as expired by whoever runs it
    in a later month.
    """
    try:
        return date.fromisoformat(str(profile().get("AsOfDate"))[:10])
    except (TypeError, ValueError):
        return date.today()


def _live(q: dict, as_of: date) -> bool:
    """Whether an offer still holds on the as-of date.

    A missing validity date counts as not live rather than as forever. Nobody
    can check it, and an offer nobody can check is one a buyer must re-quote.
    """
    until = _valid_to(q)
    return until is not None and until >= as_of


def _on_trade_off(rows: List[dict]) -> None:
    """Mark the offers nothing else beats on both axes at once.

    An offer dominates another when it is no dearer and no slower, and strictly
    better on one of the two. What survives dominates nothing and is dominated
    by nothing: the line a buyer is actually choosing along.
    """
    live = [r for r in rows if r["live"]]
    for r in rows:
        r["on_line"] = r["live"] and not any(
            o["unit_price"] <= r["unit_price"] and o["lead_days"] <= r["lead_days"]
            and (o["unit_price"] < r["unit_price"] or o["lead_days"] < r["lead_days"])
            for o in live
        )


@register(
    "get_quotations", "procurement",
    "The quotation file in full: material, firm, price per base unit, quoted lead time, "
    "and the day the offer stops being valid. Read it to see which materials still have "
    "firms bidding and which have run out of live offers. Pass a material code to ask "
    "about one; the whole file is long, so narrow it before quoting figures from it. "
    "QtnLifecycleStatus comes back as stored and is not a verdict: validity is read from "
    "the date beside it. Sorted by material and then by price, so the cheapest offer for "
    "a material is the first row of its group.",
    {"material": {"type": "string",
                  "description": "a material code such as M-4471. Omit it for the whole file."}},
    [],
)
def get_quotations(material: Optional[str] = None) -> Result:
    wanted = (material or "").strip() or None
    quotes = _quotes(wanted)
    if quotes.value is None:
        return quotes
    if not quotes.value:
        return Result([], quotes.origin, quotes.source,
                      note=f"no quotations on file for {wanted or 'any material'}")

    names = _master()
    as_of = _as_of()
    rows: List[dict] = []
    for q in quotes.value:
        sid = str(q.get("Supplier"))
        who = names.get(sid) or {}
        until = _valid_to(q)
        rows.append({
            "material": q.get("Material"),
            "supplier": sid,
            "name": who.get("SupplierName"),
            "country": who.get("Country"),
            "quotation": q.get("SupplierQuotation"),
            "unit_price": int(round(_unit_price(q))),
            "lead_days": int(q.get("DeliveryTimeInDays") or 0),
            "valid_to": until.isoformat() if until else None,
            "live": _live(q, as_of),
            "status": q.get("QtnLifecycleStatus"),
        })
    rows.sort(key=lambda r: (str(r["material"]), r["unit_price"], r["supplier"]))

    materials = len({r["material"] for r in rows})
    live = sum(1 for r in rows if r["live"])
    note = (f"{len(rows)} offers across {materials} material"
            f"{'s' if materials != 1 else ''}, {live} valid on {as_of}")
    if live != len(rows):
        note += f", {len(rows) - live} past their validity date"
    note += (". Price and lead time come from the quotation file; name and certificate "
             "from the supplier master.")
    return Result(rows, quotes.origin, quotes.source, note=note)


@register(
    "compare_quotations", "procurement",
    "Compare the supplier quotations on file for one material: price per base unit, "
    "quoted lead time, the total for the quantity you name, and the local-content "
    "certificate each firm carries. Ranked by total cost, and it names the fastest "
    "offer when that is a different firm, because they usually are and the gap "
    "between them is the decision. Offers past their validity date are listed but "
    "not ranked, and QtnLifecycleStatus is not taken at face value: it records what "
    "the round was closed out as, not what is true on the as-of date.",
    {"material": {"type": "string", "description": "a material code such as M-4471"},
     "qty": {"type": "number", "description": "what you intend to buy, in base units"}},
    ["material", "qty"],
)
def compare_quotations(material: str, qty: float) -> Result:
    wanted = (material or "").strip()
    try:
        amount = float(qty)
    except (TypeError, ValueError):
        amount = 0.0

    quotes = _quotes(wanted or None)
    offers = quotes.value or []
    if quotes.value is None:
        return Result(None, quotes.origin, quotes.source,
                      note=quotes.note or "the quotation file could not be read")
    if not offers:
        return Result(None, quotes.origin, quotes.source,
                      note=f"no quotations on file for {wanted or 'that material'}")
    if amount <= 0:
        return Result([], quotes.origin, quotes.source,
                      note="a quantity has to be more than zero before a total means anything")

    names = _master()
    as_of = _as_of()
    rows: List[dict] = []
    for q in offers:
        sid = str(q.get("Supplier"))
        who = names.get(sid) or {}
        until = _valid_to(q)
        unit = _unit_price(q)
        rows.append({
            "supplier": sid,
            "name": who.get("SupplierName"),
            "country": who.get("Country"),
            "quotation": q.get("SupplierQuotation"),
            "unit_price": int(round(unit)),
            "lead_days": int(q.get("DeliveryTimeInDays") or 0),
            "total": int(round(unit * amount)),
            "tkdn": who.get("TkdnCertifiedPct"),
            "valid_to": until.isoformat() if until else None,
            "live": _live(q, as_of),
            "status": q.get("QtnLifecycleStatus"),
        })

    _on_trade_off(rows)
    # Live offers cheapest first, then whatever has lapsed behind them: an
    # expired price is still evidence of what was quoted, so it is shown and
    # simply does not get a place in the ranking.
    rows.sort(key=lambda r: (not r["live"], r["total"], r["lead_days"]))
    rank = 0
    for r in rows:
        if r["live"]:
            rank += 1
            r["rank"] = rank
        else:
            r["rank"] = None

    unit_name = str(offers[0].get("PurchaseOrderQuantityUnit") or "")
    live = [r for r in rows if r["live"]]
    cheapest = min(live, key=lambda r: r["total"]) if live else None
    fastest = min(live, key=lambda r: r["lead_days"]) if live else None
    note = (f"{len(rows)} offers on {wanted} for {amount:g} {unit_name}, "
            f"{len(live)} of them valid on {as_of}.")
    if cheapest and fastest:
        if cheapest["supplier"] == fastest["supplier"]:
            note += f" {cheapest['supplier']} is both the cheapest and the fastest."
        else:
            gap = (100 * (fastest["total"] / cheapest["total"] - 1)
                   if cheapest["total"] else 0.0)
            note += (f" Cheapest is {cheapest['supplier']} at Rp {cheapest['total']:,} "
                     f"in {cheapest['lead_days']} days; fastest is {fastest['supplier']} "
                     f"at {fastest['lead_days']} days for Rp {fastest['total']:,}, "
                     f"{gap:.1f}% more.")
        on_line = sum(1 for r in rows if r["on_line"])
        note += (f" {on_line} of them sit on the trade-off line: nothing else is both "
                 f"cheaper and quicker.")

    lapsed = len(rows) - len(live)
    if lapsed:
        note += f" {lapsed} past their validity date are listed but not ranked."
    stale = sum(1 for r in rows if not r["live"] and r["status"] == "Open")
    fresh = sum(1 for r in rows if r["live"] and r["status"] == "Completed")
    if stale:
        note += f" SAP still reads {stale} of those as Open after the price lapsed."
    if fresh:
        note += f" {fresh} read Completed while the price is still good."

    # Two supplier codes bidding against each other on the same material is the
    # duplicate in the book, now with a price attached to it.
    by_firm: Dict[str, List[str]] = {}
    for r in live:
        key = _identity(r["name"] or "")
        if key:
            by_firm.setdefault(key, []).append(r["supplier"])
    twice = [v for v in by_firm.values() if len(v) > 1]
    if twice:
        note += " " + "; ".join(
            f"{' and '.join(v)} are one company bidding under two codes" for v in twice) + "."

    note += (" Price and lead time come from the quotation file; name and certificate "
             "from the supplier master.")
    return Result(rows, quotes.origin, quotes.source, note=note)


@register(
    "propose_purchase_order", "procurement",
    "Draft a purchase order against a quotation on file and raise it for approval. "
    "The price is taken from the quotation and never from the request: a draft "
    "cannot quote a number nobody sent us. Refuses when that offer has passed its "
    "validity date, naming the firms still quoting instead. Returns the draft with "
    "its total, its lead time and the certificate behind it, plus, when this is "
    "called from a run on a signal, the id of the action now waiting in the "
    "approval queue. Nothing is sent to SAP and nothing is approved here: a "
    "purchase order always waits for a person.",
    {"material": {"type": "string", "description": "a material code such as M-4471"},
     "supplier": {"type": "string", "description": "the supplier id the quote belongs to"},
     "qty": {"type": "number", "description": "what to buy, in base units"},
     "needed_by": {"type": "string", "description": "YYYY-MM-DD, the date the material is needed"},
     "rationale": {"type": "string",
                   "description": "why this firm, in one sentence. The approver reads it."}},
    ["material", "supplier", "qty", "needed_by", "rationale"],
)
def propose_purchase_order(material: str, supplier: str, qty: float,
                           needed_by: str, rationale: str) -> Result:
    wanted = (material or "").strip()
    sid = (supplier or "").strip()
    reason = (rationale or "").strip()
    try:
        amount = float(qty)
    except (TypeError, ValueError):
        amount = 0.0

    # Both refusals are about the request rather than the data, so neither is a
    # missing entity: nothing was read wrong, something was asked wrong.
    if amount <= 0:
        return Result(None, Origin.MISSING, "purchase order",
                      note="a purchase order for zero is a record of nothing. "
                           "Name a quantity.")
    if not reason:
        return Result(None, Origin.MISSING, "purchase order",
                      note="an approver signs a reason, so the draft needs one.")

    quotes = _quotes(wanted or None)
    if quotes.value is None:
        return Result(None, quotes.origin, quotes.source,
                      note=quotes.note or "the quotation file could not be read")
    offers = quotes.value or []
    mine = [q for q in offers if str(q.get("Supplier")) == sid]
    if not mine:
        others = sorted({str(q.get("Supplier")) for q in offers})
        return Result(None, quotes.origin, quotes.source,
                      note=f"{sid or 'that supplier'} has not quoted "
                           f"{wanted or 'that material'}"
                           + (f". Firms that have: {', '.join(others)}" if others else ""))

    as_of = _as_of()
    current = [q for q in mine if _live(q, as_of)]
    if not current:
        last = max(mine, key=lambda q: str(q.get("CreationDate")))
        still = sorted({str(q.get("Supplier")) for q in offers
                        if _live(q, as_of) and str(q.get("Supplier")) != sid})
        return Result(None, quotes.origin, quotes.source,
                      note=(f"quotation {last.get('SupplierQuotation')} from {sid} on "
                            f"{wanted} stopped being valid on "
                            f"{last.get('QuotationValidityEndDate')} and {sid} has no "
                            f"current offer. Re-quote before drafting."
                            + (f" Still quoting: {', '.join(still)}." if still else "")))

    # The newest live offer from this firm, if it sent more than one.
    q = max(current, key=lambda r: str(r.get("CreationDate")))
    unit = _unit_price(q)
    until = _valid_to(q)
    who = _master().get(sid) or {}
    unit_name = str(q.get("PurchaseOrderQuantityUnit") or "")
    total = int(round(unit * amount))

    payload = {
        "material": wanted, "supplier": sid, "qty": amount, "needed_by": str(needed_by),
        "unit_price_idr": int(round(unit)), "cost_idr": total,
        "quotation": q.get("SupplierQuotation"),
        "lead_time_days": int(q.get("DeliveryTimeInDays") or 0),
        "tkdn_certified_pct": who.get("TkdnCertifiedPct"),
        "rationale": reason,
    }
    raised = raise_action("draft_po", False, **payload)

    name = who.get("SupplierName") or sid
    valid = until.isoformat() if until else "an unknown date"
    head = (f"{name} on {wanted}: Rp {total:,} for {amount:g} {unit_name} at "
            f"Rp {payload['unit_price_idr']:,} per {unit_name}, "
            f"{payload['lead_time_days']} days lead, quotation "
            f"{payload['quotation']}, valid to {valid}.")
    if raised.value is None:
        note = head + " " + raised.note + " The draft is written here but not recorded."
    elif raised.value.get("repeated"):
        note = head + " " + raised.note
    else:
        note = (head + f" Raised as {raised.value['id']}, status "
                       f"{raised.value['status']}: a purchase order waits for "
                       f"procurement_lead and is never sent to SAP by the sender.")

    return Result(
        {**payload, "supplier_name": name, "country": who.get("Country"),
         "unit": unit_name, "valid_to": until.isoformat() if until else None,
         "action_id": (raised.value or {}).get("id"),
         "action_status": (raised.value or {}).get("status")},
        quotes.origin, quotes.source, note=note,
    )
