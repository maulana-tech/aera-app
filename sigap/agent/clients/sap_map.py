"""SAP S/4HANA, read into the rows every tool already speaks.

The fixtures, the upload templates (core/schema.py) and every tool use one
flat row per entity: a purchase order line carries its material, its
supplier, its loading port and its dates. SAP keeps those in four places
(header, item, schedule line, business partner) and some of them nowhere.
The tools used to read the SAP header as if it were that flat row, so on a
live tenant every one of them came back empty: no Material on a PO header,
and the first hundred stock rows filtered in Python rarely held the material
asked about. An empty list reads exactly like "no exposure". This file does
the joins once, so the tools above it do not know SAP's transport shape.

Four rules:

  - Filter at SAP. A material or a plant goes into $filter, never into a
    Python filter over a capped page.
  - SAP sends every number as a string and every date as /Date(ms)/. Both
    are converted here, once.
  - A field SAP does not hold is None, never a default, and the note on the
    result names it. What SAP does not hold, in SIGAP's terms:
        MaterialStock.DailyConsumption   derived here from 90 days of goods issues
        PurchaseOrder.LoadingPort        derived from the incoterms location, when it names a port
        Supplier.TkdnCertifiedPct        not in SAP (Indonesian local-content certificate)
        AlternateSource.Quantity, ExtraCostIDR, TkdnAfterPct, NewOrigin
        SalesOrder.LatePenaltyPctPerDay, LatePenaltyCapPct  (contract terms)
    tools/fetcher.read() fills these from an upload, when there is one,
    labelled as such.
  - A read is capped (SIGAP_SAP_ROWS, default 2000). A capped read says so,
    because "the first 2000" is not "all".
"""
from __future__ import annotations

import os
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from clients import sap_s4
from core.provenance import Origin, Result

CAP = int(os.environ.get("SIGAP_SAP_ROWS", "2000"))
TTL_SECONDS = 120                   # one handling reads the same rows many times
CONSUMPTION_DAYS = 90
CHUNK = 20                          # values per `or` group in a $filter

#: Goods movements that consume stock, and the reversals that undo them.
#: 201 cost centre, 221 project, 261 production order, 281 network, 291 any
#: account, 601 delivery to a customer. A transfer (311, 641) moves stock
#: without using it and is not here.
ISSUES = ("201", "221", "261", "281", "291", "601")
REVERSALS = ("202", "222", "262", "282", "292", "602")

#: InventoryStockType: what may be used and what may not.
USABLE, QUALITY, BLOCKED = "01", "02", "07"

PO = "API_PURCHASEORDER_PROCESS_SRV"
STOCK = "API_MATERIAL_STOCK_SRV"
SALES = "API_SALES_ORDER_SRV"
BP = "API_BUSINESS_PARTNER"
INFO = "API_INFORECORD_PROCESS_SRV"
QTN = "API_QTN_PROCESS_SRV"
MATDOC = "API_MATERIAL_DOCUMENT_SRV"
PRODUCT = "API_PRODUCT_SRV"
BOM = "API_BILL_OF_MATERIAL_SRV"

_lock = threading.Lock()
_cache: Dict[Tuple, Tuple[float, list, bool]] = {}


# --------------------------------------------------------------- conversion
def sap_date(v: Any) -> Optional[str]:
    """/Date(1629936000000)/ or /Date(1629936000000+0000)/ -> '2021-08-26'."""
    m = re.match(r"/Date\((-?\d+)", str(v or ""))
    if not m:
        return None
    d = datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc).date()
    return None if d.year >= 9999 else d.isoformat()


