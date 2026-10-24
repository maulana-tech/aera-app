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
    "SalesOrder": ("API_SALES_ORDER_SRV", "A_SalesOrder"),
    "AlternateSource": ("API_PURCHASING_INFO_RECORD_SRV", "A_PurchasingInfoRecord"),
    "Supplier": ("API_BUSINESS_PARTNER", "A_Supplier"),
    # The only entity carrying a price. ExtraCost on an alternate source is what
    # an option costs over the baseline; this is what a firm charges for a tonne.
    "Quotation": ("API_QTN_PROCESS_SRV", "A_SupplierQuotation"),
}


_BOM_HEADER_SELECT = "Material,BillOfMaterial,BillOfMaterialHeaderUUID,Plant"
_BOM_ITEM_SELECT = (
    "BillOfMaterial,BillOfMaterialHeaderUUID,BillOfMaterialComponent,"
    "BillOfMaterialItemQuantity,ComponentDescription"
)


def _sap_rows(service: str, entity: str, select: str) -> list:
    """Read only the fields that form SIGAP's canonical audit schema."""
    return sap_s4.rows(sap_s4.get(service, entity, {"$top": "500", "$select": select}))


def _normalise_audit_entities() -> Dict[str, Result]:
    """Map SAP header/item APIs into the shape the audit and tools consume."""
    po_service = "API_PURCHASEORDER_PROCESS_SRV"
    sales_service = "API_SALES_ORDER_SRV"
    supplier_service = "API_BUSINESS_PARTNER"
    try:
        stock = _sap_rows("API_MATERIAL_STOCK_SRV", "A_MatlStkInAcctMod",
                          "Material,Plant,MatlWrhsStkQtyInMatlBaseUnit")
        po_headers = _sap_rows(po_service, "A_PurchaseOrder", "PurchaseOrder,Supplier")
        supplier_for = {row.get("PurchaseOrder"): row.get("Supplier") for row in po_headers}
        po_items = _sap_rows(po_service, "A_PurchaseOrderItem",
                             "PurchaseOrder,PurchaseOrderItem,Material,OrderQuantity,Plant,IsCompletelyDelivered")
        orders = [{
            "PurchaseOrder": f"{row.get('PurchaseOrder', '')}-{row.get('PurchaseOrderItem', '')}",
            "Material": row.get("Material") or "",
            "Plant": row.get("Plant") or "",
            "OrderQuantity": row.get("OrderQuantity") or 0,
            "Supplier": supplier_for.get(row.get("PurchaseOrder")) or "",
            # The public sandbox separates the delivery date into its schedule-line API.
            # Do not invent dates in an audit: absent dates simply skip date checks.
            "Status": "delivered" if row.get("IsCompletelyDelivered") else "open",
        } for row in po_items]
        sales_items = _sap_rows(sales_service, "A_SalesOrderItem",
                                "SalesOrder,SalesOrderItem,Material,NetAmount,TransactionCurrency")
        sales = [{
            "SalesOrder": f"{row.get('SalesOrder', '')}-{row.get('SalesOrderItem', '')}",
            "Material": row.get("Material") or "",
            "NetAmount": row.get("NetAmount") or 0,
            "Currency": row.get("TransactionCurrency") or "",
        } for row in sales_items]
        suppliers = _sap_rows(supplier_service, "A_Supplier",
                              "Supplier,SupplierName,SupplierFullName")
        return {
            "MaterialStock": Result(stock, Origin.LIVE, "API_MATERIAL_STOCK_SRV"),
            "PurchaseOrder": Result(orders, Origin.LIVE, po_service),
            "SalesOrder": Result(sales, Origin.LIVE, sales_service),
            "Supplier": Result(suppliers, Origin.LIVE, supplier_service),
        }
    except Exception as e:                                        # noqa: BLE001
        note = f"{type(e).__name__}: {e}"
        return {
            "MaterialStock": Result(None, Origin.MISSING, "API_MATERIAL_STOCK_SRV", note=note),
            "PurchaseOrder": Result(None, Origin.MISSING, po_service, note=note),
            "SalesOrder": Result(None, Origin.MISSING, sales_service, note=note),
            "Supplier": Result(None, Origin.MISSING, supplier_service, note=note),
        }


def _bom_rows() -> Result:
    """Return BOM items in SIGAP's Material -> FinishedGood shape.

    SAP separates a BOM into headers (the finished good) and items (the
    component). The fixture and every downstream tool use one flattened row,
    so joining them here keeps the rest of the product independent of SAP's
    transport shape. Narrow $select calls also avoid malformed blank numeric
    fields returned by the public sandbox's full item response.
    """
    service = "API_BILL_OF_MATERIAL_SRV"
    if not sap_s4.available():
        try:
            return Result(fixture("BillOfMaterial"), Origin.MODELLED,
                          "fixture:BillOfMaterial",
                          note="SAP_API_KEY is not set. Using modelled data")
        except KeyError:
            return Result([], Origin.MISSING, "fixture:BillOfMaterial",
                          note="BillOfMaterial is not available")

    try:
        headers = sap_s4.rows(sap_s4.get(
            service, "A_BillOfMaterial", {"$top": "500", "$select": _BOM_HEADER_SELECT},
        ))
        finished_for = {
            h.get("BillOfMaterialHeaderUUID"): h
            for h in headers if h.get("BillOfMaterialHeaderUUID") and h.get("Material")
        }
        items = sap_s4.rows(sap_s4.get(
            service, "A_BillOfMaterialItem", {"$top": "5000", "$select": _BOM_ITEM_SELECT},
        ))
        rows = []
        for item in items:
            header = finished_for.get(item.get("BillOfMaterialHeaderUUID"))
            component = item.get("BillOfMaterialComponent")
            if not header or not component:
                continue
            rows.append({
                "Material": component,
                "FinishedGood": header["Material"],
                "Description": item.get("ComponentDescription") or "",
                "ComponentQuantity": item.get("BillOfMaterialItemQuantity") or 0,
                "Plant": header.get("Plant") or "",
            })
        return Result(rows, Origin.LIVE, service)
    except Exception as e:                                        # noqa: BLE001
        return Result(None, Origin.MISSING, service, note=f"{type(e).__name__}: {e}")


def bom() -> Result:
    """The canonical product structure read by Impact, Audit, and views."""
    return _bom_rows()


def current_dataset() -> tuple[dict, dict]:
    """Everything the system can currently see, by the same path the tools use.

    Returns the rows and, separately, where each entity came from. An audit that
    does not say which of its inputs were modelled is an audit of nothing.
    """
    data: Dict[str, list] = {}
    origins: Dict[str, dict] = {}

    if sap_s4.available():
        results = _normalise_audit_entities()
    else:
        results = {}
        for entity in ("MaterialStock", "PurchaseOrder", "SalesOrder", "Supplier"):
            service, sap_entity = ENTITIES[entity]
            try:
                results[entity] = pull(entity, service, sap_entity, {"$top": "500"})
            except KeyError:
                continue

    for entity, r in results.items():
        data[entity] = r.value or []
        origins[entity] = {"origin": r.origin.value, "source": r.source, "note": r.note}

    for entity in ("AlternateSource", "Quotation"):
        service, sap_entity = ENTITIES[entity]
        try:
            r = pull(entity, service, sap_entity, {"$top": "500"})
        except KeyError:
            continue
        data[entity] = r.value or []
        origins[entity] = {"origin": r.origin.value, "source": r.source, "note": r.note}

    r = bom()
    data["BillOfMaterial"] = r.value or []
    origins["BillOfMaterial"] = {"origin": r.origin.value, "source": r.source, "note": r.note}
    return data, origins
