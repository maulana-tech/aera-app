"""Clint's tools (Sourcing).

Finds and qualifies replacement supply: other suppliers, internal stock,
expedited shipping, and other materials the product may be made from.
"""
from __future__ import annotations

from typing import List, Optional

from core.provenance import Origin, Result, weakest
from core.registry import register
from tools.fetcher import as_of, read, read_extra


@register("find_alternate_sources", "sourcing",
          "Replacement supply options: another supplier, internal stock, or expedited freight.",
          {"material": {"type": "string"}}, ["material"])
def find_alternate_sources(material: str) -> Result:
    return read("AlternateSource", material=material)


@register("find_internal_transfers", "sourcing",
          "Plants that could send a material to one that is short, with what each "
          "transfer would cost the plant sending it. Returns the ones that break the "
          "donor as well as the ones that do not, because an option removed silently "
          "cannot be argued with.",
          {"material": {"type": "string"}, "to_plant": {"type": "string"},
           "need_qty": {"type": "number"},
           "floor_days": {"type": "integer", "description": "donor safety floor, default 14"}},
          ["material", "to_plant", "need_qty"])
def find_internal_transfers(material: str, to_plant: str, need_qty: float,
                            floor_days: int = 14) -> Result:
    from engine.matching import find

    stock = read("MaterialStock", material=material)
    if not stock.value:
        return Result(None, Origin.MISSING, stock.source, note="no stock to transfer from")
    # A plant whose consumption could not be read would count as using nothing,
    # so all of its stock would look spare. It is left out, and named.
    unknown = sorted(r["Plant"] for r in stock.value
                     if r.get("Material") == material and r.get("DailyConsumption") is None)
    rows = [r for r in stock.value if r.get("DailyConsumption") is not None]
    found = find(rows, material, to_plant, need_qty, as_of(), floor_days)
    note = (f"{sum(1 for t in found if t.verdict == 'available')} of "
            f"{len(found)} donor plants can afford it")
    if unknown:
        note += f"; consumption unknown at {', '.join(unknown)}, so not offered as donors"
    return Result([t.as_dict() for t in found], stock.origin, stock.source, note=note)


def _yes(v) -> Optional[bool]:
    """An approval flag as an upload writes it: true/false, yes/no, 1/0."""
    if isinstance(v, bool) or v is None:
        return v
    t = str(v).strip().lower()
    return True if t in ("true", "yes", "y", "1") else False if t in ("false", "no", "n", "0") else None


@register("find_substitute_materials", "sourcing",
          "Other materials a finished good may be made from instead of this one, whether "
          "each is approved for that product, and how much of the substitute is in stock "
          "where. Reads any uploaded "
          "MaterialSubstitute list (engineering's approvals). A substitute not approved for "
          "the product comes back with what approving it would take: it cannot be used "
          "before then, however much of it is on the shelf.",
          {"material": {"type": "string"},
           "finished_good": {"type": ["string", "null"],
                             "description": "only substitutes for this product"}},
          ["material"])
def find_substitute_materials(material: str, finished_good: Optional[str] = None) -> Result:
    parts: List[Result] = []
    rows: List[dict] = []
    listed = read_extra("MaterialSubstitute", lambda x: x.get("Material") == material)
    parts.append(listed)
    rows += [dict(r, _from=listed.source) for r in listed.value or []]
    if finished_good:
        rows = [r for r in rows if r.get("FinishedGood") in (None, "", finished_good)]

    read_ok = [p for p in parts if p.value is not None]
    if not rows:
        searched = "; ".join(f"{p.source}: {p.note or 'none'}" for p in parts)
        # Nothing found where a source could not be read is a hole, not an
        # answer, so the weakest source decides, a missing one included.
        return Result([], weakest(*(p.origin for p in parts)), " + ".join(p.source for p in parts),
                      note=f"no substitute for {material}"
                           + (f" in {finished_good}" if finished_good else "")
                           + f" on record ({searched})")

    out, origins = [], [p.origin for p in read_ok]
    for r in rows:
        sub = str(r["Substitute"])
        stock = read("MaterialStock", material=sub)
        origins.append(stock.origin)
        approved = _yes(r.get("Approved"))
        days = r.get("QualificationDays")
        why = ("approved for " + (r.get("FinishedGood") or "the product") if approved else
               "not approved for " + (r.get("FinishedGood") or "the product")
               + (f": {r['Basis']}" if r.get("Basis") else "")
               + (f"; qualification takes about {days} days" if days not in (None, "") else ""))
        out.append({
            "material": material, "substitute": sub,
            "finished_good": r.get("FinishedGood") or None,
            "ratio": r.get("Ratio"), "approved": bool(approved), "usable": bool(approved),
            "why": why, "basis": r.get("Basis"), "source": r["_from"],
            "stock": [{"plant": x.get("Plant"), "on_hand": x.get("MatlWrhsStkQtyInMatlBaseUnit"),
                       "unit": x.get("BaseUnit"), "own_daily_use": x.get("DailyConsumption"),
                       "description": x.get("Description")}
                      for x in stock.value or []],
        })
    note = ("stock is the substitute's own on-hand, which its own products also draw on; "
            "a ratio scales the quantity, 1.2 means 1.2 of the substitute per 1 of the material")
    if len(read_ok) < len(parts):
        note += "; " + "; ".join(f"{p.source} could not be read: {p.note}"
                                 for p in parts if p.value is None)
    return Result(out, weakest(*origins), " + ".join(p.source for p in parts), note=note)


def demo() -> None:
    r = find_substitute_materials("M-4471")
    assert r.origin is Origin.MODELLED and len(r.value) == 1, (r.origin, r.value)
    a356 = r.value[0]
    assert a356["substitute"] == "M-4472" and a356["usable"] is False, a356
    assert "not approved" in a356["why"] and "21 days" in a356["why"], a356["why"]
    assert sum(x["on_hand"] for x in a356["stock"]) > 500, "the shelf is full, the approval is not"

    ok = find_substitute_materials("M-5518", "FG-1145").value[0]
    assert ok["usable"] is True and ok["substitute"] == "M-5512", ok
    assert find_substitute_materials("M-5518", "FG-2040").value == []

    none = find_substitute_materials("M-7710")
    assert none.value == [] and "no substitute" in none.note
    assert _yes("Yes") is True and _yes("0") is False and _yes("maybe") is None
    print("sourcing ok, a substitute in stock but not approved is not usable ✓ · "
          "approved substitute found ✓ · filtered by product ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_SOURCING_CHECK")
    demo()
