"""Data fetcher: SAP first, then an upload, then the fixtures.

The point: falling back is NOT hidden. The origin becomes CACHED for an upload
and MODELLED for a fixture, and that shows up both in the UI and in the
calculator's own trust check.

Every tool reads through `read()`. With SAP connected the rows come from
clients/sap_map.py, already in the flat shape the tools use, and a field SAP
does not hold (a loading port, a TKDN figure) is filled from the latest upload
of that entity where the upload has it, with the result's origin lowered to
the upload's and the note saying how many rows it filled. Without SAP the rows
come from the upload, or the fixture, exactly as before.
"""
from __future__ import annotations

import json
import pathlib
import re
import threading
import time
from datetime import date
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from clients import sap_s4
from core.provenance import STRENGTH, Origin, Result

_FIXTURE = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "ningbo_scenario.json"
_cache: Optional[dict] = None


def fixture(entity: str) -> List[dict]:
    global _cache
    if _cache is None:
        _cache = json.loads(_FIXTURE.read_text())
    return _cache[entity]


def profile() -> dict:
    return fixture("Profile")  # type: ignore[return-value]


def as_of() -> date:
    """The date the figures are read as of: today with SAP connected, the
    fixture's own date without it (the scenario is written around that day)."""
    if sap_s4.available():
        from clients import sap_map
        return sap_map.as_of()
    return date.fromisoformat(profile()["AsOfDate"])


def _offline(entity: str, keep: Optional[Callable[[dict], bool]] = None) -> Result:
    """An upload of the entity, else the fixture."""
    # Real company data that was uploaded rather than pulled outranks a fixture:
    # it is genuine, just not live. Hence CACHED. A file the uploader declared
    # as generated stays MODELLED, because calling it cached would launder it.
    u = _upload(entity)
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

    data = fixture(entity)
    if keep:
        data = [r for r in data if keep(r)]
    return Result(
        data, Origin.MODELLED, f"fixture:{entity}",
        note="SAP_API_KEY is not set. Using modelled data",
    )


def _upload(entity: str) -> Optional[dict]:
    try:
        from core import store
        return store.latest_upload(entity)
    except Exception:                                            # noqa: BLE001
        return None


#: Per entity: the fields that match an upload row to an SAP row, and the
#: fields SAP does not hold, which the upload may fill.
SUPPLEMENT: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {
    "MaterialStock": (("Material", "Plant"), ("DailyConsumption",)),
    "PurchaseOrder": (("PurchaseOrder",), ("LoadingPort",)),
    "SalesOrder": (("SalesOrder",), ("LatePenaltyPctPerDay", "LatePenaltyCapPct")),
    "Supplier": (("Supplier",), ("TkdnCertifiedPct",)),
    "AlternateSource": (("Supplier", "Material"),
                        ("Quantity", "ExtraCostIDR", "TkdnAfterPct", "NewOrigin")),
}

#: Weakest first, borrowed rather than restated: this list is the one thing
#: standing between a live figure and an upload quietly lending it its own
#: authority, and two copies of it are one copy that can go stale.
_ORDER = list(STRENGTH)


def _supplement(entity: str, r: Result) -> Result:
    """Fill what SAP does not hold from the latest upload of the entity."""
    if entity not in SUPPLEMENT or not r.value:
        return r
    u = _upload(entity)
    if not u:
        return r
    keys, fields = SUPPLEMENT[entity]

    def key(row: dict, alt: bool = False) -> tuple:
        if entity == "PurchaseOrder" and alt:
            return (str(row.get("PurchaseOrderNumber") or ""),)
        return tuple(str(row.get(k) or "") for k in keys)

    by_key = {key(x): x for x in u["payload"]}
    filled: Dict[str, int] = {}
    for row in r.value:
        src = by_key.get(key(row)) or (by_key.get(key(row, alt=True))
                                       if entity == "PurchaseOrder" else None)
        if not src:
            continue
        for f in fields:
            if row.get(f) is None and src.get(f) not in (None, ""):
                row[f] = src[f]
                filled[f] = filled.get(f, 0) + 1
    if not filled:
        return r
    weaker = Origin.MODELLED if u.get("synthetic") else Origin.CACHED
    r.origin = min(r.origin, weaker, key=_ORDER.index)
    r.source = f"{r.source} + upload:{u['filename']}"
    said = ", ".join(f"{f} for {n} of {len(r.value)} rows" for f, n in filled.items())
    r.note = f"{r.note}; {said} from the upload of {u['uploaded_at']}".lstrip("; ")
    return r


