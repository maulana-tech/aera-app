<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="public/logo/aera-mark-19-dark.svg" />
    <img src="public/logo/aera-mark-19-light.svg" alt="AERA" width="104" />
  </picture>
</p>

<h1 align="center">AERA</h1>

<p align="center">
  <b>Supply Disruption Intelligence &amp; Anticipation System</b>
</p>

<p align="center">
  An autonomous assistant for manufacturers that import most of their raw material.
  When a port closes, a supplier misses a shipment or goods are held at customs, the system
  investigates the impact itself, assembles the ways out, strikes the ones that break Indonesian
  regulation or the customer contract, works out which is cheapest — and issues it
  only once someone with the authority approves.
</p>

<p align="center">
  <a href="https://aera.lumbungstack.dev"><img src="https://img.shields.io/badge/LIVE-aera.lumbungstack.dev-16A34A?style=flat-square&labelColor=555555" alt="Live app" /></a>
  <a href="https://github.com/maulana-tech/socrates/actions/workflows/deploy.yml"><img src="https://img.shields.io/badge/CI-GITHUB%20ACTIONS-181717?style=flat-square&labelColor=555555&logo=githubactions&logoColor=white" alt="CI" /></a>
  <a href="https://nextjs.org"><img src="https://img.shields.io/badge/WEB-NEXT.JS%2016-000000?style=flat-square&labelColor=555555&logo=nextdotjs&logoColor=white" alt="Next.js 16" /></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/AGENT-PYTHON%203-3776AB?style=flat-square&labelColor=555555&logo=python&logoColor=white" alt="Python" /></a>
  <a href="https://aws.amazon.com/bedrock/"><img src="https://img.shields.io/badge/MODELS-AMAZON%20BEDROCK-FF9900?style=flat-square&labelColor=555555&logo=amazonec2&logoColor=white" alt="Amazon Bedrock" /></a>
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
>   and nothing reaches a supplier or a customer except through a person's approval.

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

#Username : admin@kpn.co.id
password : secret123

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

**5. Execute, then explain.** Bram issues the approved action within authority, drafts the customer and
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
| **Iris** | `inventory` | Which stock may actually be used — quality holds, rejected batches, safety floors | 5 | Read only |
| **Clint** | `sourcing` | Replacement supply: other suppliers, internal stock, fast freight, substitute materials with their approval status | 3 | Read only |
| **Prita** | `procurement` | The supplier book: volume, country, certificate, on-time record; quotations compared on price against lead time; drafts the purchase order | 7 | Read only (drafts wait for approval) |
| **Milo** | `logistics` | Arrival dates that survive contact with reality — measured customs dwell, port status, weather, news and holidays on the lane | 8 | Read only |
| **Kira** ⚖️ | `compliance` | Tests every candidate against TKDN, the contract floor, LARTAS licensing and the calendar; says which rules are verified | 3 | **Veto: a rejection here cannot be overturned on cost** |
| **Tara** | `simulation` | Costs the options that cleared the rules, and allocates short material across customer orders. Calls `engine/simulate.py` and `engine/allocate.py` | 2 | Deterministic engines, no model in the arithmetic |
| **Otto** | `precedent` | Institutional memory: what was done last time something like this happened, and how it turned out | 1 | Read only |
| **Bram** | `execution` | Issues approved actions as documents, tells the affected roles, drafts customer and supplier messages, records the outcome | 9 | Within its authority, and only after approval |
| **Vega** | `exposure` | Prevent mode: hunts risk that has not happened yet, ranked by what it would cost | 3 | Recommends; Bram raises it, a person approves |

49 tools across the twelve: **40 read, 9 write**. Every one of the nine belongs to Bram, so
eleven agents cannot change a record at all, and nothing leaves the company except as a draft
a person approves.

Every agent's tools, parameters and prompts are **generated from the registry** into
[`aera/AGENT-REFERENCE.md`](aera/AGENT-REFERENCE.md) by `python3 manage.py docs`, so the
document cannot disagree with the code.

### What every agent can also do

Two things sit outside the roster above, because they are about how an agent works rather
than what it knows.

**`use_skill(name)` — work through a written procedure.** A tool is one call; a skill is a
named procedure that composes several of them in an order somebody decided once, so the order
is not re-derived, differently, on every handling. Calling it returns the steps and is
recorded. Three consequences:

- A skill restricted to an agent is *enforced*, not merely described: `close_the_loop` is
  Bram's, and anybody else asking is told whose it is.
- A skill asked for by a name nobody wrote is recorded too. That count is the useful one — a
  model reaching for a procedure that does not exist is a gap in the catalogue and the only
  evidence of it.
