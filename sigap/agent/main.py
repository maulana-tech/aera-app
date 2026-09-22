"""Run one scenario and write out its trace.

    python3 main.py                      # the Ningbo scenario
    python3 main.py --out ../../app/sigap/trace.json

Without Bedrock credentials this runs in GUIDED MODE: the step order follows
the design, and the figures still come from the real calculator. The mode is
stamped on the trace — it does not pretend an agent did the reasoning.
"""
from __future__ import annotations

import argparse
import os
from datetime import date

from agents.definitions import ALL
from core.provenance import Origin, Result
from core.trace import Trace
from engine.simulate import Arrival, Ruling, simulate_scenario
from tools.fetcher import profile
from tools.impact import (get_bom_explosion, get_material_stock,
                          get_open_purchase_orders, get_sales_order_commitments)
from tools.sourcing import find_alternate_sources

A = ALL


def run_ningbo(treat_as_live: bool = False) -> Trace:
    mode = ("autonomous" if os.environ.get("AWS_REGION") and os.environ.get("BEDROCK_READY")
            else "guided")
    t = Trace("Typhoon closes the Port of Ningbo",
              "Maritime advisory: Ningbo–Zhoushan closed 8–13 Sep 2026", mode)
    p = profile()
    start = date.fromisoformat(p["AsOfDate"])

    t.record("DETECT", A["supervisor"],
             "Recognises Ningbo as a lane this company actually uses",
             ["detect_disruption"])

    po = get_open_purchase_orders(port="CNNGB")
    t.record("SCOPE", A["impact"],
             f"{len(po.value or [])} purchase orders routed through Ningbo are affected",
             ["get_open_purchase_orders"], po,
             orders=[r["PurchaseOrder"] for r in (po.value or [])])

    stock = get_material_stock(material="M-4471", plant="KRW1")
    krw = (stock.value or [{}])[0]
    daily = krw.get("DailyConsumption", 9.2)
    opening = krw.get("MatlWrhsStkQtyInMatlBaseUnit", 0.0)
    t.record("IMPACT", A["impact"],
             f"M-4471 at KRW1: {opening} t on hand, {daily} t/day consumption",
             ["get_material_stock", "get_bom_explosion"], stock,
             material="M-4471", stock_tonnes=opening, daily_consumption=daily)

    bom = get_bom_explosion("M-4471")
    fg = [r["FinishedGood"] for r in (bom.value or [])]
    so = get_sales_order_commitments(fg)
    exposed = sum(r["NetAmount"] for r in (so.value or []))
    t.record("QUANTIFY", A["impact"],
             f"{len(so.value or [])} customer orders worth Rp {exposed:,} are at risk",
             ["get_sales_order_commitments"], so, value_idr=exposed, products=fg)

    options = find_alternate_sources("M-4471")
    t.record("GENERATE", A["sourcing"],
             f"{len(options.value or [])} supply options assembled",
             ["find_alternate_sources"], options,
             options=[o["id"] for o in (options.value or [])])

    rulings = {
        "A": Ruling("A", "air freight", True),
        "B": Ruling("B", "local supplier, Gresik", True),
        "C": Ruling("C", "reallocate from SBY1", True),
        "D": Ruling("D", "Vietnam", False,
                    "LARTAS: a new origin country adds 10 working days — arrives after the "
                    "line has already stopped"),
        "E": Ruling("E", "cheapest, China", False,
                    f"TKDN drops to 34.8%; contract floor {p['TkdnContractFloorPct']}%"),
    }
    blocked = [k for k, v in rulings.items() if not v.allowed]
    t.record("FILTER", A["compliance"],
             f"{len(blocked)} options struck out on the rules, not on price",
             ["check_local_constraints"],
             Result(rulings, Origin.MODELLED, "references/ (rule pack)"),
             blocked=blocked, reasons={k: rulings[k].reason for k in blocked})

    if treat_as_live:                     # pretend the SAP key is already in place
        stock = Result(stock.value, Origin.LIVE, "API_MATERIAL_STOCK_SRV")
        options = Result(options.value, Origin.LIVE, "A_PurchasingInfoRecord")

    scheduled = [Arrival("4500018872", date(2026, 9, 22), 120.0)]
    sim = simulate_scenario(stock, options, rulings, p, start, daily, opening, scheduled)

    if sim.refused:
        t.record("SIMULATE", A["simulation"], sim.refusal_reason, ["simulate_scenario"],
                 Result(None, Origin.MISSING, "engine/simulate.py"))
        t.decision = {"status": "held", "reason": sim.refusal_reason}
        return t

    best = sim.chosen
    t.record("SIMULATE", A["simulation"],
             f"Cheapest safe combination: {best['combination']} — Rp {best['cost_idr']:,}",
             ["simulate_scenario"],
             Result(sim.combinations, Origin.DERIVED, "engine/simulate.py"),
             combinations=sim.combinations[:6],
             depleted_without_action=str(sim.depleted_without_action))

    singles = [c for c in sim.combinations if len(c["members"]) == 1 and c["safe"]]
    benchmark = min(singles, key=lambda c: c["cost_idr"]) if singles else None
    saved = (benchmark["cost_idr"] - best["cost_idr"]) if benchmark else 0

    t.record("DECIDE", A["supervisor"],
             f"Recommends {best['combination']} over "
             f"{benchmark['combination'] if benchmark else '—'} — saves Rp {saved:,}",
             [], None,
             residual_risk="SBY1 is left with 4 days of cover until PO 4500018901 "
                           "lands on 24 Sep")

    t.record("ACT", A["execution"],
             "The stock transfer goes ahead on its own; the purchase order stops as a draft",
             ["create_stock_transfer", "create_draft_po", "notify"], None,
             autonomous="create_stock_transfer (< Rp 50 million)",
             needs_approval="create_draft_po")

    t.decision = {
        "status": "awaiting approval",
        "combination": best["combination"],
        "cost_idr": best["cost_idr"],
        "benchmark": benchmark["combination"] if benchmark else None,
        "benchmark_cost_idr": benchmark["cost_idr"] if benchmark else None,
        "saved_idr": saved,
        "saved_pct": round(saved / benchmark["cost_idr"] * 100) if benchmark else 0,
        "tkdn_before": p["TkdnCurrentPct"],
        "tkdn_after": best["tkdn_after"],
        "value_protected_idr": exposed,
        "blocked": blocked,
    }
    return t


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../../app/sigap/trace.json")
    ap.add_argument("--treat-as-live", action="store_true",
                    help="treat fixtures as live data, to exercise the full path")
    args = ap.parse_args()

    t = run_ningbo(args.treat_as_live)
    t.write(args.out)
    print(f"mode     : {t.mode}")
    print(f"steps    : {len(t.steps)}")
    print(f"agents   : {' → '.join(t.agents_used)}")
    print(f"decision : {t.decision.get('status')}")
    if t.decision.get("combination"):
        d = t.decision
        print(f"           {d['combination']} Rp {d['cost_idr']:,} "
              f"(saves Rp {d['saved_idr']:,} / {d['saved_pct']}%)")
    print(f"trace    : {args.out}")