def read(entity: str, *, material: Optional[str] = None, plant: Optional[str] = None,
         port: Optional[str] = None, materials: Optional[Iterable[str]] = None,
         numbers: Optional[Iterable[str]] = None, ids: Optional[Iterable[str]] = None,
         supplier: Optional[str] = None, open_only: bool = True) -> Result:
    """The rows of one entity, filtered, from the best source there is.

    material, plant  exact ids
    port             a UN/LOCODE, on purchase orders
    materials        any of these materials (sales orders, by finished good)
    numbers          purchase order numbers, plain or as 'number-item'
    ids              option ids (AlternateSource) or supplier ids (Supplier)
    supplier         one supplier id, on any entity that carries a Supplier
    open_only        with SAP, leave out delivered order lines; the fixture
                     has always returned every line, and still does
    """
    mats = set(materials) if materials is not None else None
    nums = {str(n) for n in numbers} if numbers is not None else None
    wanted = {str(i) for i in ids} if ids is not None else None

    if sap_s4.available() and entity in ENTITIES:
        from clients import sap_map
        try:
            if entity == "MaterialStock":
                r = sap_map.stock(material, plant)
            elif entity == "PurchaseOrder":
                r = sap_map.purchase_orders(material, plant, nums, open_only, supplier)
            elif entity == "SalesOrder":
                r = sap_map.sales_orders(mats if mats is not None else
                                         ({material} if material else None), open_only)
            elif entity == "Supplier":
                r = sap_map.suppliers(wanted)
            elif entity == "AlternateSource":
                r = sap_map.alternate_sources(material, wanted)
            else:
                r = sap_map.quotations(material)
        except Exception as e:                                       # noqa: BLE001
            return Result(None, Origin.MISSING, ENTITIES[entity][0],
                          note=f"{type(e).__name__}: {e}")
        r = _supplement(entity, r)
        if port and r.value is not None:
            r.value = [x for x in r.value if x.get("LoadingPort") == port]
        if supplier and r.value is not None:
            r.value = [x for x in r.value if str(x.get("Supplier") or "") == supplier]
        return r

    def keep(x: dict) -> bool:
        return ((material is None or x.get("Material") == material)
                and (plant is None or x.get("Plant") == plant)
                and (port is None or x.get("LoadingPort") == port)
                and (mats is None or x.get("Material") in mats)
                and (nums is None or str(x.get("PurchaseOrder")) in nums)
                and (supplier is None or str(x.get("Supplier") or "") == supplier)
                and (wanted is None or str(x.get("id" if entity == "AlternateSource"
                                                 else "Supplier")) in wanted))

    return _offline(entity, keep)


def read_extra(entity: str, keep: Optional[Callable[[dict], bool]] = None) -> Result:
    """An entity S/4HANA does not hold: an upload of it, else the fixture.

    Customs declarations live in the customs authority's system (CEISA in
    Indonesia), engineering-approved substitutes in a change record or a
    spreadsheet; neither has an S/4 service to read. With SAP connected the
    fixture is not offered in their place, because it describes an invented
    company and would sit beside live figures as if it were this one's. No
    upload then means MISSING, which names the gap rather than filling it.
    """
    if sap_s4.available() and not _upload(entity):
        return Result(None, Origin.MISSING, f"upload:{entity}",
                      note=f"no {entity} has been uploaded, and SAP S/4HANA does not hold it")
    try:
        return _offline(entity, keep)
    except KeyError:
        return Result(None, Origin.MISSING, f"fixture:{entity}",
                      note=f"no {entity} is on record")


