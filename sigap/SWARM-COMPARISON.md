# Swarm architecture: SmartX ↔ SIGAP

> A grounded comparison of two multi-agent swarms, written to decide what is
> worth porting from SmartX into SIGAP and what would be over-engineering at
> SIGAP's scale. Every claim here is read from code, with the file named.
>
> SmartX repo: `smartx-platform` (an authorized-pentest orchestrator).
> SIGAP: this repo, `sigap/agent/`.

---

## 0. The one-paragraph difference

SmartX is a **swarm built for breadth under contention**: many ephemeral
workers, racing siblings, fired asynchronously, harvested between rounds, gated
by a two-tier admission system because 10 users each spawning heavy workers
would melt one box. SIGAP is a **swarm built for a defensible decision**: one
lead calls a few specialists, one at a time, synchronously, and the whole point
is that the answer can be audited — every fact carries its origin, and the
calculator refuses to emit a number it cannot stand behind. SmartX optimises
throughput; SIGAP optimises trust. The ports worth doing are the ones that make
SIGAP more **robust** without trading away that auditability.

---

## 1. Side by side

| Dimension | SmartX | SIGAP (today) |
|---|---|---|
| **Topology** | Orchestrator (main agent) → N workers. Two worker types: *explorer-worker* (main-agent-like, heavy, primary) and *swarm* (atomic, light, secondary). Routed by task shape. | Supervisor (Arya) → 11 specialists as tools (`ask_<code>`). One tier. |
| **Dispatch** | **Async** (`SWARM_ASYNC`): fire-and-forget, keep working, harvest verdicts **between rounds** (`swarm-harvester.ts`). Push (delegate) + idle pull (work-stealing). | **Synchronous**: `_tool_loop` runs each specialist to completion inline, blocking the lead (`graph.py`). |
| **Worker run-state** | Every run is tracked: `running\|done\|failed\|cancelled\|timeout`, with tokens, verdict, logs, trace. Persisted (`swarm_runs`), observable (`GET /runs/:id`). | None. A specialist call is a function that returns a string; its lifecycle is not a record. |
| **Shared state** | Exploration graph (persisted DAG) + an in-memory `Blackboard` of confirmed artifacts injected into siblings. | In-memory `Board` (now also mirrored to the persisted exploration graph I added — `core/exploration.py`). |
| **Concurrency control** | **Two-tier admission.** Worker side: `atServiceCapacity` (429 past `SWARM_SERVICE_MAX_RUNS`). Orchestrator side: `fair-admission.ts` — global cap + per-operator cap + weighted units + dynamic fair-share + waiter-priority aging. | Per-event only: `MAX_LEAD_ROUNDS=14`, `MAX_SPECIALIST_ROUNDS=8`, `cost_cap_per_event_idr`, `MAX_SECONDS_PER_EVENT=600`. No cross-run or cross-operator fairness. |
| **Slot accounting** | A dispatched run HOLDS its admission slot until terminal (`swarm-slot-registry.ts`), released exactly once via take-on-read. Weight released == weight acquired (never recomputed — the slot-leak class they fixed). | N/A (synchronous: nothing is held). |
| **Termination on limit** | **Non-lossy.** `DELETE /runs/:id` is a graceful drain that still harvests findings; a timed-out run still carries its verdict. | **Lossy.** `DeadlineExceeded` / `BudgetExhausted` raise → the whole handling is marked `failed`, evidence discarded (`api.py` `_handle`). |
| **Self-heal** | Crashed worker's claim lapses and returns to the frontier (lease + stale reclaim). | Now present on the graph (`reopen_stale_claims`), but the synchronous loop has no crashed-worker case to use it yet. |
| **Convergence** | Frontier-drained over the graph (`countActiveIntents==0`). | `MAX_LEAD_ROUNDS` cap, plus the graph's `converged()` I added (read-model, not yet authoritative). |
| **Result contract** | `(task, target, mode) → JSON verdict {status, confidence, evidence}`. No per-fact provenance. | Every tool → `Result{value, origin, source}`; the board refuses to let an untrusted fact back a rupiah figure. **Richer than SmartX here.** |
| **API surface** | HTTP service per layer. Swarm-service: `POST /runs`, `GET /runs/:id`, `/logs`, `/trace`, `DELETE`, `/reap-by-user`, `/health`. | stdlib `http.server`, 19 routes; `_handle` runs `graph.run` on a background thread. |
| **Stack** | Bun + TypeScript, Postgres graph, Docker-per-run containers. | Python stdlib (`http.server`, `sqlite3`), zero deps. One process. |

