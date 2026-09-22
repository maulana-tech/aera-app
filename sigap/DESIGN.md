# SIGAP — Design

> The scenario, its figures, and the rules the system reasons over.
> Every number in §2 is reproduced by `engine/simulate.py`. If a figure here cannot be
> reproduced by that command, **this document is wrong**, not the code.

---

## 1. The master scenario

All the figures below are consistent with one another. Do not change one without
checking what it derives.

### 1.1 The company

**PT Karya Presisi Nusantara (KPN)** — a Tier-1 automotive component maker.

- Plant **KRW1** Karawang (main), plant **SBY1** Surabaya
- 340 active materials, **61% of raw-material value imported**, mostly via Tanjung Priok
- Products: brake caliper assembly, transmission housing — for an OEM on a JIT contract
- The OEM contract requires **TKDN of at least 40%**; the portfolio sits at **38.2%**

This company profile is the **only** genuinely modelled thing in the system, because
there is no customer yet. Each deployment fills it from its own master data on day one.
Everything else comes from SAP, or is labelled `modelled` in the open.

### 1.2 The critical material

| Field | Value |
|---|---|
| Code | **M-4471** |
| Name | Aluminium alloy ingot ADC12 |
| Plant | KRW1 |
| Opening stock (4 Sep) | **84 t** |
| Daily consumption | **9.2 t/day** |
| Cover | 84 ÷ 9.2 = **9.1 days → depleted 13 Sep** |
| Feeds | FG-1120 (brake caliper assembly) |

### 1.3 Affected purchase orders

| PO | Material | Qty | Original ETA | Revised ETA | Supplier |
|---|---|---|---|---|---|
| **4500018872** | M-4471 | 120 t | 14 Sep | **22 Sep** | SUP-2201 (Ningbo) |
| 4500018901 | M-4471 | 90 t | 24 Sep | 24 Sep | SUP-2201 → plant SBY1 |
| + 10 more | 4 materials | — | — | slipped | 3 suppliers |

Twelve POs route through Ningbo, worth **Rp 8.4 billion**. Only M-4471 is critical.

### 1.4 Downstream commitment

Three OEM sales orders for FG-1120, **Rp 2.14 billion** in total.
Late penalty **0.5%/day, capped at 10%** → maximum penalty exposure **Rp 214 million**.

### 1.5 The trigger

> A typhoon closes Ningbo–Zhoushan port **8–13 September** (6 days).

The production gap to bridge: **13 Sep → 22 Sep = 9 days**.

### 1.6 How big the gap actually is

```
depleted with no action    13 Sep
scheduled supply arrives   22 Sep  (PO 4500018872, 120 t)
the gap                     9 days × 9.2 t/day = 82.8 tonnes
```

Any option standing on its own must supply **at least 82.8 tonnes** to bridge it. That is
why the air-freight option is set at 85 tonnes.

> **Correction, 21 Sep 2026.** An early draft said 40 tonnes. `engine/simulate.py` caught
> it: 40 tonnes only moves the stockout from 13 Sep to 17 Sep — still a hole. This is
> precisely why the calculator has to be deterministic. A language model will accept
> "40 tonnes covers 9 days" without blinking.

### 1.7 The five options

| | Option | Arrives | Extra cost | TKDN | Ruling |
|---|---|---|---|---|---|
| A | Air freight **85 t** from SUP-2201 | 11 Sep | +Rp 186m | 38.2% | Allowed, most expensive. 85 t is the minimum that genuinely bridges 82.8 t |
| B | Local supplier PT Logam Andalan (SUP-4417), Gresik, 60 t | 12 Sep | +Rp 94m | **41.6% ↑** | Allowed; needs 3 days of metallurgical requalification |
| C | Reallocate 55 t from SBY1 | 10 Sep | +Rp 22m | — | Allowed; leaves SBY1 thin |
| D | New supplier SUP-3390 (Vietnam) | 26 Sep | +Rp 61m | 36.1% ↓ | **BLOCKED** — LARTAS for a new origin country needs 10 working days; arrives 13 days after the line stops |
| E | Cheapest supplier SUP-5501 (China), 100 t | 19 Sep | +Rp 48m | 34.8% ↓ | **BLOCKED** — TKDN drops to 34.8%, breaching the 40% OEM contract floor |

D and E are struck out **on the rules, not on price** — and E is the cheapest of all five.
That is the whole point: no pure cost model finds this reason to say no.

### 1.8 What the system recommends: C + B