_KNOWN_LOCK = threading.Lock()
_KNOWN: Dict[str, Any] = {"until": 0.0, "ids": {}, "plants": {}}


def _known() -> Dict[str, Dict[str, str]]:
    """Every material, finished good and plant id on record, upper-cased → as
    written. Cached for five minutes: on live SAP each refresh is four reads."""
    with _KNOWN_LOCK:
        if time.monotonic() < _KNOWN["until"]:
            return _KNOWN
        ids: Dict[str, str] = {}
        plants: Dict[str, str] = {}
        if sap_s4.available():
            from clients import sap_map
            ids, plants = sap_map.known_ids()
            structure = bom().value or []
        else:
            for entity in ("MaterialStock", "PurchaseOrder", "SalesOrder", "AlternateSource"):
                for row in _offline(entity).value or []:
                    if row.get("Material"):
                        ids.setdefault(str(row["Material"]).upper(), str(row["Material"]))
                    if row.get("Plant"):
                        plants.setdefault(str(row["Plant"]).upper(), str(row["Plant"]))
            structure = fixture("BillOfMaterial")
        for row in structure:
            for k in ("Material", "FinishedGood"):
                if row.get(k):
                    ids.setdefault(str(row[k]).upper(), str(row[k]))
            if row.get("Plant"):
                plants.setdefault(str(row["Plant"]).upper(), str(row["Plant"]))
        _KNOWN.update(until=time.monotonic() + 300, ids=ids, plants=plants)
        return _KNOWN


def known_materials() -> Dict[str, str]:
    return _known()["ids"]


def known_plants() -> Dict[str, str]:
    return _known()["plants"]


def material_id(raw: str) -> str:
    """The material id a tool argument means, or ValueError.

    A tool filters its rows on `Material == material`, so an argument written
    as "KRW1 M-5512 Steel bar SCM440" matched nothing and came back as an empty
    list, which reads exactly like "no alternate source exists". That is a
    wrong answer stated with confidence, and the 24 October run on gpt-5.4
    produced one. So an id that is not on record is refused out loud (the
    model gets the error and can correct itself), and an argument that names
    exactly one id on record is read as that id.
    """
    ids = known_materials()
    v = raw.strip()
    if not ids or v.upper() in ids:
        return ids.get(v.upper(), v)
    named = {ids[k] for k in ids
             if re.search(rf"(?<![A-Z0-9-]){re.escape(k)}(?![A-Z0-9-])", v.upper())}
    if len(named) == 1:
        return named.pop()
    if not named and sap_s4.available():
        # The lists above are capped reads of a tenant that may hold far more.
        # An id they missed is asked about directly before it is refused.
        from clients import sap_map
        if sap_map.material_exists(v):
            return v
    example = next(iter(ids.values()))
    raise ValueError(
        f"no material '{raw}' on record"
        + (f"; it names several ({', '.join(sorted(named))}), ask about one" if named else "")
        + f". Pass the material id alone, for example {example}")


def plant_id(raw: str) -> str:
    """The plant id a tool argument means, or ValueError.

    The same failure as a material, one column over: on 24 October small
    models passed "1000", "HUART", "LHINT" and "PlantA", got empty lists back,
    and one then asked the user for the stock it had just failed to read. An
    empty answer to a plant that does not exist reads as "no stock there".
    Blank passes through: a tool that takes an optional plant reads it as all.
    """
    v = raw.strip()
    plants = known_plants()
    if not v or not plants or v.upper() in plants:
        return plants.get(v.upper(), v)
    named = {plants[k] for k in plants
             if re.search(rf"(?<![A-Z0-9]){re.escape(k)}(?![A-Z0-9])", v.upper())}
    if len(named) == 1:
        return named.pop()
    raise ValueError(
        f"no plant '{raw}' on record"
        + (f"; it names several ({', '.join(sorted(named))}), ask about one" if named else "")
        + f". Plants on record: {', '.join(sorted(plants.values()))}")


