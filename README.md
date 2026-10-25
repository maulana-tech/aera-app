<h1 align="center">SIGAP</h1>

<p align="center">
  <b>Supply Disruption Intelligence &amp; Anticipation System</b>
</p>

<p align="center">
  An autonomous assistant for manufacturers that import most of their raw material.
  When a port closes, a supplier misses a shipment or goods are held at customs, the system
  investigates the impact itself, assembles the ways out, strikes the ones that break Indonesian
  regulation or the customer contract, works out which is cheapest — and executes it into SAP
  only once someone with the authority approves.
</p>

<p align="center">
  <a href="https://github.com/maulana-tech/socrates/actions/workflows/deploy.yml"><img src="https://img.shields.io/badge/CI-GITHUB%20ACTIONS-181717?style=flat-square&labelColor=555555&logo=githubactions&logoColor=white" alt="CI" /></a>
  <a href="https://nextjs.org"><img src="https://img.shields.io/badge/WEB-NEXT.JS%2016-000000?style=flat-square&labelColor=555555&logo=nextdotjs&logoColor=white" alt="Next.js 16" /></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/AGENT-PYTHON%203-3776AB?style=flat-square&labelColor=555555&logo=python&logoColor=white" alt="Python" /></a>
  <a href="https://aws.amazon.com/bedrock/"><img src="https://img.shields.io/badge/MODELS-AMAZON%20BEDROCK-FF9900?style=flat-square&labelColor=555555&logo=amazonec2&logoColor=white" alt="Amazon Bedrock" /></a>
  <a href="https://www.sap.com"><img src="https://img.shields.io/badge/ERP-SAP%20S%2F4HANA%20CLOUD-0FAAFF?style=flat-square&labelColor=555555&logo=sap&logoColor=white" alt="SAP S/4HANA Cloud" /></a>
  <a href="#run-it"><img src="https://img.shields.io/badge/RUN-DOCKER%20COMPOSE-2496ED?style=flat-square&labelColor=555555&logo=docker&logoColor=white" alt="Docker Compose" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/LICENSE-MIT-000000?style=flat-square&labelColor=555555" alt="MIT License" /></a>
</p>

---

A supervised swarm of **twelve agents**, a Next.js interface, and a deterministic calculator that
refuses to produce a rupiah figure it cannot stand behind. Two processes: the web app and the
agent service. No queue to babysit — the work starts from events.

> **The models propose; they never decide, and they never spend.**
>
> - Every tool return carries its origin — `live`, `cached`, `derived`, `modelled`, `missing`.
>   A failure produces `missing`, never a plausible-looking guess.
> - The calculator is pure Python with no model in it, and it **refuses** to emit a savings
>   figure when a critical input is not trustworthy.
> - Kira's rejection cannot be overturned on cost: an option that drops the local-content
>   ratio (TKDN) below the contract floor is struck out even when it is the cheapest of all.
> - Approvals are checked against the role's rupiah limit **server-side** (`core/identity.py`),
>   and nothing reaches a supplier, a customer or SAP except through a person's approval.

---

## Who this is for

Meet Budi, a supply chain manager at a manufacturer in West Java that imports most of its raw
material. A typhoon closes Ningbo for three days. He spends the next two to three working days
in email and spreadsheets: which orders does this actually hit, what stock is genuinely usable,
who else can supply it, does the substitution break the TKDN clause, what does each option cost,
and which purchase order does he raise first.

He has run this drill before and knows the answer will be wrong by Tuesday, because the data
moved. What he needs is not another dashboard. It is the analysis done, the rule check applied,
the cost worked out, and a recommendation waiting for his signature — with the evidence attached.

---

## The Problem

- **A disruption is a research project.** One event means tracing orders, stock, BOM and
  customs status by hand, across systems that were never designed to answer that question
- **The cheapest option is often forbidden.** TKDN floors, LARTAS licences and contract terms
  live in documents nobody reads while a spreadsheet is open
- **Cost models are trusted too much.** A single bad input turns into a confident rupiah figure
  that a director signs off on
- **"AI supply chain agents" guess.** They produce fluent summaries with no origin for any fact
  and no way to audit what they did
- **Nothing anticipates.** By the time the event is in the system, the shipment is already late

**How might we turn a disruption from a multi-day investigation into a tens-of-minutes
decision, without letting a model invent a number or break a rule?**

---

## The Solution

Five pieces, each doing a job the others cannot.

**1. Events, not logins.** Signal watchers poll BMKG (earthquakes), GDACS · NASA EONET · USGS
(hazards) and Open-Meteo (port weather), dedupe against the record and raise an event.
Vega's weekly scan finds the risk that has not happened yet: single sources, concentrated lanes,
certificates about to expire.