```
opening stock 4 Sep         84 t              depleted 13 Sep
+ C: 55 t arrives 10 Sep    55 ÷ 9.2 = 6.0 days   → covered to 19 Sep
+ B: 60 t arrives 12 Sep    60 ÷ 9.2 = 6.5 days   → covered to 25 Sep
PO 4500018872 lands 22 Sep                        → joined up, no stockout
```

- **Cost: Rp 116 million** vs Rp 186 million for air freight → **saves Rp 70 million (38%)**
- Protects **Rp 2.14 billion** of committed revenue
- TKDN rises **38.2% → 41.6%**
- **Residual risk the system states outright:** SBY1 is left with 4 days of cover until
  PO 4500018901 lands on 24 Sep. It tells the SBY1 planner and adds it to the watch list
  rather than declaring the case closed.

### 1.9 These figures are machine-verified, not typed

```bash
cd agent && PYTHONPATH=. python3 engine/simulate.py
```

Output:

```
no action        → depleted 2026-09-13
modelled data    → calculator refuses to give a figure ✓
blocked by rules → ['D', 'E']
chosen           → B+C Rp 116,000,000 · TKDN 41.6%
vs option A      → Rp 186,000,000 · saves Rp 70,000,000 (38%)
```

---

## 2. The constraint engine

Four rules, run by `check_local_constraints`. These are what `references/` contains.

| Rule | Logic | Effect |
|---|---|---|
| **TKDN** | Recompute the portfolio local-content ratio if this supplier is used | Block anything that worsens the position, or drops it below the 40% contract floor from above |
| **LARTAS** | A new origin country → add 10 working days for the import licence | Shifts the ETA; often makes an option arrive too late |
| **Holiday calendar** | Collective leave and national holidays freeze customs and logistics | Add calendar days to every ETA that crosses them |
| **Priok dwell time** | A variable, not a constant — use the historical distribution | An import ETA is a range, not a single date |

⚠️ `references/tkdn-rules.md` and `lartas-procedure.md` are **not written yet**. Until they
exist, Kira judges from fixture parameters and labels the result `modelled`. Writing them
is domain work, not programming.

### A note on the TKDN rule direction

The rule is *"must not worsen the local-content position"*, not *"must be above 40%"*.
KPN already sits at 38.2%, below its own contract floor. An early version rejected
everything under 40%, which wrongly struck out option A — an option that changes nothing.
The `/data/sourcing` page made this visible; `tools/compliance.py` has the check that
keeps it fixed.

---

## 3. Authority limits

| Action | Authority |
|---|---|
| Read, analyse, simulate, recommend | Fully autonomous |
| Inter-plant stock transfer, impact < Rp 50m | Autonomous, reported afterwards |
| Issue a purchase order | **Draft only** — a buyer approves |
| A new supplier, or value > Rp 500m | Escalate to the procurement lead |
| Anything breaching TKDN / LARTAS | Blocked by design |

Bounded autonomy is not a limitation — it is what makes the system usable in a
contract-bound manufacturing environment at all.

---

## 4. Prevent mode — a second mode, not a second system

| | **Respond** | **Prevent** |
|---|---|---|
| Trigger | A disruption event | A weekly cycle, or an exposure threshold crossed |
| Horizon | Days | Weeks to months |
| Question | The plan broke; what do we do? | What is about to break, and what can we prevent now? |
| Output | Mitigation for one event | A ranked list of preventive actions |
| Urgency | Hours | Days to weeks |

**Why one swarm and not two systems.** A planning question is a response question asked
earlier. The same agents answer it: Impact traces exposure, Demand reads demand, Stock
Validity judges usable stock, Logistics models ETAs, **Rules still vetoes**, Costing
computes, Execution acts within its authority. The constraint reasoning is inherited
rather than rewritten.

### The one new agent: Vega, Risk Scanner

Her domain is risk that **has not happened yet**. She passes the test that matters for a
new agent — she can disagree with an existing one. Sourcing says supplier A is adequate;
Vega says A is the sole source for three materials at once, and that is a single point of
failure nobody has looked at.

What she scans for:

| Pattern | Why it matters |
|---|---|
| Single-sourced material | A single point of failure, invisible until it fails |
| Lanes concentrated on one port | One typhoon takes out many materials at once |
| Supplier TKDN certificate near expiry | The ratio can fall with no physical event at all |
| Cover dropping below policy within N weeks | A preventable stockout |
| Materials with the highest stockout cost | Determines the ranking, not just the list |
| National holidays ahead | A customs freeze you can plan around |

### The four tools Prevent mode still needs

