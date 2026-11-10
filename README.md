<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="public/logo/aera-mark-19-dark.svg" />
    <img src="public/logo/aera-mark-19-light.svg" alt="AERA" width="104" />
  </picture>
</p>

<h1 align="center">AERA</h1>

<p align="center"><b>Autonomous Enterprise, Run by Agents</b></p>

<p align="center">
  Describe a business. AERA composes the team of AI agents that runs it — they take the order,
  do the work, get paid and pay their own costs — thinking inside attested TEEs on NEAR AI, and
  moving money only through a NEAR vault whose rules a person set on chain.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/NEAR%20HACKATHON-2026-000000?style=flat-square" alt="NEAR Hackathon 2026" />
  <img src="https://img.shields.io/badge/MODELS-NEAR%20AI%20CLOUD%20(TEE)-16A34A?style=flat-square" alt="NEAR AI Cloud" />
  <img src="https://img.shields.io/badge/MONEY-NEAR%20VAULT%20%2B%20USDC-2563EB?style=flat-square" alt="NEAR vault" />
  <img src="https://img.shields.io/badge/AGENT-PYTHON%20STDLIB-3776AB?style=flat-square" alt="Python stdlib" />
  <img src="https://img.shields.io/badge/WEB-NEXT.JS%2016-000000?style=flat-square" alt="Next.js 16" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/LICENSE-MIT-000000?style=flat-square" alt="MIT" /></a>
</p>

---

**Tracks:** Autonomous Business · Privacy & Private AI · AI Security & Defense

> **Humans set the constraints. Agents do the work. Code — and the chain — enforce the rules.**
>
> - The team is **composed from the business a person describes**, not hard-coded: a research shop
>   gets a researcher, writer and reviewer; a brand studio gets a designer; a custom role is a draft
>   until a person approves it.
> - Every agent thinks on a **TEE-attested model** (NEAR AI Cloud), and every model call carries a
>   proof — attestation with a fresh nonce plus a signature over the exact request and response —
>   that the Verified panel shows and re-checks live.
> - Money moves only through **aera-vault**. The agent holds a **function-call key** that cannot
>   attach a deposit, so it cannot move a token except through the vault's allowlist and caps.
>   Over the limit, a person signs from their wallet. Anyone with authority can freeze it.
> - A prompt-injected agent is stopped three times: the tools take ids not addresses, the guardian's
>   rules run in code before any action, and the vault refuses on chain.

## What it does

1. **Onboarding.** A person writes what the business sells, at what price, what the team may spend
   on its own, what it must never do, which data is sensitive, and who gets a revenue share. A model
   can draft this from a paragraph; a person saves it. Every edit is a new version.
2. **The team.** The Composer (`aera/agent/core/team.py`) picks roles from a library of ten, always
   adds the three core roles — **Arya** (supervisor), **Kira** (guardian, veto), **Tara** (treasurer)
   — and grants each agent *capabilities*, never raw tools. Money and veto are locked to their owners
   in code.
3. **Work.** A customer pays on the public checkout (`ft_transfer_call` to the vault), the order
   becomes a work item, and Arya delegates: research, write, review, deliver. Goals in the profile
   become work on a schedule; anyone can ask the team something.
4. **Money.** Revenue is split on chain the moment it arrives. The team pays its own costs (data,
   APIs, other agents) within the profile's limits; above them a person approves. Refunds always
   need a person.
5. **Proof.** The run page shows who did what, every tool call with the origin of its data, every
   guardian ruling with its rules, every TEE proof, every transaction hash. The ledger is public.

## The three tracks, concretely

| Track | Where to look |
|---|---|
| **Autonomous Business** | `core/business.py` (profile), `core/team.py` (Composer), `graph.py` (orchestration), `settle.py` (orders in, payments out), vault `ft_on_transfer` + split, `/buy/[offering]`, `/ledger` |
| **Privacy & Private AI** | `core/llm.py` (`nearai:` provider, `AERA_PRIVATE=1` refuses non-attested models), `core/attest.py` (report + signature checks), `tee_proofs`, Verified panel, raw prompts kept in memory only |
| **AI Security & Defense** | `core/guardian.py`, `tools/money.py`, `aera/contracts/aera-vault`, function-call key only, kill switch / `freeze()`, `manage.py attack-demo` → `aera/demo/attack-log.md` |

## Run it

```bash
cd aera/agent
PYTHONPATH=. python3 manage.py check                      # 39 offline self-checks
cp .env.example .env && PYTHONPATH=. python3 manage.py secret   # → AERA_SECRET in .env
PYTHONPATH=. python3 manage.py demo                       # the demo business and its team
PYTHONPATH=. python3 manage.py user owner@lumen.example "Owner" owner "a-long-password"
PYTHONPATH=. python3 api.py                               # :8787

# repo root
cp .env.example .env.local && npm install && npm run dev  # :3000
```

Add `NEARAI_API_KEY` for the models and the vault variables for real payments — [`aera/SETUP.md`](aera/SETUP.md)
walks through both, and every piece works (and says so) without them: work is *held* without a
model, payments are *simulated* without a vault. `docker compose up` runs both services.

## Layout

| Path | |
|---|---|
| `aera/agent/` | Python service, standard library only: API, agents, tools, schedule, NEAR clients, crypto |
| `aera/contracts/aera-vault/` | Rust vault contract (near-sdk) with unit and sandbox tests |
| `app/`, `components/`, `lib/` | Next.js 16 web app |
| `aera/ARCHITECTURE.md` · `aera/NEAR.md` | How it fits together; every NEAR call |

## Built at NEAR Hackathon

All NEAR work and the new product were written during the hackathon window, on top of an earlier
multi-agent engine (built for a different hackathon, as a supply-chain assistant) whose domain was
removed entirely.

- Baseline before the hackathon: tag **`pre-hackathon`**. Submission: tag **`hackathon-submission`**.
- Diff: `git diff pre-hackathon..hackathon-submission` (on GitHub: `compare/pre-hackathon...hackathon-submission`).
- **Kept from the engine** (generalised): the tool-loop orchestration and its bounds, the tool
  registry, provenance labels, the SQLite record, approvals by role, the scheduler, the MCP server
  and client, skills, the outbox and channels, the PDF/XLSX writer, the web shell.
- **New**: business profile and Composer, dynamic roster, capability lock, guardian rules, actions
  and settlement, NEAR AI provider and TEE attestation, pure-Python Ed25519/Borsh/Keccak/secp256k1,
  NEAR RPC + transactions, 1Click client, the vault contract, orders and checkout, treasury, ledger,
  attack demo, the new web pages.
- **Libraries**: none in the agent service; the vault uses `near-sdk`; the web app's are in `package.json`.
- **AI-generated code**: much of this repository was written with Claude Code (Anthropic), reviewed
  and tested by the team.

## License

MIT — see [`LICENSE`](LICENSE).
