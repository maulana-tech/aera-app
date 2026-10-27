"""Generate a company's master data: a lot of it, coherent, and in both the
format the uploader takes (CSV) and the one a person opens (xlsx, written by
SIGAP's own engine/export.py)."""
import csv, io, pathlib, random, sys
from datetime import date, timedelta
sys.path.insert(0, ".")
from engine import export

random.seed(4471)
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
TODAY = date(2026, 9, 4)

PLANTS = ["KRW1", "SBY1", "GRS1", "MDN1"]
COUNTRIES = [("ID", 55), ("CN", 20), ("VN", 9), ("KR", 6), ("JP", 5), ("TH", 5)]
ID_NAMES = ["PT Logam Andalan", "PT Cipta Baja Nusantara", "PT Sinar Metalindo",
            "PT Karya Tuang Perkasa", "PT Jaya Presisi", "PT Baja Mandiri Sentosa",
            "PT Anugerah Teknik Logam", "PT Surya Alloy Indonesia"]
CN_NAMES = ["Ningbo Yongtai Metals", "Qingdao Baowu Steel", "Jiangsu Hengli Forging",
            "Shanghai Minghua Alloy", "Tianjin Northgate Steel"]
OTHER = ["Busan Forging", "Hanoi Precision Metals", "Osaka Seiko Works",
         "Bangkok Alloy Industries", "Haiphong Steelworks"]

def country():
    r = random.randint(1, 100); c = 0
    for code, w in COUNTRIES:
        c += w
        if r <= c: return code
    return "ID"

# --- suppliers -------------------------------------------------------------
suppliers = []
for i in range(120):
    cty = country()
    name = (random.choice(ID_NAMES) if cty == "ID" else
            random.choice(CN_NAMES) if cty == "CN" else random.choice(OTHER))
    suppliers.append({
        "Supplier": f"SUP-{4000+i}",
        "SupplierName": f"{name} {i:03d}",
        "Country": cty,
        # local content a foreign supplier cannot have
        "TkdnCertifiedPct": round(random.uniform(38, 62), 1) if cty == "ID" else 0.0,
    })

# --- materials and stock ---------------------------------------------------
materials = [f"M-{4400+i}" for i in range(60)]
stock = []
for m in materials:
    for p in random.sample(PLANTS, random.randint(1, 3)):
        daily = round(random.uniform(1.5, 14.0), 1)
        stock.append({
            "Material": m, "Plant": p,
            "MatlWrhsStkQtyInMatlBaseUnit": round(daily * random.uniform(3, 40), 1),
            "DailyConsumption": daily, "BaseUnit": "T",
            "Description": f"Cold-rolled coil grade {m[-3:]}",
        })

# --- quotations: Prita's entity, the big one -------------------------------
quotations = []
qn = 6000000000
for m in materials:
    for s in random.sample(suppliers, random.randint(4, 12)):
        for qty in (20.0, 60.0, 120.0):
            qn += 1
            base = random.uniform(1_200_000, 2_400_000)
            quotations.append({
                "SupplierQuotation": str(qn), "SupplierQuotationItem": 10,
                "Supplier": s["Supplier"], "Material": m,
                "OrderQuantity": qty,
                # bigger lots are cheaper per tonne, which is what a comparison must find
                "NetPrice": round(base * (1 - 0.06 * (qty / 120.0)), 0),
                "DeliveryTimeInDays": random.randint(4, 45),
                "Currency": "IDR", "QtnLifecycleStatus": random.choice("AAAB"),
                "QuotationValidityEndDate": str(TODAY + timedelta(days=random.randint(-10, 90))),
            })

# --- purchase orders -------------------------------------------------------
pos, pn = [], 4500000000
for _ in range(600):
    pn += 1
    m = random.choice(materials); s = random.choice(suppliers)
    pos.append({
        "PurchaseOrder": str(pn), "PurchaseOrderItem": 10, "Material": m,
        "Plant": random.choice(PLANTS), "OrderQuantity": round(random.uniform(10, 150), 1),
        "BaseUnit": "T", "Supplier": s["Supplier"],
        "LoadingPort": {"CN": "CNNGB", "VN": "VNHPH", "KR": "KRPUS",
                        "JP": "JPOSA", "TH": "THBKK"}.get(s["Country"], "IDTPP"),
        "DeliveryDate": str(TODAY + timedelta(days=random.randint(-20, 60))),
        "RevisedDeliveryDate": str(TODAY + timedelta(days=random.randint(-20, 75))),
        "Status": random.choice(["open", "open", "open", "delivered"]),
    })

