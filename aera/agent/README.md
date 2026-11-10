# AERA agent service

Python, standard library only. One process: the HTTP API, the dynamic agent team, the
schedule, settlement and the outbox.

```bash
PYTHONPATH=. python3 manage.py check      # every self-check, offline
PYTHONPATH=. python3 manage.py demo       # seed the demo business and its team
PYTHONPATH=. python3 api.py               # :8787
```

| Path | |
|---|---|
| `api.py` | HTTP routes (docstring lists them) |
| `graph.py` | The orchestration: supervisor → specialists, tool loops, bounds, salvage |
| `agents/roles.py` · `agents/roster.py` | Capabilities, the role library, the capability lock; the team as loaded per run |
| `core/business.py` · `core/team.py` | The business profile; the Composer |
| `core/guardian.py` · `core/actions.py` | Rules in code; the one door for outward actions |
| `core/llm.py` · `core/attest.py` | Model router (`nearai:` provider) and TEE proofs |
| `core/chain.py` · `clients/near.py` · `core/crypto.py` | Vault adapter; NEAR RPC + Borsh + signing; Ed25519, Keccak, secp256k1 |
| `clients/intents.py` | NEAR Intents 1Click |
| `tools/` | Tools by capability: research, workspace (knowledge, documents, contacts, memory), commerce (orders, messaging), money (guardian, treasury, supervisor), skills |
| `settle.py` · `notify.py` · `jobs.py` · `mcp.py` | Execution and reconciliation; outbox; schedule; MCP (read-only) |
| `prompts/` | The three core roles' prompts (library roles are in `agents/roles.py`) |
| `guardian/blocklist.json` | Shared blocklist with evidence |
| `scripts/near_spike.py` | Live check of NEAR AI models: tool calling, attestation, signatures |

See `../ARCHITECTURE.md` and `../NEAR.md`.