---

## 2. The mechanisms worth understanding

### 2.1 Async dispatch + harvest (`swarm-harvester.ts`, `delegate-to-swarm.ts`)
The orchestrator never blocks on a worker. It fires a lead (`admitDelegation`
→ `fireSwarm` → `run_id`), keeps taking its own turns, and between rounds
`harvestSwarmRuns` polls every pending run; a terminal one is folded back
through the same verdict pipeline and injected as `[SWARM RESULT] …`. This is
what lets one orchestrator drive many workers at once.

### 2.2 Two-tier admission (`admission.ts` + `fair-admission.ts`)
Defence in depth. The worker service refuses past its own container ceiling
(429) **independently** of the orchestrator, so an orchestrator bug cannot melt
the box. The orchestrator's `fair-admission` is the subtle one: a global slot
budget and a per-operator budget, counted in **weight units** (a heavy explorer
= 3, a light swarm = 1), with an optional dynamic fair-share (a lone user may
burst but one newcomer's floor is always reserved) and waiter-priority aging (a
below-floor newcomer is not starved by an above-floor incumbent reclaiming
freed slots). Every env knob is clamped so a blank `.env` line cannot collapse
the cap to 1. This is genuinely good engineering — but it exists because
SmartX has *many operators contending for one box*.

### 2.3 Slot hold-to-terminal (`swarm-slot-registry.ts`)
The admission slot is released when the run reaches terminal, not when it is
fired — otherwise the global cap bounds *fires*, not *running workers*, and
defeats itself. Released exactly once (take-on-read `Map` get+delete), and the
exact weight acquired is released (looked up, never recomputed — recompute was
their slot-leak bug `555c53293`).

### 2.4 Non-lossy cancel/timeout (`swarm-service/index.ts`)
`DELETE /runs/:id` is a graceful drain, not a kill: it harvests whatever verdict
the container produced in the race. A hard-timeout run still backfills a
`map_result` verdict from its trace. **Findings survive cancellation.**

### 2.5 Explorer vs swarm, routed by shape (`explorer-contract.ts`)
The explorer-worker gets a *narrowed* system contract — first-hand chaining
only, no delegate tool, no "decide the engagement is done". Atomic/known tasks
go to the light swarm; broad/ambiguous/chain-opening go to the heavy explorer;
when in doubt, explorer. Routing atomic work to the cheap worker *preserves*
scarce heavy-worker capacity — a throughput lever, not just a fallback.

---

## 3. What SIGAP already does better

Worth stating, so the port does not erode it:

- **Provenance on every fact.** SmartX's verdict is a judged claim; SIGAP's
  every value says live/cached/derived/modelled/missing. A decision read back
  off SIGAP's graph can be audited for the trustworthiness of its inputs.
- **A calculator with no model in it.** `engine/simulate.py` refuses a figure
  when a critical input is untrusted. SmartX has nothing equivalent; its
  numbers come from the model.
- **A veto that cost cannot overturn.** Kira's block is structural, now enforced
  at the graph level too (`engine/planner.py` negative-knowledge gate).
- **Zero dependencies.** stdlib only. Easy to audit, nothing to supply-chain.

---

## 4. Recommended ports, ranked for SIGAP's scale

