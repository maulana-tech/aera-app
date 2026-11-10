"""Data fetcher: an upload, then the fixtures.

The point: falling back is NOT hidden. The origin becomes CACHED for an upload
and MODELLED for a fixture, and that shows up both in the UI and in the
calculator's own trust check.

Every tool reads through `read()`.
"""
from __future__ import annotations

import json
import pathlib
import re
import threading
import time
from datetime import date
from typing import Any, Callable, Dict, Iterable, List, Optional

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
    """The date the figures are read as of: the fixture's own date (the
    scenario is written around that day)."""
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
        note=f"no {entity} has been uploaded. Using modelled data",
    )


def _upload(entity: str) -> Optional[dict]:
    try:
        from core import store
        return store.latest_upload(entity)
    except Exception:                                            # noqa: BLE001
        return None


#: Weakest first, borrowed rather than restated.
_ORDER = list(STRENGTH)


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
    open_only        kept for callers; an upload or the fixture returns
                     every line
    """
    mats = set(materials) if materials is not None else None
    nums = {str(n) for n in numbers} if numbers is not None else None
    wanted = {str(i) for i in ids} if ids is not None else None

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
    """An entity outside the core book: an upload of it, else the fixture.

    Customs declarations live in the customs authority's system (CEISA in
    Indonesia), engineering-approved substitutes in a change record or a
    spreadsheet. An unknown entity is MISSING, which names the gap rather than
    filling it.
    """
    try:
        return _offline(entity, keep)
    except KeyError:
        return Result(None, Origin.MISSING, f"fixture:{entity}",
                      note=f"no {entity} is on record")


_KNOWN_LOCK = threading.Lock()
_KNOWN: Dict[str, Any] = {"until": 0.0, "ids": {}, "plants": {}}


def _known() -> Dict[str, Dict[str, str]]:
    """Every material, finished good and plant id on record, upper-cased → as
    written. Cached for five minutes."""
    with _KNOWN_LOCK:
        if time.monotonic() < _KNOWN["until"]:
            return _KNOWN
        ids: Dict[str, str] = {}
        plants: Dict[str, str] = {}
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


#: Every entity the audit reads.
ENTITIES = ("MaterialStock", "PurchaseOrder", "SalesOrder", "AlternateSource",
            "Supplier", "Quotation")


def bom() -> Result:
    """The canonical product structure read by Impact, Audit, and views."""
    try:
        return Result(fixture("BillOfMaterial"), Origin.MODELLED, "fixture:BillOfMaterial",
                      note="no BillOfMaterial has been uploaded. Using modelled data")
    except KeyError:
        return Result([], Origin.MISSING, "fixture:BillOfMaterial",
                      note="BillOfMaterial is not available")


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
    def uploaded(upload: Optional[dict] = None):
        """Run a block with one upload on file."""
        was_upload = globals()["_upload"]
        globals()["_upload"] = lambda entity: upload
        _KNOWN["until"] = 0.0
        try:
            yield
        finally:
            globals()["_upload"] = was_upload
            _KNOWN["until"] = 0.0

    # The ordering is the whole mechanism, and it is borrowed, not restated.
    assert _ORDER == [Origin.MISSING, Origin.MODELLED, Origin.CACHED,
                      Origin.DERIVED, Origin.LIVE]
    assert min(Origin.LIVE, Origin.CACHED, key=_ORDER.index) is Origin.CACHED
    assert min(Origin.CACHED, Origin.MODELLED, key=_ORDER.index) is Origin.MODELLED

    # No upload: the fixture says so, in the note, and is not trusted for money.
    with uploaded():
        r = read("MaterialStock")
        assert r.value and r.origin is Origin.MODELLED and not r.trusted
        assert "Using modelled data" in r.note, r.note
        assert r.source == "fixture:MaterialStock"
        one = read("MaterialStock", material=r.value[0]["Material"])
        assert one.value and all(x["Material"] == r.value[0]["Material"] for x in one.value)
        assert read("MaterialStock", material="M-NOPE").value == []

    # An upload is real company data, so CACHED outranks a fixture...
    real = {"filename": "stock-oct.xlsx", "uploaded_at": "2026-10-20T04:00:00+00:00",
            "payload": [{"Material": "M-4471", "Plant": "P-01", "DailyConsumption": 12.0}]}
    with uploaded(real):
        r = read("MaterialStock")
        assert r.origin is Origin.CACHED and r.trusted, r.brief()
        assert r.source == "upload:stock-oct.xlsx" and "2026-10-20" in r.note

    # ...but a file its own uploader declared as generated stays MODELLED.
    # Calling that cached would launder invented numbers into trusted ones.
    with uploaded({**real, "synthetic": True}):
        r = read("MaterialStock")
        assert r.origin is Origin.MODELLED and not r.trusted, r.brief()
        assert "declared as generated sample data" in r.note, r.note

    with uploaded():
        assert read_extra("CustomsDeclaration").origin is Origin.MODELLED
        assert read_extra("NotAnEntity").origin is Origin.MISSING, "an unknown entity is a gap"

    # Ids. An argument that matched nothing used to come back as an empty list,
    # which reads exactly like "no alternate source exists" - a wrong answer
    # stated with confidence. Now it is refused out loud.
    with uploaded():
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
    with uploaded():
        data, origins = current_dataset()
    assert set(origins) == set(ENTITIES) | {"BillOfMaterial"}, sorted(origins)
    assert all(o["origin"] and o["source"] for o in origins.values())
    assert all(set(o) == {"origin", "source", "note"} for o in origins.values())
    assert origins["MaterialStock"]["origin"] == "modelled"
    assert data["BillOfMaterial"], "the product structure is read by Impact and Audit"

    print("  ordering borrowed from provenance, not restated ✓ · fixture says so ✓")
    print("  upload outranks a fixture ✓ · a declared sample is never laundered to cached ✓")
    print("  unknown ids refused out loud ✓")
    print("fetcher ok")


if __name__ == "__main__":
    # The upload path is stubbed, but _known() and current_dataset() read the
    # fixtures through the same calls the tools use, so keep it off a real DB.
    from core.config import fixtures_only

    fixtures_only(__file__, "AERA_FETCHER_CHECK")
    demo()