# --- alternate sources -----------------------------------------------------
alts = []
for i, m in enumerate(materials[:20]):
    for tag, s in zip("ABCDE", random.sample(suppliers, 5)):
        cty = s["Country"]
        alts.append({
            "id": f"{m}-{tag}", "label": f"{s['SupplierName']} for {m}",
            "Material": m, "Supplier": s["Supplier"],
            "Quantity": round(random.uniform(30, 120), 1),
            "ArrivalDate": str(TODAY + timedelta(days=random.randint(5, 40))),
            "ExtraCostIDR": int(random.uniform(20, 200) * 1_000_000),
            "Origin": cty, "NewOrigin": 0 if cty == "ID" else random.choice([0, 1]),
            "TkdnAfterPct": round(random.uniform(33, 46), 1),
            "QualificationDays": random.choice([0, 0, 3, 14]),
        })

# --- sales orders and BOM --------------------------------------------------
fgs = [f"FG-{1100+i}" for i in range(18)]
sos, sn = [], 10000
for _ in range(200):
    sn += 1
    sos.append({"SalesOrder": str(sn), "Material": random.choice(fgs),
                "Customer": f"OEM-{random.randint(1,12):02d}", "CustomerName": "Astra OEM",
                "NetAmount": int(random.uniform(0.4, 6.0) * 1_000_000_000), "Currency": "IDR",
                "RequestedDeliveryDate": str(TODAY + timedelta(days=random.randint(3, 60))),
                "Quantity": random.randint(200, 3000),
                "LatePenaltyPctPerDay": 0.5, "LatePenaltyCapPct": 10.0})
bom = []
for fg in fgs:
    for m in random.sample(materials, random.randint(3, 8)):
        bom.append({"Material": m, "FinishedGood": fg,
                    "ComponentQuantity": round(random.uniform(0.3, 3.5), 2),
                    "Description": "component"})

SETS = {"Supplier": suppliers, "MaterialStock": stock, "Quotation": quotations,
        "PurchaseOrder": pos, "AlternateSource": alts, "SalesOrder": sos,
        "BillOfMaterial": bom}

def to_csv(rows):
    cols = list(rows[0])
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols); w.writeheader(); w.writerows(rows)
    return buf.getvalue()

sheets = []
for name, rows in SETS.items():
    (OUT / f"{name}.csv").write_text(to_csv(rows))
    cols = list(rows[0])
    sheets.append(export.Sheet(name, cols, [[r.get(c) for c in cols] for r in rows]))
    print(f"  {name:17} {len(rows):>5} rows  ·  {len((OUT / f'{name}.csv').read_text())//1024:>4} KB csv")

book = export.xlsx(sheets, title="SIGAP master data")
(OUT / "sigap-master-data.xlsx").write_bytes(book)
print(f"\n  sigap-master-data.xlsx  {len(book)//1024} KB  ·  {len(sheets)} sheets  "
      f"·  {sum(len(r) for r in SETS.values()):,} rows in all")

# --- deliberately broken files, to prove the gate -------------------------
bad = OUT / "bad"; bad.mkdir(exist_ok=True)
(bad / "missing-column.csv").write_text(to_csv([
    {"Supplier": "SUP-9001", "SupplierName": "No country column", "TkdnCertifiedPct": 40.0}]))
(bad / "text-in-number.csv").write_text(to_csv([
    {"Material": "M-4471", "Plant": "KRW1",
     "MatlWrhsStkQtyInMatlBaseUnit": "delapan puluh empat", "DailyConsumption": 9.2}]))
(bad / "empty-required.csv").write_text(to_csv([
    {"SupplierQuotation": "6000000001", "Supplier": "", "Material": "M-4471",
     "OrderQuantity": 60, "NetPrice": 1_560_000, "DeliveryTimeInDays": 9}]))
print("  bad/: missing-column.csv, text-in-number.csv, empty-required.csv")
