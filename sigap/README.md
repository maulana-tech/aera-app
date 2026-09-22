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
python3 manage.py secret                  # export its output as SIGAP_SECRET
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
| Understand the product | `PLAN.md` §1 and §3 |
| See how far along it is | `PLAN.md` §2, or `manage.py check` |
| Start writing code | `agent/README.md`, then `TECHNICAL.md` |
| Meet the agents one by one | `AGENT-REFERENCE.md` |
| Find a number or the scenario | `DESIGN.md` §2 |
| Work out where data comes from | `DATA-SOURCES.md` |

## Contents

| File | What's in it |
|---|---|
| **`PLAN.md`** ⭐ | The plan, the status of each part, the order of work |
| **`AGENT-REFERENCE.md`** | All 11 agents: tools, parameters, limits. **Generated** — `manage.py docs` |
| `DESIGN.md` | Scenario figures, local rules, the eval suite |
| `TECHNICAL.md` | Exact function names and parameters |
| `DATA-SOURCES.md` | What was verified about each data source |
| `agent/` | The code — see `agent/README.md` |

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

**What is blocking, right now** — `PYTHONPATH=. python3 manage.py check` prints this
live, but in short: `SAP_API_KEY`, `AWS_REGION`, nine agent prompts, four Prevent-mode
tools, and `references/` (the TKDN & LARTAS rules). The prompts and `references/` need
nobody's permission and can be started today.