#: Every entity the audit reads, with the SAP service it would come from live.
ENTITIES = {
    "MaterialStock": ("API_MATERIAL_STOCK_SRV", "A_MatlStkInAcctMod"),
    "PurchaseOrder": ("API_PURCHASEORDER_PROCESS_SRV", "A_PurchaseOrderItem"),
    "SalesOrder": ("API_SALES_ORDER_SRV", "A_SalesOrderItem"),
    # API_PURCHASING_INFO_RECORD_SRV answers 403 on the sandbox; this is its successor.
    "AlternateSource": ("API_INFORECORD_PROCESS_SRV", "A_PurchasingInfoRecord"),
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
    for entity in ENTITIES:
        try:
            # The audit looks at the whole book, delivered lines included.
            r = read(entity, open_only=False)
        except KeyError:
            continue
        data[entity] = r.value or []
        origins[entity] = {"origin": r.origin.value, "source": r.source, "note": r.note}

    r = bom()
    data["BillOfMaterial"] = r.value or []
    origins["BillOfMaterial"] = {"origin": r.origin.value, "source": r.source, "note": r.note}
    return data, origins


def demo() -> None:
    """What this module promises is not the rows: it is the label on them.

    So the check is about the label. Every case below is one way a figure could
    come out looking better sourced than it is.
    """
    import contextlib

    @contextlib.contextmanager
    def sap(available: bool, upload: Optional[dict] = None):
        """Run a block as if SAP were (not) connected, with one upload on file."""
        was_available, was_upload = sap_s4.available, globals()["_upload"]
        sap_s4.available = lambda: available                     # type: ignore[assignment]
        globals()["_upload"] = lambda entity: upload
        _KNOWN["until"] = 0.0
        try:
            yield
        finally:
            sap_s4.available = was_available                     # type: ignore[assignment]
            globals()["_upload"] = was_upload
            _KNOWN["until"] = 0.0

    # The ordering is the whole mechanism, and it is borrowed, not restated.
    assert _ORDER == [Origin.MISSING, Origin.MODELLED, Origin.CACHED,
                      Origin.DERIVED, Origin.LIVE]
    assert min(Origin.LIVE, Origin.CACHED, key=_ORDER.index) is Origin.CACHED
    assert min(Origin.CACHED, Origin.MODELLED, key=_ORDER.index) is Origin.MODELLED

    # No SAP: the fixture says so, in the note, and is not trusted for money.
    with sap(False):
        r = read("MaterialStock")
        assert r.value and r.origin is Origin.MODELLED and not r.trusted
        assert "SAP_API_KEY is not set" in r.note, r.note
        assert r.source == "fixture:MaterialStock"
        one = read("MaterialStock", material=r.value[0]["Material"])
        assert one.value and all(x["Material"] == r.value[0]["Material"] for x in one.value)
        assert read("MaterialStock", material="M-NOPE").value == []

    # An upload is real company data, so CACHED outranks a fixture...
    real = {"filename": "stock-oct.xlsx", "uploaded_at": "2026-10-20T04:00:00+00:00",
            "payload": [{"Material": "M-4471", "Plant": "P-01", "DailyConsumption": 12.0}]}
    with sap(False, real):
        r = read("MaterialStock")
        assert r.origin is Origin.CACHED and r.trusted, r.brief()
        assert r.source == "upload:stock-oct.xlsx" and "2026-10-20" in r.note

    # ...but a file its own uploader declared as generated stays MODELLED.
    # Calling that cached would launder invented numbers into trusted ones.
    with sap(False, {**real, "synthetic": True}):
        r = read("MaterialStock")
        assert r.origin is Origin.MODELLED and not r.trusted, r.brief()
        assert "declared as generated sample data" in r.note, r.note

    # Supplementing LIVE rows from an upload lowers the label to the upload's,
    # and says which field filled how many rows. A live row wearing a figure
    # that came from a spreadsheet is the exact lie this prevents.
    live = Result([{"Material": "M-4471", "Plant": "P-01", "DailyConsumption": None},
                   {"Material": "M-9999", "Plant": "P-01", "DailyConsumption": None}],
                  Origin.LIVE, "API_MATERIAL_STOCK_SRV")
    with sap(True, real):
        out = _supplement("MaterialStock", live)
    assert out.origin is Origin.CACHED, out.brief()
    assert out.value[0]["DailyConsumption"] == 12.0
    assert out.value[1]["DailyConsumption"] is None, "only the row that matched"
    assert "DailyConsumption for 1 of 2 rows" in out.note, out.note
    assert "upload:stock-oct.xlsx" in out.source and "API_MATERIAL_STOCK_SRV" in out.source

    # Nothing filled, nothing lowered: an upload that matched no row leaves a
    # live read live.
    untouched = Result([{"Material": "M-0000", "Plant": "P-9", "DailyConsumption": None}],
                       Origin.LIVE, "API_MATERIAL_STOCK_SRV")
    with sap(True, real):
        assert _supplement("MaterialStock", untouched).origin is Origin.LIVE

    # An entity SAP does not hold: with SAP connected the fixture is NOT
    # offered in its place, because it describes an invented company.
    with sap(True, None):
        r = read_extra("CustomsDeclaration")
        assert r.origin is Origin.MISSING and r.value is None, r.brief()
        assert "does not hold it" in r.note, r.note
    with sap(False, None):
        assert read_extra("CustomsDeclaration").origin is Origin.MODELLED
        assert read_extra("NotAnEntity").origin is Origin.MISSING, "an unknown entity is a gap"

    # Ids. An argument that matched nothing used to come back as an empty list,
    # which reads exactly like "no alternate source exists" - a wrong answer
    # stated with confidence. Now it is refused out loud.
    with sap(False):
        mats, plants = known_materials(), known_plants()
        assert mats and plants, "the fixture must name some"
        pick = sorted(mats.values())[0]
        assert material_id(pick) == pick and material_id(pick.lower()) == pick
        assert material_id(f"KRW1 {pick} Steel bar SCM440") == pick, "an id inside prose"
        for bad in ("M-NOPE", "1000", "PlantA"):
            try:
                material_id(bad)
                raise AssertionError(f"material '{bad}' must be refused, not answered emptily")
            except ValueError as e:
                assert "no material" in str(e) and "for example" in str(e), e
        plant = sorted(plants.values())[0]
        assert plant_id(plant) == plant and plant_id("") == "", "blank means every plant"
        try:
            plant_id("HUART")
            raise AssertionError("an unknown plant must be refused")
        except ValueError as e:
            assert plant.lower() in str(e).lower(), "and the error names the real ones"

    # The audit's view: every entity, each with where it came from. An audit
    # that does not say which inputs were modelled is an audit of nothing.
    with sap(False):
        data, origins = current_dataset()
    assert set(origins) == set(ENTITIES) | {"BillOfMaterial"}, sorted(origins)
    assert all(o["origin"] and o["source"] for o in origins.values())
    assert all(set(o) == {"origin", "source", "note"} for o in origins.values())
    assert origins["MaterialStock"]["origin"] == "modelled"
    assert data["BillOfMaterial"], "the product structure is read by Impact and Audit"

    print("  ordering borrowed from provenance, not restated ✓ · fixture says so ✓")
    print("  upload outranks a fixture ✓ · a declared sample is never laundered to cached ✓")
    print("  a live row filled from a spreadsheet drops to the spreadsheet's label ✓")
    print("  no fixture stands in for a live company ✓ · unknown ids refused out loud ✓")
    print("fetcher ok")


if __name__ == "__main__":
    # The upload path is stubbed, but _known() and current_dataset() read the
    # fixtures through the same calls the tools use, so keep it off a real DB.
    from core.config import fixtures_only

    fixtures_only(__file__, "SIGAP_FETCHER_CHECK")
    demo()
