"""What a valid upload of each entity must contain.

Today an uploaded CSV is stored as-is: any columns at all are accepted, so a
file missing `Material` or with text where a quantity belongs sits in the record
as "data" until a tool or the audit trips on it downstream. That is exactly the
silent bad data AERA's whole provenance discipline exists to prevent — a figure
is only as trustworthy as the row under it.

This module is the gate. For each entity it names the columns the code actually
reads (so "required" is grounded in what the engine and tools consume, not a
guess), and which of them must be numbers. Validation is deterministic and
returns the specific problem — a missing column, a non-numeric quantity, an
empty required cell, with the row number — so the uploader can fix the file
rather than discover the breakage three agents later. Extra columns are allowed
through untouched: a real ERP export carries more than AERA reads.
"""
from __future__ import annotations

from typing import Any, Dict, List

# Per entity: the columns a valid row must carry, and which of those must parse
# as a number. Everything not listed is optional and passes through.
ENTITIES: Dict[str, Dict[str, List[str]]] = {
    # Optional columns that change how a figure is READ rather than what it is:
    #   ReplenishmentPolicy  JIT | stock | consignment. Four days of cover on a
    #                        JIT line is the policy working, not an emergency.
    #   LastMovementDate     how deadstock is found: quantity nobody has touched
    #                        is still quantity, and it is the cheapest source
    #                        there is.
    #   Rotation             FIFO | LIFO. With ShelfLifeDays it decides which
    #                        lot may actually be issued.
    "MaterialStock": {
        "required": ["Material", "Plant", "MatlWrhsStkQtyInMatlBaseUnit", "DailyConsumption"],
        "numeric": ["MatlWrhsStkQtyInMatlBaseUnit", "DailyConsumption",
                    "ShelfLifeDays", "DeadstockQty"],
    },
    "PurchaseOrder": {
        "required": ["PurchaseOrder", "Material", "Plant", "OrderQuantity", "Supplier", "DeliveryDate"],
        "numeric": ["OrderQuantity"],
    },
    "SalesOrder": {
        "required": ["SalesOrder", "Material", "Customer", "NetAmount", "RequestedDeliveryDate"],
        "numeric": ["NetAmount"],
    },
    "BillOfMaterial": {
        "required": ["Material", "FinishedGood", "ComponentQuantity"],
        "numeric": ["ComponentQuantity"],
    },
    # HsCode is optional in the file and required by the ruling: an import
    # whose classification is not on record cannot be checked against LARTAS,
    # and tools/compliance.py refuses it rather than waving it through. Keeping
    # the column optional here lets a domestic-only file stay short.
    "AlternateSource": {
        "required": ["id", "Material", "Supplier", "Quantity", "ArrivalDate", "ExtraCostIDR", "Origin"],
        "numeric": ["Quantity", "ExtraCostIDR"],
    },
    # TkdnCertifiedPct is NOT required, and that is the point. A foreign
    # supplier has no Indonesian local-content certificate, so demanding the
    # column forces whoever fills the file to type 0 - which is a claim
    # ("certified at zero") rather than the truth ("no certificate on record").
    # tools/compliance.py already reads the two apart: it blocks a DOMESTIC
    # supplier that carries no figure, and does not ask a foreign one for one.
    # Requiring it here contradicted that, and rejected this project's own
    # fixtures/demo/Supplier.csv - 9 of its 18 rows are foreign.
    "Supplier": {
        "required": ["Supplier", "SupplierName", "Country"],
        "numeric": ["TkdnCertifiedPct"],
    },
    # A long-term contract at a fixed price. It belongs here because the
    # quantity may already be bought: a spot purchase placed beside an unused
    # call-off is money spent twice, and nothing in the system stops it.
    "BlanketOrder": {
        "required": ["BlanketOrder", "Supplier", "Material", "AgreedPriceIDR",
                     "RemainingQty", "ValidTo"],
        "numeric": ["AgreedPriceIDR", "RemainingQty"],
    },
    "Quotation": {
        "required": ["SupplierQuotation", "Supplier", "Material", "OrderQuantity", "NetPrice", "DeliveryTimeInDays"],
        "numeric": ["OrderQuantity", "NetPrice", "DeliveryTimeInDays"],
    },
    # Neither of these is in the core book. A customs declaration lives in the
    # customs authority's system (CEISA in Indonesia); an engineering-approved
    # substitute in a change record. An upload is how AERA gets to see them.
    "CustomsDeclaration": {
        "required": ["PurchaseOrder", "Port", "ArrivalDate", "Status"],
        "numeric": [],
    },
    "MaterialSubstitute": {
        "required": ["Material", "Substitute", "Approved"],
        "numeric": ["Ratio", "QualificationDays"],
    },
    # Where a supplier request or a customer notice is sent.
    "PartnerContact": {
        "required": ["Partner", "Email"],
        "numeric": [],
    },
}