```python
# Vega — Risk Scanner (neither written)
scan_supply_exposure(horizon_weeks) -> list[Exposure]
get_supplier_certifications(supplier) -> Certifications   # TKDN validity

# Bram — Execution, planning-flavoured actions (neither written)
create_sourcing_event(material, rationale) -> SourcingEvent          # needs approval
propose_safety_stock_change(material, plant, new_level) -> ChangeRequest  # always escalates
```

`create_stock_transfer` is reused for pre-positioning ahead of a calendar freeze — give it
a future date; no new tool needed.

### Authority in Prevent mode

Tighter, because no urgency justifies autonomy here:

| Action | Authority |
|---|---|
| Scan, assess, rank, recommend | Autonomous |
| Pre-position stock < Rp 50m | Autonomous, reported afterwards |
| Start a sourcing event / qualification | **Draft — procurement approves** |
| Change a safety stock policy | **Always** escalate — this is a policy change |

Respond and Prevent write to the **same queue**. A planner sees one list, not two apps.

---

## 5. The eval suite — 14 scenarios

This is what turns "autonomous" into something demonstrable. **None of it is written yet.**

| # | Scenario | What it tests |
|---|---|---|
| 1 | Typhoon closes Ningbo for 6 days | Baseline — the full path |
| 2 | Supplier plant fire, zero capacity for 3 weeks | A disruption with no clear end date |
| 3 | COO paperwork disputed, held at Priok 12 days | A domestic disruption, not one at sea |
| 4 | OEM raises demand 40% without warning | Disruption from the demand side |
| 5 | Import tariff jumps on one HS code | An economic change, not a physical one |
| 6 | Inbound batch fails inspection, 80 t rejected | Stock that "exists" turns out to be unusable |
| 7 | Singapore transhipment delayed | A cascading delay |
| 8 | Rupiah weakens 8% in a week | The economics of import options change |
| 9 | Collective leave freezes customs for 9 days | A calendar constraint |
| 10 | A local supplier loses its TKDN certification | A constraint that changes mid-flight |
| 11 | Material X has a single supplier, nothing has happened | Risk detection with no trigger |
| 12 | A supplier's TKDN certificate expires in 6 weeks | Anticipating a constraint before it bites |
| 13 | Nine days of collective leave in 5 weeks | Calendar-driven planning |
| 14 | Seven materials through the same one port | Lane concentration |

Scenarios 8, 9 and 10 exercise constraint reasoning specifically — the part that most
distinguishes this system. Scenarios 11–14 have no disruption trigger at all; **only
Prevent mode can answer them.**

---

## 6. Data sources

Summarised here; the verification detail is in `DATA-SOURCES.md`.

| Layer | Source | Status |
|---|---|---|
| **ERP** | SAP S/4HANA Cloud **sandbox** at SAP Business Accelerator Hub | ✅ confirmed · free API key from api.sap.com |
| **Reasoning** | Claude on Amazon Bedrock | ✅ pay-as-you-go |
| **TKDN** | Kemenperin TKDN register (P3DN) | ⚠️ public; likely manual ingest → a versioned rule pack |
| **LARTAS** | INSW restriction classification | ⚠️ public; ingest into the rule pack |
| **Holiday calendar** | SKB 3 Menteri, national holidays & collective leave | ✅ public, published annually |
| **FX rate** | Bank Indonesia JISDOR | ✅ published daily |
| **Weather & quakes** | BMKG `data.bmkg.go.id` | ✅ confirmed · JSON & XML, free, no registration |
| **Foreign typhoons** | JTWC / JMA — **not BMKG** | ⚠️ BMKG only covers Indonesian waters |
| **Vessel positions** | AIS (e.g. aisstream.io free tier) | ⚠️ needs registration |

The BMKG point is worth keeping straight: BMKG is genuinely useful and genuinely free, but
only for **domestic** disruption. The Ningbo trigger in §1.5 is in the East China Sea, which
BMKG does not cover. Claiming otherwise would be wrong.

---

## 7. Principles worth not forgetting

1. **The dashboard is not the product.** The system works off events. The interface is
   where you inspect and approve, not where work begins.
2. **Cost figures never come from a language model.** They have to be deterministic, or
   every savings claim falls to the first sceptical question.
3. **Never mock what you can get for real.** The SAP sandbox is free and real. The only
   modelled thing is the company profile, and it says so out loud.
4. **An agent that admits a trade-off is worth more than one that is always right.**
   Stating the residual risk is the feature, not a weakness.
5. **Adding agents or tools is not progress.** What matters is the depth of the reasoning
   and how the supervisor chooses a route — not the number of boxes in the diagram.