- A procedure is never evidence. It says how to look, not what is there, so it cannot be what
  an action rests on (`tools/execution.py`, the same exclusion precedent has).

Five are written in `core/skills.py`; four of those are what `/mcp` serves as prompts. Operators add their own at `/skills`, validated on save with the same checks the
built-in catalogue meets at build time — no unknown tool, no unknown agent, no procedure
restricted to an agent that cannot reach its own tools, no skill without steps.

**Tools on MCP servers AERA does not operate.** Registered at `/mcp`, granted per agent, and
namespaced `mcp__<server>__<tool>` before anything sees them. Four limits, each on authority
rather than plumbing:

| Limit | Why |
|---|---|
| Read-only only, and a server that did not annotate its tool counts as a writer | The test is the server's own declaration, never a guess from the tool's name |
| A remote tool whose bare name is already ours is dropped | A remote `check_local_constraints` can never stand in for Kira's |
| Never re-exported over our own `/mcp` | We do not hand a caller a third party's tool as though it were AERA's |
| Never evidence | We cannot audit it, and a person has to sign what it would otherwise support |

What connects today is anything speaking **streamable HTTP** with no auth or a static bearer
token — a JSON body or an SSE frame, both are read. What does not: **stdio** servers (most of
`awslabs/mcp`), and anything wanting **OAuth 2.1** (Atlassian, Notion) or SigV4. For those the
route is a local bridge that fronts the stdio server over HTTP.

### Approval limits

Enforced server-side in `core/identity.py`, never in the UI:

| Role | May approve up to |
|---|---|
| `planner` | read only |
| `buyer` | Rp 500,000,000 |
| `procurement_lead` | Rp 10,000,000,000 |
| `admin` | Rp 10,000,000,000 |

Below `AERA_AUTONOMOUS_LIMIT_IDR` (default Rp 50 million) the system may act unattended; above
it, a person must sign. Model spend per event is capped by `AERA_COST_CAP_IDR`.

### The origin label every fact carries

| Label | Meaning |
|---|---|
| `live` | Read from the real source just now (an upload, an outside feed) |
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
  ├─ Bram: the action written up, drafted emails attached, payload ready to issue
  ├─ a person approves, within their role's limit (checked server-side)
  └─ delivery: sender.py → document   ·   notify.py → email, team channels, morning digest 07:30
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
- **Schedule**: eight jobs that run without a person — three signal watchers, Vega's exposure
  scan, the TKDN certificate watch, alert and outreach delivery, the action sender and the 07:30
  digest; each toggleable and runnable by hand
- **Contacts and notifications**: who is told about what, by email or team channel, with a
  mailbox you connect and a test button; approved supplier and customer messages go out
  verbatim from the draft
- **Uploads**: bring your own data with downloadable templates; every read is labelled with
  where it came from
- **Data audit**: `engine/audit.py` reads whatever the system can see and reports what is
  wrong with it — deterministic, every finding carries its evidence
- **Models page**: list, test and switch the model behind each agent (`provider:model` on
  Bedrock or Mantle), with a ping that proves it answers
- **MCP, both directions**: the agent service exposes `/mcp` — 49 tools with `readOnlyHint`
  annotations, 3 resources, 4 prompts — so AgentCore Gateway or any MCP client can call the same tools
  the swarm uses; and it calls *out* to servers somebody else operates, read-only and granted
  per agent
- **Skills**: named procedures agents work through instead of improvising the order, metered
  including the ones named but never written, and extendable from `/skills`
- **Action issuing**: an approved order, transfer or sourcing event is issued as a local
  document with a stable number derived from its idempotency key
- **Auth**: session tokens signed by `AERA_SECRET`, identity from the token, `AERA_ENV=prod`
  refuses to start without a reachable lead model

---

## Visual Walkthrough & Core Screenshots

### 1. Decision Queue (Antrean Keputusan & Triage Gangguan)
Real-time triage untuk setiap insiden rantai pasok (gempa BMKG, penutupan pelabuhan, penahanan bea cukai, kegagalan inspeksi batch). Menampilkan estimasi dampak, status penanganan otomatis, dan biaya model.

![Decision Queue](public/screenshots/01-decision-queue.png)

---

### 2. Multi-Agent Conversation & Live Orchestration Panel ⭐

#### A. Hasil Analisis Percakapan & Rekomendasi
Hasil konsultasi dengan **Arya** (Lead) menganalisis lampiran file sampel `MaterialStock.csv`. Sistem menghitung sisa hari cover stok material kritis (tabel M-4436, M-4417, M-4456), mengidentifikasi data perusahaan yang belum lengkap secara jujur, dan merumuskan mitigasi terstruktur.

![Chat Response & Analysis Table](public/screenshots/04a-chat-response.png)

