"""Audit a supply-chain dataset the way an advisor would read it.

No model. The same arithmetic and set logic an auditor applies by hand, which
means every finding here can be traced to named rows and recomputed by anyone
holding the same file. A finding without evidence is an opinion, so each one
carries the identifiers it rests on.

Five things it looks for:

  integrity      references that point nowhere, dates that cannot happen,
                 quantities that mean nothing, one supplier under two codes
  continuity     cover below the floor, orders already overdue, materials
                 with a single source and real money behind them
  concentration  many materials through one port or one supplier
  compliance     options in the file that would breach the TKDN floor
  capital        stock held against something nobody consumes

Severity is about consequence, not about how unusual the finding is. A missing
bill of materials line on a product nobody sells is a note. Cover below the
floor on a product worth two billion rupiah is critical.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

SEVERITIES = ["critical", "serious", "warning", "note"]


@dataclass
class Finding:
    severity: str
    category: str
    title: str
    detail: str
    evidence: List[str] = field(default_factory=list)
    #: Revenue that *depends on* what this finding is about, not revenue that
    #: would be lost. A component appearing in most products carries most of
    #: the book, and saying so as though it were an expected loss is the kind
    #: of figure that falls apart under the first question.
    value_idr: Optional[int] = None
    action: str = ""

    def as_dict(self) -> dict:
        return {"severity": self.severity, "category": self.category,
                "title": self.title, "detail": self.detail,
                "evidence": self.evidence, "value_idr": self.value_idr,
                "action": self.action}


@dataclass
class Audit:
    findings: List[Finding]
    counts: Dict[str, int]
    coverage: Dict[str, object]

    def as_dict(self) -> dict:
        return {"findings": [f.as_dict() for f in self.findings],
                "counts": self.counts, "coverage": self.coverage}


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def run(data: Dict[str, list], profile: dict, as_of: Optional[date] = None,
        cover_floor_days: int = 14) -> Audit:
    stock = data.get("MaterialStock", [])
    orders = data.get("PurchaseOrder", [])
    bom = data.get("BillOfMaterial", [])
    sales = data.get("SalesOrder", [])
    alternates = data.get("AlternateSource", [])
    suppliers = data.get("Supplier", [])
    today = as_of or date.fromisoformat(profile["AsOfDate"])
    tkdn_floor = profile.get("TkdnContractFloorPct", 40.0)

    findings: List[Finding] = []

    stocked = {r["Material"] for r in stock}
    finished_for: Dict[str, set] = defaultdict(set)
    for b in bom:
        finished_for[b["Material"]].add(b["FinishedGood"])
    sold_goods = {s["Material"] for s in sales}
    bom_goods = {b["FinishedGood"] for b in bom}

    def committed(materials) -> Optional[int]:
        goods: set = set()
        for m in materials:
            goods |= finished_for.get(m, set())
        matched = [int(_num(s["NetAmount"])) for s in sales if s["Material"] in goods]
        return sum(matched) if matched else None

    # ---------------------------------------------------------- integrity --
    orphan_components = sorted({b["Material"] for b in bom} - stocked)
    if orphan_components:
        findings.append(Finding(
            "serious", "integrity",
            "Bill of materials names a component that is not stocked anywhere",
            f"{len(orphan_components)} component(s) appear in a product structure but have "
            "no stock record at any plant. Planning cannot see them, so a shortage will "
            "surface as a line stoppage rather than as a warning.",
            orphan_components,
            committed(orphan_components),
            "Create the stock record, or remove the line if the component is obsolete.",
        ))

    orphan_sold = sorted(sold_goods - bom_goods)
    if orphan_sold:
        findings.append(Finding(
            "warning", "integrity",
            "Customer order for a product with no bill of materials",
            f"{len(orphan_sold)} finished good(s) are being sold with no component "
            "structure behind them. Nothing can trace a disruption from a raw material "
            "to these orders.",
            orphan_sold,
            sum(int(_num(s["NetAmount"])) for s in sales if s["Material"] in orphan_sold),
            "Build the structure, or confirm the product is bought in finished.",
        ))

    impossible = [o["PurchaseOrder"] for o in orders
                  if o.get("RevisedDeliveryDate") and o.get("DeliveryDate")
                  and o["RevisedDeliveryDate"] < o["DeliveryDate"]]
    if impossible:
        findings.append(Finding(
            "warning", "integrity",
            "Revised delivery date falls before the date originally promised",
            f"{len(impossible)} order(s) were revised earlier than the commitment. Either "
            "the supplier genuinely pulled the date in, or the revision overwrote the "
            "original. Every lead-time figure computed from this field inherits the error.",
            impossible, None,
            "Confirm with the supplier, and keep the original commitment in its own field.",
        ))

    overdue = [o["PurchaseOrder"] for o in orders
               if o.get("Status") == "not_shipped"
               and o.get("RevisedDeliveryDate", "9999") < today.isoformat()]
    if overdue:
        findings.append(Finding(
            "serious", "integrity",
            "Order past its delivery date and still not shipped",
            f"{len(overdue)} order(s) are overdue with no shipment recorded. Either the "
            "goods moved and nobody updated the record, or they did not move and nobody "
            "noticed.",
            overdue, None,
            "Chase the supplier and reconcile the status before planning trusts it.",
        ))

    empty = [o["PurchaseOrder"] for o in orders if _num(o.get("OrderQuantity")) <= 0]
    if empty:
        findings.append(Finding(
            "note", "integrity", "Purchase order for a quantity of zero",
            f"{len(empty)} order line(s) commit to nothing. Harmless individually, and a "
            "sign that order entry accepts input it should reject.",
            empty, None, "Void the line and add a minimum-quantity check at entry.",
        ))

    by_name: Dict[str, List[str]] = defaultdict(list)
    for s in suppliers:
        key = "".join(ch for ch in s["SupplierName"].lower() if ch.isalnum())
        key = key.replace("tbk", "").replace("pt", "")
        by_name[key].append(s["Supplier"])
    dupes = {k: v for k, v in by_name.items() if len(v) > 1}
    if dupes:
        flat = sorted(c for codes in dupes.values() for c in codes)
        findings.append(Finding(
            "serious", "integrity", "One supplier carries more than one code",
            f"{len(dupes)} supplier(s) appear under multiple codes. Spend is split across "
            "them, so the firm looks smaller than it is, concentration is understated, and "
            "a single certificate lapse hits more materials than the records suggest.",
            flat, None,
            "Merge the duplicates and repoint open orders at the surviving code.",
        ))

    # --------------------------------------------------------- continuity --
    sourced: Dict[str, set] = defaultdict(set)
    for o in orders:
        sourced[o["Material"]].add(o["Supplier"])
    for a in alternates:
        sourced[a["Material"]].add(a["Supplier"])

    single = sorted(m for m, s in sourced.items() if len(s) == 1)
    priced_single = [m for m in single if committed([m])]
    if priced_single:
        findings.append(Finding(
            "critical", "continuity", "Material with one source and committed revenue behind it",
            f"{len(priced_single)} material(s) have exactly one supplier on record and no "
            "alternate. Each is a single point of failure that stays invisible until the "
            "supplier misses. The figure beside this is the revenue that touches those "
            "materials, not an expected loss: one missed delivery does not stop every "
            "product that happens to contain the part.",
            priced_single, committed(priced_single),
            "Qualify a second source, starting with the highest committed value.",
        ))
    unpriced_single = [m for m in single if not committed([m])]
    if unpriced_single:
        findings.append(Finding(
            "warning", "continuity", "Material with one source and no traceable revenue",
            f"{len(unpriced_single)} single-sourced material(s) could not be priced, because "
            "no bill of materials links them to a customer order. Unpriced is not the same "
            "as unimportant; it means the records do not say.",
            unpriced_single, None,
            "Complete the product structure before judging whether these matter.",
        ))

    thin = []
    for r in stock:
        daily = _num(r.get("DailyConsumption"))
        if daily <= 0:
            continue
        cover = _num(r.get("MatlWrhsStkQtyInMatlBaseUnit")) / daily
        if cover < cover_floor_days:
            thin.append((f"{r['Material']} at {r['Plant']}", round(cover, 1), r["Material"]))
    if thin:
        worst = min(thin, key=lambda t: t[1])
        findings.append(Finding(
            "critical", "continuity", "Cover below the safety floor",
            f"{len(thin)} material and plant pair(s) hold less than {cover_floor_days} days "
            f"of cover. The thinnest is {worst[0]} at {worst[1]} days.",
            [t[0] for t in thin], committed({t[2] for t in thin}),
            "Bring supply forward or pre-position stock from another plant.",
        ))

    # ------------------------------------------------------ concentration --
    lanes: Dict[str, set] = defaultdict(set)
    for o in orders:
        if o.get("LoadingPort"):
            lanes[o["LoadingPort"]].add(o["Material"])
    busiest = max(lanes.items(), key=lambda kv: len(kv[1]), default=None)
    if busiest and len(busiest[1]) > 1:
        port, mats = busiest
        share = len(mats) / max(len({o["Material"] for o in orders}), 1)
        findings.append(Finding(
            "serious" if share > 0.3 else "warning", "concentration",
            "Inbound lane concentrated on one port",
            f"{len(mats)} of {len({o['Material'] for o in orders})} purchased materials "
            f"route through {port}, which is {share:.0%} of the inbound book. One closure "
            "takes out all of them on the same day.",
            sorted(mats)[:12], committed(mats),
            "Split the lane, or hold buffer on the far side of the chokepoint.",
        ))

    spend = Counter(o["Supplier"] for o in orders)
    if spend:
        top, lines = spend.most_common(1)[0]
        if lines / sum(spend.values()) > 0.15:
            findings.append(Finding(
                "warning", "concentration", "Order book concentrated on one supplier",
                f"{top} carries {lines} of {sum(spend.values())} order lines, "
                f"{lines / sum(spend.values()):.0%} of the book.",
                [top], None,
                "Check whether the concentration is deliberate and covered by contract.",
            ))

    # ---------------------------------------------------------- compliance --
    current = profile.get("TkdnCurrentPct", 0.0)
    breaching = [a for a in alternates
                 if a.get("TkdnAfterPct") is not None
                 and _num(a["TkdnAfterPct"]) < current - 0.05]
    if breaching:
        cheapest = min(breaching, key=lambda a: _num(a["ExtraCostIDR"]))
        findings.append(Finding(
            "serious", "compliance", "Sourcing options in the file would worsen local content",
            f"{len(breaching)} option(s) would drop the local-content ratio below the "
            f"current {current}%, against a contract floor of {tkdn_floor}%. The cheapest "
            f"of them, {cheapest['label']}, is Rp {int(_num(cheapest['ExtraCostIDR'])):,}, "
            "which is exactly the trade a cost-only model would take.",
            [a["id"] for a in breaching], None,
            "Keep the veto ahead of the cost comparison, not after it.",
        ))

    uncertified = [s["Supplier"] for s in suppliers
                   if s.get("Country") == "ID" and not s.get("TkdnCertifiedPct")]
    if uncertified:
        findings.append(Finding(
            "note", "compliance", "Domestic supplier with no TKDN figure on record",
            f"{len(uncertified)} Indonesian supplier(s) carry no certified local-content "
            "percentage, so their contribution cannot be counted toward the ratio.",
            uncertified, None,
            "Collect the certificates; local content you cannot evidence does not count.",
        ))

    # ------------------------------------------------------------ capital --
    dead = [f"{r['Material']} at {r['Plant']}" for r in stock
            if _num(r.get("MatlWrhsStkQtyInMatlBaseUnit")) > 0
            and _num(r.get("DailyConsumption")) == 0]
    if dead:
        findings.append(Finding(
            "warning", "capital", "Stock held against a material nobody consumes",
            f"{len(dead)} position(s) carry stock with a consumption rate of zero. Either "
            "the rate is missing from the record or the stock is dead and tying up capital "
            "and floor space.",
            dead, None,
            "Confirm the rate, then write off or redeploy what is genuinely dead.",
        ))

    total_committed = sum(int(_num(s["NetAmount"])) for s in sales)
    for f in findings:
        # The same guard the exposure scan carries. A figure above the whole
        # order book means something was counted twice.
        if f.value_idr is not None and f.value_idr > total_committed:
            raise AssertionError(
                f"{f.title} priced at {f.value_idr:,}, above the {total_committed:,} "
                "committed across every customer order"
            )

    order = {s: i for i, s in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (order[f.severity], -(f.value_idr or 0)))

    counts = Counter(f.severity for f in findings)
    coverage = {
        "materials": len({r["Material"] for r in stock}),
        "plants": len({r["Plant"] for r in stock}),
        "suppliers": len({o["Supplier"] for o in orders}),
        "purchase_orders": len(orders),
        "customer_orders": len(sales),
        "finished_goods": len(bom_goods | sold_goods),
        "committed_idr": sum(int(_num(s["NetAmount"])) for s in sales),
        "rows": sum(len(v) for v in data.values() if isinstance(v, list)),
    }
    return Audit(findings, {s: counts.get(s, 0) for s in SEVERITIES}, coverage)


def demo() -> None:
    import json
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from fixtures.generate import DEFECTS, build

    data = build()
    profile = json.loads(
        (pathlib.Path(__file__).resolve().parent.parent
         / "fixtures" / "ningbo_scenario.json").read_text())["Profile"]

    a = run(data, profile)
    titles = " ".join(f.title.lower() for f in a.findings)

    # Every planted defect must surface. A clean audit over dirty data is the
    # failure mode that matters here.
    wanted = {
        "revised date lands before": "revised delivery date falls before",
        "overdue purchase order": "past its delivery date",
        "stock held against a material nobody": "nobody consumes",
        "bill of materials line for a material with no stock": "not stocked anywhere",
        "customer order for a finished good with no bill": "no bill of materials",
        "one supplier appearing twice": "more than one code",
        "single-sourced material carrying real customer value": "one source and committed revenue",
        "cover below the safety floor": "cover below the safety floor",
        "alternate source that would breach": "worsen local content",
        "purchase order for a quantity of zero": "quantity of zero",
    }
    assert len(wanted) == len(DEFECTS), (len(wanted), len(DEFECTS))
    for defect, needle in wanted.items():
        assert needle in titles, f"audit missed: {defect}"

    assert a.counts["critical"] >= 2, a.counts

    # No finding may be worth more than the whole order book.
    for f in a.findings:
        if f.value_idr is not None:
            assert f.value_idr <= a.coverage["committed_idr"], (f.title, f.value_idr)

    # The revenue figure has to be described as dependency, never as loss.
    single = next(f for f in a.findings if "one source and committed" in f.title)
    assert "not an expected loss" in single.detail
    assert a.coverage["rows"] > 150, a.coverage
    for f in a.findings:
        assert f.evidence or f.value_idr is not None, f"{f.title} has no evidence"
        assert f.action, f"{f.title} has no recommended action"

    print(f"audit ok, {len(a.findings)} findings over {a.coverage['rows']} rows")
    print(f"  {a.counts['critical']} critical, {a.counts['serious']} serious, "
          f"{a.counts['warning']} warning, {a.counts['note']} note")
    for f in a.findings[:5]:
        money = f" Rp {f.value_idr:,}" if f.value_idr else ""
        print(f"  {f.severity:<8} {f.title[:58]}{money}")


if __name__ == "__main__":
    demo()
