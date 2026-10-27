# Sample master data

A company's book, generated to be coherent rather than random: **2,633 rows across seven
entities**, with Indonesian suppliers carrying TKDN percentages and foreign ones carrying
none, larger lots quoted cheaper per tonne, and ports that follow the supplier's country.

| | |
|---|---|
| [`sigap-master-data.xlsx`](sigap-master-data.xlsx) | All seven entities as one workbook, 137 KB, one sheet each. Written by SIGAP's own `engine/export.py`, so it opens in Excel without a dependency anywhere |
| [`csv/`](csv/) | The same data, one file per entity — **this is what the uploader takes** |
| [`invalid/`](invalid/) | Three files that are meant to fail, so the gate can be seen working |
| [`generate.py`](generate.py) | What made it. `python3 generate.py <outdir>` |

```
Supplier           120 rows     Quotation        1,395 rows
MaterialStock      115 rows     PurchaseOrder      600 rows
AlternateSource    100 rows     SalesOrder         200 rows
BillOfMaterial     103 rows
```

## Uploading it

The uploader takes **CSV**, not `.xlsx` — the browser reads the file as text and posts it
to `POST /uploads`, which parses it with `csv.DictReader`. Open the workbook in Excel and
*Save As → CSV* per sheet, or use `csv/` directly. Feeding it `.xlsx` bytes is refused
cleanly (`could not read the CSV: line contains NUL`) rather than stored as rubbish.

Every file here uploads clean:

```
AlternateSource.csv   HTTP 201  stored  100 rows
BillOfMaterial.csv    HTTP 201  stored  103 rows
MaterialStock.csv     HTTP 201  stored  115 rows
PurchaseOrder.csv     HTTP 201  stored  600 rows
Quotation.csv         HTTP 201  stored 1395 rows
SalesOrder.csv        HTTP 201  stored  200 rows
Supplier.csv          HTTP 201  stored  120 rows
```

Once stored, every read of those entities comes back labelled **`cached`** with
`source: upload:<filename>` — which is what lets the calculator state rupiah at all. The
uploader is also asked whether the file is real master data or a generated sample; nothing
in a file can tell SIGAP that, and guessing would mean labelling generated rows as though
somebody had measured them.

## What the invalid files prove

| File | Result |
|---|---|
| `missing-column.csv` | **422** · `missing required column(s): Country` |
| `text-in-number.csv` | **422** · row 1: `MatlWrhsStkQtyInMatlBaseUnit is not a number ('delapan puluh empat')` |
| `empty-required.csv` | **422** · row 1: `Supplier is empty` |

and, without a file at all: an unknown entity is **400** with the list of entities that
exist, an empty body is **400**, and a file with headers but no rows is **400**. Nothing
part-valid is ever stored — a file is kept whole or refused whole.

## A defect this dataset found

The first upload of `Quotation.csv` produced **0 of 12 offers valid** for every material.
`tools/procurement.py` reads `QuotationValidityEndDate`, and counts a missing validity date
as *not live* — deliberately, because an offer nobody can check is one a buyer must
re-quote. But `core/schema.py` did not show that column in the Quotation template, so a
company following the template uploads a book of quotations that is **dead on arrival**,
and `compare_quotations` recommends nothing.

Fixed by naming the column in the template, with the reason beside it. With the column
present the same data reads `12 offers, 12 valid on 2026-09-04. Cheapest is SUP-4061`.