#### B. Panel Live Orchestration (Langkah Kerja Agen di Sisi Kanan)
Panel kerja spesialis saat menelusuri data: memperlihatkan delegasi dinamis Arya ke 6 agen (Iris, Elsa, Dara, Clint, Prita, Otto), alur penalaran internal (*thinking*), hingga eksekusi 24 data checks dan tool calls nyata per langkah.

![Live Agent Orchestration Panel](public/screenshots/04-chat-agents-orchestration.png)

---

### 3. Disruption Investigation & Multi-Agent Reasoning Trail
Analisis terperinci terhadap setiap gangguan suplai (seperti penutupan Pelabuhan Ningbo). Menampilkan rekomendasi terstruktur, validasi ketiadaan asumsi liar, serta rekam jejak penalaran agen lintas peran (*Delegation, Data Check, Finding, Summary*).

![Disruption Reasoning Trail](public/screenshots/03-disruption-reasoning.png)

---

### 4. Executive Supply Chain Dashboard
Dasbor komprehensif untuk memantau kesehatan rantai pasok: proyeksi hari habis stok material kritis, dampak penegakan aturan (*cost of compliance* TKDN), status pengiriman tertunda, dan ringkasan biaya model.

![Dashboard Overview](public/screenshots/02-dashboard.png)

---

### 5. Audit Trail & Decision Log
Pencatatan setiap langkah eksekusi, persetujuan transaksi berbasis limit wewenang (*server-side authority check*), dan riwayat tindakan yang diterbitkan untuk kepatuhan tata kelola perusahaan (*enterprise governance*).

![Decision Log](public/screenshots/05-audit-trail-log.png)

---

### 6. Agent Council & Tool Registry
Direktori 12 agen mandiri dengan kesiapan 46/46 tool dan 12/12 prompt tersertifikasi. Dilengkapi board bersama (*shared board*) tempat spesialis bertukar temuan tanpa bottleneck.

![Agent Team Directory](public/screenshots/06-agent-team.png)

---

### 7. Disruption Reports & Document Export
Pembuatan laporan operasional instan untuk setiap penanganan insiden atau portofolio global, siap diunduh dalam format PDF resmi dan lembar kerja Excel (XLSX).

![Reports Export](public/screenshots/07-reports-export.png)

---

### 8. Master Data Uploads & Provenance Verification
Modul unggah CSV untuk memperkaya data master perusahaan dengan validasi skema ketat. Mendukung pelabelan sumber data secara transparan (`cached` vs `modelled`).

![Data Uploads](public/screenshots/08-data-uploads.png)

---

### 9. Autonomous Background Watchers & Schedule
Manajemen 8 jadwal tugas otonom tanpa campur tangan manusia: pemantau gempa BMKG (5 mnt), bahaya global GDACS/NASA (30 mnt), cuaca Open-Meteo (3 jam), audit sertifikat TKDN (harian), penerbitan aksi yang disetujui (10 mnt), dan ringkasan harian (07:30 WIB).

![Schedule Watchers](public/screenshots/09-schedule-watchers.png)

---

### 10. Multi-Model Configuration & Routing
Pengaturan model AI fleksibel per peran agen (Bedrock Claude Haiku/Sonnet/Opus, Mantle DeepSeek, GLM, MiniMax, Qwen, Kimi) lengkap dengan konfigurasi model fallback dan uji respons langsung (*ping test*).

![Models Configuration](public/screenshots/10-models-configuration.png)

---

### 11. Stakeholder Contacts & Multi-Channel Alerts
Pusat distribusi notifikasi otomatis ke tim internal (Buyer, Planner, Head of Procurement, QA) melalui Email (Composio/Gmail), Slack, Telegram, dan Webhook begitu insiden terjadi.

![Contacts & Alerts](public/screenshots/11-contacts-alerts.png)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web app | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, shadcn-ui, D3 |
| Agent service | Python, stdlib `http.server` + `sqlite3`; `anthropic` only when Bedrock is configured |
| Models | Amazon Bedrock (Claude by default), Mantle — one model per agent, with a fallback |
| Persistence | SQLite (`data/sigap.db`): events, runs, steps, actions, approvals, contacts, outbox |
| Outside feeds | BMKG · GDACS · NASA EONET · USGS · Open-Meteo · holidays · FX · news, each labelled |
| Company data | CSV uploads (`POST /uploads`), shipped fixtures when nothing is uploaded |
| Interfaces | REST (61 routes, session required except `/health` and `/login`) · MCP (`/mcp`) |
| Delivery | Email (SMTP outbox with retries) and team channels, quoted from the record |
| Containers | Docker Compose: Next.js web, Python agent service, PostgreSQL |
| CI/CD | GitHub Actions: lint, agent output, Python self-check on every push; SSH deploy from `main` to EC2 |
| Tests | Python self-check, transport and rollback tests for the deploy scripts |

