# Data sources, what was actually verified

> Checked on 21 September 2026 by opening each source directly. Earlier drafts had some
> of these marked "unchecked"; they are not any more. §10, the live outside sources, was
> checked on 24 October 2026 the same way: every feed called, every tool run live.

---

## Summary

| Data | Status | How to get it |
|---|---|---|
| Orders, stock, products, customers, production schedule | ✅ **ready** | CSV upload, fixtures until then, see §1 |
| Indonesian earthquakes | ✅ **wired up and live** | `signals/bmkg.py`, polls `data.bmkg.go.id` |
| Weather at every port and plant | ✅ **wired up and live** | `signals/weather.py`, Open-Meteo, see §10 |
| Cyclones, floods, quakes, eruptions, fires abroad | ✅ **wired up and live** | `signals/hazards.py`, GDACS + NASA EONET + USGS, see §10 |
| National holiday calendar | ✅ **live** for most countries | Nager.Date, see §10. Cuti bersama still by hand |
| Exchange rates | ✅ **live**, ECB reference | Frankfurter, see §10. No VND |
| News | ✅ **live** | Google News RSS, see §10 |
| TKDN | ⚠️ public portal, **no API** | Take a copy → a rule document |
| LARTAS | ⚠️ public portal, **no open API** | Copy from the regulation → a rule document |
| Foreign typhoons | ✅ **not from BMKG, from GDACS and EONET** | See §5 and §10 |
| Vessel positions | ⚠️ registration required | An AIS service |
| Company profile | 🔵 **invented, and said so openly** | See §7 |

---

## 1. Company data, from uploads

**Source:** the company's own exports, uploaded as CSV on the **Upload data** page (or
`POST /uploads`), one file per entity, with a downloadable template for each
(`core/schema.py` has the columns). An entity nobody uploaded falls back to the shipped
fixture (`fixtures/ningbo_scenario.json`).

**Labels:** an upload is `cached` (genuine, just not live), or `modelled` when the uploader
declared it generated sample data. A fixture is always `modelled`, and the calculator
refuses to price on it.

Some reads have no source beyond an upload:

| Entity | Where it really lives | What reads it |
|---|---|---|
| `CustomsDeclaration` | the customs authority's system (CEISA in Indonesia), via the importer or its customs broker | `get_customs_status`, and the dwell `estimate_eta` measures |
| `MaterialSubstitute` | engineering's change records: which material a product may be made from instead, approved or not | `find_substitute_materials`, which reads only this list |
| `PartnerContact` | the company's supplier and customer contacts | the address a supplier request or customer notice goes to |

And some are not connected at all, so the tool says so rather than guess:
`get_quality_holds` returns no holds (no inspection-lot source), `get_safety_stock_policy`
returns `missing` (no MRP source), and `get_demand_signal` says a demand plan is not
connected.

An approved action is not posted to an ERP: `sender.py` issues it as a local document with
a stable number derived from its idempotency key, and marks it `sent`.

---

## 2. TKDN, public, but fetched by hand

**Official portals:**
- https://tkdn.kemenperin.go.id/, certificate search and verification
- http://pusatp3dn.kemenperin.go.id/Sertifikattkdn, summaries by commodity group

**What the check found:** the pages are public and searchable, **but there is no documented
API**. No official endpoint documentation was found.

**What to do:** take a copy once, into the rule pack (`aera/references/README.md`, the
format; the pack itself is installed per deployment and never committed). It needs:

- `tkdn_contract_floor_pct`, the floor in the customer contract, with the clause it is from
- `tkdn_current_pct`, the company's position today
- `certificates`, each supplier's certificate with its validity dates, which
  `get_supplier_certifications` reads

How the ratio is calculated stays in the document the pack cites. Each rule carries its
source and whether someone verified it there; only a verified rule makes a ruling derived.

**You do not need the whole database.** What the agent needs is the **rule**, not thousands
of certificates. And TKDN rules do not change daily.

> **This is better than an API, not worse.** A rule document can be read and audited. Buried
> behind an API call, nobody can check the basis on which the agent said no.

---

## 3. LARTAS, use the regulation, not the lookup portal

**Portal:** https://insw.go.id/, the INTR menu takes an HS code and returns duty, VAT,
income tax, and restriction status.

