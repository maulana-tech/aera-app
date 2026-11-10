# AERA on NEAR

Every NEAR integration in AERA, what it is for, and the exact calls. All of it was built during
the NEAR Hackathon (`git diff pre-hackathon..hackathon-submission`).

## NEAR AI Cloud — private inference with proof (Privacy & Private AI)

| | |
|---|---|
| Endpoint | `POST https://cloud-api.near.ai/v1/chat/completions` (OpenAI format), `Authorization: Bearer $NEARAI_API_KEY`, `x-no-aliasing: true`, `Accept-Encoding: identity` |
| Models | Attested only, in `AERA_PRIVATE=1`: e.g. `moonshotai/kimi-k3` (deciders), `z-ai/glm-5.3-flash` (specialists), `z-ai/glm-5.3` (fallback). The attested set is refreshed from `GET /v1/model/list` (`metadata.verifiable`). |
| Attestation | `GET /v1/attestation/report?signing_algo=ecdsa&nonce=<64 hex>&model=<id>` — checks in `core/attest.py`: `nonce_bound` (TDX `report_data` = signing address ‖ our nonce), `compose_hash` (`mr_config_id` = `01‖sha256(app_compose)`), `signing_key_present` (keccak(pubkey) → address), `model_verifiable`, optional `gpu_nras` (NVIDIA NRAS), `tdx_quote_dcap` (with `dcap-qvl`) |
| Response signature | `GET /v1/signature/{chat_id}?model=…&signing_algo=ecdsa` → text `model:sha256(req):sha256(resp)`, EIP-191 signer recovered with `core/crypto.py` and required to be an attested address |
| Code | `core/llm.py` (`_NearAIBackend`, `private_mode`, `attested`), `core/attest.py`, `tee_proofs` table, `GET /runs/{id}/proofs`, `GET /attestation/{model}` |
| Try | `PYTHONPATH=. python3 core/attest.py --live z-ai/glm-5.3-flash` (no key needed for the report) · `python3 scripts/near_spike.py` (with a key: tool calling + signature on each candidate model) |

## aera-vault — the only way money moves (Autonomous Business, AI Security)

Rust, `near-sdk` 5.x, in `aera/contracts/aera-vault` (README there: build, test, deploy).

| Method | Who | Rule |
|---|---|---|
| `ft_on_transfer(sender_id, amount, msg)` | USDC token | `msg = {"order_id","offering"}` → order recorded, revenue split paid; wrong token / bad msg / duplicate → refunded |
| `request_payment(request_id, receiver_id, amount, purpose, reference)` | agent only | allowlisted receiver; ≤ per-tx cap and within daily cap → paid, else `pending`; duplicate id refused; frozen refused |
| `approve(request_id)` / `reject(request_id, reason)` | approver wallet, 1 yocto | approver's role limit ≥ amount |
| `refund(order_id, amount)` | approver wallet, 1 yocto | never the agent |
| `deliver_receipt(order_id, content_hash)` | agent | sha256 of the delivered document, once |
| `freeze()` | owner, approver **or agent** | the guardian can pull the brake; only the owner can `unfreeze()` |
| `set_policy`, `add_counterparty`, `set_approver`, `set_split`, `set_agent` | owner, 1 yocto | |

**The agent's key** (`AERA_NEAR_AGENT_KEY`) is a function-call key on the vault for
`request_payment, deliver_receipt, freeze`. The agent account has no full-access key
(`manage.py ready` checks). A function-call key cannot attach a deposit, so it can never call
`ft_transfer` or send NEAR itself — the vault's rules are the only path.

Python side: `clients/near.py` (JSON-RPC, Borsh, `send_tx`, nonce lock), `core/chain.py`
(adapter, simulated rail when unconfigured), `settle.py` (execute approved payments, follow
pending ones, ingest paid orders), `core/guardian.py` (reads the vault allowlist and account
facts before a payment is even raised).

Setup: `python3 manage.py near-setup` prints the near-cli-rs commands (create vault + agent
sub-accounts, deploy with caps from the profile, add the function-call key, delete the agent's
full-access key, storage deposits, allowlist, approvers).

## NEAR Intents 1Click — paying across chains (Autonomous Business)

`clients/intents.py`: `quote` (`dry: true` first, `EXACT_OUTPUT`), `submit_deposit`, `status`,
and `check_quote_against_policy` (recipient, max amount in, slippage, amount out). Mainnet only
(no Intents testnet); fee 0.25% without a 1Click key (`ONECLICK_JWT`). Used for customers paying
in any token and vendors paid on their own chain; capped small for the demo.

## Data on chain the guardian reads

`view_account` (exists), `view_code` hash (contract vs wallet), NearBlocks account age, the
vault's `get_counterparty` — each labelled `live` in the ruling, so a person sees what was
checked and where it came from.