### The stack, drawn

```mermaid
flowchart TB
    subgraph CLIENT["Who talks to it"]
        U["Browser — the app at :3000"]
        EXT["External clients over MCP"]
    end

    subgraph WEB["Docker: web — Next.js 16 · React 19 · Tailwind v4 · shadcn-ui · D3"]
        P["app/(app) pages, server components"]
        PX["/api/aera proxy — attaches the session token"]
        LI["/api/login — httpOnly cookie"]
    end

    subgraph AGENT["Docker: agents — Python, stdlib http.server + sqlite3"]
        API["api.py :8787 — 48 routes"]
        GR["graph.py — Arya + 11 specialists<br/>14 rounds · 600 s · spend cap"]
        REG["core/registry.py — 49 tools"]
        ENG["engines — simulate · allocate · forecast<br/>matching · audit · report · export"]
        SCH["core/schedule.py — 8 jobs"]
        SND["sender.py — approved actions"]
        OUT["notify.py · outreach.py — the outbox"]
        DB[("SQLite — the record")]
    end

    subgraph AWSS["AWS"]
        BR["Bedrock — Claude Opus for Arya &amp; Kira<br/>Mantle: MiniMax for the specialists<br/>Haiku for report prose"]
        EC2["EC2 Ubuntu — aera-web · aera-agent (systemd)"]
        IAM["IAM role — the only credential AWS sees"]
    end

    subgraph DATA["Company data"]
        UP["CSV uploads — cached"]
        FX["fixtures — modelled"]
    end

    subgraph FEEDS["Public feeds, all labelled"]
        F1["BMKG · GDACS · NASA EONET · USGS"]
        F2["Open-Meteo · Nager.Date · Frankfurter · News RSS"]
    end

    subgraph DELIVERY["Delivery"]
        CH["Email — SMTP or Composio Gmail"]
        TC["Slack · Telegram · webhook"]
    end

    GH["GitHub Actions — CI on every push,<br/>SSH deploy from main to EC2"]

    U --> P
    LI --> API
    P --> PX --> API
    EXT -->|POST /mcp, no model| API

    API --> GR --> REG
    REG --> ENG
    API --> DB
    GR -->|models| BR

    SCH --> F1
    SCH --> F2
    SCH --> SND --> DB
    REG -->|reads| UP
    REG -->|reads| FX
    SCH --> OUT --> CH
    OUT --> TC

    GH --> EC2
    EC2 -.->|"runs the same images"| WEB
    EC2 -.-> AGENT

    style BR fill:#FF9900,color:#000
    style DB fill:#16a34a,color:#fff
    style GH fill:#181717,color:#fff
```

Locally that is `docker compose up` (web container, agents container, Postgres). In
production the same two images run as `aera-web.service` and `aera-agent.service` on an
Ubuntu EC2 instance, deployed over SSH by GitHub Actions when a push to `main` passes CI —
[`ops/CICD.md`](ops/CICD.md) is the runbook, and the instance's IAM role is what lets the
agent service call Bedrock.

---

## Architecture

> The one-page version lives in [`aera/ARCHITECTURE.md`](aera/ARCHITECTURE.md). Paths
> below are relative to `aera/agent/`
> unless they begin with `app/`, `components/` or `lib/`.

### System context

Two processes, one record.

```mermaid
flowchart LR
    B[Browser] --> N["Next.js :3000<br/>the app pages"]
    N -->|proxy attaches the session token| A["Agent service :8787<br/>api.py"]
    A --> DB[(SQLite)]
    A --> M["Models<br/>Bedrock · Mantle"]
    A --> S["CSV uploads<br/>or fixtures"]
    A --> F["Feeds<br/>BMKG · GDACS · EONET · USGS · Open-Meteo"]
    A --> O["Outbox<br/>email · Slack · Telegram · webhook"]
    A -.->|AERA_GRAPH=1| G["graph_nodes · graph_edges"]
```

| Process | Where | Job |
|---|---|---|
| Web app | `app/(app)/**`, `app/lib.ts`, `app/api/aera/[...path]` | Server components read the agent service at render time; buttons POST through the proxy, which attaches the token. **The app holds no data and makes no decision** |
| Agent service | `aera/agent/api.py` | Routes matched by regex from the `@route` table, one thread per request, runs the schedule, starts each handling on its own daemon thread |

Every route but `GET /health` and `POST /login` needs a bearer token. With `AERA_ENV=prod`
the service refuses to start without a lead model it can call, and
`POST /events` answers `503` while it is missing.

### The agent team

