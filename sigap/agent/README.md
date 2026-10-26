# SIGAP, the agent system

Supply-disruption response. Not a demo: production refuses to run without real SAP
and a real model.

## Run it

```bash
# 1. the agent service
cd sigap/agent
python3 api.py                      # :8787

# 2. the interface
cd ../..
SIGAP_API=http://127.0.0.1:8787 npm run dev

# 3. nothing else to start: api.py runs the schedule (jobs.py), which
#    watches the feeds, delivers alerts and pushes approved actions to SAP
open http://localhost:3000/dashboard
```

## Set up an account

```bash
python3 manage.py secret                  # export its output as SIGAP_SECRET
python3 manage.py user budi@kpn.co.id "Budi Santoso" buyer secret123
python3 manage.py seed                    # optional: demo events and actions
```

Roles and how much each may approve:

| Role | Limit |
|---|---|
| `planner` | read only, may not approve |
| `buyer` | up to Rp 500 million |
| `procurement_lead` | up to Rp 10 billion |
| `admin` | up to Rp 10 billion |

## Configuration

| Variable | Meaning | Required in prod |
|---|---|---|
| `SIGAP_ENV` | `dev` · `staging` · `prod` |, |
| `SAP_API_KEY` | key from api.sap.com | ✅ |
| `SAP_BASE_URL` | defaults to the SAP sandbox |, |
| `AWS_REGION` | a region that offers Claude | ✅ unless the lead runs on AI Core |
| `AWS_FALLBACK_ACCESS_KEY_ID` · `AWS_FALLBACK_SECRET_ACCESS_KEY` · `AWS_FALLBACK_REGION` | required second Bedrock account for rate-limit failover | ✅ with Bedrock |
| `SIGAP_REASONING_WORKERS` | concurrent event reasoning limit, default 1 |, |
| `SIGAP_MODEL` | defaults to `anthropic.claude-opus-5`; `provider:model`, see `ENV.md` Models |, |
| `SIGAP_MODEL_SPECIALISTS` · `SIGAP_MODEL_<CODE>` · `SIGAP_MODEL_FALLBACK` | the model split, see `ENV.md` Models |, |
| `SIGAP_AUTONOMOUS_LIMIT_IDR` | ceiling for unapproved actions, default 50m |, |
| `SIGAP_COST_CAP_IDR` | model spend cap per event, default 500k |, |
| `SIGAP_DB` | SQLite file, default `data/sigap.db` |, |
| `SIGAP_SECRET` | signing key for session tokens | ✅ |

`SIGAP_ENV=prod` without `SAP_API_KEY` or a lead model it can call **refuses to start**. Production
does not guess at anything.

## API