**2. A lead who calls specialists one at a time.** Arya pulls the agent the last finding calls
for — Impact, then Sourcing, then Logistics — deciding from evidence rather than a fixed
pipeline. There is no parallel guess-fest: the run is synchronous, ordered and fully recorded.

**3. Provenance on every fact.** Each tool returns `Result{value, origin, source}`. The board
refuses to let an untrusted fact back a rupiah figure, and the interface shows the label on
every number it prints.

**4. Rules before cost.** Kira tests every candidate against the rule pack — TKDN, contract
floor, LARTAS licensing, the holiday calendar — and marks which rules are verified and which
are assumptions. Only what survives reaches Tara's deterministic calculator.

**5. Execute, then explain.** Bram writes back to SAP within authority, drafts the customer and
supplier messages (both wait for a person to send), watches through to receipt, and records what
actually happened. Every approval, every send and every reason lands in the decision log.

---

## The Agent Council

Twelve agents, one lead. Each has its own page in the app (`/agents/:code`) and can be asked
anything directly from `/chat`.

| Agent | Code | Role | Tools | What it may do |
|---|---|---|---|---|
| **Arya** 👑 | `supervisor` | Team lead: pulls specialists as findings warrant, judges when evidence is enough, writes the recommendation with its trade-offs and residual risk | 1 | Nothing alone — every action waits for a person |
| **Elsa** | `impact` | Traces a disruption through orders, stock and the BOM to the customer commitments genuinely at risk | 4 | Read only |
| **Dara** | `demand` | The demand side: daily consumption as a variable that moves, not a fixed number | 3 | Read only |
| **Iris** | `inventory` | Which stock may actually be used — quality holds, rejected batches, safety floors | 3 | Read only |
| **Clint** | `sourcing` | Replacement supply: other suppliers, internal stock, fast freight, substitute materials with their approval status | 3 | Read only |
| **Prita** | `procurement` | The supplier book: volume, country, certificate, on-time record; quotations compared on price against lead time; drafts the purchase order | 6 | Read only (drafts wait for approval) |
| **Milo** | `logistics` | Arrival dates that survive contact with reality — measured customs dwell, port status, weather, news and holidays on the lane | 7 | Read only |
| **Kira** ⚖️ | `compliance` | Tests every candidate against TKDN, the contract floor, LARTAS licensing and the calendar; says which rules are verified | 2 | **Veto: a rejection here cannot be overturned on cost** |
| **Tara** | `simulation` | Costs the options that cleared the rules, and allocates short material across customer orders. Calls `engine/simulate.py` and `engine/allocate.py` | 2 | Deterministic engines, no model in the arithmetic |
| **Otto** | `precedent` | Institutional memory: what was done last time something like this happened, and how it turned out | 1 | Read only |
| **Bram** | `execution` | Writes back to SAP, tells the affected roles, drafts customer and supplier messages, records the outcome | 9 | Within its authority, and only after approval |
| **Vega** | `exposure` | Prevent mode: hunts risk that has not happened yet, ranked by what it would cost | 4 | Recommends; Bram raises it, a person approves |

Every agent's tools, parameters and prompts are **generated from the registry** into
[`sigap/AGENT-REFERENCE.md`](sigap/AGENT-REFERENCE.md) by `python3 manage.py docs`, so the
document cannot disagree with the code.

### Approval limits

Enforced server-side in `core/identity.py`, never in the UI:

| Role | May approve up to |
|---|---|
| `planner` | read only |
| `buyer` | Rp 500,000,000 |
| `procurement_lead` | Rp 10,000,000,000 |
| `admin` | Rp 10,000,000,000 |

Below `SIGAP_AUTONOMOUS_LIMIT_IDR` (default Rp 50 million) the system may act unattended; above
it, a person must sign. Model spend per event is capped by `SIGAP_COST_CAP_IDR`.

### The origin label every fact carries

| Label | Meaning |
|---|---|
| `live` | Read from the real source just now (SAP, an upload, an outside feed) |
| `cached` | From the record, still within its freshness window |
| `derived` | Computed from `live` inputs by deterministic code |
| `modelled` | From a fixture or a model's judgement — usable, never priced as fact |
| `missing` | The source did not answer. Never substituted with a guess |

---

## How one disruption runs

```
a signal arrives (BMKG · GDACS · Open-Meteo · POST /events)
  ├─ event recorded once, deduped against the record
  ├─ Arya: "what does this actually hit?"   → calls Impact
  ├─ that answer raises a new question      → Arya calls the next specialist
  │     one at a time, in the order the findings demand
  ├─ Kira: rules check → candidates that break TKDN, contract or licence are struck out
  │     (a strike here cannot be overturned on cost)
  ├─ Tara: deterministic costing of what survived → ranked in rupiah
  │     refuses outright if a critical input is not trustworthy
  ├─ Bram: the action written up, drafted emails attached, payload ready for SAP
  ├─ a person approves, within their role's limit (checked server-side)
  └─ delivery: sender.py → SAP   ·   notify.py → email, team channels, morning digest 07:30
        everything lands in the decision log with its trace
```