```mermaid
flowchart TB
    EVT["Event: POST /events, or a watcher"] --> ARYA

    subgraph DECIDE["Deciders: AERA_MODEL"]
        ARYA["Arya · supervisor · effort high"]
        KIRA["Kira · compliance · holds the veto"]
    end

    subgraph GATHER["Specialists: AERA_MODEL_SPECIALISTS"]
        ELSA["Elsa · Impact"]
        DARA["Dara · Demand"]
        IRIS["Iris · Stock Validity"]
        CLINT["Clint · Sourcing"]
        PRITA["Prita · Procurement"]
        MILO["Milo · Logistics"]
        TARA["Tara · Costing"]
        OTTO["Otto · Precedent"]
        BRAM["Bram · Execution"]
        VEGA["Vega · Risk Scanner"]
    end

    ARYA -->|"ask_impact · ask_demand · ask_inventory"| ELSA
    ARYA -->|"ask_sourcing · ask_procurement"| CLINT
    ARYA -->|"ask_logistics · ask_precedent"| MILO
    ARYA -->|"ask_compliance"| KIRA
    ARYA -->|"ask_simulation"| TARA
    ARYA -->|"ask_execution · ask_exposure"| BRAM

    KIRA -.->|"rulings Tara costs against"| TARA
    BRAM -->|"raise_action"| ACT["actions: pending for a person, or autonomous"]
    PRITA -->|"propose_purchase_order"| ACT

    BOARD["Shared board: every tool result with its origin and source"]
    GATHER --- BOARD
    DECIDE --- BOARD
```

**Delegation has no fixed pipeline.** Each specialist is offered to the lead as one tool,
`ask_<code>`, described by its nickname, title and brief ("HAS VETO." for Kira). A
specialist sees only its own tools, so specialists cannot call one another — every hand-off
goes through the lead.

**The board is the evidence of one handling.** Every tool result is written under
`<agent>.<tool>` with its origin, source and fetch time, so no value can exist on the board
without saying where it came from. `Board.untrusted_keys()` — everything that is not
`live`, `cached` or `derived` — travels into the run's decision, the alert, the report and
Bram's autonomy check.

Inside the loop: at most **14 lead rounds**, **8 rounds per specialist**, **600 seconds** and
a spend cap (`AERA_COST_CAP_IDR`, default Rp 500,000). Progress is written as `steps` rows:
`DELEGATE`, `TOOL` (arguments, result, origin, source, milliseconds), `FINDING`, `SUMMARY`,
`FALLBACK`. One specialist failing does not end the handling — the lead is told to carry on
without it.

| How a handling ends | `decision.status` | Cause |
|---|---|---|
| The lead writes its answer | `done` | `end_turn` |
| A limit is hit | `partial` | spend over the cap, or 600 s elapsed — salvage lists what is on the board and writes no recommendation |
| Out of lead rounds | `stopped` | more than 14 rounds |
| Anything else raised | `failed` | the error is stored on the run |
| No model the lead can call | `held` | closed at once; nothing runs |

### Kira's veto, held in four places

1. **`tools/compliance.py`** — `check_local_constraints` rules one option at a time from
   the rule pack, the company profile and the holiday calendar, naming the rule and the
   numbers. The ruling is Python, whatever model Kira runs on
2. **`engine/simulate.py`** — costs only options that cleared. `allowed_options` can narrow
   the rulings, never widen them, and an option the rules struck out stays out even when a
   list names it. It also reports `compliance_cost`: what obeying the rules cost
3. **The prompts** — `supervisor.txt` never recommends an option Kira rejected,
   `execution.txt` never acts on one, not at a lower quantity, not partially
4. **The exploration graph** — Kira's ruling is a `ruling` node, and the planner
   (`engine/planner.py`) opens a price lead only for an option ruled `allowed`

### Models per agent

A model is named `provider:model`, resolved per call:

| Provider | Wire format | Where |
|---|---|---|
| `bedrock` | Anthropic Messages | Claude on Amazon Bedrock |
| `bedrock-openai` | OpenAI Chat Completions | other models on Bedrock (MiniMax, DeepSeek, Kimi, Qwen, GLM…) |

Resolution order, most specific first — a choice saved on the **Models** page beats the
variable at the same level:

1. one agent — `<code>` / `AERA_MODEL_<CODE>`
2. the ten specialists — `specialists` / `AERA_MODEL_SPECIALISTS`
3. the lead and everyone else — `lead` / `AERA_MODEL` (default `anthropic.claude-opus-5`)
4. **fallback**, tried once when an agent's own model fails — `AERA_MODEL_FALLBACK`
5. **aux**, which writes report prose from figures it is handed and never a number

Arya and Kira skip level 2: the agent that decides what to do, and the one that decides what
may be done, stay on the strong model unless set one by one. `GET /models` lists every
agent's model and whether it answers.

