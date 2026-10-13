# Building SIGAP on AWS and SAP

> What runs where, which service does which job, and what is wired versus what
> is only named. Written 29 September 2026.
>
> `AWS-PLAN.md` has the **order** of the AWS work and the reasoning behind the
> Runtime decision. `DATA-SOURCES.md` has **where each kind of data comes from**
> and how it was verified. This file is the **wiring**: the service list on both
> sides, and the paths a request takes through them.

---

## 1. The case, in one page

PT Karya Presisi Nusantara, a Tier-1 automotive component maker. Two plants,
KRW1 Karawang and SBY1 Surabaya. 340 active materials, 61% of raw-material value
imported, mostly through Tanjung Priok. The OEM contract requires TKDN of at
least 40%; the portfolio sits at 38.2%.

A typhoon closes Ningbo-Zhoushan for six days. PO 4500018872, 120 t of M-4471
aluminium alloy ingot, slips from 14 September to 22 September. KRW1 holds 84 t
and the master data says it burns 9.2 t a day, so it empties on 13 September.
Nine days with no material, against three OEM sales orders worth Rp 2.14 billion
and a late penalty of 0.5% a day capped at 10%.

What the system does with that:

1. Works out what the disruption actually hits, and how deep the hole is
2. Assembles the ways out: air freight, a local supplier, a transfer from SBY1
3. Strikes the ones that breach TKDN or need an import licence that will not
   arrive in time. **This veto is arithmetic, not a prompt, and cannot be
   overturned on cost**
4. Prices what is left and recommends one
5. Executes it into SAP once someone with the authority approves, or on its own
   authority below Rp 50 million
6. Watches until the goods land

Three things about the case are the product, and everything below serves them:

- **The plant does not run at 9.2.** It has run at 10.33 for a month. The gap is
  118.4 t, not 82.8 t, and the 85 t air freight option does not bridge it.
  `engine/forecast.py` is what finds that.
- **The transfer from SBY1 breaks SBY1.** Moving 55 t drops it from 18.0 to 12.3
  days, under its own 14 day floor, emptying 16 September while its own PO lands
  24 September. `engine/matching.py` judges a transfer from both ends.
- **Every figure says where it came from.** `LIVE`, `CACHED`, `DERIVED`,
  `MODELLED`, `MISSING`. The calculator refuses to produce a rupiah figure from
  untrusted inputs rather than producing a confident wrong one.

---

## 2. Two clouds, one line

| | AWS | SAP |
|---|---|---|
| Job | Where the agents **think and run** | Where the **record** lives and where an action **takes effect** |
| Protocol at the boundary | MCP, once on Gateway. HTTPS + OData today | OData V2 |
| Today | `AWS_REGION` empty, so the model has never run | Sandbox reachable with a free key. `SAP_API_KEY` not set |

---

## 3. AWS: the service list

Ordering, exit tests and cost are in `AWS-PLAN.md` §4 and §5. This is the list.

### Adopted

| Service | What it carries in SIGAP |
|---|---|
| **Bedrock**, `anthropic.claude-opus-5` | Every agent turn. `high` effort for Arya and Kira, `medium` for the rest |
| **AgentCore Runtime** | Hosts `graph.py`. Chosen over Managed Harness because we own the orchestration loop: the supervisor exposes ten specialists as `ask_<code>` tools and decides the route from the last finding |
| **AgentCore Gateway** | The 31 tools in `core/registry.py` as MCP. `registry.schemas_for_model()` already emits the shape Gateway wants |
| **AgentCore Observability** | OTel traces per specialist call, token count and latency. Replaces the placeholder cost rates in `graph.py` with real ones |
| **AgentCore Memory + Knowledge Base** | For Otto only, and now an upgrade rather than a gap. `search_past_incidents` reads the `runs` and `events` tables, so precedent works on exact words today. A Knowledge Base would add semantic recall over the same record, not a second record |
| **AgentCore Evaluation** | The scenario suite in `DESIGN.md` §5, unwritten |
| **ECR** | The Runtime image |

### Declined, on purpose

