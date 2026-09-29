"""Build a realistic supply-chain dataset for a Tier-1 automotive supplier.

Deterministic: the same seed gives the same rows every run, so a figure quoted
in a document can be reproduced rather than taken on trust.

Everything here is invented. The company, its plants, its suppliers and its
customers do not exist, and the file says so in its own header. What is real is
the shape: SAP field names, Indonesian port codes, plausible lead times, and
the kind of mess that accumulates in master data nobody has audited.

That mess is deliberate. An audit that finds nothing has not been run against
anything worth auditing, so this plants known defects and engine/audit.py is
expected to find every one of them. The catalogue is in DEFECTS below.

    python3 fixtures/generate.py            # write CSV and the JSON fixture
    python3 fixtures/generate.py --check    # rebuild and confirm it is stable
"""
from __future__ import annotations

import csv
import json
import pathlib
import random
import sys
from datetime import date, timedelta

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "demo"
SEED = 20260929
AS_OF = date(2026, 9, 4)

# Known defects planted on purpose, each one something a real master-data audit
# turns up. engine/audit.py must find all of these.
DEFECTS = [
    "a purchase order whose revised date lands before the date it was promised",
    "an overdue purchase order still marked not_shipped",
    "stock held against a material nobody consumes",
    "a bill of materials line for a material with no stock record",
    "a customer order for a finished good with no bill of materials",
    "one supplier appearing twice under different codes",
    "a single-sourced material carrying real customer value",
    "cover below the safety floor",
    "an alternate source that would breach the TKDN contract floor",
    "a purchase order for a quantity of zero",
]

PORTS = {
    "CN": "CNNGB", "JP": "JPYOK", "KR": "KRPUS", "VN": "VNSGN",
    "TH": "THLCH", "MY": "MYPKG", "ID": "IDTPP",
}

# Invented suppliers. Indonesian ones carry a PT prefix as they would locally.
SUPPLIERS = [
    ("SUP-2201", "Ningbo Yongtai Metals", "CN", 38.2),
    ("SUP-2207", "Hangzhou Sealtech", "CN", 0.0),
    ("SUP-2209", "Qingdao Baowu Steel", "CN", 0.0),
    ("SUP-2244", "Suzhou Precision Casting", "CN", 0.0),
    ("SUP-3390", "Hai Phong Alloy", "VN", 36.1),
    ("SUP-3402", "Dong Nai Rubberworks", "VN", 0.0),
    ("SUP-4417", "PT Logam Andalan", "ID", 41.6),
    ("SUP-4418", "PT Cipta Baja Nusantara", "ID", 44.0),
    ("SUP-4423", "PT Karet Prima Sejahtera", "ID", 47.5),
    ("SUP-4431", "PT Sinar Tempa Presisi", "ID", 43.2),
    ("SUP-4455", "PT Anugerah Kawat Tembaga", "ID", 45.8),
    ("SUP-5501", "Guangzhou Lowcost Alloy", "CN", 34.8),
    ("SUP-6610", "Yokohama Fineblank", "JP", 0.0),
    ("SUP-6622", "Nagoya Heat Treat", "JP", 0.0),
    ("SUP-7701", "Busan Forging", "KR", 0.0),
    ("SUP-8801", "Rayong Polymer", "TH", 0.0),
    ("SUP-8815", "Port Klang Fasteners", "MY", 0.0),
    # The duplicate. Same firm, second code, slightly different spelling.
    ("SUP-4417B", "PT Logam Andalan Tbk", "ID", 41.6),
]

PLANTS = ["KRW1", "SBY1", "CKR1"]

FINISHED = [
    ("FG-1120", "Brake caliper assembly", 4),
    ("FG-1145", "Brake disc, ventilated", 3),
    ("FG-2040", "Transmission housing", 5),
    ("FG-2075", "Clutch bell housing", 3),
    ("FG-3310", "Steering knuckle", 4),
    ("FG-3355", "Control arm, lower", 3),
    ("FG-4420", "Water pump housing", 3),
    ("FG-4480", "Oil pump body", 2),
]

