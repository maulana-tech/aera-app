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
from tools.fetcher import as_of as _today, read

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
    """Every purchase order line — the denominator of every share in this file.
    Delivered lines included: whether a supplier kept its dates is on them."""
    return read("PurchaseOrder", open_only=False)


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
    rows = read("Supplier").value or []
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
    suppliers = read("Supplier")
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
    return read("Quotation", material=material)


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
    in a later month. With SAP connected it is today.
    """
    try:
        return _today()
    except (KeyError, TypeError, ValueError):
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


#: Figures a reader takes out of a sentence: rupiah amounts and day counts.
#: Percentages and tonnages are deliberately not matched - "0.6% above" and
#: "60 T" are not claims about price or lead time.
_RUPIAH = re.compile(r"(?:Rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})+|\d{6,})", re.I)
_DAYS = re.compile(r"\b(\d{1,3})\s*(?:-|\s)?\s*(?:day|days|hari)\b", re.I)


def _figures_in(text: str) -> tuple:
    money = set()
    for m in _RUPIAH.finditer(text or ""):
        digits = re.sub(r"[.,]", "", m.group(1))
        if digits.isdigit():
            money.add(int(digits))
    return money, {int(m.group(1)) for m in _DAYS.finditer(text or "")}


def _shortfall(material: str, lead_days: int) -> Optional[dict]:
    """What the plant is short of this material by the time an order lands.

    Read from the stock rows, not from the request. A purchase order quantity
    is the one figure in the draft that comes straight from a model, and in
    testing a model ordered 1 unit of a material burning 13 tonnes a day. This
    does not refuse that order - a buyer may have a reason - but the approver
    now sees the gap beside the quantity instead of having to go and work it out.
    """
    rows = read("MaterialStock", material=material).value or []
    if not rows:
        return None
    stock = sum(float(r.get("MatlWrhsStkQtyInMatlBaseUnit") or 0) for r in rows)
    daily = sum(float(r.get("DailyConsumption") or 0) for r in rows)
    if daily <= 0:
        return {"stock": stock, "daily": 0.0, "cover_days": None, "short_at_arrival": None}
    return {
        "stock": round(stock, 1),
        "daily": round(daily, 1),
        "cover_days": round(stock / daily, 1),
        "short_at_arrival": round(max(0.0, daily * max(lead_days, 0) - stock), 1),
    }


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

    # Kira rules the supplier before a draft exists. Until this gate was here
    # the whole procurement path reached a purchase order without a ruling at
    # all: check_local_constraints rules an AlternateSource option, a quotation
    # is not one, and so price walked around the veto. Asked here rather than
    # left to the lead to remember, for the same reason simulate_scenario rules
    # its own options instead of trusting the list it was handed.
    from tools.compliance import check_supplier_constraints
    ruling = check_supplier_constraints(sid)
    verdict = ruling.value or {}
    if verdict and not verdict.get("allowed"):
        return Result(None, Origin.MISSING, ruling.source,
                      note=(f"the rules do not clear {sid}: {verdict.get('reason')}. "
                            "A purchase order cannot be drafted against a supplier the "
                            "rules struck out, and price does not overturn that."))
    if ruling.value is None:
        return Result(None, ruling.origin, ruling.source,
                      note=f"{sid} could not be ruled on, so no draft was written. "
                           + (ruling.note or ""))

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

    lead = int(q.get("DeliveryTimeInDays") or 0)

    # The rationale is the one thing on this draft an approver actually reads
    # before signing, and the one thing a model writes freely. Two ways it goes
    # wrong, and they are not equally bad.
    #
    #   A figure that matches NOTHING on file is a fabrication, and is refused
    #   the same way a price taken from the request is refused.
    #
    #   A figure that is real but belongs to a DIFFERENT offer is worse to read
    #   and must not be refused: "only 0.6% above the cheapest at Rp 1,219,098"
    #   is a fair thing to write. In testing a model described quotation ...848
    #   at Rp 1,228,526 in 6 days while the draft ordered ...847 at Rp 1,266,272
    #   in 21 days, so a buyer would have approved the slower, dearer offer
    #   believing it was the faster, cheaper one. That one is stated, loudly,
    #   beside the draft's own figures, and the approver decides.
    mine_money = {int(round(unit)), total}
    mine_days = {lead}
    on_file_money = {int(round(_unit_price(o))) for o in offers
                     if str(o.get("Material")) == wanted}
    on_file_days = {int(o.get("DeliveryTimeInDays") or 0) for o in offers
                    if str(o.get("Material")) == wanted}
    said_money, said_days = _figures_in(reason)

    invented_money = sorted(said_money - on_file_money - mine_money)
    invented_days = sorted(said_days - on_file_days - mine_days)
    if invented_money or invented_days:
        bits = []
        if invented_money:
            bits.append("figure(s) " + ", ".join(f"Rp {m:,}" for m in invented_money))
        if invented_days:
            bits.append("lead time(s) of " + ", ".join(f"{d} days" for d in invented_days))
        return Result(None, Origin.MISSING, "purchase order",
                      note=("the reason names " + " and ".join(bits)
                            + f", which no quotation on file for {wanted} states. This draft "
                              f"is Rp {int(round(unit)):,} per unit, Rp {total:,} in all, "
                              f"{lead} days, on quotation {q.get('SupplierQuotation')}."))

    elsewhere_money = sorted(said_money - mine_money)
    elsewhere_days = sorted(said_days - mine_days)
    conflict = ""
    if elsewhere_money or elsewhere_days:
        said = []
        if elsewhere_money:
            said.append(", ".join(f"Rp {m:,}" for m in elsewhere_money))
        if elsewhere_days:
            said.append(", ".join(f"{d} days" for d in elsewhere_days))
        conflict = (f" The reason quotes {' and '.join(said)}, which is another offer on file, "
                    f"not this one: this draft is Rp {int(round(unit)):,} per unit and "
                    f"{lead} days on quotation {q.get('SupplierQuotation')}.")

    gap = _shortfall(wanted, lead)
    payload = {
        "material": wanted, "supplier": sid, "qty": amount, "needed_by": str(needed_by),
        "unit_price_idr": int(round(unit)), "cost_idr": total,
        "quotation": q.get("SupplierQuotation"),
        "lead_time_days": lead,
        "tkdn_certified_pct": who.get("TkdnCertifiedPct"),
        "rationale": reason,
        "rules_checked": verdict.get("reason"),
        **({"rationale_conflict": conflict.strip()} if conflict else {}),
        **({"stock_on_hand": gap["stock"], "daily_consumption": gap["daily"],
            "days_of_cover": gap["cover_days"],
            "short_at_arrival": gap["short_at_arrival"]} if gap else {}),
    }
    raised = raise_action("draft_po", False, **payload)

    name = who.get("SupplierName") or sid
    valid = until.isoformat() if until else "an unknown date"
    head = (f"{name} on {wanted}: Rp {total:,} for {amount:g} {unit_name} at "
            f"Rp {payload['unit_price_idr']:,} per {unit_name}, "
            f"{payload['lead_time_days']} days lead, quotation "
            f"{payload['quotation']}, valid to {valid}.")
    # The quantity, set against the gap it is meant to close. Never a refusal:
    # a buyer may be topping up deliberately. But the approver sees both.
    head += conflict
    if gap and gap.get("short_at_arrival") is not None:
        short = gap["short_at_arrival"]
        head += (f" {wanted} holds {gap['stock']:g} at {gap['daily']:g} a day, "
                 f"{gap['cover_days']:g} days of cover")
        head += (f", and will be {short:g} short by the time this lands; this order covers "
                 f"{min(100, round(amount / short * 100)):g}% of that."
                 if short > 0 else ", and is not short before this lands.")
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


@register(
    "get_exchange_rate", "procurement",
    "The latest European Central Bank reference rate between two currencies: how many "
    "`quote` one `base` buys, and the date the rate was set. Use it to put a supplier's "
    "price in a foreign currency next to a rupiah one. A reference rate, not the rate a "
    "bank deals at. The ECB publishes no VND.",
    {"base": {"type": "string", "description": "ISO 4217 code, e.g. USD, CNY, JPY"},
     "quote": {"type": "string", "description": "ISO 4217 code, default IDR"}},
    ["base"],
)
def get_exchange_rate(base: str, quote: str = "IDR") -> Result:
    from clients.web_data import exchange_rate
    return exchange_rate(base, quote)


def demo() -> None:
    """The module that drafts purchase orders had no self-check at all, which
    is how three defects reached a live run: quotations read as expired because
    the template never named the validity column, a reason that described one
    offer while the draft ordered another, and a quantity nobody compared with
    the shortfall it was meant to close."""
    from core.config import fixtures_only
    fixtures_only(__file__, "SIGAP_PROCUREMENT_CHECK")

    a = _as_of()
    live = [q for q in (read("Quotation").value or []) if _live(q, a)]
    assert live, "the fixture must carry quotations that are still valid on its as-of date"

    # The draft must go to a supplier the rules clear, because Kira now rules
    # the supplier before a draft exists. In this fixture the company sits
    # below its contract floor, so every foreign firm is struck out and only a
    # domestic one can be ordered from at all.
    mat = "M-1118"
    mine = sorted([q for q in live if q.get("Material") == mat], key=_unit_price)
    assert len(mine) >= 2, mat
    from tools.compliance import check_supplier_constraints
    cleared = [q for q in mine
               if (check_supplier_constraints(str(q.get("Supplier"))).value or {}).get("allowed")]
    assert cleared, "the fixture must carry one domestic supplier quoting this material"
    ours, rival = cleared[0], mine[0]
    sid = str(ours.get("Supplier"))
    draft_unit = int(round(_unit_price(ours)))
    other_unit = int(round(_unit_price(rival)))
    assert other_unit != draft_unit, "the comparison needs two different prices"

    def propose(reason, qty=10.0, supplier=sid):
        return propose_purchase_order(mat, supplier, qty, "2026-09-20", reason)

    # The request is refused before the file is read when it asks for nothing.
    assert propose("why", qty=0).value is None
    assert "zero is a record of nothing" in propose("why", qty=0).note
    assert propose("").value is None and "signs a reason" in propose("").note

    # The veto binds this path. A firm the rules struck out cannot be drafted
    # against at all, whatever it quotes: price does not overturn a ruling.
    blocked = next(q for q in mine
                   if not (check_supplier_constraints(str(q.get("Supplier"))).value or {})
                   .get("allowed"))
    bid = str(blocked.get("Supplier"))
    refused = propose("Cheapest firm on file.", supplier=bid)
    assert refused.value is None, "a blocked supplier must not reach a draft"
    assert f"the rules do not clear {bid}" in refused.note, refused.note
    assert "price does not overturn that" in refused.note

    # A supplier nobody has heard of is refused at the ruling, before quotations
    # are read: there is nothing to rule on.
    gone = propose_purchase_order(mat, "SUP-NOBODY", 10.0, "2026-09-20", "why")
    assert gone.value is None and "could not be ruled on" in gone.note, gone.note

    # A figure that matches nothing on file is a fabrication, and is refused the
    # same way a price taken from the request is.
    made_up = propose("Cheapest anywhere at Rp 1,234,567 per unit.")
    assert made_up.value is None and made_up.origin is Origin.MISSING
    assert "no quotation on file" in made_up.note and "1,234,567" in made_up.note, made_up.note
    assert propose("Lands in 99 days.").value is None, "an invented lead time is a figure too"

    # A real figure that belongs to ANOTHER offer is not refused - citing a
    # rival quote is fair - but the approver is told which number is which.
    crossed = propose(f"Only a little above the cheapest at Rp {other_unit:,}.")
    assert crossed.value is not None, "a comparison must not block a draft"
    assert crossed.value["rationale_conflict"], crossed.value
    assert f"Rp {other_unit:,}" in crossed.note and f"Rp {draft_unit:,}" in crossed.note
    assert "another offer on file, not this one" in crossed.note

    # Written against the offer being ordered, nothing is flagged.
    clean = propose("The incumbent failed its audit, so this is the next approved firm.")
    assert clean.value is not None and "rationale_conflict" not in clean.value, clean.value
    assert "another offer on file" not in clean.note

    # And the quantity now travels beside the gap it is meant to close. The
    # draft is not refused for being small; the approver simply sees both.
    assert clean.value["short_at_arrival"] is not None, clean.value
    assert clean.value["days_of_cover"] and clean.value["daily_consumption"]
    assert "days of cover" in clean.note, clean.note
    # This material has more cover than the lead time, so the honest line is
    # that it is NOT short, and the draft says so rather than inventing a gap.
    assert clean.value["short_at_arrival"] == 0.0, clean.value
    assert "is not short before this lands" in clean.note, clean.note

    # The other branch, on the same rows: stretch the lead past the cover and a
    # real gap appears, computed from the stock and the daily rate.
    g = _shortfall(mat, 60)
    assert g["cover_days"] and g["short_at_arrival"] > 0, g
    assert round(g["daily"] * 60 - g["stock"], 1) == g["short_at_arrival"], g
    assert _shortfall("M-NOT-A-MATERIAL", 10) is None, "no rows means no claim"

    print("procurement ok, zero and reasonless drafts refused ✓ · a supplier the rules "
          "struck out cannot be drafted against ✓ · invented figures refused ✓ "
          "· another offer's figures flagged, not blocked ✓ "
          "· the quantity travels beside the shortfall ✓")


if __name__ == "__main__":
    demo()
