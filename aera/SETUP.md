# Setup

Every step can be checked. Python 3.9+ (3.12 in Docker), Node 20+. No Python packages.

## 0. Offline, on nothing

```bash
cd aera/agent
PYTHONPATH=. python3 manage.py check        # every self-check, offline (39 of them)
```

## 1. The demo business, locally

```bash
cd aera/agent
cp .env.example .env
PYTHONPATH=. python3 manage.py secret        # paste into .env as AERA_SECRET
PYTHONPATH=. python3 manage.py demo          # Lumen Research: profile, composed team, contacts
PYTHONPATH=. python3 manage.py user owner@lumen.example "Owner" owner "a-long-password"
PYTHONPATH=. python3 api.py                  # :8787

# in the repo root, another terminal
cp .env.example .env.local                   # AERA_API=http://127.0.0.1:8787
npm install && npm run dev                   # :3000, sign in as the owner
```

Without a model key, work items are recorded and **held** ("the supervisor's model cannot be
called"); without a vault, payments run on the **simulated** rail. Both are labelled everywhere.

## 2. NEAR AI Cloud (the models)

1. Get a key at <https://cloud.near.ai> (or claim $10 at <https://nearbuilders.org/dashboard>).
2. `mkdir -p .secrets && echo 'NEARAI_API_KEY=...' > .secrets/near.env && chmod 600 .secrets/near.env`
3. `PYTHONPATH=. python3 scripts/near_spike.py` — tool calling, attestation and signature on each candidate model.
4. `PYTHONPATH=. python3 manage.py models --ping` — every agent's model answers, and whether it is TEE.

## 3. The vault (testnet)

```bash
cd aera/contracts/aera-vault && cargo near build non-reproducible-wasm   # see its README
cd ../../agent && PYTHONPATH=. python3 manage.py near-setup             # prints every command
```

Run the printed `near` (near-cli-rs) commands as the owner, put the agent's **function-call**
key in `.secrets/near.env`, then:

```bash
PYTHONPATH=. python3 manage.py ready          # vault answers, caps match, agent has no full-access key
PYTHONPATH=. python3 manage.py attack-demo    # all three brakes, including the vault, with tx hashes
```

## 4. A real loop

1. Open `/buy/brief` (public), fill the inputs, pay 15 USDC from a testnet wallet
   (`ft_transfer_call` to the vault). Without a vault: Orders → *Mark paid (simulated)*.
2. `settle` (30 s) sees the order, `work` (20 s) hands it to the team.
3. Work → the run: delegation timeline, Verified panel (TEE proofs), guardian rulings, the
   delivered document and its receipt on chain.
4. Ledger: the sale, the split to the contributor, model spend.

## If something is wrong

`PYTHONPATH=. python3 manage.py ready` names it. `GET /health` says which model, rail and network are in force.