# (code, description, unit, family)
MATERIALS = [
    ("M-4471", "Aluminium alloy ingot ADC12", "TON", "alloy"),
    ("M-4472", "Aluminium alloy ingot A356", "TON", "alloy"),
    ("M-4478", "Aluminium billet 6061", "TON", "alloy"),
    ("M-5512", "Steel bar SCM440", "TON", "steel"),
    ("M-5518", "Steel bar S45C", "TON", "steel"),
    ("M-5524", "Bearing steel SUJ2", "TON", "steel"),
    ("M-5530", "Cast iron FC250 pig", "TON", "iron"),
    ("M-3308", "Brake seal kit NBR", "PC", "rubber"),
    ("M-3312", "O-ring set EPDM", "PC", "rubber"),
    ("M-3320", "Rubber compound NR60", "KG", "rubber"),
    ("M-6640", "Copper wire 2.0mm", "KG", "copper"),
    ("M-6648", "Brass fitting M10", "PC", "copper"),
    ("M-7710", "Hex bolt M12 class 10.9", "PC", "fastener"),
    ("M-7716", "Flange nut M12", "PC", "fastener"),
    ("M-7722", "Spring washer M12", "PC", "fastener"),
    ("M-8830", "Epoxy primer, grey", "LTR", "coating"),
    ("M-8836", "Topcoat, black semi-gloss", "LTR", "coating"),
    ("M-8842", "Anti-corrosion wax", "LTR", "coating"),
    ("M-9910", "Machining coolant", "LTR", "consumable"),
    ("M-9916", "Grinding wheel 350mm", "PC", "consumable"),
    ("M-9922", "Carbide insert CNMG", "PC", "consumable"),
    ("M-2210", "Graphite electrode", "PC", "consumable"),
    ("M-2216", "Foundry sand, resin coated", "TON", "foundry"),
    ("M-2222", "Ceramic filter 50ppi", "PC", "foundry"),
    ("M-2228", "Ladle refractory mix", "KG", "foundry"),
    ("M-1105", "Gasket sheet, compressed", "SQM", "rubber"),
    ("M-1112", "Hydraulic hose 3/8", "MTR", "rubber"),
    ("M-1118", "Dust boot, TPE", "PC", "rubber"),
    ("M-1124", "Piston seal, PTFE", "PC", "rubber"),
    ("M-1130", "Bleeder screw M8", "PC", "fastener"),
    ("M-1136", "Retaining clip, spring steel", "PC", "fastener"),
    ("M-1142", "Shim plate 0.5mm", "PC", "steel"),
    ("M-1148", "Guide pin, chrome", "PC", "steel"),
    ("M-1154", "Bushing, sintered bronze", "PC", "copper"),
    ("M-1160", "Needle bearing HK1210", "PC", "steel"),
    ("M-1166", "Oil seal 35x52x8", "PC", "rubber"),
    ("M-1172", "Snap ring 52mm", "PC", "steel"),
    ("M-1178", "Dowel pin 8x16", "PC", "steel"),
    ("M-1184", "Thread insert M8", "PC", "fastener"),
    ("M-1190", "Vent plug, brass", "PC", "copper"),
    ("M-1196", "Label, laser etched", "PC", "consumable"),
    ("M-1202", "Packaging crate, returnable", "PC", "consumable"),
    # The orphan: named in a bill of materials, never stocked anywhere.
    ("M-1208", "Impeller blank, investment cast", "PC", "foundry"),
]

CUSTOMERS = [
    ("CUS-1001", "Anantara Motor Manufacturing"),
    ("CUS-1002", "Nusa Otomotif Industri"),
    ("CUS-1003", "Pratama Kendaraan Niaga"),
    ("CUS-1004", "Wijaya Auto Components"),
]