| Service | Why not |
|---|---|
| **AgentCore Identity** | It authenticates an agent to a tool. `core/identity.py` authenticates a buyer to an approval endpoint. Different problem; swapping would weaken the approval trail |
| **Bedrock Guardrails** | Guardrails filter model output. Kira's veto is Python arithmetic the model cannot talk past, which is strictly stronger |
| **Browser, Code Interpreter, Web Search, Payments** | No use case. Adding them to lengthen the AWS list is the name-dropping the rubric punishes |

### Under review, found 29 September

| Service | Why it matters |
|---|---|
| **AWS for SAP MCP Server** | A container AWS ships at no cost, running on AgentCore Runtime, that exposes SAP OData as MCP tools with catalog discovery and OAuth 2.0 already handled. It did not exist when `clients/sap_s4.py` was written. See §5, it addresses the auth problem directly. `RESEARCH-AWS-SAP.md` §3 has the detail |

---

## 4. SAP: the surface we actually touch

Connector is `clients/sap_s4.py`. Base URL defaults to
`https://sandbox.api.sap.com`, overridable with `SAP_BASE_URL`.

Everything routes through `tools/fetcher.py`, which tries SAP first and falls
back to `fixtures/` when there is no key. **The fallback is never hidden**: the
origin becomes `MODELLED`, which shows on screen and fails the calculator's
trust check.

### Read, ten services

| OData service | What we take from it | Who needs it |
|---|---|---|
| `API_MATERIAL_STOCK_SRV` | On-hand stock per material per plant | Iris, Elsa, Clint, Vega |
| `API_PURCHASEORDER_PROCESS_SRV` | Open POs, ETAs, supplier, quantity | Elsa, Vega |
| `API_SALES_ORDER_SRV` | OEM commitments behind a material | Elsa |
| `API_BILL_OF_MATERIAL_SRV` | Which finished goods a material feeds | Elsa |
| `API_PRODUCT_SRV` | Safety stock floor per material | Iris |
| `API_INSPECTIONLOT_SRV` | Quality holds, so recorded stock is not assumed usable | Iris |
| `API_PRODUCTION_ORDER_2_SRV` | Production schedule and planned consumption rate | Dara |
| `API_PURCHASING_INFO_RECORD_SRV` | Alternate sources for a material | Clint |
| `API_BUSINESS_PARTNER` | Supplier master, for compliance and contact | shared |
| `API_STOCK_TRANSFER_SRV` | Existing transfers, read side | Bram |

### Write, three targets, none verified

`sender.py` maps an approved action to a service and entity:

| Action kind | Service | Entity | Checked 6 Oct |
|---|---|---|---|
| `draft_po` | `API_PURCHASEREQ_PROCESS_SRV` | `A_PurchaseRequisitionHeader` | **verified**, reads back |
| `stock_transfer` | `API_STOCK_TRANSFER_SRV` | `A_StockTransfer` | service 403 |
| `create_sourcing_event` | `API_SOURCING_PROJECT_SRV` | `A_SourcingProject` | service 403 |

The write path is complete, CSRF token fetched then posted.

Checked with a real key. `draft_po` is confirmed: the service answers, the
entity exists, a row reads back. The other two fail at the **service**, not the
entity: `$metadata` on both returns 403 with the key that reads the other ten
services happily, so those APIs are not exposed on the free sandbox and their
entity names remain unverifiable from here.

What that means for the demo: `draft_po` is the one action kind that can be
shown writing into SAP. A stock transfer or a sourcing event needs a system
that carries those services.

---

## 5. Auth, and the thing that will bite

`clients/sap_s4.py` sends an `APIKey` header. That is the SAP Business
Accelerator Hub sandbox scheme, and it works today.

A real customer system does not accept it. S/4HANA Cloud wants a communication
user or OAuth 2.0 through a BTP destination.

So `DATA-SOURCES.md` §1's line, *"change the base URL and the key, the code does
not change"*, is optimistic. The base URL changes, the key changes, **and the
authentication scheme changes**. It is one function, `sap_s4.get()`, so it is a
small change, but it is a change and it should be written down rather than
discovered on the day.

This is exactly what the AWS for SAP MCP Server already solves, and it is the
strongest argument for evaluating it before we write more connector code.

---

## 6. The three paths through the system

### A disruption arrives

