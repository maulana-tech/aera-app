# SIGAP

**Supply Disruption Intelligence & Anticipation System**

An autonomous assistant for manufacturers that import most of their raw material. When
supply is disrupted — a port closes, a supplier misses a shipment, goods are held at
customs — the system investigates the impact itself, assembles the ways out, strikes the
ones that break Indonesian regulation or the customer contract, works out which is
cheapest, and executes it into SAP once someone with the authority approves.

A supervised swarm of eleven agents on Amazon Bedrock, a Next.js interface, and a
deterministic calculator that refuses to produce a rupiah figure it cannot stand behind.

---

## Run it

Two processes: the Python agent service, and the Next.js interface.

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

To see what is and isn't wired up:

```bash
cd sigap/agent && PYTHONPATH=. python3 manage.py check
```

## Documentation

Everything lives in [`sigap/`](sigap/):

| File | What's in it |
|---|---|
| [`sigap/PLAN.md`](sigap/PLAN.md) ⭐ | The plan, the status of each part, what to do next |
| [`sigap/AGENT-REFERENCE.md`](sigap/AGENT-REFERENCE.md) | All 11 agents and their tools — **generated** from the registry |
| [`sigap/DESIGN.md`](sigap/DESIGN.md) | The scenario and its figures, the constraint rules, the eval suite |
| [`sigap/TECHNICAL.md`](sigap/TECHNICAL.md) | Bedrock calling conventions, caching, limits |
| [`sigap/DATA-SOURCES.md`](sigap/DATA-SOURCES.md) | What was verified about each data source |
| [`sigap/agent/README.md`](sigap/agent/README.md) | Running the agent service, configuration, the API |

## What makes it different

Most systems that reroute supply optimise for cost. This one can say **no on grounds that
cost cannot overturn**: an option that drops the local-content ratio (TKDN) below the
customer contract floor is struck out even when it is the cheapest of all. In the reference
scenario, the cheapest option is exactly the one that gets blocked.

Two further things the code enforces rather than asks for:

- **Every tool return carries its origin** — `live`, `cached`, `derived`, `modelled`, or
  `missing`. A failure produces `missing`, never a plausible-looking guess.
- **The calculator refuses** to emit a savings figure when any critical input is not
  trustworthy. It is pure Python with no model in it, so the arithmetic cannot be
  talked into agreeing.

## Status

Working: provenance labelling, the calculator, SAP reads, persistence with idempotent
actions and one-shot approvals, auth with server-side authority limits, 19 API routes, the
full interface, and 19 of 23 tools.

Not done: `AWS_REGION` is unset, so `graph.py` has never run — the system holds back rather
than pretending. Nine of eleven agent prompts are unwritten. The four Prevent-mode tools
and the `references/` rule documents are outstanding. `sigap/PLAN.md` §2 has the detail.

## Stack

Python 3.9 (stdlib `http.server`, `sqlite3`) · Amazon Bedrock (`anthropic.claude-opus-5`) ·
SAP S/4HANA Cloud OData · Next.js 16 · React 19 · Tailwind v4 · shadcn-ui
