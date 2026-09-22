# SIGAP — the agent system

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

# 3. push approved actions to SAP (run on a schedule)
cd sigap/agent && python3 sender.py
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
| `SIGAP_ENV` | `dev` · `staging` · `prod` | — |
| `SAP_API_KEY` | key from api.sap.com | ✅ |
| `SAP_BASE_URL` | defaults to the SAP sandbox | — |
| `AWS_REGION` | a region that offers Claude | ✅ |
| `SIGAP_MODEL` | defaults to `anthropic.claude-opus-5` | — |
| `SIGAP_AUTONOMOUS_LIMIT_IDR` | ceiling for unapproved actions, default 50m | — |
| `SIGAP_COST_CAP_IDR` | model spend cap per event, default 500k | — |
| `SIGAP_DB` | SQLite file, default `data/sigap.db` | — |
| `SIGAP_SECRET` | signing key for session tokens | ✅ |

`SIGAP_ENV=prod` without `SAP_API_KEY` or `AWS_REGION` **refuses to start**. Production
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
| `POST /actions/{id}/decision` | approve · reject · escalate — **needs a token** |
| `GET /agents` · `POST /agents/{code}/ask` | team anatomy · ask one specialist |
| `GET /summary` · `GET /data/{domain}` · `GET /log` | dashboard, tables, audit trail |
| `GET /uploads` · `POST /uploads` | company CSV in place of SAP |
| `GET /reports/{run_id}` · `GET /contacts` · `POST /contacts` | write-up, notify list |

```bash
curl -X POST localhost:8787/events -H 'content-type: application/json' \
  -d '{"kind":"port_closure","title":"Ningbo closed 6 days",
       "trigger":"maritime advisory","payload":{"port":"CNNGB"}}'
```

## Shape of the system

```
api.py                 the HTTP service
graph.py               the agent team — lead + specialists, tool-use loop to Bedrock
sender.py              pushes approved actions to SAP; retried, never double-sent
manage.py              admin: user · secret · seed · check · docs
core/config.py         production refuses modelled data
core/store.py          SQLite: events, runs, steps, actions, approvals, uploads, contacts
core/provenance.py     the data-origin label — attached to EVERY tool return
core/registry.py       tool registry: the schema the model sees IS the function that runs
core/identity.py       pbkdf2 passwords, HMAC session tokens, per-role approval limits
core/trace.py          step recorder; its output is what the dashboard reads
clients/sap_s4.py      OData; the sandbox today, a customer tenant tomorrow
engine/simulate.py     the calculator — pure Python, no AI
agents/definitions.py  the 11 agents; instructions live in prompts/
tools/                 one file per agent, named after the agent code
```

Every tool file is named for the agent that owns it — `impact.py` holds Elsa's tools,
`compliance.py` holds Kira's. A page and its specialist cannot drift apart.

## Guarantees the code enforces, not the prompt

1. **A failure never invents a value.** Tool fails → `Origin.MISSING`, not a guess.
2. **The calculator refuses** to emit a rupiah figure when its inputs aren't trustworthy.
3. **Actions are idempotent.** The same key never creates a second order.
4. **Approvals are one-shot.** A decided action cannot be decided again.
5. **Round limits and a spend cap** per event — the team cannot loop forever.
6. **Production refuses to start** without SAP and a model.
7. **Identity comes only from the session token.** Claiming a role through the request
   body is ignored — this is what makes the "approved by" column mean anything.
8. **Authority is checked on the server**, not on the button. A disabled button is a
   convenience; the real refusal happens in the API.
9. **A failed SAP write does not change status.** The action stays `approved` and is
   retried; the idempotency key prevents a duplicate order.
10. **A missing prompt raises.** An agent with no `prompts/<code>.txt` cannot be run at
    all, rather than being sent to the model with a placeholder.

## Checks

```bash
python3 manage.py check        # every self-check, then what is still missing
```

Individually:

```bash
PYTHONPATH=. python3 core/provenance.py   # the origin label
PYTHONPATH=. python3 engine/simulate.py   # the calculator — reproduces DESIGN.md §2
PYTHONPATH=. python3 tools/compliance.py  # TKDN direction, LARTAS delay
PYTHONPATH=. python3 tools/execution.py   # idempotency key
PYTHONPATH=. python3 agents/definitions.py
```

## Not done yet

- **`references/`** — the TKDN & LARTAS rules. Kira reads them when they exist; without
  them she judges from parameters and labels the result `MODELLED`. Domain work.
- **9 prompts.** Only `supervisor` and `compliance` are written. The other nine agents
  raise `PromptMissing` on invocation.
- **4 tools**, all Prevent mode: `create_sourcing_event`, `propose_safety_stock_change`
  (Bram), `scan_supply_exposure`, `get_supplier_certifications` (Vega — so Vega has
  no tools at all yet).
- **SSO.** Auth is local today (pbkdf2 + HMAC token). In a real company this becomes
  corporate SSO — `identity.from_token()` is the only place that changes.
- **SAP write service names are unverified.** `sender.py` maps actions to
  `API_PURCHASEREQ_PROCESS_SRV` and friends; the path is complete including the CSRF
  token, but the entity names need checking against the sandbox before real use.
- **Python 3.10+** for Strands. This machine is on 3.9.