def build() -> dict:
    rnd = random.Random(SEED)
    by_family = {}
    for code, desc, unit, fam in MATERIALS:
        by_family.setdefault(fam, []).append(code)

    # ---- bill of materials ------------------------------------------------
    bom = []
    for fg, fg_desc, n_components in FINISHED:
        pool = [m for m, _, _, _ in MATERIALS if m != "M-1208"]
        for comp in rnd.sample(pool, n_components):
            bom.append({"Material": comp, "FinishedGood": fg, "Description": fg_desc,
                        "ComponentQuantity": rnd.choice([1, 1, 2, 2, 4, 6, 8])})
    # planted defect: a component that has no stock record anywhere
    bom.append({"Material": "M-1208", "FinishedGood": "FG-4420",
                "Description": "Water pump housing", "ComponentQuantity": 1})

    consumed = {b["Material"] for b in bom}

    # ---- stock ------------------------------------------------------------
    stock = []
    for code, desc, unit, fam in MATERIALS:
        if code == "M-1208":
            continue                      # the orphan is deliberately unstocked
        for plant in rnd.sample(PLANTS, rnd.choice([1, 1, 2])):
            daily = {"TON": (2.0, 12.0), "PC": (40.0, 900.0), "KG": (8.0, 260.0),
                     "LTR": (5.0, 90.0), "MTR": (10.0, 120.0),
                     "SQM": (2.0, 20.0)}[unit]
            rate = round(rnd.uniform(*daily), 1)
            cover = rnd.choice([6, 9, 11, 18, 24, 30, 45, 60, 90])
            stock.append({
                "Material": code, "Plant": plant,
                "MatlWrhsStkQtyInMatlBaseUnit": round(rate * cover, 1),
                "BaseUnit": unit, "DailyConsumption": rate, "Description": desc,
            })
    # planted defect: stock nobody consumes
    stock.append({"Material": "M-1202", "Plant": "CKR1",
                  "MatlWrhsStkQtyInMatlBaseUnit": 4800.0, "BaseUnit": "PC",
                  "DailyConsumption": 0.0, "Description": "Packaging crate, returnable"})
    # planted defect: the scenario material, below any sane floor
    for row in stock:
        if row["Material"] == "M-4471" and row["Plant"] == "KRW1":
            row["MatlWrhsStkQtyInMatlBaseUnit"] = 84.0
            row["DailyConsumption"] = 9.2
            break
    else:
        stock.append({"Material": "M-4471", "Plant": "KRW1",
                      "MatlWrhsStkQtyInMatlBaseUnit": 84.0, "BaseUnit": "TON",
                      "DailyConsumption": 9.2, "Description": "Aluminium alloy ingot ADC12"})

    # ---- purchase orders --------------------------------------------------
    single_sourced = {"M-3308", "M-5512", "M-2210", "M-1160"}
    orders, n = [], 4500018870
    for row in stock:
        if rnd.random() > 0.78 and row["Material"] not in single_sourced:
            continue
        code = row["Material"]
        pool = [s for s in SUPPLIERS if s[0] != "SUP-4417B"]
        supplier = rnd.choice(pool)[0] if code not in single_sourced else {
            "M-3308": "SUP-2207", "M-5512": "SUP-2209",
            "M-2210": "SUP-2244", "M-1160": "SUP-6610"}[code]
        origin = next(s[2] for s in SUPPLIERS if s[0] == supplier)
        promised = AS_OF + timedelta(days=rnd.randint(4, 40))
        slip = rnd.choice([0, 0, 0, 2, 5, 8])
        n += rnd.randint(1, 3)
        orders.append({
            "PurchaseOrder": str(n), "Material": code, "Plant": row["Plant"],
            "OrderQuantity": round(row["DailyConsumption"] * rnd.randint(10, 30), 1),
            "BaseUnit": row["BaseUnit"], "Supplier": supplier,
            "LoadingPort": PORTS[origin],
            "DeliveryDate": promised.isoformat(),
            "RevisedDeliveryDate": (promised + timedelta(days=slip)).isoformat(),
            "Status": "in_transit" if slip else rnd.choice(["not_shipped", "in_transit"]),
        })

    # the Ningbo scenario, fixed so the documented figures still reproduce
    orders.append({"PurchaseOrder": "4500018872", "Material": "M-4471", "Plant": "KRW1",
                   "OrderQuantity": 120.0, "BaseUnit": "TON", "Supplier": "SUP-2201",
                   "LoadingPort": "CNNGB", "DeliveryDate": "2026-09-14",
                   "RevisedDeliveryDate": "2026-09-22", "Status": "in_transit"})
    orders.append({"PurchaseOrder": "4500018901", "Material": "M-4471", "Plant": "SBY1",
                   "OrderQuantity": 90.0, "BaseUnit": "TON", "Supplier": "SUP-2201",
                   "LoadingPort": "CNNGB", "DeliveryDate": "2026-09-24",
                   "RevisedDeliveryDate": "2026-09-24", "Status": "not_shipped"})
    # planted defect: revised earlier than promised
    orders.append({"PurchaseOrder": "4500019204", "Material": "M-8830", "Plant": "KRW1",
                   "OrderQuantity": 600.0, "BaseUnit": "LTR", "Supplier": "SUP-8801",
                   "LoadingPort": "THLCH", "DeliveryDate": "2026-10-02",
                   "RevisedDeliveryDate": "2026-09-27", "Status": "in_transit"})
    # planted defect: overdue and still not shipped
    orders.append({"PurchaseOrder": "4500018640", "Material": "M-7710", "Plant": "SBY1",
                   "OrderQuantity": 24000.0, "BaseUnit": "PC", "Supplier": "SUP-8815",
                   "LoadingPort": "MYPKG", "DeliveryDate": "2026-08-18",
                   "RevisedDeliveryDate": "2026-08-18", "Status": "not_shipped"})
    # planted defect: a line ordering nothing
    orders.append({"PurchaseOrder": "4500019310", "Material": "M-9916", "Plant": "CKR1",
                   "OrderQuantity": 0.0, "BaseUnit": "PC", "Supplier": "SUP-6622",
                   "LoadingPort": "JPYOK", "DeliveryDate": "2026-10-11",
                   "RevisedDeliveryDate": "2026-10-11", "Status": "not_shipped"})
    # the duplicate supplier, used once so the audit can see it in traffic
    orders.append({"PurchaseOrder": "4500019288", "Material": "M-4472", "Plant": "KRW1",
                   "OrderQuantity": 40.0, "BaseUnit": "TON", "Supplier": "SUP-4417B",
                   "LoadingPort": "IDTPP", "DeliveryDate": "2026-09-30",
                   "RevisedDeliveryDate": "2026-09-30", "Status": "not_shipped"})

    # ---- customer orders --------------------------------------------------
    sales, so = [], 104400
    for fg, desc, _ in FINISHED:
        for _ in range(rnd.choice([2, 3, 4])):
            so += rnd.randint(3, 19)
            cust = rnd.choice(CUSTOMERS)
            sales.append({
                "SalesOrder": f"{so:010d}", "Material": fg, "Customer": cust[0],
                "CustomerName": cust[1],
                "NetAmount": rnd.randrange(180, 1400) * 1_000_000,
                "Currency": "IDR",
                "RequestedDeliveryDate": (AS_OF + timedelta(days=rnd.randint(10, 75))).isoformat(),
                "LatePenaltyPctPerDay": 0.5, "LatePenaltyCapPct": 10.0,
            })
    # planted defect: sold product with no bill of materials behind it
    sales.append({"SalesOrder": "0000105990", "Material": "FG-9099",
                  "Customer": "CUS-1002", "CustomerName": "Nusa Otomotif Industri",
                  "NetAmount": 310_000_000, "Currency": "IDR",
                  "RequestedDeliveryDate": "2026-11-05",
                  "LatePenaltyPctPerDay": 0.5, "LatePenaltyCapPct": 10.0})
    # the three FG-1120 orders the documented scenario rests on
    sales = [s for s in sales if s["Material"] != "FG-1120"]
    for sid, amount, cust in (("0000104411", 980_000_000, "CUS-1001"),
                              ("0000104427", 715_000_000, "CUS-1001"),
                              ("0000104455", 445_000_000, "CUS-1003")):
        sales.append({"SalesOrder": sid, "Material": "FG-1120", "Customer": cust,
                      "CustomerName": dict(CUSTOMERS)[cust], "NetAmount": amount,
                      "Currency": "IDR", "RequestedDeliveryDate": "2026-09-30",
                      "LatePenaltyPctPerDay": 0.5, "LatePenaltyCapPct": 10.0})

    # ---- alternate sources ------------------------------------------------
    alternates = [
        {"id": "A", "label": "Air freight 85 t from the incumbent supplier",
         "Supplier": "SUP-2201", "Material": "M-4471", "Quantity": 85.0,
         "ArrivalDate": "2026-09-11", "ExtraCostIDR": 186_000_000,
         "TkdnAfterPct": 38.2, "Origin": "CN", "NewOrigin": False, "QualificationDays": 0},
        {"id": "B", "label": "Local supplier PT Logam Andalan, Gresik",
         "Supplier": "SUP-4417", "Material": "M-4471", "Quantity": 60.0,
         "ArrivalDate": "2026-09-12", "ExtraCostIDR": 94_000_000,
         "TkdnAfterPct": 41.6, "Origin": "ID", "NewOrigin": False, "QualificationDays": 3},
        {"id": "C", "label": "Reallocate stock from plant SBY1",
         "Supplier": "INTERNAL", "Material": "M-4471", "Quantity": 55.0,
         "ArrivalDate": "2026-09-10", "ExtraCostIDR": 22_000_000,
         "TkdnAfterPct": None, "Origin": "ID", "NewOrigin": False, "QualificationDays": 0},
        {"id": "D", "label": "New import source in Vietnam",
         "Supplier": "SUP-3390", "Material": "M-4471", "Quantity": 80.0,
         "ArrivalDate": "2026-09-26", "ExtraCostIDR": 61_000_000,
         "TkdnAfterPct": 36.1, "Origin": "VN", "NewOrigin": True, "QualificationDays": 7},
        {"id": "E", "label": "Cheapest source in China",
         "Supplier": "SUP-5501", "Material": "M-4471", "Quantity": 100.0,
         "ArrivalDate": "2026-09-19", "ExtraCostIDR": 48_000_000,
         "TkdnAfterPct": 34.8, "Origin": "CN", "NewOrigin": False, "QualificationDays": 0},
    ]
    # a second material with real alternatives, so M-4471 is not the only one
    alternates += [
        {"id": "F", "label": "PT Cipta Baja Nusantara, Cilegon",
         "Supplier": "SUP-4418", "Material": "M-5518", "Quantity": 45.0,
         "ArrivalDate": "2026-09-18", "ExtraCostIDR": 31_000_000,
         "TkdnAfterPct": 44.0, "Origin": "ID", "NewOrigin": False, "QualificationDays": 5},
        {"id": "G", "label": "Busan Forging, expedited",
         "Supplier": "SUP-7701", "Material": "M-5518", "Quantity": 60.0,
         "ArrivalDate": "2026-09-16", "ExtraCostIDR": 88_000_000,
         "TkdnAfterPct": 0.0, "Origin": "KR", "NewOrigin": False, "QualificationDays": 0},
    ]

    suppliers = [{"Supplier": c, "SupplierName": n, "Country": ctry,
                  "TkdnCertifiedPct": pct or None} for c, n, ctry, pct in SUPPLIERS]

    return {"MaterialStock": stock, "PurchaseOrder": orders, "BillOfMaterial": bom,
            "SalesOrder": sales, "AlternateSource": alternates, "Supplier": suppliers}


