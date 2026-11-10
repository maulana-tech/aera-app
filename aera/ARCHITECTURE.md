# AERA — Architecture

**AERA — Autonomous Enterprise, Run by Agents.** A person describes a business; AERA composes
a multi-agent team for it; the team takes orders, does the work, gets paid and pays its own
costs — thinking inside attested TEEs and moving money only through a vault whose rules a
person set on chain.

Built for **NEAR Hackathon 2026**: *Autonomous Business*, *Privacy & Private AI*,
*AI Security & Defense*. Where this page and the code disagree, the code is right.

| Also | |
|---|---|
| [`../README.md`](../README.md) | What it does, how to run it, what was built during the hackathon |
| [`NEAR.md`](NEAR.md) | Every NEAR integration, with the exact calls |
| [`SETUP.md`](SETUP.md) · [`ENV.md`](ENV.md) | Running it; every variable |
| [`AGENT-REFERENCE.md`](AGENT-REFERENCE.md) | Every tool, by capability (generated) |
| [`NEAR-PLAN.md`](NEAR-PLAN.md) | The implementation plan |

---

## 1. The shape of it

```
 person ── onboarding ──▶ business profile (versioned) ──▶ Composer ──▶ team (agents table)
                                   │                                     │
 customer ── checkout ─▶ vault.ft_on_transfer ─▶ order paid ─▶ work item ┤
 schedule (goals) / chat / API ─────────────────────────────▶ work item ┤
                                                                         ▼
          Arya (supervisor) ─ask_<code>─▶ specialists (Nova, Wira, Quin, Odi, …)
                 │                         │ tools by CAPABILITY, granted per agent
                 ├──▶ Kira (guardian, veto) ── core/guardian.py ── rules in code
                 └──▶ Tara (treasurer) ── pay_vendor ─▶ core/actions.py ─▶ settle.py ─▶ vault
                                                                       (function-call key only)
 every model call ─▶ NEAR AI Cloud (TEE) ─▶ core/attest.py ─▶ tee_proofs ─▶ Verified panel
```

**One Python process** (stdlib only: `http.server`, `sqlite3`, `urllib`, `hashlib`) holds the
API, the agents, the schedule and the workers. Ed25519, Borsh, Keccak-256 and secp256k1
recovery are implemented in `core/crypto.py`, so signing a NEAR transaction and verifying a
TEE signature need no dependency. The web app is Next.js 16; its server components keep the
session token and the service URL off the browser.

## 2. The team is the business's, not ours

| Piece | File | What it guarantees |
|---|---|---|
| Business profile | `core/business.py` | One normalised source of truth: offerings, prices, autonomous spend caps, inference cap, forbidden actions, approval-required kinds, sensitive data, revenue split, kill switch. Versioned in `business`. |
| Composer | `core/team.py` | Deterministic: same profile, same team. Three core roles always; library roles picked from offerings/channels/goals; `team.include/exclude/preset`; free-text extra roles become **drafts** a person approves. |
| Role library | `agents/roles.py` | 10 roles × capabilities × prompt templates. `{BUSINESS}` is filled from the profile at call time, so a profile edit reaches every agent on its next turn. |
| Capability lock | `agents/roles.py`, `agents/roster.py` | `treasury` only on the treasurer, `guardian` only on the guardian, `supervisor` only on the supervisor — enforced when composing, when a person edits, and again when a row is read. |
| Grant check | `graph.py` `_run_tool` → `registry.may_call` | A model naming a tool it was not shown is refused. |

## 3. One work item, end to end

1. A work item arrives (`work_items`, deduplicated: a paid order is worked once).
2. `jobs.work` claims it (one `UPDATE … WHERE status='new'`), checks the kill switch and the
   daily inference cap, and opens a run recording the team and profile versions used.
3. `graph.run`: Arya delegates one specialist at a time (`ask_<code>`); each runs its own tool
   loop; findings land on a board with their origin (`live | cached | derived | modelled | missing`).
4. Anything outward goes through `core/actions.raise_action` with a verdict from
   `core/guardian.py`: **block** → recorded `blocked`, final; **warn** → `pending` for a person;
   **allow** → executed by `settle.py` on the team's authority.
5. Bounds: 8 rounds per specialist, 14 for the lead, 600 s, `AERA_COST_CAP_USD`. Hitting one
   ends in `_salvage`: what was established, labelled, and no invented conclusion.
6. `notify.py` tells the team (figures from the tables, never the model's prose).

## 4. Three brakes on money

| Layer | Where | Stops |
|---|---|---|
| 1. Record, not text | `tools/money.pay_vendor` takes a **contact id**; the payout account is read from `contacts` (payout fields are owner-edited; a change is stamped) | An injected address has no parameter to land in |
| 2. Guardian in code | `core/guardian.py`: kill switch, injection phrases, forbidden, approval-required, caps per payment/day, counterparty (on record, vendor role, blocklist, address cooldown, first payment, vault allowlist, account exists/age, contract-or-wallet), privacy (other contacts' details) | A fooled model, a poisoned record |
| 3. Vault on chain | `aera/contracts/aera-vault`: agent-only `request_payment`, allowlist, per-tx and daily caps, approver role limits, `assert_one_yocto` on every human method, freeze | A compromised server: the agent's key is a **function-call key** that cannot attach a deposit, so it cannot move a token except through the vault's rules |

`python3 manage.py attack-demo` runs the same injected request against each layer and writes
`aera/demo/attack-log.md`.

## 5. Private AI with proof

- `core/llm.py` provider `nearai:` → `https://cloud-api.near.ai/v1/chat/completions`
  (OpenAI format). `AERA_PRIVATE=1` (default) refuses any model not attested
  (`metadata.verifiable` on NEAR AI's model list); Claude/GPT/Gemini on NEAR AI are proxied, not TEE.
- Each call keeps the exact request/response bytes **in memory only**, records their SHA-256 in
  `tee_proofs`, and a background thread verifies: fresh-nonce attestation report
  (`report_data` binds signing address ‖ nonce, compose hash = `mr_config_id`, signing key ↔
  address), response signature (`model:sha256(req):sha256(resp)`, EIP-191 recovered signer ∈
  attested addresses), optional NVIDIA NRAS / DCAP. Then the bytes are dropped.
- Customer inputs never go to a non-TEE model in private mode; outward messages are checked for
  other contacts' details; outside production they are redirected or not sent.

## 6. What is stored where

| Data | Where | Leaves? |
|---|---|---|
| Profile, team, work, steps, actions, approvals, guardian rulings, payments, orders | SQLite `AERA_DB` | Never, except the public ledger (amounts, tx hashes, no customer data) |
| Prompts and model responses | NEAR AI TEE (stateless chat completions) | Bytes held in process memory until verified; only hashes stored |
| Money | NEAR (vault + USDC) | On chain by design |
| Keys | `.secrets/near.env`: the agent's function-call key only | — |

## 7. Surfaces

- **HTTP API** (`api.py`): business, team, work, runs, actions, orders, treasury, ledger, guardian,
  attestation, files, public checkout. Identity only from the session token; approval limits by role
  (viewer 0 · operator $100 · approver $1,000 · owner).
- **MCP** (`POST /mcp`, `mcp.py`): read-only tools only — no payment, message or delivery is
  reachable from outside; resources (profile, team, work, ledger); prompts from the skill catalogue.
- **Schedule** (`jobs.py`): `work` 20 s · `settle` 30 s · `notify` 30 s · `attest` 2 min · `goals` daily · `digest` 07:30.