---

## Features

- **Decision queue**: every handling with what it proposes, what it would cost and what is
  waiting for a signature
- **Approval with authority limits**: role checked on the server, one-shot approvals,
  idempotent actions — approving twice cannot send twice
- **Dashboard**: the sharp end of the book — charts of exposure, orders at risk, what is
  blocked and why, with the full table one click away
- **Agent pages and chat**: ask any of the twelve directly, see its tools, prompts and past
  runs; conversations are kept per agent
- **Decision log and run trace**: every step of a run, every tool call with its origin label,
  the exploration graph of what was asked and what it found
- **Reports**: generated per handling or across the portfolio, exported to PDF and XLSX, and
  sent by email straight from the page
- **Schedule**: seven jobs that run without a person — three signal watchers, Vega's exposure
  scan, alert and outreach delivery, the SAP sender and the 07:30 digest; each toggleable and
  runnable by hand
- **Contacts and notifications**: who is told about what, by email or team channel, with a
  mailbox you connect and a test button; approved supplier and customer messages go out
  verbatim from the draft
- **Uploads**: bring your own data with downloadable templates; every read is labelled with
  where it came from
- **Data audit**: `engine/audit.py` reads whatever the system can see and reports what is
  wrong with it — deterministic, every finding carries its evidence
- **Models page**: list, test and switch the model behind each agent (`provider:model` on
  Bedrock, AI Core or Mantle), with a ping that proves it answers
- **MCP endpoint**: the agent service exposes `/mcp`, so external clients can call the same
  tools the swarm uses
- **SAP connector**: reads against the sandbox once `SAP_API_KEY` is set, writes through a
  CSRF-aware sender that only sends what a person approved
- **Auth**: session tokens signed by `SIGAP_SECRET`, identity from the token, `SIGAP_ENV=prod`
  refuses to start without SAP and a reachable lead model

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web app | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, shadcn-ui, D3 |
| Agent service | Python, stdlib `http.server` + `sqlite3`; `anthropic` only when Bedrock is configured |
| Models | Amazon Bedrock (Claude by default), SAP AI Core, Mantle — one model per agent, with a fallback |
| Persistence | SQLite (`data/sigap.db`): events, runs, steps, actions, approvals, contacts, outbox |
| Outside feeds | BMKG · GDACS · NASA EONET · USGS · Open-Meteo · holidays · FX · news, each labelled |
| ERP | SAP S/4HANA Cloud OData (sandbox by default, fixtures when the key is absent) |
| Interfaces | REST (47 routes, session required except `/health` and `/login`) · MCP (`/mcp`) |
| Delivery | Email (SMTP outbox with retries) and team channels, quoted from the record |
| Containers | Docker Compose: Next.js web, Python agent service, PostgreSQL |
| CI/CD | GitHub Actions: lint, agent output, Python self-check on every push; SSH deploy from `main` to EC2 |
| Tests | Python self-check, transport and rollback tests for the deploy scripts |

---

## Architecture

### One handling, end to end

```mermaid
sequenceDiagram
    participant F as Feeds (BMKG · GDACS · Open-Meteo)
    participant API as Agent service (Python, :8787)
    participant A as Arya (lead)
    participant S as Specialists
    participant K as Kira (Rules) · Tara (Costing)
    participant DB as SQLite record
    participant W as Next.js (:3000)
    participant P as Person
    participant X as SAP · Email · Channels

    F->>API: signal → event (deduped)
    API->>A: handling starts
    A->>S: ask_impact → ask_sourcing → ask_logistics (one at a time)
    S-->>API: Result{value, origin, source}
    API->>K: rules check, then deterministic costing
    K-->>DB: options struck out, with reasons
    API->>DB: run, steps, trace, proposed action
    W->>API: decision queue
    P->>W: approve (limit checked in core/identity.py)
    API->>X: sender.py posts to SAP · notify.py quotes the record
    X-->>DB: message id, sent stamp, outcome
```

### How an option is judged

