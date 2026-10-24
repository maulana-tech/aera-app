# SIGAP, Plan & Status

> Context: **application development.** Not a competition entry.
> Jargon is decoded in §8 if a word is unfamiliar.
>
> Updated: 24 October 2026

---

## 1. What is being built

An autonomous assistant for manufacturers that import most of their raw material.

When supply is disrupted, a port closes, a supplier misses a shipment, goods are held at
customs, the system investigates the impact itself, assembles the ways out, strikes the
ones that break regulation or the customer contract, works out which is cheapest, and
executes it into SAP once someone with the authority approves.

What takes 2–3 human working days today happens in tens of minutes.

**This is not a website people open every morning.** The system works off events. The web
interface is where you inspect and approve, not where the work starts.

---

## 2. Where it stands

| Part | Status | Notes |
|---|---|---|
| Data-origin label | ✅ **working** | On every tool. A failure → `MISSING`, never a guess |
| Cost calculator | ✅ **working** | Pure Python. Refuses figures when inputs aren't trustworthy |
| SAP connector (read) | ✅ **ready** | Uses the sandbox automatically once `SAP_API_KEY` is set |
| Live disruption signal | ✅ **working** | `signals/bmkg.py` polls BMKG quakes and raises events. `signals/hazards.py` (GDACS + NASA EONET + USGS) and `signals/weather.py` (Open-Meteo) are written and verified live on 24 Oct, Champi caught at 588 km from Ningbo; each needs a slot in the scheduler. `DATA-SOURCES.md` §10 |
| SAP connector (write) | ⚠️ **path complete, untested** | CSRF handled; entity names need checking |
| Persistence | ✅ **working** | SQLite. Idempotent actions, one-shot approvals |
| Auth & authority | ✅ **working** | Identity from the token; value limits checked server-side |
| API service | ✅ **working** | `POST /events` needs a session since 24 Oct. Several reads (`/summary`, `/runs`, `/log`) still answer without one |
| Interface | ✅ **working** | Dashboard with charts, queue, detail, approval, per-domain tables, conversations. shadcn-ui |
| Tools | ✅ **39 of 39** | Every declared tool exists. Six read the open web: hazards, port weather, news, holidays, FX, a cited web answer |
| Agent prompts | ✅ **12 of 12** | Every agent can be invoked |
| Agent team (`graph.py`) | ✅ **runs end to end on AI Core** | Ningbo handled on `gpt-5.4` on 24 Oct, 10 model calls, 86 s. Not yet against Bedrock: waiting on credentials |
| Model per agent (`core/llm.py`) | ✅ **working** | Claude on Bedrock Mantle, MiniMax on Mantle Chat Completions, `gpt-5.4` on AI Core, with a fallback. `manage.py models --ping` |
| Joule (`sigap/joule/`) | 🔶 **built, tested against a stub** | A2A shim, three skills, capability YAML. Waiting on CF push and a BTP destination |
| RPT-1.6 slip ranking | ✅ **working** | Vega's `rank_po_slip_risk`, live on AI Core. Labelled modelled, never priced |
| Rule pack (`references/`) | 🔶 **read, not written** | `tools/compliance.py` reads `rule-pack.json`, each rule with its source and whether it was verified; `get_rule_pack` shows what is in force. The pack itself, the company's terms and certificates, is domain work and is not committed |
| Supply-chain coverage | ✅ **supplier, customs, substitution, allocation** | Orders by supplier, customs status and measured dwell, substitute materials with their approval, short supply allocated to customer orders by penalty, customer and supplier messages as drafts |
| Scenario eval suite | ❌ **absent** | |
| Inter-plant transfers | ✅ **judged from both ends** | `engine/matching.py`. Iris rules on whether the donor plant can afford a transfer, the way Kira rules on regulation |
| Data audit | ✅ **working** | `engine/audit.py` reads whatever the system can see and reports what is wrong with it. Deterministic, every finding carries its evidence |
| Prevent mode | 🔶 **scans, does not act yet** | Vega finds exposures and ranks them. The actions she recommends are raised by Bram and always wait for a person |

`PYTHONPATH=. python3 manage.py check` prints this live, from the code rather than from
this table.

### What is blocking

1. **`SAP_API_KEY`**, free, 15 minutes. Once set, five read tools use real data and the
   origin label flips from `modelled` to `live`.
2. **Bedrock credentials.** The team has run end to end on AI Core, not yet on Bedrock.
   `ENV.md`, under Models, has the steps. Until a model is reachable the system honestly
   holds back and makes no decisions at all.
3. **The rule pack** (`sigap/references/README.md`). Kira reads it when it is installed;
   without it she judges from built-in parameters and the company profile, and labels the
   result `modelled`. **This is knowledge work, not code.** A programmer cannot write it.

---

## 3. How it works

Picture a small team: a lead, and several specialists with their own areas. The lead does
not do the work, he calls the relevant specialist, one at a time, according to what the
previous one found.

```
a disruption arrives
  → the lead calls Impact            "what does this actually hit?"
  → that answer raises a new question
  → the lead calls the next one      "is there another source?"
  → Rules strikes out what breaks regulation
  → Costing prices what's left
  → the lead writes a recommendation, and admits the residual risk
  → small things it executes itself, large things it asks a human
  → it watches until the goods actually land
```

**The order is not written in advance.** If moving stock between plants solves it, the
sourcing specialist is never called at all.

### Twelve agents

