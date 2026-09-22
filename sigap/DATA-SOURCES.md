# Data sources — what was actually verified

> Checked on 21 September 2026 by opening each source directly. Earlier drafts had some
> of these marked "unchecked"; they are not any more.

---

## Summary

| Data | Status | How to get it |
|---|---|---|
| Orders, stock, products, customers, production schedule, quality lots | ✅ **ready** | SAP sandbox, free API key |
| Indonesian weather & earthquakes | ✅ **ready, has a JSON API** | `data.bmkg.go.id` |
| National holiday calendar | ✅ published annually | Copy it by hand |
| Rupiah exchange rate | ✅ published daily | Bank Indonesia |
| TKDN | ⚠️ public portal, **no API** | Take a copy → a rule document |
| LARTAS | ⚠️ public portal, **no open API** | Copy from the regulation → a rule document |
| Foreign typhoons | ❌ **not from BMKG** | See §5 |
| Vessel positions | ⚠️ registration required | An AIS service |
| Company profile | 🔵 **invented, and said so openly** | See §7 |

---

## 1. Company data — settled, no research needed

**Source:** SAP Business Accelerator Hub, at `https://sandbox.api.sap.com/`

**How:** register a free SAP ID account at `api.sap.com`, open the API page you need, click
*Show API Key*. That's it.

This is a real S/4HANA Cloud system holding sample data — the shapes, the pagination, and
the error messages are identical to a real customer system.

**What's there:**

| Need | Service name |
|---|---|
| Purchase orders | `API_PURCHASEORDER_PROCESS_SRV` |
| Material stock | `API_MATERIAL_STOCK_SRV` |
| Bill of materials | `API_BILL_OF_MATERIAL_SRV` |
| Sales orders | `API_SALES_ORDER_SRV` |
| Production schedule | `API_PRODUCTION_ORDER_2_SRV` |
| Quality inspection results | `API_INSPECTIONLOT_SRV` |
| Safety stock | `API_PRODUCT_SRV` |
| Create a purchase requisition | `API_PURCHASEREQ_PROCESS_SRV` |

**Moving to a customer later:** change the base URL and the key. The code does not change.

⚠️ The write-side service names in `sender.py` are **not yet verified** against the
sandbox. The path is complete, CSRF token and all, but the entity names need checking
before any real write.

---

## 2. TKDN — public, but fetched by hand

**Official portals:**
- https://tkdn.kemenperin.go.id/ — certificate search and verification
- http://pusatp3dn.kemenperin.go.id/Sertifikattkdn — summaries by commodity group

**What the check found:** the pages are public and searchable, **but there is no documented
API**. No official endpoint documentation was found.

**What to do:** take a copy once, and keep it as `references/tkdn-rules.md`. It needs:

- The minimum local-content floor per sector
- How the ratio is calculated
- The certificates of the 5–6 suppliers in the scenario, with their validity dates

**You do not need the whole database.** What the agent needs is the **rule**, not thousands
of certificates. And TKDN rules do not change daily.

> **This is better than an API, not worse.** A rule document can be read and audited. Buried
> behind an API call, nobody can check the basis on which the agent said no.

---

## 3. LARTAS — use the regulation, not the lookup portal

**Portal:** https://insw.go.id/ — the INTR menu takes an HS code and returns duty, VAT,
income tax, and restriction status.

