# SIGAP

**Supply Disruption Intelligence & Anticipation System**

An autonomous assistant for manufacturers that import most of their raw material. When
supply is disrupted, the system investigates the impact itself, assembles the ways out,
strikes the ones that break Indonesian regulation or the customer contract, works out
which is cheapest, and executes it into SAP once someone with the authority approves.

---

## Run it

```bash
cd sigap/agent
cp .env.example .env                      # then fill SIGAP_SECRET
python3 manage.py secret                  # its output goes in .env
python3 manage.py user budi@kpn.co.id "Budi" buyer secret123
python3 manage.py seed                    # optional demo data
python3 api.py                            # :8787

cd ../..
SIGAP_API=http://127.0.0.1:8787 npm run dev
open http://localhost:3000/dashboard
```

## Where to start

| You want to | Open |
|---|---|
| Set it up, key by key | `SETUP.md` |
| Understand the product | `PLAN.md` §1 and §3 |
| See how far along it is | `PLAN.md` §2, or `manage.py check` |
| Start writing code | `agent/README.md`, then `TECHNICAL.md` |
| Know what happens before Demo Day | `AWS-PLAN.md` |
| Meet the agents one by one | `AGENT-REFERENCE.md` |
| Find a number or the scenario | `DESIGN.md` §2 |
| Work out where data comes from | `DATA-SOURCES.md` |
| Know which AWS and SAP services we use | `BUILD-SPEC.md` |
| See what AWS and SAP themselves publish | `RESEARCH-AWS-SAP.md` |

## Contents

| File | What's in it |
|---|---|
| **`PLAN.md`** ⭐ | The plan, the status of each part, the order of work |
| **`SETUP.md`** | From a clone to a system that reasons. Every step ends with a test |
| **`AGENT-REFERENCE.md`** | All 12 agents: tools, parameters, limits. **Generated**, `manage.py docs` |
| **`AWS-PLAN.md`** | Getting onto Bedrock and AgentCore, in the order that survives contact with a loop that has never run |
| `DESIGN.md` | Scenario figures, local rules, the eval suite |
| `TECHNICAL.md` | Exact function names and parameters |
| `DATA-SOURCES.md` | What was verified about each data source |
| `BUILD-SPEC.md` | The wiring: every AWS and SAP service, and the three request paths |
| `RESEARCH-AWS-SAP.md` | What AWS and SAP publish about building this, read from their own pages |
| `agent/` | The code, see `agent/README.md` |

## Things to remember

**PLAN.md is the reference.** Where documents disagree, PLAN.md is right.

**AGENT-REFERENCE.md is generated, never edited.** It is derived from the live tool
registry, so it cannot drift from the code the way a hand-written copy does:

```bash
cd agent && PYTHONPATH=. python3 manage.py docs
```

**Numbers always come from DESIGN.md §2**, and the machine verifies them:

```bash
cd agent && PYTHONPATH=. python3 engine/simulate.py
```

If a figure in a document cannot be reproduced by that command, **the document is wrong.**

**What is blocking, right now**, `PYTHONPATH=. python3 manage.py check` prints this
live, but in short: `SAP_API_KEY`, `AWS_REGION`, and `references/` (the TKDN & LARTAS
rules). All 12 prompts are written and all 31 tools are installed. The SAP key is
self-service and takes 15 minutes; `references/` needs nobody's permission and is
domain work, not code. `SETUP.md` is the runbook for the two keys.