| Agent | The question it owns |
|---|---|
| **Arya** (lead) | Who do I call next, and when is the evidence enough? |
| Elsa, Impact | Which POs are hit, which customers are exposed? |
| Dara, Demand | Is consumption still that rate, or is demand rising? |
| Iris, Stock Validity | Is the recorded stock actually usable? |
| Clint, Sourcing | Is there another source? |
| Milo, Logistics | Realistically, when does it land? |
| **Kira, Rules** ⭐ | May we use that supplier at all? **Has veto** |
| Tara, Costing | What does it cost, which is cheapest? |
| Otto, Precedent | Has this happened before? How did it end? |
| Prita, Procurement | Who do we buy from, did they keep their dates, what does a quote really cost? |
| Bram, Execution | Carry it out, then watch until the goods arrive |
| Vega, Risk Scanner | What is **about** to break? *(Prevent mode)* |

Each agent's tools and parameters are in `AGENT-REFERENCE.md`, generated from the registry.

---

## 4. Technology

| | AWS | SAP |
|---|---|---|
| Its job | Where the agents **think and run** | Where the **real data** and **the actions** live |
| What | Bedrock (the model), Strands, Lambda | S/4HANA, Ariba, Business Network |

Decisions that are locked in:

| Thing | Choice |
|---|---|
| Model | Per agent (`core/llm.py`), picked in `.env` or on the Models page: Claude Opus 4.6 for Arya and Kira, MiniMax M2.5 for the other ten, `gpt-5.4` on AI Core as fallback. `JOULE-BEDROCK-PLAN.md` §4 |
| Languages | Python (agents) · TypeScript (interface) |
| Persistence | SQLite, move to Postgres once this is multi-tenant |
| Interface | Next.js 16 + React 19 + Tailwind v4 + shadcn-ui |
| API service | stdlib `http.server`, move to FastAPI if you need >10 rps |
| Language of the codebase | English throughout: files, identifiers, DB columns, API keys, UI |

⚠️ Not every AWS region offers Claude. Check first; keep `us-west-2` as the fallback.

---

## 5. Guarantees the code enforces

Not instructions to a model, these are enforced by the program, so no prompt can break them.

1. **A failure never invents a value.** Tool fails → `MISSING`.
2. **The calculator refuses** rupiah figures when its inputs aren't trustworthy.
3. **Actions are idempotent.** The same key never creates a second order.
4. **Identity comes only from the session token.** Claiming a role via the request body
   is ignored.
5. **Authority is checked on the server**, not on the button.
6. **Production refuses to start** without SAP and a model, it may not guess at anything.
7. **A missing prompt raises** rather than sending a placeholder to the model.
8. **Importing a tool module is what registers it**, so `tools/__init__.py` imports
   all of them. The registry used to be populated by whoever imported first.

The full list, with the reasoning, is in `agent/README.md`.

---

## 6. What to do next

| # | Work | Who | How long |
|---|---|---|---|
| 1 | Get `SAP_API_KEY` at api.sap.com | anyone | 15 min |
| 2 | Enable Bedrock, confirm the region. `AWS-PLAN.md` has the rest | backend | 1 hour |
| 3 | Run `graph.py` against Bedrock, fix what breaks | backend | 1-2 days |
| 4 | Write the rule pack: TKDN floor and certificates, LARTAS licensing time, collective leave, each sourced and verified | **domain** | 2 days |
| 5 | Upload customs declarations and engineering's substitute list | whoever holds them | 1 hour each |
| 6 | Verify SAP write entity names in `sender.py` | backend | 1 day |
| 7 | A 10-scenario eval suite | data | 2 days |
| 8 | Schedule Vega weekly, wire her findings into the queue | backend | 2 days |

Item 4 can start now and **waits on nothing.**

---

## 7. File layout

```
sigap/
├── PLAN.md              this file, plan & status
├── AGENT-REFERENCE.md   the 12 agents. GENERATED, run `manage.py docs`
├── AWS-PLAN.md          Bedrock and AgentCore, week by week
├── DESIGN.md            scenario figures, local rules
├── TECHNICAL.md         exact function names & parameters
├── DATA-SOURCES.md      what was verified about each data source
└── agent/               the code
    ├── core/            provenance · identity · store · config · registry · trace
    ├── clients/         the SAP connector
    ├── tools/           one file per agent, named after the agent code
    ├── engine/          the calculator, pure Python
    ├── agents/          the 12 agent definitions
    ├── prompts/         each agent's instructions
    ├── fixtures/        modelled data, clearly labelled as such
    ├── graph.py         the agent team
    ├── api.py           the HTTP service
    ├── sender.py        pushes approved actions to SAP
    └── manage.py        admin: user · secret · seed · check · docs

app/(app)/               the Next.js interface
app/api/                 the bridge to the agent service
components/              sidebar, charts, tables, badges
```

---

## 8. Glossary

| Said plainly here | The technical term |
|---|---|
| A team of agents with a lead | multi-agent system · *supervised swarm* |
| The lead | *supervisor agent* |
| What an agent can do | *tool* |
| The data-origin label | *provenance* |
| An ordinary calculator | *deterministic engine* |
| The order is decided while running | *runtime routing* |
| An action never doubles | *idempotency* |
| SAP's try-it-out system | *sandbox* |
| Moving to a customer's own system | *tenant swap* |
| Local content ratio | TKDN |
| Import licensing | LARTAS |
| Delivery reliability | OTIF |