**What the check found:** there is a [SINSW service catalogue](https://panduan.insw.go.id/en/katalog-layanan)
listing 19 services, but it is for registered traders — not an open API.

**The better route:** LARTAS is governed by **Permendag No. 18 of 2021**. That is a
regulation, readable directly, and a sounder basis than looking codes up one at a time.

**What to do:** `references/lartas-procedure.md`, containing:

- Which goods are restricted
- Which licence is required
- **How long the licence takes** ← this is what the agent uses to strike out an option
- What changes when the origin country is new

---

## 4. Indonesian weather and earthquakes — ✅ has an API, free, ready now

**Source:** https://data.bmkg.go.id/

**This is the one disruption signal that can genuinely be wired up without much effort.**

| Data | Path | Format |
|---|---|---|
| 3-day forecast, by district | `data.bmkg.go.id/prakiraan-cuaca/` | JSON |
| Latest earthquake | `autogempa.json` | JSON & XML |
| Last 15 quakes M5.0+ | `gempaterkini.json` | JSON & XML |
| Last 15 felt quakes | `gempadirasakan.json` | JSON & XML |

Official sample code: [infoBMKG/data-cuaca](https://github.com/infoBMKG/data-cuaca) and
[infoBMKG/data-gempabumi](https://github.com/infoBMKG/data-gempabumi).

---

## 5. ❌ Correction: BMKG is not the source for the Ningbo typhoon

**A mistake that needed fixing.** An earlier draft cited *"BMKG tropical-cyclone bulletins"*
as the trigger for the Ningbo scenario. That was wrong.

BMKG monitors **Indonesian waters**. The typhoon that closes the Port of Ningbo is in the
East China Sea, outside its remit.

**The correct mapping:**

| Disruption type | Signal source | Status |
|---|---|---|
| East Asian typhoon (the Ningbo scenario) | JTWC or JMA | Needs its own check |
| **Earthquakes in Indonesia** | ✅ **BMKG** | Ready now |
| **Extreme weather & flooding in Indonesia** | ✅ **BMKG** | Ready now |
| Indonesian ports | Port authority notices | Needs checking |
| Vessel delays | AIS data | Registration required |

### Worth doing: add a domestic scenario

BMKG is most useful precisely for domestic disruption — a quake cutting a Java land route,
flooding closing access to Priok. And its data is the easiest of all to get.

**Add one scenario with a real BMKG earthquake as the trigger.** The value is that you can
then say *"this signal came from a BMKG API that is running right now"* — not from a
fixture. One genuinely live source is worth more than four that only appear on a slide.

---

## 6. Holiday calendar and exchange rate — easy

| Data | Source | Note |
|---|---|---|
| National holidays & collective leave | SKB 3 Menteri | Published once a year. Copy by hand into `references/holiday-calendar.md` |
| Rupiah rate | Bank Indonesia JISDOR | Published daily. A fixed value is fine for now |

Don't spend time automating these two. The payoff is small.

---

## 7. The company profile — the only invented thing

The plant list, the daily consumption rates, the contract terms and late penalties.

**There is no source, because there is no customer yet.** Each installation will fill this
from its own master data on day one.

**Say so openly, always.** It is stated in `DESIGN.md` §1.1 and in the UI's origin labels,
and it should stay that way: a clearly stated limit is worth more than a claim you cannot
stand behind.

---

## 8. Order of work

| Order | Work | How long | Who |
|---|---|---|---|
| 1 | Get the SAP API key | 15 min | anyone, today |
| 2 | Wire up BMKG (quakes + weather) | 2 hours | backend |
| 3 | Write `references/tkdn-rules.md` | 1 day | **domain** |
| 4 | Write `references/lartas-procedure.md` | 1 day | **domain** |
| 5 | Copy in the holiday calendar | 1 hour | anyone |
| 6 | Find a foreign typhoon source | — | only if the Ningbo scenario stays |
| 7 | Register with an AIS service | — | optional, later |

**The one that gets mis-scheduled:** 3 and 4 are done by **a domain person, not a
programmer**. They are regulatory knowledge, not code.

---

## 9. Rules that apply

1. **What is ✅ may be stated plainly.**
2. **What is ⚠️ is described as** *"ingested into a versioned rule pack"* — honest, and
   still not invented data, because the source is real.
3. **Never promote a ⚠️ to an "it has an API" claim** before proving it yourself.
4. **The company profile is always named** as modelled, with the reason.