SIGAP's stated scale is "a dozen events a day, one box" and its roadmap note is
"move to Postgres once this is multi-tenant or needs concurrent writes". That
calibrates what is valuable now vs premature.

| # | Port | Value for SIGAP | Status |
|---|---|---|---|
| **1** | **Non-lossy termination** (§2.4). On deadline/budget, conclude on the evidence on the board — labelled with its provenance — instead of failing the handling and discarding it. | **High.** A slow handling used to lose everything; now it degrades honestly, which is exactly SIGAP's ethos ("say what is missing, don't guess" → "decide on what we have, labelled"). | ✅ **done** — `graph.py` `_salvage`, always on |
| **2** | **Specialist run-state on the graph** (§2.1/2.3 substrate). Each worked lead is a tracked node: `worked\|failed\|capped\|blocked\|stopped`, tokens, summary. | **High.** Observability (which specialist stalled, what each cost) and the spine for async. | ✅ **done** — `core/exploration.py` `annotate_lead` + `failed` terminal |
| **3** | **Fail-open specialist isolation.** One specialist raising settles that lead `failed` and lets the handling continue — SmartX's fail-open discipline the inline loop lacked. | **High.** Robustness, small change. | ✅ **done** — `graph.py` `_run_specialist_isolated` |
| **4** | **Admission / fairness** (§2.2). A Python `fair-admission` (global + per-operator, weighted, clamped knobs). | **Medium, future.** Needed *when SIGAP goes multi-tenant*. Built off to the side, generous defaults, so it does not gate a single operator today. | ✅ **done** — `core/admission.py`, flag-gated |
| **5** | **Async dispatch + harvest** (§2.1). Fire leads over the claimable frontier and harvest as they finish, several at once. | **Low now, high later.** The big behavioural change (SmartX's Phase 2). At a dozen events/day the synchronous path is simpler; this is there for when events arrive concurrently or specialists run long in parallel. | ✅ **done** — `engine/dispatch.py`, flag-gated (default off) |
| **6** | **Weighted two-tier specialists** (§2.5). The rule-giver runs heavier than a light lookup; admission counts the weight. | **Low on its own.** Folded into #4+#5: `engine/dispatch.py` `_ROUTE` assigns per-lead weight, admission bounds it. | ✅ **done** (as part of #4+#5) |

All six are implemented, all flag-gated + fail-open, so with every flag off the
default behaviour is byte-identical to before. Each module carries a `demo()`
self-check run by `python3 manage.py check`.

### Flags

| Flag | Default | Turns on |
|---|---|---|
| `SIGAP_GRAPH` | off | The persisted exploration graph (write-through mirror, planner, convergence). Prerequisite for #5. |
| `SIGAP_FAIR_ADMISSION` | **on** | Admission gating. Generous defaults (`SIGAP_GLOBAL_SLOTS`=8, `SIGAP_PER_OPERATOR_SLOTS`=4) so one operator is not gated; lower them for multi-tenant. |
| `SIGAP_SWARM_ASYNC` | off | The frontier-driven concurrent dispatcher (needs `SIGAP_GRAPH=1`). `SIGAP_ASYNC_WORKERS`=4 sets the pool size. |

Non-lossy termination (#1) and fail-open isolation (#3) are **always on** — they
only change what happens on a stop or a crash, never the happy path.

---

## 5. What would be over-engineering (said plainly)

- A **container-per-run worker service** (SmartX's swarm-service) makes no sense
  for SIGAP: its specialists are in-process Python functions, not sandboxed
  black-box pentesters. The isolation SmartX needs (untrusted exploit code) does
  not exist here.
- **Racing 4 solver siblings** at different temperatures is a breadth trick for
  an open search space. SIGAP's specialists each own a bounded question; racing
  them would multiply Bedrock cost for no coverage gain.
- **Dynamic fair-share + waiter-priority aging** are beautiful but are a
  many-operators-one-box solution. SIGAP should keep the simple global +
  per-operator caps and skip the aging machinery until it measurably needs it.