```mermaid
flowchart LR
    O[Option from a specialist] --> K[Kira: TKDN · contract · LARTAS · calendar]
    K -->|breaks a rule| X[Struck out, reason logged<br/>cannot be overturned on cost]
    K -->|survives| C[Tara: engine/simulate.py<br/>engine/allocate.py]
    C -->|inputs not trusted| N[No figure — refused]
    C -->|trusted| R[Ranked in rupiah]
    R --> A{Within the approver's limit?}
    A -->|yes| S[sender.py → SAP]
    A -->|no| H[Held in the queue]
    X --> L[Decision log]
    N --> L
    S --> L
    H --> L

    style X fill:#dc2626,color:#fff
    style N fill:#dc2626,color:#fff
    style S fill:#16a34a,color:#fff
```

Every path ends in the decision log. There is no route to SAP or to an outside party that does
not pass through a person's approval first.

---

## Run it

### Option A: Docker Compose (recommended)

Runs all three containers — **Next.js web**, **Python agent service** and **PostgreSQL** —
with one command.

```bash
# 1. prepare the environment file
cp sigap/agent/.env.example sigap/agent/.env     # see sigap/ENV.md for every line

# 2. build and start
docker compose up -d --build

# 3. watch it
docker compose ps
docker compose logs -f agents

# 4. open it
#    web   → http://localhost:3000
#    agent → http://localhost:8787
#    db    → localhost:5432
docker compose down          # stop
docker compose down -v       # stop and wipe the database volumes
```

### Option B: Manual (two processes)

```bash
# the agent service
cd sigap/agent
python3 manage.py secret                  # export its output as SIGAP_SECRET
python3 manage.py user you@example.com "Your Name" buyer yourpassword
python3 manage.py seed                    # optional demo data
python3 api.py                            # :8787

# the interface, in another terminal
npm install
SIGAP_API=http://127.0.0.1:8787 npm run dev
open http://localhost:3000/dashboard
```

Nothing else needs starting: `api.py` runs the schedule, which watches the feeds, delivers
alerts and pushes approved actions to SAP.

To see what is and is not wired up:

```bash
cd sigap/agent && PYTHONPATH=. python3 manage.py check
```

With no accounts anywhere, the four-line fast path in [`sigap/ENV.md`](sigap/ENV.md) brings
the whole system up on fixtures. Everything from a fixture is labelled `modelled`, so the
calculator will not price it — production refuses to run without real SAP and a real model.

---

## Documentation

Everything lives in [`sigap/`](sigap/):

| File | What's in it |
|---|---|
| [`sigap/PLAN.md`](sigap/PLAN.md) ⭐ | The plan, the status of each part, what to do next |
| [`sigap/AGENT-REFERENCE.md`](sigap/AGENT-REFERENCE.md) | All 12 agents and their 45 tools, **generated** from the registry |
| [`sigap/architecture/`](sigap/architecture/) | How the parts fit together: app, agents, tools, workers, data |
| [`sigap/ENV.md`](sigap/ENV.md) | Every environment variable, where to get it, how to check it works |
| [`sigap/SETUP.md`](sigap/SETUP.md) | The ordered walkthrough for a first-time setup |
| [`sigap/DESIGN.md`](sigap/DESIGN.md) | The scenario and its figures, the constraint rules, the eval suite |
| [`sigap/TECHNICAL.md`](sigap/TECHNICAL.md) | Model calling conventions, caching, limits |
| [`sigap/DATA-SOURCES.md`](sigap/DATA-SOURCES.md) | What was verified about each data source |
| [`sigap/SWARM-COMPARISON.md`](sigap/SWARM-COMPARISON.md) | SmartX ↔ SIGAP: what a swarm architecture can teach this one |
| [`sigap/AWS-PLAN.md`](sigap/AWS-PLAN.md) | Getting onto Bedrock and AgentCore, in the order that works |
| [`sigap/agent/README.md`](sigap/agent/README.md) | Running the agent service, configuration, the API |
| [`ops/CICD.md`](ops/CICD.md) | GitHub Actions: CI on all branches, SSH deployment from main to EC2 |

---

## Status

`PYTHONPATH=. python3 manage.py check` prints this live, from the code rather than from a table.

**Working**: provenance labelling on every tool, the deterministic calculator, SAP reads,
persistence with idempotent actions and one-shot approvals, auth with server-side authority
limits, the full interface, all 45 tools, all 12 prompts, the signal watchers (BMKG, hazards,
weather), the schedule, email and outreach delivery, reports by email, the data audit, and the
agent team running end to end on AI Core.

**Held back honestly**: the SAP write path is complete but untested against real entities; the
rule pack (`sigap/references/`) is read but not written — that is knowledge work, not code;
`AWS_REGION` unset means the team has not run against Bedrock yet, and until a model is
reachable the system makes no decisions at all rather than pretending to.

[`sigap/PLAN.md`](sigap/PLAN.md) §2 has the detail, and what is blocking each item.

---

## License

MIT — see [`LICENSE`](LICENSE).
