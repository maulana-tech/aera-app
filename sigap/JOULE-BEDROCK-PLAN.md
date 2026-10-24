# Joule, Bedrock and AI Core: who does what

> Written 24 October 2026. Demo Day is 31 October, so this covers 7 days.
> Grounded in the organisers' repo (`SAP_AWS_Hackathon_ID_2026`: `README.md`,
> `BTP_Instructions/README.md`, `joule_a2a/project/Python-LangGraph/`), the
> Bedrock model cards, and calls actually made on 24 October.

---

## 0. The short version

Joule and Bedrock are not alternatives for the same job.

| | Its job in SIGAP |
|---|---|
| **Joule** | Where a user inside SAP **talks to** SIGAP. A channel, not a brain |
| **Bedrock** | Where the agents **think**. Claude for the decisions, MiniMax for the specialists |
| **AI Core** | SAP's model hub, provided by the organisers. A fallback brain that costs no AWS credit |
| **SIGAP web** | Where a person **approves**. It stays the only place an action can be authorised |

Two splits follow: which interactions go through Joule (§2), and which model
each agent runs on (§4).

---

## 1. What the organisers' material changes

`BUILD-SPEC.md` §6b planned Joule over MCP, with principal propagation. The
organisers' repo says otherwise on both counts.

| Assumed in §6b | What the organisers support |
|---|---|
| Joule reaches us over MCP (`mcp.py`) | **A2A.** A capability function with an `agent-request` action (`schema_version: 3.28.0`), resolved through a system alias to a BTP destination, which fetches `/.well-known/agent-card.json` and sends A2A `message/send` |
| Destination with principal propagation | **`NoAuthentication`, Proxy Type Internet.** Principal propagation is "not supported for this hackathon": one shared Joule tenant, no backend for an identity to flow into |
| Joule waits for the answer | Over a minute needs the **multi-turn async** pattern (`fyx99/joule-pro-code-a2a`, `a2a_multiturn_async`). A SIGAP handling may run to `MAX_SECONDS_PER_EVENT` = 600 s |

Consequences:

- `mcp.py` stays, for AgentCore Gateway. It is not the Joule path.
- A call from Joule carries **no user identity**. So an approval can never
  arrive through Joule, which `core/identity.py` already demands: identity comes
  only from a SIGAP session token, and authority is checked on the server.

---

## 2. Channel split: Joule or SIGAP web

| Interaction | Where | Why |
|---|---|---|
| "What does the Ningbo closure hit?" | **Joule** | Read-only, answered from a finished run |
| "Investigate this disruption" | **Joule** | Raises an event, answers at once with the run id and a link |
| "How is run X going?" | **Joule** | Second scenario. This is how the >1 minute handling stays inside Joule's limit |
| "What is about to break this week?" (Vega) | **Joule** | Read-only summary of the exposure scan |
| Approve or reject an action | **SIGAP web only** | Joule has no identity. A button on Joule would be an approval with no approver |
| Audit trail, reasoning graph, data audit, uploads | **SIGAP web** | Too dense for chat; Joule links to them |

Joule answers in markdown, and for the options table a UI integration card
(see the "Joule Responses" links in the organisers' README). Every figure keeps
its origin label, as on every other screen.

---

## 3. The A2A path

```
Joule ─ agent-request ─▶ BTP destination (NoAuthentication)
      ─▶ A2A shim on Cloud Foundry ─▶ SIGAP API on EC2 (sigap.lumbungstack.dev)
```

**A thin shim, not A2A inside `api.py`.**

- The organisers' Python sample (`a2a-sdk[http-server]==0.3.25`, Python 3.13
  buildpack) is the shape Joule is known to accept. Copying it is the
  lowest-risk route. SIGAP's service is stdlib Python 3.9 and stays that way.
- `NoAuthentication` makes the shim's URL public. The shim exposes three skills
  and nothing else: `investigate_disruption`, `disruption_status`, `risk_scan`.
  It cannot approve, by construction.
- The shim signs in to SIGAP as a service user with role `planner`, which
  `ROLE_LIMITS` in `core/identity.py` already gives a limit of 0. Create it with
  `manage.py user`. Sessions last 12 hours (`SESSION_HOURS`), so the shim logs in
  again when its token expires.
- The Next bridge (`app/api/sigap/[...path]/route.ts`) reads the token **only**
  from the `sigap_session` cookie and drops any `Authorization` header. The shim
  either sends the cookie, or nginx gets a direct route to the agent service.

Files to write, mirroring the sample's `joule/` folder:

| File | Holds |
|---|---|
| `da.sapdas.yaml` | The digital assistant, listing the capability |
| `capability.sapdas.yaml` | `schema_version: 3.28.0`, system alias → our destination name |
| `scenarios/*.yaml` | One per skill. Joule matches the user's words against `description` |
| `functions/*.yaml` | `status-update`, then `agent-request` (`agent_type: remote`), then a `message` |

Gate the scenarios with `visibility_condition` and the team's IAS group, so
other teams on the shared tenant do not see them.