# A realistic one-row example per entity, so the template a user downloads shows
# the shape, not just the headers.
EXAMPLES: Dict[str, Dict[str, Any]] = {
    "MaterialStock": {"Material": "M-4471", "Plant": "KRW1",
                      "MatlWrhsStkQtyInMatlBaseUnit": 84.0, "DailyConsumption": 9.2,
                      "BaseUnit": "T", "Description": "Cold-rolled coil"},
    "PurchaseOrder": {"PurchaseOrder": "4500000123", "Material": "M-4471", "Plant": "KRW1",
                      "OrderQuantity": 85.0, "Supplier": "SUP-2201", "LoadingPort": "CNNGB",
                      "DeliveryDate": "2026-09-12", "Status": "open"},
    "SalesOrder": {"SalesOrder": "10001", "Material": "FG-9001", "Customer": "OEM-01",
                   "CustomerName": "Astra OEM", "NetAmount": 2_000_000_000, "Currency": "IDR",
                   "RequestedDeliveryDate": "2026-09-20", "Quantity": 1600,
                   "LatePenaltyPctPerDay": 0.5, "LatePenaltyCapPct": 10.0},
    "BillOfMaterial": {"Material": "M-4471", "FinishedGood": "FG-9001",
                       "ComponentQuantity": 1.4, "Description": "bracket"},
    "AlternateSource": {"id": "B", "Material": "M-4471", "Supplier": "SUP-4417",
                        "Quantity": 60.0, "ArrivalDate": "2026-09-12", "ExtraCostIDR": 94_000_000,
                        "Origin": "ID", "TkdnAfterPct": 41.6, "NewOrigin": 0, "QualificationDays": 3,
                        "label": "Local supplier, Gresik"},
    "Supplier": {"Supplier": "SUP-2201", "SupplierName": "Ningbo Yongtai Metals",
                 "Country": "CN", "TkdnCertifiedPct": 38.2},
    # QuotationValidityEndDate is not required, but leave it out and every offer
    # in the file reads as expired: tools/procurement.py counts an offer nobody
    # can check as one a buyer must re-quote. A template that did not show the
    # column handed companies a book of quotations that was dead on arrival.
    # A long-term contract at a fixed price. It belongs here because the
    # quantity may already be bought: a spot purchase placed beside an unused
    # call-off is money spent twice, and nothing in the system stops it.
    "BlanketOrder": {
        "required": ["BlanketOrder", "Supplier", "Material", "AgreedPriceIDR",
                     "RemainingQty", "ValidTo"],
        "numeric": ["AgreedPriceIDR", "RemainingQty"],
    },
    "BlanketOrder": {"BlanketOrder": "4600001200", "Supplier": "SUP-2201",
                     "Material": "M-4471", "AgreedPriceIDR": 32_000_000,
                     "RemainingQty": 154.9, "ValidFrom": "2026-03-01",
                     "ValidTo": "2026-12-17"},
    "Quotation": {"SupplierQuotation": "6000000045", "Supplier": "SUP-4417", "Material": "M-4471",
                  "OrderQuantity": 60.0, "NetPrice": 1_560_000, "DeliveryTimeInDays": 9,
                  "Currency": "IDR", "QtnLifecycleStatus": "A",
                  "QuotationValidityEndDate": "2026-10-31"},
    "CustomsDeclaration": {"DeclarationNumber": "PIB-2609-0027", "PurchaseOrder": "4500018876",
                           "Material": "M-5512", "Supplier": "SUP-2209", "OriginCountry": "CN",
                           "Port": "IDTPP", "ArrivalDate": "2026-09-01",
                           "SubmittedDate": "2026-09-01", "Lane": "red", "Status": "held",
                           "ReleasedDate": "", "HoldReason": "certificate of origin disputed"},
    "MaterialSubstitute": {"Material": "M-4471", "Substitute": "M-4472", "FinishedGood": "FG-1120",
                           "Ratio": 1.0, "Approved": "false", "QualificationDays": 21,
                           "Basis": "casting trial passed; OEM approval pending"},
    "PartnerContact": {"Partner": "SUP-2209", "PartnerName": "Qingdao Baowu Steel",
                       "Role": "supplier", "Email": "export.sales@supplier.example"},
}


