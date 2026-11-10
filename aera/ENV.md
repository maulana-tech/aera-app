# Environment and credentials

`aera/agent/.env` holds settings; `aera/agent/.secrets/*.env` (gitignored, mode 600) holds keys.
A real environment variable beats both. `aera/agent/.env.example` lists everything.

## The one rule about keys

The service holds **one** NEAR key: the agent's function-call key on the vault. It cannot attach
a deposit, so it cannot move tokens except through the vault's rules. The owner's full-access key
and the approvers' keys live in their wallets, never here.

## Required

| Variable | What | Check |
|---|---|---|
| `AERA_SECRET` | Signs session tokens (`manage.py secret`) | `manage.py ready` |

## Models (NEAR AI Cloud)

| Variable | Default | |
|---|---|---|
| `NEARAI_API_KEY` | — | `.secrets/near.env`. cloud.near.ai, or the NEAR Builders $10 credit |
| `AERA_PRIVATE` | `1` | Only attested TEE models may run. `0` allows proxied/other providers |
| `AERA_MODEL` | `nearai:moonshotai/kimi-k3` | Supervisor and guardian |
| `AERA_MODEL_SPECIALISTS` | (= `AERA_MODEL`) | Everyone else |
| `AERA_MODEL_<CODE>` | — | One agent, e.g. `AERA_MODEL_WRITER` |
| `AERA_MODEL_FALLBACK` | — | Tried once when a model fails |
| `AERA_AUX_MODEL` | `nearai:z-ai/glm-5.3-flash` | Profile drafts, titles |
| `NEARAI_BASE_URL` | `https://cloud-api.near.ai/v1` | |
| `AERA_ATTEST_NRAS` | — | `1`: also verify GPU evidence with NVIDIA NRAS |

Check: `manage.py models --ping`, `scripts/near_spike.py`.

## NEAR

| Variable | Default | |
|---|---|---|
| `NEAR_NETWORK` | `testnet` | |
| `NEAR_RPC_URL` | FastNEAR for the network | |
| `AERA_VAULT_CONTRACT` | — | Without it: simulated rail |
| `AERA_NEAR_AGENT_ACCOUNT` | — | e.g. `agent.<owner>.testnet` |
| `AERA_NEAR_AGENT_KEY` | — | `ed25519:…` function-call key (`.secrets/near.env`) |
| `AERA_USDC_TOKEN` | Circle USDC for the network | |
| `ONECLICK_JWT` | — | NEAR Intents 1Click partner key (mainnet; without it +0.25%) |
| `AERA_NEAR_OWNER` | — | Only for `manage.py near-setup` output |

Check: `manage.py ready`, `manage.py attack-demo`.

## Limits

| Variable | Default | |
|---|---|---|
| `AERA_PAY_AUTONOMOUS_LIMIT_USD` | `50` | Ceiling per payment without a person; the profile can only lower it |
| `AERA_COST_CAP_USD` | `1.0` | Model spend per run |
| `AERA_REASONING_WORKERS` | `2` | Concurrent runs |

The profile adds its own: autonomous per payment/day, inference per day, min price, approvals.

## Behaviour

| Variable | Default | |
|---|---|---|
| `AERA_ENV` | `dev` | `prod` refuses to start without a callable supervisor model |
| `AERA_DB` | `data/aera.db` | Absolute path on a server; back it up |
| `AERA_WATCH` | `1` | `0`: the team does not start work on its own |
| `AERA_SCHEDULE` | `1` | `0`: nothing runs on its own |
| `AERA_WEB_URL` | `http://localhost:3000` | Links in alerts |
| `AERA_EXTERNAL_REDIRECT` | — | Outside prod, messages to customers/vendors go here, or nowhere |
| `AERA_EXTERNAL_DOMAINS` | — | In prod, the only domains outward mail may go to |

Alerts (SMTP, Slack, Telegram, webhook, Composio Gmail): see `.env.example`; values in `.secrets/notify.env`.

## Web app (repo root `.env.local`)

| Variable | |
|---|---|
| `AERA_API` | The agent service, e.g. `http://127.0.0.1:8787` |