### The autonomy limit

`AERA_AUTONOMOUS_LIMIT_IDR` (default Rp 50,000,000) is the ceiling for an action taken
without a person. `tools/execution.py autonomy_check` lets one go alone only when all four
hold: under the limit · raised inside a handling (there is a board) · nothing on the board
is `modelled` or `missing` · something was read before deciding.

Only `create_stock_transfer` asks that question. Every other change to the outside world —
`create_draft_po`, `propose_purchase_order`, `create_sourcing_event`,
`propose_safety_stock_change`, `draft_customer_notice`, `request_supplier_update` — is
recorded `pending` and waits for a person whatever its value.

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
    participant X as Documents · Email · Channels

    F->>API: signal → event (deduped)
    API->>A: handling starts
    A->>S: ask_impact → ask_sourcing → ask_logistics (one at a time)
    S-->>API: Result{value, origin, source}
    API->>K: rules check, then deterministic costing
    K-->>DB: options struck out, with reasons
    API->>DB: run, steps, trace, proposed action
    W->>API: decision queue
    P->>W: approve (limit checked in core/identity.py)
    API->>X: sender.py issues the document · notify.py quotes the record
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
    A -->|yes| S[sender.py → issued document]
    A -->|no| H[Held in the queue]
    X --> L[Decision log]
    N --> L
    S --> L
    H --> L

    style X fill:#dc2626,color:#fff
    style N fill:#dc2626,color:#fff
    style S fill:#16a34a,color:#fff
```

Every path ends in the decision log. There is no route to an issued document or to an outside party that does
not pass through a person's approval first.

### The tools and the data path

`core/registry.py` holds one `Tool` per name: owner, description, JSON schema and the
function that runs. The schema the model sees is the schema that runs (`strict: true`,
`additionalProperties: false`), and **every tool returns a `Result`, never a bare value**.
An argument naming a material or a plant is checked before the tool runs — an id on record
passes, an ambiguous phrase raises back to the model rather than returning "nothing found".

Reads fall through two sources, and the label says which:

```
tools/fetcher.py   →  an uploaded CSV (cached)  →  fixtures/ (modelled)
                                                    a failed fetch → missing
```

| Agent | Tools | What it reads |
|---|---|---|
| Arya `supervisor` | 1 | the `events` table |
| Elsa `impact` | 4 | purchase orders, material stock, BOM explosion, sales-order commitments |
| Dara `demand` | 3 | production schedule, 90 days of goods issues → `engine/forecast.py` |
| Iris `inventory` | 5 | quality holds, safety-stock policy, transfer checks, replenishment policy, deadstock → `engine/matching.py` |
| Clint `sourcing` | 3 | alternate sources, internal transfers, substitute materials |
| Prita `procurement` | 7 | supplier book, quotations, exchange rates (ECB), blanket orders, drafts a `draft_po` action |
| Milo `logistics` | 8 | shipment status, ETA from measured customs dwell, customs status, port weather, news, holidays, shipments at a port, bonded stock |
| Kira `compliance` | 3 | the rule pack, the company profile, the holiday calendar |
| Tara `simulation` | 2 | `engine/simulate.py`, `engine/allocate.py` — arithmetic with no model in it |
| Otto `precedent` | 1 | past incidents, their outcomes, what was done |
| Bram `execution` | 9 | raises actions, drafts outward messages, records outcomes, watches through to receipt |
| Vega `exposure` | 3 | single sources, concentrated lanes, certificate lapse, live hazards |

**The rule pack** (`aera/references/`) is what Kira rules from: each rule carries its source
and whether it was verified. It is read by `tools/compliance.py` and shown by `get_rule_pack`.
The pack itself is knowledge work written per company, not code.

### Workers: what runs without a person

One Python process. `core/schedule.py` ticks every 15 seconds and starts whatever is due; a
job never overlaps itself, its next run is remembered in the `jobs` table, and a daily job
missed by more than two hours is skipped rather than delivered late.

| Job | Cadence | Effect |
|---|---|---|
| `bmkg` | 5 min | a quake of M5.0+ within 300 km of a facility becomes an event |
| `hazards` | 30 min | cyclone, flood, quake, eruption, fire or drought within radius of a plant or loading port |
| `weather` | 3 h | a forecast day over threshold at a port or plant (gusts 62 km/h, waves 4 m, rain 100 mm/day) |
| `exposure` | weekly | Vega's scan with **no model**: the top three findings by committed value |
| `notify` | 30 s | delivers the outbox — alerts, digests, reports, outreach |
| `send` | 10 min | approved actions issued as documents |
| `digest` | daily 07:30 WIB | the morning summary to every contact who chose it, and the team channels |

Every watcher dedupes against the record (`store.event_exists`) and raises the event through
the same call a person's `POST /events` makes, so a restart never replays a feed. Every
outside GET goes through `clients/feeds.py`: a cache that keeps the real fetch time, a
timeout, and a short memory of a failure — a feed that is down costs one timeout and becomes
`missing`, never a quiet day.

**Approve, then send.** An action is a row in `actions`, and its status only moves forward:

```
tool raises it → pending (decision queue) → approved (role limit checked server-side)
                → sender.py → a document numbered from its idempotency key → sent
                → or outreach → the outbox → email, as written, never composed here
                → outcome recorded once
