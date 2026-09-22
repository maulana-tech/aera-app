# SIGAP — Plan & Status

> Context: **application development.** Not a competition entry.
> Jargon is decoded in §8 if a word is unfamiliar.
>
> Updated: 22 September 2026

---

## 1. What is being built

An autonomous assistant for manufacturers that import most of their raw material.

When supply is disrupted — a port closes, a supplier misses a shipment, goods are held at
customs — the system investigates the impact itself, assembles the ways out, strikes the
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
| SAP connector (write) | ⚠️ **path complete, untested** | CSRF handled; entity names need checking |
| Persistence | ✅ **working** | SQLite. Idempotent actions, one-shot approvals |
| Auth & authority | ✅ **working** | Identity from the token; value limits checked server-side |
| API service | ✅ **working** | 19 routes |
| Interface | ✅ **working** | Dashboard with charts, queue, detail, approval, per-domain tables, conversations. shadcn-ui |
| Tools | 🔶 **19 of 23** | The other 4 are Prevent-mode only |
| Agent prompts | 🔶 **2 of 11** | Only `supervisor` and `compliance`. The rest raise on invocation |
| Agent team (`graph.py`) | ⚠️ **written, never run** | Waiting on `AWS_REGION` |
| Rule documents (`references/`) | ❌ **absent** | The main blocker. Domain work |
| Scenario eval suite | ❌ **absent** | |
| Prevent mode | ❌ **absent** | Vega has no tools at all yet |

`PYTHONPATH=. python3 manage.py check` prints this live, from the code rather than from
this table.

### What is blocking

1. **`SAP_API_KEY`** — free, 15 minutes. Once set, five read tools use real data and the
   origin label flips from `modelled` to `live`.
2. **`AWS_REGION`** — `graph.py` has never been executed, not once. Until it is set, the
   system honestly holds back and makes no decisions at all.
3. **The nine missing prompts.** An agent with no `prompts/<code>.txt` raises
   `PromptMissing`. Writing them needs nobody's permission.
4. **`references/tkdn-rules.md` and `lartas-procedure.md`** — Kira reads them when they
   exist; without them she judges from parameters and labels the result `modelled`.
   **This is knowledge work, not code** — a programmer cannot write it.

---

## 3. How it works

Picture a small team: a lead, and several specialists with their own areas. The lead does
not do the work — he calls the relevant specialist, one at a time, according to what the
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

### Eleven agents

| Agent | The question it owns |
|---|---|
| **Arya** (lead) | Who do I call next, and when is the evidence enough? |
| Elsa — Impact | Which POs are hit, which customers are exposed? |
| Dara — Demand | Is consumption still that rate, or is demand rising? |
| Iris — Stock Validity | Is the recorded stock actually usable? |
| Clint — Sourcing | Is there another source? |
| Milo — Logistics | Realistically, when does it land? |
| **Kira — Rules** ⭐ | May we use that supplier at all? **Has veto** |
| Tara — Costing | What does it cost, which is cheapest? |
| Otto — Precedent | Has this happened before? How did it end? |
| Bram — Execution | Carry it out, then watch until the goods arrive |
| Vega — Risk Scanner | What is **about** to break? *(Prevent mode)* |

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
| Model | `anthropic.claude-opus-5` via Bedrock |
| Languages | Python (agents) · TypeScript (interface) |
| Persistence | SQLite — move to Postgres once this is multi-tenant |
| Interface | Next.js 16 + React 19 + Tailwind v4 + shadcn-ui |
| API service | stdlib `http.server` — move to FastAPI if you need >10 rps |
| Language of the codebase | English throughout: files, identifiers, DB columns, API keys, UI |

⚠️ Not every AWS region offers Claude. Check first; keep `us-west-2` as the fallback.

---

## 5. Guarantees the code enforces

Not instructions to a model — these are enforced by the program, so no prompt can break them.

1. **A failure never invents a value.** Tool fails → `MISSING`.
2. **The calculator refuses** rupiah figures when its inputs aren't trustworthy.
3. **Actions are idempotent.** The same key never creates a second order.
4. **Identity comes only from the session token.** Claiming a role via the request body
   is ignored.
5. **Authority is checked on the server**, not on the button.
6. **Production refuses to start** without SAP and a model — it may not guess at anything.
7. **A missing prompt raises** rather than sending a placeholder to the model.

The full list, with the reasoning, is in `agent/README.md`.

---

## 6. What to do next

| # | Work | Who | How long |
|---|---|---|---|
| 1 | Get `SAP_API_KEY` at api.sap.com | anyone | 15 min |
| 2 | Enable Bedrock, confirm the region | backend | 1 hour |
| 3 | Write the 9 missing agent prompts | backend + domain | 1–2 days |
| 4 | Run `graph.py` for real, fix what breaks | backend | 1–2 days |
| 5 | Write `references/tkdn-rules.md` + `lartas-procedure.md` | **domain** | 2 days |
| 6 | Verify SAP write entity names in `sender.py` | backend | 1 day |
| 7 | The 4 remaining tools (Prevent mode) | backend + data | 2 days |
| 8 | A 10-scenario eval suite | data | 2 days |
| 9 | Prevent mode end to end | backend | 3 days |

Items 3 and 5 can start now and **wait on nothing.**

---

## 7. File layout

```
sigap/
├── PLAN.md              this file — plan & status
├── AGENT-REFERENCE.md   the 11 agents — GENERATED, run `manage.py docs`
├── DESIGN.md            scenario figures, local rules
├── TECHNICAL.md         exact function names & parameters
├── DATA-SOURCES.md      what was verified about each data source
└── agent/               the code
    ├── core/            provenance · identity · store · config · registry · trace
    ├── clients/         the SAP connector
    ├── tools/           one file per agent, named after the agent code
    ├── engine/          the calculator — pure Python
    ├── agents/          the 11 agent definitions
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