def num(v: Any) -> Optional[float]:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _lit(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def _eq(field: str, value: Optional[str]) -> Optional[str]:
    return f"{field} eq {_lit(value)}" if value else None


def _any(field: str, values: Iterable[str]) -> List[str]:
    """`(f eq 'a' or f eq 'b')` in groups of CHUNK, so a long list is several
    short requests rather than one URL the gateway refuses."""
    vals = sorted({str(v) for v in values if v})
    return ["(" + " or ".join(f"{field} eq {_lit(v)}" for v in vals[i:i + CHUNK]) + ")"
            for i in range(0, len(vals), CHUNK)]


def _and(*parts: Optional[str]) -> Optional[str]:
    kept = [p for p in parts if p]
    return " and ".join(kept) if kept else None


def as_of() -> date:
    """Today in Jakarta. Live data is read as of now, not as of a fixture."""
    return datetime.now(timezone(timedelta(hours=7))).date()


# --------------------------------------------------------------------- read
def _read(service: str, entity: str, filt: Optional[str] = None, select: str = "",
          expand: str = "", top: Optional[int] = None, orderby: str = "") -> Tuple[list, bool]:
    """Rows, and whether the cap cut them off. Cached for TTL_SECONDS."""
    top = top or CAP
    key = (service, entity, filt, select, expand, top, orderby)
    with _lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < TTL_SECONDS:
            return hit[1], hit[2]
    params: Dict[str, str] = {"$top": str(top)}
    if filt:
        params["$filter"] = filt
    if select:
        params["$select"] = select
    if expand:
        params["$expand"] = expand
    if orderby:
        params["$orderby"] = orderby
    rows = sap_s4.rows(sap_s4.get(service, entity, params))
    capped = len(rows) >= top
    with _lock:
        _cache[key] = (time.monotonic(), rows, capped)
    return rows, capped


def _read_any(service: str, entity: str, field: str, values: Iterable[str],
              rest: Optional[str] = None, **kw) -> Tuple[list, bool]:
    out, capped = [], False
    for group in _any(field, values):
        rows, c = _read(service, entity, _and(group, rest), **kw)
        out += rows
        capped |= c
    return out, capped


def forget() -> None:
    with _lock:
        _cache.clear()


def _nested(row: dict, nav: str) -> Any:
    v = row.get(nav) or {}
    return v.get("results", v) if isinstance(v, dict) else v


def _capped_note(capped: bool, what: str) -> List[str]:
    return [f"the first {CAP} {what} only (SIGAP_SAP_ROWS)"] if capped else []


# -------------------------------------------------------------------- stock
def consumption(material: Optional[str] = None, plant: Optional[str] = None,
                days: int = CONSUMPTION_DAYS) -> Tuple[Dict[Tuple[str, str], float], bool, date]:
    """(material, plant) -> units issued per day over the last `days`, net of
    reversals; whether the read was capped; and the window's first day."""
    start = as_of() - timedelta(days=days)
    kinds = " or ".join(f"GoodsMovementType eq {_lit(t)}" for t in ISSUES + REVERSALS)
    filt = _and(f"to_MaterialDocumentHeader/PostingDate ge datetime'{start.isoformat()}T00:00:00'",
                f"({kinds})", _eq("Material", material), _eq("Plant", plant))
    rows, capped = _read(MATDOC, "A_MaterialDocumentItem", filt,
                         select="Material,Plant,GoodsMovementType,QuantityInBaseUnit",
                         top=max(CAP, 5000))
    total: Dict[Tuple[str, str], float] = {}
    for r in rows:
        q = num(r.get("QuantityInBaseUnit")) or 0.0
        sign = -1 if r.get("GoodsMovementType") in REVERSALS else 1
        k = (r.get("Material"), r.get("Plant"))
        total[k] = total.get(k, 0.0) + sign * q
    return {k: round(max(v, 0.0) / days, 3) for k, v in total.items()}, capped, start


def consumption_series(material: str, plant: str,
                       days: int = CONSUMPTION_DAYS) -> List[Tuple[date, float]]:
    """Daily units issued, one entry per calendar day (zero days included),
    for the forecast."""
    start = as_of() - timedelta(days=days)
    kinds = " or ".join(f"GoodsMovementType eq {_lit(t)}" for t in ISSUES + REVERSALS)
    filt = _and(f"to_MaterialDocumentHeader/PostingDate ge datetime'{start.isoformat()}T00:00:00'",
                f"({kinds})", _eq("Material", material), _eq("Plant", plant))
    rows, _ = _read(MATDOC, "A_MaterialDocumentItem", filt, expand="to_MaterialDocumentHeader",
                    select="GoodsMovementType,QuantityInBaseUnit,to_MaterialDocumentHeader/PostingDate",
                    top=max(CAP, 5000))
    by_day: Dict[date, float] = {}
    for r in rows:
        d = sap_date((r.get("to_MaterialDocumentHeader") or {}).get("PostingDate"))
        if not d:
            continue
        sign = -1 if r.get("GoodsMovementType") in REVERSALS else 1
        day = date.fromisoformat(d)
        by_day[day] = by_day.get(day, 0.0) + sign * (num(r.get("QuantityInBaseUnit")) or 0.0)
    if not by_day:
        return []
    return [(start + timedelta(days=i), max(by_day.get(start + timedelta(days=i), 0.0), 0.0))
            for i in range(days + 1)]


def descriptions(materials: Iterable[str]) -> Dict[str, str]:
    mats = sorted({m for m in materials if m})
    if not mats or len(mats) > 3 * CHUNK:
        return {}
    rows, _ = _read_any(PRODUCT, "A_ProductDescription", "Product", mats,
                        rest="Language eq 'EN'", select="Product,ProductDescription")
    return {r["Product"]: r.get("ProductDescription") or "" for r in rows}


def stock(material: Optional[str] = None, plant: Optional[str] = None,
          with_consumption: bool = True) -> Result:
    """One row per material and plant: what may be used, what is held, and
    how fast it goes."""
    rows, capped = _read(STOCK, "A_MatlStkInAcctMod", _and(_eq("Material", material),
                                                          _eq("Plant", plant)),
                         select="Material,Plant,InventoryStockType,InventorySpecialStockType,"
                                "MatlWrhsStkQtyInMatlBaseUnit,MaterialBaseUnit")
    agg: Dict[Tuple[str, str], dict] = {}
    for r in rows:
        k = (r.get("Material"), r.get("Plant"))
        a = agg.setdefault(k, {"Material": k[0], "Plant": k[1], "MatlWrhsStkQtyInMatlBaseUnit": 0.0,
                               "QualityInspectionQty": 0.0, "BlockedQty": 0.0,
                               "SpecialStockQty": 0.0, "BaseUnit": r.get("MaterialBaseUnit") or ""})
        q = num(r.get("MatlWrhsStkQtyInMatlBaseUnit")) or 0.0
        if r.get("InventorySpecialStockType"):
            a["SpecialStockQty"] += q              # promised to a sales order, a project, a consignor
        elif r.get("InventoryStockType") == USABLE:
            a["MatlWrhsStkQtyInMatlBaseUnit"] += q
        elif r.get("InventoryStockType") == QUALITY:
            a["QualityInspectionQty"] += q
        elif r.get("InventoryStockType") == BLOCKED:
            a["BlockedQty"] += q
    out = list(agg.values())
    notes = ["MatlWrhsStkQtyInMatlBaseUnit is unrestricted stock only; quality inspection, "
             "blocked and special stock are reported beside it"] + _capped_note(capped, "stock rows")

    origin = Origin.LIVE
    if with_consumption and out:
        rate, ccapped, start = consumption(material, plant)
        for a in out:
            k = (a["Material"], a["Plant"])
            # Found none in a capped read is not "used none".
            a["DailyConsumption"] = rate.get(k, None if ccapped else 0.0)
        origin = Origin.DERIVED
        notes.append(f"DailyConsumption is goods issued since {start} (movements "
                     f"{', '.join(ISSUES)}, net of reversals) over {CONSUMPTION_DAYS} days")
        notes += _capped_note(ccapped, "goods movements")
    else:
        for a in out:
            a["DailyConsumption"] = None
    names = descriptions(a["Material"] for a in out)
    for a in out:
        a["Description"] = names.get(a["Material"], "")
    return Result(out, origin, STOCK, note="; ".join(notes))


def safety_stock(material: str, plant: str) -> Result:
    rows, _ = _read(PRODUCT, "A_ProductSupplyPlanning",
                    _and(_eq("Product", material), _eq("Plant", plant)),
                    select="Product,Plant,SafetyStockQuantity,MinimumSafetyStockQuantity,SafetyDuration")
    if not rows:
        return Result(None, Origin.MISSING, f"{PRODUCT} A_ProductSupplyPlanning",
                      note=f"no MRP data for {material} at {plant}")
    r = rows[0]
    return Result({"material": material, "plant": plant,
                   "safety_stock": num(r.get("SafetyStockQuantity")),
                   "minimum_safety_stock": num(r.get("MinimumSafetyStockQuantity")),
                   "safety_days": num(r.get("SafetyDuration"))},
                  Origin.LIVE, f"{PRODUCT} A_ProductSupplyPlanning")


def bom_alternatives(material: str) -> Result:
    """Components the bill of materials itself names as interchangeable with
    `material`, one row per (finished good, substitute).

    Items of one BOM that share an AlternativeItemGroup are alternatives for
    each other: the routing and the costing already allow either. That is the
    only substitution S/4 holds as data. A substitute an engineer approved
    outside the BOM is not in it, which is why the tool also reads an upload.
    """
    sel = ("BillOfMaterial,BillOfMaterialHeaderUUID,BillOfMaterialComponent,"
           "BillOfMaterialItemQuantity,AlternativeItemGroup")
    rows, capped = _read(BOM, "A_BillOfMaterialItem",
                         _eq("BillOfMaterialComponent", material), select=sel)
    grouped = [r for r in rows if r.get("AlternativeItemGroup")]
    if not grouped:
        return Result([], Origin.LIVE, f"{BOM} A_BillOfMaterialItem",
                      note=f"{len(rows)} BOM item(s) use {material}; none sits in an "
                           "alternative item group" + ("; the read was capped" if capped else ""))

    heads, _ = _read_any(BOM, "A_BillOfMaterial", "BillOfMaterial",
                         {r["BillOfMaterial"] for r in grouped},
                         select="Material,BillOfMaterial,BillOfMaterialHeaderUUID,Plant")
    head = {h.get("BillOfMaterialHeaderUUID"): h for h in heads}
    out = []
    for r in grouped:
        group, uuid = r["AlternativeItemGroup"], r.get("BillOfMaterialHeaderUUID")
        siblings, _ = _read(BOM, "A_BillOfMaterialItem",
                            _and(_eq("BillOfMaterial", r["BillOfMaterial"]),
                                 _eq("AlternativeItemGroup", group)), select=sel)
        mine = num(r.get("BillOfMaterialItemQuantity"))
        for s in siblings:
            sub = s.get("BillOfMaterialComponent")
            if s.get("BillOfMaterialHeaderUUID") != uuid or not sub or sub == material:
                continue
            theirs = num(s.get("BillOfMaterialItemQuantity"))
            h = head.get(uuid) or {}
            out.append({
                "Material": material, "Substitute": sub,
                "FinishedGood": h.get("Material") or None, "Plant": h.get("Plant") or None,
                "Ratio": round(theirs / mine, 6) if mine and theirs else None,
                "Approved": True,
                "Basis": f"alternative item group {group} in BOM {r['BillOfMaterial']}",
            })
    return Result(out, Origin.LIVE, f"{BOM} A_BillOfMaterialItem",
                  note="items sharing an alternative item group; Ratio is the substitute's "
                       "BOM quantity over the material's")


# ------------------------------------------------------------ purchase orders
def _port(*texts: Optional[str]) -> Optional[str]:
    from signals.places import port_for_location
    for t in texts:
        code = port_for_location(t)
        if code:
            return code
    return None


def purchase_orders(material: Optional[str] = None, plant: Optional[str] = None,
                    numbers: Optional[Iterable[str]] = None, open_only: bool = True,
                    supplier: Optional[str] = None) -> Result:
    """One row per purchase order item, joined to its header (supplier) and
    its schedule lines (dates).

    The supplier sits on the header, not the item, so a supplier's orders are
    found by reading its headers first and then their items by number. Reading
    every item and filtering afterwards would lose any order past the cap.
    """
    if supplier and numbers is None:
        heads, head_capped = _read(PO, "A_PurchaseOrder", _eq("Supplier", supplier),
                                   select="PurchaseOrder,Supplier")
        numbers = sorted({h["PurchaseOrder"] for h in heads if h.get("PurchaseOrder")})
        if not numbers:
            return Result([], Origin.LIVE, PO, note=f"no purchase order with supplier {supplier}")
        if head_capped:
            supplier_capped = f"; the first {len(numbers)} of the supplier's orders only"
        else:
            supplier_capped = ""
    else:
        supplier_capped = ""
    rest = _and(_eq("Material", material), _eq("Plant", plant),
                "IsCompletelyDelivered eq false and PurchasingDocumentDeletionCode eq ''"
                if open_only else None)
    kw = dict(expand="to_PurchaseOrder,to_ScheduleLine",
              select="PurchaseOrder,PurchaseOrderItem,Material,Plant,OrderQuantity,"
                     "PurchaseOrderQuantityUnit,NetPriceAmount,NetPriceQuantity,DocumentCurrency,"
                     "IsCompletelyDelivered,PurchasingDocumentDeletionCode,IncotermsClassification,"
                     "IncotermsLocation1,IncotermsTransferLocation,PurchasingInfoRecord,"
                     "to_PurchaseOrder/Supplier,to_PurchaseOrder/AddressCountry,"
                     "to_PurchaseOrder/IncotermsClassification,to_PurchaseOrder/IncotermsLocation1,"
                     "to_ScheduleLine/ScheduleLineDeliveryDate,"
                     "to_ScheduleLine/SchedLineStscDeliveryDate")
    if numbers:
        plain = {str(n).split("-")[0] for n in numbers}
        rows, capped = _read_any(PO, "A_PurchaseOrderItem", "PurchaseOrder", plain, rest, **kw)
        wanted = {str(n) for n in numbers}
        rows = [r for r in rows if r.get("PurchaseOrder") in wanted
                or f"{r.get('PurchaseOrder')}-{r.get('PurchaseOrderItem')}" in wanted]
    else:
        rows, capped = _read(PO, "A_PurchaseOrderItem", rest, **kw)

    out = []
    for r in rows:
        head = r.get("to_PurchaseOrder") or {}
        lines = _nested(r, "to_ScheduleLine") or []
        planned = sorted(d for d in (sap_date(s.get("SchedLineStscDeliveryDate")) or
                                     sap_date(s.get("ScheduleLineDeliveryDate")) for s in lines) if d)
        current = sorted(d for d in (sap_date(s.get("ScheduleLineDeliveryDate")) for s in lines) if d)
        location = r.get("IncotermsLocation1") or head.get("IncotermsLocation1") or ""
        terms = r.get("IncotermsClassification") or head.get("IncotermsClassification") or ""
        price, per = num(r.get("NetPriceAmount")), num(r.get("NetPriceQuantity")) or 1.0
        status = ("deleted" if r.get("PurchasingDocumentDeletionCode") else
                  "delivered" if r.get("IsCompletelyDelivered") else "open")
        out.append({
            "PurchaseOrder": f"{r.get('PurchaseOrder')}-{r.get('PurchaseOrderItem')}",
            "PurchaseOrderNumber": r.get("PurchaseOrder"),
            "PurchaseOrderItem": r.get("PurchaseOrderItem"),
            "Material": r.get("Material") or "",
            "Plant": r.get("Plant") or "",
            "OrderQuantity": num(r.get("OrderQuantity")) or 0.0,
            "BaseUnit": r.get("PurchaseOrderQuantityUnit") or "",
            "Supplier": head.get("Supplier") or "",
            "SupplierCountry": head.get("AddressCountry") or None,
            "Incoterms": f"{terms} {location}".strip() or None,
            "LoadingPort": _port(location, r.get("IncotermsTransferLocation")),
            "DeliveryDate": planned[0] if planned else None,
            "RevisedDeliveryDate": current[-1] if current else None,
            "Status": status,
            "UnitPrice": round(price / per, 6) if price is not None else None,
            "Currency": r.get("DocumentCurrency") or "",
            "PurchasingInfoRecord": r.get("PurchasingInfoRecord") or None,
        })
    if supplier:
        out = [o for o in out if o["Supplier"] == supplier]
    missing_port = sum(1 for o in out if not o["LoadingPort"])
    notes = ["one row per order item; DeliveryDate is the schedule line's statistical "
             "(first agreed) date, RevisedDeliveryDate its current one"]
    if missing_port:
        notes.append(f"LoadingPort derived from the incoterms location; {missing_port} of "
                     f"{len(out)} lines name no port SAP or this table knows")
    notes += _capped_note(capped, "order lines")
    return Result(out, Origin.LIVE, PO, note="; ".join(notes) + supplier_capped)


# --------------------------------------------------------------- sales orders
def _idr(amount: Optional[float], currency: str) -> Tuple[Optional[float], Optional[float]]:
    """(amount in rupiah, rate) at the ECB reference rate, or (None, None)."""
    if amount is None:
        return None, None
    if (currency or "IDR").upper() == "IDR":
        return amount, 1.0
    try:
        from clients.web_data import exchange_rate
        r = exchange_rate(currency, "IDR")
        rate = r.value and r.value.get("rate")
    except Exception:                                                # noqa: BLE001
        rate = None
    return (round(amount * rate), rate) if rate else (None, None)


def customers(ids: Iterable[str]) -> Dict[str, str]:
    ids = sorted({i for i in ids if i})
    if not ids or len(ids) > 5 * CHUNK:
        return {}
    rows, _ = _read_any(BP, "A_Customer", "Customer", ids, select="Customer,CustomerName")
    return {r["Customer"]: r.get("CustomerName") or "" for r in rows}


def sales_orders(materials: Optional[Iterable[str]] = None, open_only: bool = True) -> Result:
    rest = "SDProcessStatus ne 'C'" if open_only else None
    kw = dict(expand="to_SalesOrder",
              select="SalesOrder,SalesOrderItem,Material,RequestedQuantity,RequestedQuantityUnit,"
                     "NetAmount,TransactionCurrency,SDProcessStatus,"
                     "to_SalesOrder/SoldToParty,to_SalesOrder/RequestedDeliveryDate")
    if materials is not None:
        rows, capped = _read_any(SALES, "A_SalesOrderItem", "Material", materials, rest, **kw)
    else:
        rows, capped = _read(SALES, "A_SalesOrderItem", rest, **kw)
    names = customers((r.get("to_SalesOrder") or {}).get("SoldToParty") for r in rows)
    out, unconverted = [], 0
    for r in rows:
        head = r.get("to_SalesOrder") or {}
        amount, cur = num(r.get("NetAmount")), r.get("TransactionCurrency") or ""
        idr, rate = _idr(amount, cur)
        unconverted += idr is None and amount is not None
        sold_to = head.get("SoldToParty") or ""
        out.append({
            "SalesOrder": f"{r.get('SalesOrder')}-{r.get('SalesOrderItem')}",
            "Material": r.get("Material") or "",
            "Customer": sold_to,
            "CustomerName": names.get(sold_to) or None,
            "NetAmount": idr,
            "Currency": "IDR" if idr is not None else cur,
            "OriginalAmount": amount,
            "OriginalCurrency": cur,
            "Quantity": num(r.get("RequestedQuantity")),
            "RequestedDeliveryDate": sap_date(head.get("RequestedDeliveryDate")),
            "LatePenaltyPctPerDay": None,
            "LatePenaltyCapPct": None,
        })
    notes = ["one row per order item; NetAmount in rupiah at the ECB reference rate"
             + ("" if not unconverted else f", {unconverted} line(s) could not be converted")]
    if open_only:
        notes.append("open items only (SDProcessStatus not C)")
    notes += _capped_note(capped, "order items")
    origin = Origin.DERIVED if any(o["OriginalCurrency"] not in ("", "IDR") for o in out) else Origin.LIVE
    return Result(out, origin, SALES, note="; ".join(notes))


# ------------------------------------------------------------------ suppliers
def suppliers(ids: Optional[Iterable[str]] = None) -> Result:
    sel = "Supplier,SupplierName"
    if ids is not None:
        rows, capped = _read_any(BP, "A_Supplier", "Supplier", ids, select=sel)
        addr, _ = _read_any(BP, "A_BusinessPartnerAddress", "BusinessPartner", ids,
                            select="BusinessPartner,Country")
    else:
        rows, capped = _read(BP, "A_Supplier", select=sel)
        addr, _ = _read(BP, "A_BusinessPartnerAddress", select="BusinessPartner,Country",
                        top=max(CAP, 5000))
    country = {a.get("BusinessPartner"): a.get("Country") for a in addr if a.get("Country")}
    out = [{"Supplier": r.get("Supplier"), "SupplierName": r.get("SupplierName") or "",
            "Country": country.get(r.get("Supplier")), "TkdnCertifiedPct": None} for r in rows]
    notes = ["Country from the business partner's address; TkdnCertifiedPct is not held in SAP"]
    notes += _capped_note(capped, "suppliers")
    return Result(out, Origin.LIVE, BP, note="; ".join(notes))


def partner_email(partner: str) -> Result:
    """The email on a supplier's or customer's business partner address. In
    S/4HANA a supplier and a customer are business partners under the same
    number, so one read serves both. The default address comes first."""
    rows, _ = _read(BP, "A_BusinessPartnerAddress", f"BusinessPartner eq '{partner}'",
                    select="BusinessPartner,AddressID,to_EmailAddress/EmailAddress,"
                           "to_EmailAddress/IsDefaultEmailAddress",
                    expand="to_EmailAddress", top=10)
    found = [(bool(e.get("IsDefaultEmailAddress")), str(e.get("EmailAddress") or "").strip())
             for r in rows for e in _nested(r, "to_EmailAddress") or []]
    found = sorted((d, a) for d, a in found if a)
    if not found:
        return Result(None, Origin.MISSING, BP,
                      note=f"business partner {partner} has no email on its address"
                      if rows else f"no business partner {partner}")
    return Result(found[-1][1], Origin.LIVE, BP,
                  note=f"the default email of business partner {partner}"
                  if found[-1][0] else f"an email on business partner {partner}'s address")


# ------------------------------------------------------------ alternate sources
def _option_id(record: str, plant: str) -> str:
    return f"IR{record}-{plant}"


def alternate_sources(material: Optional[str] = None,
                      ids: Optional[Iterable[str]] = None) -> Result:
    """Every supplier SAP is already set up to buy this material from: one row
    per purchasing info record and plant, with its price and planned lead
    time. An info record is a supplier the buyer has already qualified, so
    QualificationDays is 0."""
    kw = dict(expand="to_PurgInfoRecdOrgPlantData",
              select="PurchasingInfoRecord,Supplier,Material,IsDeleted,SupplierCertOriginCountry,"
                     "to_PurgInfoRecdOrgPlantData/Plant,to_PurgInfoRecdOrgPlantData/NetPriceAmount,"
                     "to_PurgInfoRecdOrgPlantData/MaterialPriceUnitQty,"
                     "to_PurgInfoRecdOrgPlantData/Currency,"
                     "to_PurgInfoRecdOrgPlantData/MaterialPlannedDeliveryDurn,"
                     "to_PurgInfoRecdOrgPlantData/IsMarkedForDeletion")
    wanted: Optional[set] = None
    if ids is not None:
        wanted = {str(i) for i in ids}
        records = {m.group(1) for m in (re.match(r"IR(\d+)-", i) for i in wanted) if m}
        if not records:
            return Result([], Origin.LIVE, INFO, note="no SAP info record id among "
                                                      f"{', '.join(sorted(wanted))}")
        rows, capped = _read_any(INFO, "A_PurchasingInfoRecord", "PurchasingInfoRecord",
                                 records, **kw)
    else:
        rows, capped = _read(INFO, "A_PurchasingInfoRecord", _eq("Material", material), **kw)
    names = {s["Supplier"]: s for s in suppliers({r.get("Supplier") for r in rows}).value or []} \
        if rows else {}
    today = as_of()
    out = []
    for r in rows:
        if r.get("IsDeleted"):
            continue
        sup = names.get(r.get("Supplier"), {})
        for p in _nested(r, "to_PurgInfoRecdOrgPlantData") or []:
            if p.get("IsMarkedForDeletion"):
                continue
            oid = _option_id(r.get("PurchasingInfoRecord"), p.get("Plant") or "")
            if wanted is not None and oid not in wanted:
                continue
            lead = num(p.get("MaterialPlannedDeliveryDurn"))
            price, per = num(p.get("NetPriceAmount")), num(p.get("MaterialPriceUnitQty")) or 1.0
            unit = round(price / per, 6) if price is not None else None
            cur = p.get("Currency") or ""
            unit_idr, _ = _idr(unit, cur)
            origin_country = r.get("SupplierCertOriginCountry") or sup.get("Country")
            out.append({
                "id": oid,
                "label": f"{sup.get('SupplierName') or r.get('Supplier')}"
                         + (f" ({origin_country})" if origin_country else "")
                         + f", info record {r.get('PurchasingInfoRecord')}, plant {p.get('Plant')}",
                "Supplier": r.get("Supplier"),
                "Material": r.get("Material"),
                "Plant": p.get("Plant"),
                "LeadTimeDays": lead,
                "ArrivalDate": (today + timedelta(days=int(lead))).isoformat() if lead is not None else None,
                "UnitPrice": unit, "Currency": cur, "UnitPriceIDR": unit_idr,
                "Origin": origin_country,
                "Quantity": None, "ExtraCostIDR": None, "TkdnAfterPct": None, "NewOrigin": None,
                "QualificationDays": 0,
            })
    notes = ["from purchasing info records; ArrivalDate is today plus the planned delivery "
             "time; Quantity, ExtraCostIDR, TkdnAfterPct and NewOrigin are not held in SAP"]
    notes += _capped_note(capped, "info records")
    return Result(out, Origin.DERIVED, INFO, note="; ".join(notes))


# ----------------------------------------------------------------- quotations
def quotations(material: Optional[str] = None) -> Result:
    rows, capped = _read(QTN, "A_SupplierQuotationItem", _eq("Material", material),
                         expand="to_SupplierQuotation",
                         select="SupplierQuotation,SupplierQuotationItem,Material,Plant,"
                                "ScheduleLineOrderQuantity,OrderQuantityUnit,NetPriceAmount,"
                                "NetPriceQuantity,DocumentCurrency,ScheduleLineDeliveryDate,"
                                "to_SupplierQuotation/Supplier,to_SupplierQuotation/CreationDate,"
                                "to_SupplierQuotation/QuotationSubmissionDate,"
                                "to_SupplierQuotation/BindingPeriodValidityEndDate,"
                                "to_SupplierQuotation/QTNLifecycleStatus,"
                                "to_SupplierQuotation/PurchasingOrganization")
    out = []
    for r in rows:
        head = r.get("to_SupplierQuotation") or {}
        sent = sap_date(head.get("QuotationSubmissionDate")) or sap_date(head.get("CreationDate"))
        due = sap_date(r.get("ScheduleLineDeliveryDate"))
        days = ((date.fromisoformat(due) - date.fromisoformat(sent)).days
                if sent and due else None)
        out.append({
            "SupplierQuotation": r.get("SupplierQuotation"),
            "SupplierQuotationItem": r.get("SupplierQuotationItem"),
            "Supplier": head.get("Supplier"),
            "Material": r.get("Material"),
            "OrderQuantity": num(r.get("ScheduleLineOrderQuantity")),
            "PurchaseOrderQuantityUnit": r.get("OrderQuantityUnit"),
            "NetPrice": num(r.get("NetPriceAmount")),
            "PriceUnit": num(r.get("NetPriceQuantity")) or 1.0,
            "Currency": r.get("DocumentCurrency"),
            "DeliveryTimeInDays": days,
            "CreationDate": sap_date(head.get("CreationDate")),
            "QuotationValidityEndDate": sap_date(head.get("BindingPeriodValidityEndDate")),
            "QtnLifecycleStatus": head.get("QTNLifecycleStatus"),
            "PurchasingOrganization": head.get("PurchasingOrganization"),
        })
    notes = ["one row per quotation item; DeliveryTimeInDays is the item's delivery date "
             "minus the quotation's submission date"] + _capped_note(capped, "quotation items")
    return Result(out, Origin.LIVE, QTN, note="; ".join(notes))


# ------------------------------------------------------------------ identities
def known_ids() -> Tuple[Dict[str, str], Dict[str, str]]:
    """Materials and plants on record, upper-cased -> as written. Narrow
    $selects, so this is four short reads rather than four full ones."""
    mats: Dict[str, str] = {}
    plants: Dict[str, str] = {}
    for svc, ent, sel in ((STOCK, "A_MatlStkInAcctMod", "Material,Plant"),
                          (PO, "A_PurchaseOrderItem", "Material,Plant"),
                          (SALES, "A_SalesOrderItem", "Material"),
                          (INFO, "A_PurchasingInfoRecord", "Material")):
        try:
            rows, _ = _read(svc, ent, select=sel, top=5000)
        except Exception:                                            # noqa: BLE001
            continue
        for r in rows:
            if r.get("Material"):
                mats.setdefault(str(r["Material"]).upper(), str(r["Material"]))
            if r.get("Plant"):
                plants.setdefault(str(r["Plant"]).upper(), str(r["Plant"]))
    return mats, plants


def material_exists(material: str) -> bool:
    """For an id the capped lists above did not include."""
    try:
        rows, _ = _read(PRODUCT, "A_Product", _eq("Product", material), select="Product", top=1)
    except Exception:                                                # noqa: BLE001
        return False
    return bool(rows)


# ----------------------------------------------------------------- self-check
#: Trimmed from the SAP sandbox (sandbox.api.sap.com), 24 Oct 2026.
SAMPLES: Dict[str, list] = {
    "A_MatlStkInAcctMod": [
        {"Material": "MZ-TG-A18", "Plant": "1710", "InventoryStockType": "01",
         "InventorySpecialStockType": "", "MatlWrhsStkQtyInMatlBaseUnit": "4350", "MaterialBaseUnit": "PC"},
        {"Material": "MZ-TG-A18", "Plant": "1710", "InventoryStockType": "02",
         "InventorySpecialStockType": "", "MatlWrhsStkQtyInMatlBaseUnit": "50", "MaterialBaseUnit": "PC"},
        {"Material": "MZ-TG-A18", "Plant": "1710", "InventoryStockType": "01",
         "InventorySpecialStockType": "E", "MatlWrhsStkQtyInMatlBaseUnit": "20", "MaterialBaseUnit": "PC"},
    ],
    "A_MaterialDocumentItem": [
        {"Material": "MZ-TG-A18", "Plant": "1710", "GoodsMovementType": "601", "QuantityInBaseUnit": "1000"},
        {"Material": "MZ-TG-A18", "Plant": "1710", "GoodsMovementType": "601", "QuantityInBaseUnit": "900"},
        {"Material": "MZ-TG-A18", "Plant": "1710", "GoodsMovementType": "602", "QuantityInBaseUnit": "100"},
    ],
    "A_ProductDescription": [{"Product": "MZ-TG-A18", "ProductDescription": "Trading good A18"}],
    "A_PurchaseOrderItem": [
        {"PurchaseOrder": "4500000012", "PurchaseOrderItem": "40", "Material": "MZ-TG-A18",
         "Plant": "1710", "OrderQuantity": "20", "PurchaseOrderQuantityUnit": "PC",
         "NetPriceAmount": "12.50", "NetPriceQuantity": "1", "DocumentCurrency": "USD",
         "IsCompletelyDelivered": False, "PurchasingDocumentDeletionCode": "",
         "IncotermsClassification": "FOB", "IncotermsLocation1": "Ningbo", "PurchasingInfoRecord": "",
         "to_PurchaseOrder": {"Supplier": "17300001", "AddressCountry": "CN", "IncotermsLocation1": ""},
         "to_ScheduleLine": {"results": [
             {"ScheduleLineDeliveryDate": "/Date(1793836800000)/",
              "SchedLineStscDeliveryDate": "/Date(1793232000000)/"}]}},
        {"PurchaseOrder": "4500000011", "PurchaseOrderItem": "10", "Material": "MZ-RM-R14-01",
         "Plant": "1710", "OrderQuantity": "100", "PurchaseOrderQuantityUnit": "PC",
         "NetPriceAmount": "0.10", "NetPriceQuantity": "1", "DocumentCurrency": "USD",
         "IsCompletelyDelivered": False, "PurchasingDocumentDeletionCode": "",
         "IncotermsClassification": "", "IncotermsLocation1": "",
         "to_PurchaseOrder": {"Supplier": "17300001", "AddressCountry": "US"},
         "to_ScheduleLine": {"results": []}},
    ],
    "A_SalesOrderItem": [
        {"SalesOrder": "1", "SalesOrderItem": "10", "Material": "TG11", "RequestedQuantity": "3",
         "NetAmount": "52.65", "TransactionCurrency": "USD",
         "to_SalesOrder": {"SoldToParty": "17100001", "RequestedDeliveryDate": "/Date(1471392000000)/"}},
    ],
    "A_Customer": [{"Customer": "17100001", "CustomerName": "Domestic US Customer 1"}],
    "A_Supplier": [{"Supplier": "10300001", "SupplierName": "Inlandslieferant DE 1"}],
    "A_BusinessPartnerAddress": [{"BusinessPartner": "10300001", "Country": "DE"}],
    "A_PurchasingInfoRecord": [
        {"PurchasingInfoRecord": "5300000102", "Supplier": "10300001", "Material": "TG11",
         "IsDeleted": False, "SupplierCertOriginCountry": "",
         "to_PurgInfoRecdOrgPlantData": {"results": [
             {"Plant": "1010", "NetPriceAmount": "12.35", "MaterialPriceUnitQty": "1", "Currency": "EUR",
              "MaterialPlannedDeliveryDurn": "8", "IsMarkedForDeletion": False}]}},
    ],
}


def demo() -> None:
    real_get, calls = sap_s4.get, []

    def fake_get(service, entity, params=None):
        calls.append((entity, (params or {}).get("$filter")))
        return {"d": {"results": [dict(r) for r in SAMPLES.get(entity, [])]}}

    from clients import web_data
    from core.provenance import Result as R
    real_fx = web_data.exchange_rate
    web_data.exchange_rate = lambda base, quote="IDR": R(
        {"rate": {"USD": 18000.0, "EUR": 19500.0}.get(base)}, Origin.LIVE, "test")
    sap_s4.get = fake_get
    forget()
    try:
        assert sap_date("/Date(1629936000000)/") == "2021-08-26"
        assert sap_date("/Date(253402300799000+0000)/") is None, "9999-12-31 means no date"
        assert num("4350") == 4350.0 and num("") is None

        s = stock("MZ-TG-A18", "1710")
        row = s.value[0]
        assert ("A_MatlStkInAcctMod", "Material eq 'MZ-TG-A18' and Plant eq '1710'") in calls, \
            "the material goes to SAP, not into a Python filter"
        assert row["MatlWrhsStkQtyInMatlBaseUnit"] == 4350.0, "unrestricted only"
        assert row["QualityInspectionQty"] == 50.0 and row["SpecialStockQty"] == 20.0
        assert row["DailyConsumption"] == round(1800 / CONSUMPTION_DAYS, 3), "issues net of reversals"
        assert row["Description"] == "Trading good A18" and s.origin is Origin.DERIVED

        po = purchase_orders("MZ-TG-A18").value
        a = next(o for o in po if o["Material"] == "MZ-TG-A18")
        assert a["PurchaseOrder"] == "4500000012-40" and a["Supplier"] == "17300001"
        assert a["LoadingPort"] == "CNNGB", "FOB Ningbo names the port"
        assert a["DeliveryDate"] < a["RevisedDeliveryDate"], "the date moved"
        b = next(o for o in po if o["Material"] == "MZ-RM-R14-01")
        assert b["LoadingPort"] is None and b["DeliveryDate"] is None, "no port and no date stay None"

        so = sales_orders(["TG11"])
        assert so.value[0]["NetAmount"] == round(52.65 * 18000) and so.value[0]["Currency"] == "IDR"
        assert so.value[0]["CustomerName"] == "Domestic US Customer 1"

        alt = alternate_sources("TG11").value[0]
        assert alt["id"] == "IR5300000102-1010" and alt["LeadTimeDays"] == 8.0
        assert alt["Origin"] == "DE", "the supplier's country when the record names none"
        assert alt["ExtraCostIDR"] is None and alt["UnitPriceIDR"] == round(12.35 * 19500)
        assert alternate_sources(ids=["IR5300000102-1010"]).value[0]["id"] == alt["id"]
        assert alternate_sources(ids=["B"]).value == [], "a fixture option id is not an SAP one"

        sup = suppliers(["10300001"]).value[0]
        assert sup["Country"] == "DE" and sup["TkdnCertifiedPct"] is None
    finally:
        sap_s4.get = real_get
        web_data.exchange_rate = real_fx
        forget()
    print("  sap_map: filters at SAP ✓ · unrestricted vs held stock ✓ · consumption from goods "
          "issues ✓ · PO item + header + schedule line ✓ · port from incoterms ✓ · sales in "
          "rupiah ✓ · info records as options ✓ · missing stays None ✓")
    print("sap_map ok")


if __name__ == "__main__":
    demo()