```

A failed write keeps the status and is retried next pass; a decided action cannot be decided
again; a rejection releases the stock the action was holding in the same transaction. Outreach
needs a buyer above for a supplier request and a procurement lead above for a customer notice,
on top of the money limit — and outside `prod` nothing reaches a real partner, it goes to
`AERA_EXTERNAL_REDIRECT` marked `[TEST]`.

**Channels**: SMTP, Composio Gmail, Slack, Telegram or a webhook. A channel that is not set
up marks its messages `skipped` with what it lacks rather than holding them; a failure is
retried three times, then `failed`.

### The record, and what comes out

One SQLite file (`AERA_DB`, default `data/sigap.db`). What lands there is the official
record: what was decided, on what evidence, who approved it and what was actually sent.
`approvals` rows are never changed; an `actions` row moves one way; a correction is a new row.

| Group | Tables |
|---|---|
| The handling | `events` · `runs` · `steps` · `actions` · `approvals` · `reservations` |
| Exploration | `graph_nodes` · `graph_edges` (with `AERA_GRAPH=1`) |
| People and settings | `users` · `conversations` · `messages` · `contacts` · `uploads` · `settings` · `jobs` |
| Delivery | `notifications` — one message to one address over one channel, with its status and attempts |

Everything the system produces is built from that record:

- **Reports** — per handling or across the whole portfolio, markdown, PDF and XLSX, written
  with the Python standard library (`engine/report.py`, `engine/export.py`). The only text a
  model writes is the optional executive summary, handed the figures and told not to
  introduce a number
- **The trace** — `core/topology.py` folds the steps into a graph of event → agent → tool →
  source → action, each edge carrying its calls, step numbers and weakest origin; drawn on
  `/log/[id]`
- **The exploration graph** — the same handling as a DAG, served by `GET /runs/{id}/graph`
  and drawn on `/disruptions/[id]`
- **Alerts** — the message as sent: status, the lead's recommendation quoted and labelled,
  what waits for approval with the lowest role that may approve it, and a warning when
  evidence was modelled or missing
- **Issued documents** — each numbered from the action's idempotency key, stored as the
  action's `reference`
- **[`aera/AGENT-REFERENCE.md`](aera/AGENT-REFERENCE.md)** — regenerated from the live
  registry by `python3 manage.py docs`, so it cannot disagree with the code

### The pages

| URL | Shows |
|---|---|
| `/` | the decision queue: every handling, what it proposes, what it costs, what waits for a signature |
| `/dashboard` | exposure, orders at risk, what is blocked and why |
| `/disruptions/[id]` | one handling: recommendation, actions, approvals, the exploration graph |
| `/log`, `/log/[id]` | every run, and one run's trace — each tool call with its origin |
| `/reports`, `/reports/[id]`, `/reports/portfolio` | reports and the portfolio, as PDF/XLSX or emailed from the page |
| `/agents`, `/agents/[code]`, `/chat` | the twelve, their tools, their data, and a conversation with any of them |
| `/audit` | what is wrong with the data the system can see, with its evidence |
| `/uploads` | bring your own data, with downloadable templates |
| `/contacts`, `/notifications` | who is told about what, and by which channel |
| `/models` | the model behind each agent, testable from the page |
| `/schedule` | the eight jobs: on/off, last result, run now |

A page whose handling is running refreshes every four seconds while the tab is visible, so
the queue, a disruption and its trace follow the agents without a reload.

### The other ways an agent runs

| Entry | What runs | Records |
|---|---|---|
| `POST /agents/{code}/ask` (the conversation page) | one specialist's tool loop on your question, with chat history and attachments | conversations and messages; an action raised from a question comes back `missing` — actions come from a signal |
| `POST /mcp` | the same registry tools, called directly, **no model** | only what the tool itself writes |
| `GET /exposure`, the `exposure` job | Vega's scan through the registry, **no model** | the top three become events |
| `python3 main.py` | a scripted walk of the design scenario, **no model**, real calculator | a JSON trace only |
| `python3 graph.py` | the orchestration's self-check on a stand-in model and a scratch database | nothing in the real record |

Two flags, both off by default, change how a handling runs:

| Flag | Turns on |
|---|---|
| `AERA_GRAPH=1` | the exploration graph: board writes mirrored as `fact` nodes, Clint's options as `option`, Kira's rulings as `ruling`, and the deterministic planner opening the next leads. Fail-open: a graph error never touches the handling |
| `AERA_SWARM_ASYNC=1` | `engine/dispatch.py`: several specialists at once over a claimable frontier on `AERA_ASYNC_WORKERS` threads (default 4), with `core/admission.py` bounding work per operator and globally. Arya writes the recommendation once, from the settled graph |

The planner is deterministic because the mitigation chain is known:

```mermaid
flowchart LR
    E["event"] -->|spawns| IMP["lead impact:event, Elsa"]
    E -->|per material| SRC["lead source:material, Clint"]
    SRC -->|yields| OPT["option nodes"]
    OPT -->|no ruling yet| RULE["lead rule:option, Kira"]
    RULE -->|rules_on| RUL{"ruling"}
    RUL -->|allowed, not priced| PRICE["lead price:option, Tara"]
    RUL -->|blocked| STOP["no further lead"]
    PRICE --> FIN["Arya writes the recommendation"]
    IMP --> FIN

    style STOP fill:#dc2626,color:#fff