def write(data: dict) -> None:
    """CSV per entity for the upload path, and the JSON fixture the tools read."""
    OUT.mkdir(parents=True, exist_ok=True)
    for entity, rows in data.items():
        keys = list(rows[0])
        with (OUT / f"{entity}.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)

    # The fixture keeps its Profile, which is the customer's own master data and
    # not ours to generate. Everything else is replaced.
    scenario = HERE / "ningbo_scenario.json"
    existing = json.loads(scenario.read_text())
    merged = {
        "_note": ("MODELLED DATA, generated by fixtures/generate.py. Not from SAP. The "
                  "company, its plants, its suppliers and its customers are invented. "
                  "Field names mirror SAP conventions, and the documented scenario "
                  "figures in DESIGN.md section 1 are preserved exactly."),
        **data,
        "Profile": existing["Profile"],
    }
    scenario.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")


def demo() -> None:
    data = build()
    again = build()
    assert data == again, "the generator is not deterministic"

    counts = {k: len(v) for k, v in data.items()}
    assert counts["MaterialStock"] > 40, counts
    assert counts["PurchaseOrder"] > 40, counts

    # The scenario figures the documents quote must survive regeneration.
    krw = next(r for r in data["MaterialStock"]
               if r["Material"] == "M-4471" and r["Plant"] == "KRW1")
    assert krw["MatlWrhsStkQtyInMatlBaseUnit"] == 84.0 and krw["DailyConsumption"] == 9.2
    fg1120 = sum(s["NetAmount"] for s in data["SalesOrder"] if s["Material"] == "FG-1120")
    assert fg1120 == 2_140_000_000, fg1120

    write(data)
    print(f"generated {sum(counts.values())} rows into {OUT.relative_to(HERE.parent)}")
    for k, v in counts.items():
        print(f"  {k:<16} {v:>4}")
    print(f"  {len(DEFECTS)} defects planted for the audit to find")


if __name__ == "__main__":
    demo() if "--check" not in sys.argv else (build(), print("stable"))