```
signals/watch.py, every 5 min -> signals/bmkg.py, or POST /events
  → store.record_event          events table
  → store.start_run             runs table, status running
  → graph.handle in a thread
      → Arya picks a specialist, calls ask_<code>
      → that specialist calls its tools
          → tools/fetcher.py → clients/sap_s4.py → SAP OData
          → no key? → fixtures/, origin MODELLED
      → every result lands on the Board with its origin
      → store.save_step          steps table, one row per turn
      → Kira may veto. Arithmetic, not judgement
      → engine/simulate.py prices what survives
  → store.record_action          idempotency_key, so a retry never doubles a PO
  → under Rp 50m: status sent. Over: status pending
```

### A person approves

```
POST /actions/{id}/decision
  → identity.from_token          identity ONLY from the token, never the body
  → user.may_approve(value)      role cap, server side
  → store.decide_action          one shot; a decided action never changes again
                                 approvals table records who, what role, when
```

### An approved action reaches SAP

```
sender.send_approved
  → for each approved, unsent action
  → sap_s4._csrf_token(service)  fetch
  → sap_s4.post(service, entity, payload)
  → store.mark_sent(sap_reference)
```

Guards that hold regardless of what any model says: `MAX_SPECIALIST_ROUNDS = 8`,
`MAX_LEAD_ROUNDS = 14`, `MAX_SECONDS_PER_EVENT = 600`,
`CFG.cost_cap_per_event_idr`.

---

## 6b. How SAP Joule reaches us

Found on 6 October by reading the CLI's own schema, `da.sapdas.schema.json`,
rather than the manual. A digital assistant manifest has a first-class
`mcp_servers` array:

| Field | Meaning |
|---|---|
| `namespace` + `path` | How the server is addressed. Unique together |
| `type` | Transport |
| `destination.design_time` | A BTP destination used to **list** the tools, with technical credentials |
| `destination.runtime` | A BTP destination used to **call** them, with **principal propagation** |

So Joule does not need a bespoke adapter. It needs our tools as MCP, which is
the same thing AgentCore Gateway wants. `mcp.py` is that surface: a translation
over `core/registry.py`, not a second registry.

Principal propagation on the runtime destination matters more than it looks.
The acting user's identity reaches our tools, which is what makes the role caps
in `core/identity.py` meaningful on a call that arrived through SAP rather than
through our own interface.

**Open question, and it is a real one.** Creating a BTP destination needs write
access to the subaccount, and the hackathon manual says participants get
read-only. If that holds, the destination has to be created by an organiser, or
the integration has to arrive some other way. Worth asking early rather than on
the last weekend.

---

## 7. What moving to Runtime changes

Less than it sounds, which is the point of having owned the loop.

| File | Change |
|---|---|
| `graph.py` | Entry point gets the AgentCore Runtime decorator. The loop itself does not change |
| `core/registry.py` | Same schemas, published over MCP through Gateway instead of passed in-process |
| `core/trace.py` | Also emits OTel spans. Keeps writing `steps`, because that table is the approval record, not a debug log |
| `core/store.py` | Unchanged. SQLite moves to Postgres when this is multi-tenant, not before |
| `core/identity.py` | Unchanged, deliberately |
| `clients/sap_s4.py` | Either gains OAuth, or is replaced by the AWS for SAP MCP Server. Decide before writing more of it |
| `api.py` | Unchanged. It is the interface's bridge, not the agent runtime |
| `mcp.py` | Unchanged. It already speaks what Gateway and Joule both want |

---

## 8. Not built yet

Stated plainly so nobody discovers it during a demo.

| | Status |
|---|---|
| `AWS_REGION` | Empty. `graph.py` has never run against a real model. Everything above is plumbing that a scripted client proves and judgement that nothing proves yet |
| `SAP_API_KEY` | Not set. All ten read services fall back to fixtures, labelled `MODELLED` |
| SAP write entity names | Unverified against the sandbox |
| `references/tkdn-rules.md`, `lartas-procedure.md` | Absent. Kira judges from parameters and labels the result `MODELLED`. Domain work, not code |
| Scenario eval suite | Absent. `RESEARCH-AWS-SAP.md` §6 has the four-level shape to build it against |
| Foreign typhoon signal | Absent. BMKG covers Indonesia only, so the Ningbo trigger has no live source. `signals/watch.py` polls BMKG on a timer and raises quakes near a facility by itself, deduplicated against the record, so the seismic half of perception is autonomous. A foreign maritime feed is not. See `DATA-SOURCES.md` §5 |