def entity_names() -> List[str]:
    return sorted(ENTITIES)


def template(entity: str) -> Dict[str, Any]:
    """Columns, required set, numeric set and a one-row CSV example for `entity`."""
    spec = ENTITIES[entity]
    example = EXAMPLES.get(entity, {})
    columns = list(example.keys()) or spec["required"]
    header = ",".join(columns)
    row = ",".join(str(example.get(c, "")) for c in columns)
    return {
        "entity": entity,
        "columns": columns,
        "required": spec["required"],
        "numeric": spec["numeric"],
        "example_csv": f"{header}\n{row}" if example else header,
    }


def _is_number(v: Any) -> bool:
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v.strip())
            return True
        except ValueError:
            return False
    return False


def _is_empty(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def validate(entity: str, rows: List[dict], *, max_problems: int = 20) -> Dict[str, Any]:
    """Check uploaded rows against the entity's schema. Deterministic.

    Returns {ok, errors, row_problems, accepted}. A missing required column (at
    the header level) or any row problem makes ok False — AERA refuses to store
    data it cannot stand behind, and says exactly what is wrong. `row_problems`
    is capped so a wholly-broken file does not return megabytes of errors."""
    if entity not in ENTITIES:
        return {"ok": False, "errors": [f"unknown entity '{entity}'; one of {entity_names()}"],
                "row_problems": [], "accepted": 0}
    if not rows:
        return {"ok": False, "errors": ["the file has no data rows"],
                "row_problems": [], "accepted": 0}

    spec = ENTITIES[entity]
    present = set(rows[0].keys())
    missing_cols = [c for c in spec["required"] if c not in present]
    errors: List[str] = []
    if missing_cols:
        errors.append(f"missing required column(s): {', '.join(missing_cols)}")

    row_problems: List[dict] = []
    for i, r in enumerate(rows, start=1):
        probs: List[str] = []
        for c in spec["required"]:
            if c in present and _is_empty(r.get(c)):
                probs.append(f"{c} is empty")
        for c in spec["numeric"]:
            v = r.get(c)
            if not _is_empty(v) and not _is_number(v):
                probs.append(f"{c} is not a number ({v!r})")
        if probs:
            if len(row_problems) < max_problems:
                row_problems.append({"row": i, "problems": probs})

    bad_rows = sum(1 for _ in row_problems)  # at least this many; capped view
    ok = not missing_cols and not row_problems
    if row_problems and not errors:
        errors.append(f"{bad_rows}{'+' if bad_rows >= max_problems else ''} row(s) have problems")
    return {"ok": ok, "errors": errors, "row_problems": row_problems,
            "accepted": len(rows) if ok else 0}


def demo() -> None:
    # Every uploadable entity has an example whose columns satisfy its own schema.
    for e in entity_names():
        ex = EXAMPLES.get(e)
        assert ex, f"{e} has no example"
        v = validate(e, [ex])
        assert v["ok"], (e, v)

    # Supplier and Quotation — the two the old whitelist left out — are present.
    assert "Supplier" in entity_names() and "Quotation" in entity_names()

    # A missing required column is named, not swallowed.
    bad = validate("MaterialStock", [{"Material": "M-1", "Plant": "KRW1"}])
    assert not bad["ok"] and any("MatlWrhsStkQtyInMatlBaseUnit" in e for e in bad["errors"]), bad

    # A non-numeric quantity is caught with the row number.
    v = validate("MaterialStock", [{"Material": "M-1", "Plant": "KRW1",
                                     "MatlWrhsStkQtyInMatlBaseUnit": "plenty",
                                     "DailyConsumption": 9.2}])
    assert not v["ok"] and v["row_problems"][0]["row"] == 1
    assert any("not a number" in p for p in v["row_problems"][0]["problems"]), v

    # An empty required cell is caught.
    v = validate("Supplier", [{"Supplier": "SUP-1", "SupplierName": "", "Country": "ID",
                               "TkdnCertifiedPct": 40}])
    assert not v["ok"] and any("SupplierName is empty" in p for p in v["row_problems"][0]["problems"])

    # Unknown entity is refused.
    assert not validate("Nonsense", [{"x": 1}])["ok"]

    # The template carries headers + a sample.
    t = template("Quotation")
    assert "SupplierQuotation" in t["columns"] and t["example_csv"].count("\n") == 1

    print(f"schema ok, {len(entity_names())} entities validate ✓ · missing/numeric/empty caught ✓ "
          "· Supplier+Quotation uploadable ✓ · templates ✓")


if __name__ == "__main__":
    demo()