| | |
|---|---|
| `GET /health` | connection status |
| `POST /events` | take a disruption, start a handling |
| `GET /runs` | list handlings |
| `GET /runs/{id}` | steps, actions, approvals |
| `POST /login` | exchange email+password for a session token |
| `GET /me` | identity and approval limit |
| `POST /actions/{id}/decision` | approve · reject · escalate, **needs a token** |
| `GET /agents` · `POST /agents/{code}/ask` | team anatomy · ask one specialist |
| `GET /summary` · `GET /data/{domain}` · `GET /log` | dashboard, tables, audit trail |
| `GET /uploads` · `POST /uploads` | company CSV in place of SAP |
| `GET /reports/{run_id}` · `GET /contacts` · `POST /contacts` | write-up, notify list |
| `GET /reports/{run_id}.pdf` · `.xlsx` · `GET /portfolio.pdf` · `.xlsx` | a report as a PDF, or a workbook of every table it produced (actions, steps, each tool's rows) |
| `GET /audit` | audit the data the system can currently see |
| `GET /runs/{id}/trace` · `GET /runs/{id}/steps/{seq}` | one handling as a topology with every call; one step in full |

```bash
curl -X POST localhost:8787/events -H 'content-type: application/json' \
  -d '{"kind":"port_closure","title":"Ningbo closed 6 days",
       "trigger":"maritime advisory","payload":{"port":"CNNGB"}}'
```

## Shape of the system

```
api.py                 the HTTP service
graph.py               the agent team, lead + specialists, tool-use loop to Bedrock
sender.py              pushes approved actions to SAP; retried, never double-sent
notify.py              tells people a handling ended: from the record, through an outbox
outreach.py            sends an approved supplier request or customer notice, as written
jobs.py                everything that runs on its own, with its cadence
manage.py              admin: user · secret · seed · check · ready · models · docs
core/schedule.py       the one loop that runs jobs.py: no overlap, state in the jobs table
core/config.py         production refuses modelled data
core/store.py          SQLite: events, runs, steps, actions, approvals, uploads, contacts,
                       settings, notifications, jobs
core/provenance.py     the data-origin label, attached to EVERY tool return
core/registry.py       tool registry: the schema the model sees IS the function that runs
core/identity.py       pbkdf2 passwords, HMAC session tokens, per-role approval limits
core/trace.py          step recorder; its output is what the dashboard reads
core/topology.py       a handling's steps folded into a graph: lead, specialists, tools, sources, actions
clients/sap_s4.py      OData; the sandbox today, a customer tenant tomorrow; backs off on a rate quota
clients/sap_map.py     SAP read into the flat rows the tools use: the joins, the dates, consumption
clients/channels.py    email (SMTP or Composio), Slack, Telegram, a webhook; each set up or not
clients/composio.py    Gmail through Composio: send with attachments, SIGAP's own mailbox only
clients/feeds.py       one GET for every public feed: timeout, cache with real fetch time, failure memory
clients/web_data.py    news headlines, ECB exchange rates, public holidays, a cited web answer
engine/simulate.py     the calculator, pure Python, no AI
engine/allocate.py     short supply to customer orders: costliest lateness first, against due-date order
engine/audit.py        the data audit, also pure Python, every finding evidenced
engine/report.py       a handling written up: markdown, PDF and workbook, figures never from a model
engine/export.py       .xlsx and .pdf writers on the standard library alone
fixtures/generate.py   builds the dataset, deterministic, plants known defects
signals/bmkg.py        the live quake feed for Indonesia
signals/places.py      the plants, and the loading port of every open order: what the feeds are measured against
signals/hazards.py     cyclones, floods, quakes, fires abroad: GDACS + NASA EONET + USGS, fused per storm
signals/weather.py     three-day forecast at every port and plant against named thresholds (Open-Meteo)
agents/definitions.py  the 12 agents; instructions live in prompts/
tools/                 one file per agent, named after the agent code
../references/         the rule pack format; the pack itself is installed, not committed
```

Every tool file is named for the agent that owns it, `impact.py` holds Elsa's tools,
`compliance.py` holds Kira's. A page and its specialist cannot drift apart.

## Guarantees the code enforces, not the prompt

1. **A failure never invents a value.** Tool fails → `Origin.MISSING`, not a guess.
2. **The calculator refuses** to emit a rupiah figure when its inputs aren't trustworthy.
3. **Actions are idempotent.** The same key never creates a second order.
4. **Approvals are one-shot.** A decided action cannot be decided again.
5. **Round limits and a spend cap** per event, the team cannot loop forever.
6. **Production refuses to start** without SAP and a model.
7. **Identity comes only from the session token.** Claiming a role through the request
   body is ignored, this is what makes the "approved by" column mean anything.
8. **Authority is checked on the server**, not on the button. A disabled button is a
   convenience; the real refusal happens in the API.
9. **A failed SAP write does not change status.** The action stays `approved` and is
   retried; the idempotency key prevents a duplicate order.
10. **A missing prompt raises.** An agent with no `prompts/<code>.txt` cannot be run at
    all, rather than being sent to the model with a placeholder.
11. **Nothing is said outside the company without a person.** A customer notice and a
    supplier request are drafts, addressed from the record and written as the email
    itself, never autonomous. A buyer (supplier) or a procurement lead (customer)
    approves one; only then does `outreach.py` send it, word for word. Outside
    production it goes to `SIGAP_EXTERNAL_REDIRECT` or nowhere, never to the partner.

## Checks

```bash
python3 manage.py check        # every self-check, then what is still missing
```

Individually:

```bash
PYTHONPATH=. python3 core/provenance.py   # the origin label
PYTHONPATH=. python3 engine/simulate.py   # the calculator, reproduces DESIGN.md §2
PYTHONPATH=. python3 tools/compliance.py  # TKDN direction, LARTAS over holidays, rule pack origins
PYTHONPATH=. python3 tools/execution.py   # idempotency key, outward messages are drafts
PYTHONPATH=. python3 tools/logistics.py   # dwell measured on customs releases, customs holds
PYTHONPATH=. python3 tools/sourcing.py    # substitutes: in stock is not approved
PYTHONPATH=. python3 engine/allocate.py   # short supply to the costliest lateness first
PYTHONPATH=. python3 agents/definitions.py
PYTHONPATH=. python3 signals/hazards.py   # Champi fused from two feeds, offline
PYTHONPATH=. python3 signals/weather.py   # thresholds, one event per spell, offline
```

## Not done yet

- **The rule pack** (`../references/README.md`), the TKDN & LARTAS rules. Kira reads it
  when it is installed; without it she judges from built-in parameters and labels the
  result `MODELLED`. The code is done, the content is domain work.
- **SSO.** Auth is local today (pbkdf2 + HMAC token). In a real company this becomes
  corporate SSO, `identity.from_token()` is the only place that changes.
- **SAP write service names are unverified.** `sender.py` maps actions to
  `API_PURCHASEREQ_PROCESS_SRV` and friends; the path is complete including the CSRF
  token, but the entity names need checking against the sandbox before real use.
- **Python 3.10+** for Strands. This machine is on 3.9.