**What the check found:** there is a [SINSW service catalogue](https://panduan.insw.go.id/en/katalog-layanan)
listing 19 services, but it is for registered traders, not an open API.

**The better route:** LARTAS is governed by **Permendag No. 18 of 2021**. That is a
regulation, readable directly, and a sounder basis than looking codes up one at a time.

**What to do:** read the regulation for the goods in question and put **how long the
licence takes for a new origin country** into the rule pack as
`lartas_new_origin_working_days`, with the article it comes from. That is the number the
agent uses to move an arrival and strike out an option. Until it is there, Kira applies a
built-in 10 working days and labels every LARTAS ruling modelled.

Which goods are restricted and which licence they need are not encoded: Kira's prompt has
her name such a restriction as not checked rather than rule on it.

---

## 3a. Customs declarations, held by the importer

**What the check found:** declaration status (the lane a declaration was given, whether
the goods are released, held, or under inspection) sits in the customs authority's
system and with the importer's customs broker. There is no open API for it.

**What to do:** export the declarations once a day and upload them as
`CustomsDeclaration`: one row per declaration with the purchase order, port, arrival,
lane, status, release date and hold reason (`core/schema.py` has the columns).

**Why it is worth the hour:** the released ones are the dwell history. `estimate_eta`
takes the median days from discharge to release at the port and the 80th percentile as
the slow case, which replaces a fixed four days with a distribution anyone can recompute.
With no history it still falls back to the rule pack's default, and says so.

---

## 4. Indonesian weather and earthquakes, ✅ has an API, free, ready now

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
| East Asian typhoon (the Ningbo scenario) | ✅ JTWC tracks, via NASA EONET and GDACS | Live, §10 |
| **Earthquakes in Indonesia** | ✅ **BMKG** | Ready now |
| **Extreme weather & flooding in Indonesia** | ✅ **BMKG**, not wired; Open-Meteo is, §10 | Ready now |
| Indonesian ports | Port authority notices | Needs checking |
| Vessel delays | AIS data | Registration required |

### Worth doing: add a domestic scenario

BMKG is most useful precisely for domestic disruption, a quake cutting a Java land route,
flooding closing access to Priok. And its data is the easiest of all to get.

**Add one scenario with a real BMKG earthquake as the trigger.** The value is that you can
then say *"this signal came from a BMKG API that is running right now"*, not from a
fixture. One genuinely live source is worth more than four that only appear on a slide.

---

## 6. Holiday calendar and exchange rate, easy

| Data | Source | Note |
|---|---|---|
| National holidays & collective leave | SKB 3 Menteri | Published once a year. Copy the collective leave by hand into the rule pack's `collective_leave` |
| Rupiah rate | Bank Indonesia JISDOR | Published daily. A fixed value is fine for now |

Don't spend time automating these two. The payoff is small.

**Update, 24 October:** both turned out to be one free call each, so they are now
live (§10): public holidays for most countries from Nager.Date, and the ECB's
reference rates from Frankfurter. Kira's LARTAS count of working days skips the
Indonesian ones. Two gaps remain. Nager.Date's Indonesian calendar has no cuti bersama,
so the SKB copy above is still worth making. And the ECB rate is not JISDOR: it is a
reference for comparing quotes, not the rate Indonesian contracts settle at.

---

## 7. The company profile, the only invented thing

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
| 1 | Upload the company's own data | 1 hour | anyone, today |
| 2 | ~~Wire up BMKG quakes~~ done. Weather from the same feed family is still open | 1 hour | backend |
| 3 | Rule pack: the TKDN floor, position and supplier certificates, each with its source | 1 day | **domain** |
| 4 | Rule pack: the LARTAS licensing time for a new origin, with its article | 1 day | **domain** |
| 5 | Rule pack: copy in the collective leave | 1 hour | anyone |
| 6 | Upload the customs declarations and engineering's substitute list | 1 hour each | whoever holds them |
| 7 | ~~Find a foreign typhoon source~~ done, §10 |, | |
| 8 | Register with an AIS service |, | optional, later |

**The one that gets mis-scheduled:** 3 and 4 are done by **a domain person, not a
programmer**. They are regulatory knowledge, not code.

---

## 9. Rules that apply

1. **What is ✅ may be stated plainly.**
2. **What is ⚠️ is described as** *"ingested into a versioned rule pack"*, honest, and
   still not invented data, because the source is real.
3. **Never promote a ⚠️ to an "it has an API" claim** before proving it yourself.
4. **The company profile is always named** as modelled, with the reason.

---

## 10. Live outside sources, ✅ wired up 24 October 2026

Everything AERA reads from the open web without a credential, apart from BMKG (§4).
Every call goes through `agent/clients/feeds.py`: a named User-Agent, a timeout, a
cache that keeps each copy's real fetch time, and a five-minute memory of failures so
a dead feed costs one timeout rather than one per question. A feed that cannot be
reached returns `MISSING` with the reason. It never returns an empty list, which would
read as a quiet day.

### What is read

| Source | Endpoint | What it gives | Cache | Label |
|---|---|---|---|---|
| **GDACS** (UN/EC) | `gdacs.org/xml/rss.xml` | Current cyclones, floods, quakes, eruptions, fires, droughts, graded Green/Orange/Red | 30 min | live |
| **NASA EONET** v3 | `eonet.gsfc.nasa.gov/api/v3/events?status=open&days=20` | Events seen in satellite imagery; for cyclones, the JTWC fix every six hours | 30 min | live |
| **USGS** | `earthquake.usgs.gov/.../summary/4.5_week.geojson` | Quakes worldwide; read from M5.5 | 15 min | live |
| **Open-Meteo** | `api.open-meteo.com/v1/forecast`, `marine-api.open-meteo.com/v1/marine` | Three days of daily max gusts, rain total and max wave height, every place in one request | 1 h | live |
| **Nager.Date** | `date.nager.at/api/v3/PublicHolidays/{year}/{CC}` | National public holidays | 24 h | live |
| **Frankfurter** | `api.frankfurter.dev/v1/latest?from=&to=` | ECB reference rates, one a working day | 6 h | live |
| **Google News** | `news.google.com/rss/search?q=…+when:7d` | Headline, publisher, time, link. The article is not fetched | 15 min | live |

### Where it goes

| Code | Owner | Does |
|---|---|---|
| `signals/places.py` | | The places worth watching: the profile's plants and port, plus the loading port of every open purchase order, from a fixed UN/LOCODE table. An unknown port code is reported, never placed |
| `signals/hazards.py` | sweep | GDACS + EONET + USGS, one storm in two feeds fused into one hazard, measured against every place. One event per hazard per place |
| `signals/weather.py` | sweep | The forecast against named thresholds. One event per place per spell of bad weather |
| `scan_live_hazards` | Vega | Every hazard within reach of a place, with its distance and radius |
| `get_port_conditions` | Milo | One port or plant: forecast, flagged days, hazards nearby |
| `search_news` | Milo | Headlines |
| `get_public_holidays` | Milo | Holidays at either end of a lane |
| `get_exchange_rate` | Prita | A foreign-currency quote next to a rupiah one |

### Judgement calls, named so they can be argued with

| Rule | Value | Why |
|---|---|---|
| Cyclone radius | 600 km | The gale field and the closures ahead of a typhoon; a day or two to act |
| Flood / quake / eruption / fire / drought radius | 150 / 300 / 100 / 50 / 300 km | How far the damage reaches. The quake radius is BMKG's |
| GDACS grades read | every cyclone, flood and eruption; Orange and up for quakes, fires, droughts | The grade measures people affected, not ports closed. GDACS lists about 250 Green fires a day |
| Quakes near an Indonesian place | skipped | BMKG's ground, raised by `signals/bmkg.py`; never raised twice under two kinds |
| Gusts | 62 km/h | The bottom of Beaufort 8. Quay cranes commonly stop near 72 km/h sustained |
| Waves | 4 m | Douglas 6, "very rough"; pilot boarding and berthing are suspended around here |
| Rain | 100 mm a day | BMKG's *hujan sangat lebat*. Plants are judged on rain only |

### Verified on 24 October 2026

- **Champi reached the system on its own.** EONET's JTWC fix at 00:00 UTC put Super
  Typhoon Champi at 24.8°N 123.3°E, **588 km from Ningbo (CNNGB)**, inside the 600 km
  radius. GDACS graded it **Red** but placed it at its 23 October episode, about 820 km
  out. Fused, the hazard carries GDACS's grade and EONET's position, and raises one
  event: *"Tropical cyclone CHAMPI near Ningbo-Zhoushan (Beilun) port (CNNGB)"*. On
  GDACS's position alone it would have been missed.
- **The forecast agreed.** Open-Meteo forecast gale-force gusts at Ningbo on 24 and 25
  October (79.2 and 79.6 km/h), and very heavy rain at Busan (117 and 113 mm) with
  gusts to 71 km/h. Both raise a weather event.
- Google News returned eight Champi headlines inside a week.
- USD/IDR was 18,108 on the ECB's 23 October fix, CNY/IDR 2,714.71.

### Gaps, stated

- **GDACS's JSON API** (`gdacsapi/api/events/…`) timed out or took 50 to 80 s on every
  call, and its geometry and event-data endpoints answered 400 and 500. The RSS file is
  read instead, in about 6 s.
- **Nager.Date** has no calendar for Malaysia, Thailand or Taiwan (it answers 204), and
  Indonesia's omits cuti bersama. The tool says so rather than returning an empty month.
- **Frankfurter, and the ECB behind it,** publish no VND. A Vietnamese quote cannot be
  converted here.
- **The marine model** has no sea state for river ports: Ho Chi Minh City (Cat Lai)
  returns no wave height. The forecast says so; it does not read as calm water.
- **Google News RSS** is licensed for personal, non-commercial feed readers. Fine for a
  demonstration; a licensed news API replaces it in production. GDELT, the obvious free
  alternative, answered 429 on every call.
- **Headlines are other people's words.** They are passed on as reported, with publisher
  and time, and no figure is taken from one.