```

---

## Run it

### Option A: Docker Compose (recommended)

Runs all three containers — **Next.js web**, **Python agent service** and **PostgreSQL** —
with one command.

```bash
# 1. prepare the environment file
cp aera/agent/.env.example aera/agent/.env     # see aera/ENV.md for every line

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
cd aera/agent
python3 manage.py secret                  # export its output as AERA_SECRET
python3 manage.py user you@example.com "Your Name" buyer yourpassword
python3 manage.py seed                    # optional demo data
python3 api.py                            # :8787

# the interface, in another terminal
npm install
AERA_API=http://127.0.0.1:8787 npm run dev
open http://localhost:3000/dashboard
```

Nothing else needs starting: `api.py` runs the schedule, which watches the feeds, delivers
alerts and issues approved actions.

To see what is and is not wired up:

```bash
cd aera/agent && PYTHONPATH=. python3 manage.py check
```

With no accounts anywhere, the four-line fast path in [`aera/ENV.md`](aera/ENV.md) brings
the whole system up on fixtures. Everything from a fixture is labelled `modelled`, so the
calculator will not price it — production refuses to run without a real model.

---

## Documentation

Everything lives in [`aera/`](aera/):

| File | What's in it |
|---|---|
| [`aera/ARCHITECTURE.md`](aera/ARCHITECTURE.md) ⭐ | **One page**: the tech stack and why each piece, eight diagrams, the decisions and what they cost |
| [`aera/AGENT-REFERENCE.md`](aera/AGENT-REFERENCE.md) | All 12 agents and their 49 tools, **generated** from the registry |
| [`aera/DEMO.md`](aera/DEMO.md) | The 6–7 minute demo storyboard: pre-flight, six scenes, judge Q&A |
| [`aera/ENV.md`](aera/ENV.md) | Every environment variable, where to get it, how to check it works |
| [`aera/SETUP.md`](aera/SETUP.md) | The ordered walkthrough for a first-time setup |
| [`aera/DESIGN.md`](aera/DESIGN.md) | The scenario and its figures, the constraint rules, the eval suite |
| [`aera/TECHNICAL.md`](aera/TECHNICAL.md) | Model calling conventions, caching, limits |
| [`aera/DATA-SOURCES.md`](aera/DATA-SOURCES.md) | What was verified about each data source |
| [`aera/agent/README.md`](aera/agent/README.md) | Running the agent service, configuration, the API |
| [`ops/CICD.md`](ops/CICD.md) | GitHub Actions: CI on all branches, SSH deployment from main to EC2 |

---

## Status

`PYTHONPATH=. python3 manage.py check` prints this live, from the code rather than from a table.

**Working**: provenance labelling on every tool, the deterministic calculator, CSV uploads,
persistence with idempotent actions and one-shot approvals, auth with server-side authority
limits, the full interface, all 49 tools, all 12 prompts, the signal watchers (BMKG, hazards,
weather), the schedule, email and outreach delivery, reports by email, the data audit, and the
agent team running end to end.

**Held back honestly**: approved actions are issued as local documents, not posted to an ERP; the
rule pack (`aera/references/`) is read but not written — that is knowledge work, not code;
`AWS_REGION` unset means the team has not run against Bedrock yet, and until a model is
reachable the system makes no decisions at all rather than pretending to.

---

## License

MIT — see [`LICENSE`](LICENSE).