**Open question: who creates the destination.** The organisers' BTP README gives
participants read-only subaccount access. Their Joule exercise tells
participants to create the destination in the cockpit. Ask through the
organisers' issue template (`.github/ISSUE_TEMPLATE/error-report.md`) today.

---

## 4. Model split

| Agent | Model | Endpoint | Why |
|---|---|---|---|
| Arya (lead), Kira (Rules, veto) | Claude Opus 4.6, `global.anthropic.claude-opus-4-6-v1` (Opus 5 where Mantle carries it) | Bedrock InvokeModel, global profile | The calls that decide. Few of them per event. Adaptive thinking, effort `high` |
| The other ten specialists | MiniMax M2.5, `minimax.minimax-m2.5` | Bedrock Mantle Chat Completions, `bedrock-mantle.{region}.api.aws/v1` | Client-side tool calling is supported on this endpoint (model card). 196K context, 8K output, which covers the 8,000 `max_tokens` specialists ask for in `graph.py` |
| Specialist fallback | `gpt-5.4` on AI Core, deployment `d1a82575de60e02a` | AI Core `chat/completions` | Tested 24 October: a correct tool call, then an answer that kept every origin label, about 3–4 s per call. Spends no AWS credit |
| Narration (`core/aux.py`) | Claude Haiku 4.5, `global.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock InvokeModel | Or `gpt-5.4`, to spend nothing on boilerplate |

The guarantees do not move with the model. Kira's veto, Tara's figures and the
origin labels are Python, so a cheaper specialist cannot weaken them.

**One region for both providers: `ap-southeast-2` (Sydney).** The team's
Bedrock key works there. Claude 4.6 and Haiku 4.5 answer through `global.`
profiles; MiniMax, DeepSeek, Kimi, Qwen, GLM, gpt-oss and Mistral through
Mantle. Mantle in Sydney does not carry the Claude 5 family (404), and on
bedrock-runtime this account gets 403 for Opus 5, Haiku 5.5, GPT-5.x and Grok.
Jakarta answers 403 "security token invalid", which is what an opt-in region
the account has not enabled looks like.

**Any of it can be changed from the app.** Settings → Models picks the model
per role and per agent from the sixteen that ran a full tool loop
(`ENV.md`, Choosing from the app).

**Measure before committing.** Run the Ningbo scenario twice: specialists on
MiniMax, and specialists on Opus at effort `low`. The second needs no new code,
because effort is already per agent. Keep MiniMax only if its answers hold up.
A cheaper call that needs a second round is not cheaper.

**Optional, only with a real use behind it** (`AWS-PLAN.md` §7 warns against
logo-counting):

- `text-embedding-3-large` on AI Core gives Otto semantic recall over past runs.
  This is the gap the AgentCore Knowledge Base was meant to fill.
- `sonar` on AI Core is a second live signal: port and customs news, with
  citations. Done 24 Oct as Milo's `web_brief`, labelled derived, beside GDACS,
  EONET, USGS, Open-Meteo, Google News, Nager.Date and Frankfurter
  (`DATA-SOURCES.md` §10).

---

## 5. SAP products: one job each

The rubric rewards purposeful use, not a long list. Each SAP product below has
one job that nothing else in SIGAP does.

| Product | Its one job | Status |
|---|---|---|
| **S/4HANA Cloud** (sandbox OData) | The record: POs, stock, BOM, sales orders. Origin flips to `live` | Reads working; `/health` on EC2 reports `sap_ready: true` |
| **Joule** | The front door inside SAP: ask, start, check (§2, §3) | To build |
| **SAP RPT-1.6** (AI Core, `d76cf689a05d504f`) | Vega's ranking: which open POs are likely to slip | To build, below |
| **AI Core `gpt-5.4`** | Specialist fallback that spends no AWS credit (§4) | Tested 24 October |
| **BTP Cloud Foundry** | Hosts the A2A shim only | To build |

**RPT-1.6 for Vega.** `PurchaseOrder` carries `DeliveryDate` and
`RevisedDeliveryDate`. Closed POs with a known slip are the context rows. Open
POs get `[PREDICT]` on the slip, as a `regression` target, with `Supplier`,
`LoadingPort`, `Material` and `OrderQuantity` as features. RPT is in-context:
it needs history rows, not training. The output is a **ranking signal**,
labelled `modelled` with RPT's confidence. It is never a priced input, so the
calculator's refusal to price modelled figures stays intact.

**Writes to S/4HANA.** `sender.py` has the write path, and it is untested. Try
one write against the sandbox early. If the sandbox refuses writes, the demo
shows the payload SIGAP would send. `components/action-payload.tsx` already
renders it.

**Left out on purpose:**

| Product | Why not |
|---|---|
| Principal propagation | Out of scope for this hackathon (organisers' README) |
| The whole agent service on Cloud Foundry | SQLite on a filesystem CF resets (`agent/manifest.yml` warns). EC2 already runs it |
| Orchestration grounding for Kira | The sample's grounding call is a stub, and the rule pack in `references/` is not written. Revisit when it is |
| `tabpfn-3.5-plus` | Does the same job as RPT-1.6. One tabular model is enough |
| `gemini-3.1-flash-image` | No use case |

---

## 6. Code work

| # | Change | Where |
|---|---|---|
| 1 | One interface over two wire formats: Anthropic Messages (Claude) and OpenAI Chat Completions (MiniMax on Bedrock, `gpt-5.4` on AI Core). It translates `input_schema` ↔ `parameters`, `tool_use` ↔ `tool_calls`, `tool_result` ↔ role `tool`, and the usage counts | new `core/llm.py` |
| 2 | A model per agent, overridable as `SIGAP_MODEL_<CODE>=provider:model`, with a fallback | `agents/definitions.py`, `core/config.py` |
| 3 | Use the agent's model instead of `CFG.model`; replace the `"haiku" in model` check with a per-model capability flag | `graph.py:219`, `:225`, `:538`, `:544`; `engine/dispatch.py:273` |
| 4 | Cost rates per model, from the Bedrock pricing page. AI Core counted in tokens | `graph.py:26-27` |
| 5 | Mantle before the legacy client | `graph.py:118`, `core/aux.py:41` |
| 6 | Drop `temperature`: Haiku 5.5 rejects non-default values, and `aux.generate()` swallows the error, so every summary is silently `None` | `core/aux.py:81` |
| 7 | `anthropic[bedrock]`, or the signing libraries are missing | `requirements.txt` |
| 8 | Replace `RETURNING`, which needs SQLite 3.35. This server has 3.34.1, and three self-checks fail on it | `core/exploration.py:124` |
| 9 | **Require a session on `POST /events`.** It checks no token today. On 24 October an empty POST to `sigap.lumbungstack.dev/api/sigap/events` got past auth to the field check, so anyone can start handlings that spend Bedrock credit | `api.py`, `receive_event` |
| 10 | The A2A shim and the Joule capability | new `joule/` |
| 11 | RPT-1.6 slip ranking for Vega (§5) | `tools/exposure.py` |
| 12 | Correct `BUILD-SPEC.md` §6b (A2A, not MCP; no principal propagation) and `PLAN.md` §2 | docs |

---

## 7. Order of work

| When | Work |
|---|---|
| **24 Oct** | Organiser issue about the destination. Bedrock model access for Opus 5, MiniMax M2.5 and Haiku 5.5 in the chosen region. Item 9 |
| 25–26 Oct | Items 1–8. Ningbo end to end, first on AI Core alone (no AWS needed), then on the Bedrock split |
| 26–28 Oct | The shim on Cloud Foundry, the capability, the destination, a Joule test. RPT-1.6 for Vega. One sandbox write |
| 29–30 Oct | Rehearsal. Decide the fallback below by 28 October, not on the day |

**If the destination does not happen by 28 October:** demo the shim in the
A2A Editor the organisers' exercise uses
(`open-resource-discovery.github.io/a2a-editor`), and present the Joule wiring
as built and one destination away. The SIGAP web interface carries the demo
either way, because that is where approval lives.

---

## 8. Still open

- Who may create a BTP destination on the hackathon subaccount.
- The team's AI Core quota. It is shared hackathon capacity, not unlimited.
- Whether `bedrock-mantle:CreateInference`, the action Anthropic's docs name for
  Claude on Mantle, also covers MiniMax on the same endpoint. The first call answers it.
- Whether MiniMax holds up as a specialist (§4, measure first).

---

## 9. Status, 24 October

| # | Item | State |
|---|---|---|
| 1–3 | `core/llm.py`: one interface over Messages and Chat Completions, a model per agent, capability flags instead of `"haiku" in model` | Done. Ningbo ran end to end on AI Core `gpt-5.4`: 10 calls, 86 s, origin labels intact |
| 4 | Cost per model, `cost_by_model` on every run | Done. Every rate is from the AWS Price List for `ap-southeast-2` |
| 5 | Mantle first, InvokeModel for profile and ARN-versioned ids | Done, called against Bedrock in Sydney: Opus 4.6 takes adaptive thinking, effort and strict tools on InvokeModel |
| 6 | `temperature` dropped; aux asks Haiku 5.5 not to think | Done |
| 7 | `anthropic[bedrock]==0.125.0`, pinned | Done |
| 8 | `RETURNING` replaced | Done. All 28 self-checks pass on SQLite 3.34 |
| 9 | Session on `POST /events` | Done. 401 without one |
| 10 | `sigap/joule/`: A2A shim and capability | Built. Tested against the real `api.py` locally; CF, destination and Joule not yet |
| 11 | `rank_po_slip_risk` on RPT-1.6 | Done, live. On the fixture, no order's interval clears zero, and the tool says so |
| 12 | Docs | `ENV.md` Models and Run it locally, `PLAN.md` §2, `BUILD-SPEC.md` §6b |
| 13 | Models page: model per role and per agent, from the app | Done. `GET/POST /models`, `POST /models/test`, `settings` table; admin and procurement lead only. Sixteen models in the catalog, each through a two-round tool loop. AI Core's `anthropic--claude-4.6-sonnet` goes through `/invoke` |

Found on the way: a tool given a malformed material id ("KRW1 M-5512 Steel bar")
returned an empty list, which reads as "no option exists". `registry.run` now
checks every `material` argument against the records and refuses an unknown one.
