# aera-vault

The NEAR contract behind AERA's money flows. It is the **third brake** (NEAR-PLAN §8.1): if
the Python layer and the Guardian guardian are both bypassed, the vault still enforces the
allowlist, the caps, the approver limits and the freeze switch on-chain.

- **Money in.** Customers pay with `ft_transfer_call` on the USDC token, using
  `msg = {"order_id": "...", "offering": "..."}`. The vault records the order and pays the
  revenue split.
- **Money out.** The agent, which holds only a function-call key, calls `request_payment`.
  A payment within the per-tx cap and the daily cap goes out on its own. Anything larger
  waits as `pending` for a human approver whose limit covers the amount.
- **Refunds** always need a human (approver or owner). The agent can never call `refund`.
- **Kill switch.** The owner, any approver, or the agent (when the guardian detects an
  attack) can `freeze`. Only the owner can `unfreeze`.

## What it enforces

| Rule | Where |
|---|---|
| Only `agent` can request payments or write delivery receipts | `request_payment`, `deliver_receipt` |
| Receiver must be allowlisted; otherwise it panics with `receiver not allowlisted` | `request_payment` |
| Request ids are unique (idempotency key shared with the agent's SQLite) | `request_payment` |
| Autonomous only if `amount ≤ per_tx_cap` and `spent_today + amount ≤ daily_cap`; the daily budget rolls over at the UTC day boundary (`block_timestamp / 86_400e9`) | `request_payment` |
| A human approves only up to their `limit`; the owner has no limit; approved payments do not use the autonomous daily budget | `approve` |
| A failed transfer marks the request `failed` and gives back `spent_today` (same day, autonomous only) | `on_transfer` |
| A refund needs a human, can't exceed `paid − refunded`, and is rolled back if the transfer fails | `refund`, `on_refund` |
| Freezing blocks `request_payment`, `approve` and revenue-split payouts. Orders are still recorded and the revenue stays in the vault | `freeze` |
| All admin calls are owner-only and need 1 yoctoNEAR, so a function-call key can't make them | `set_*`, `add/remove_counterparty`, `unfreeze` |
| Only the configured token is accepted; a bad msg or a duplicate order is refunded in full | `ft_on_transfer` |
| Split: each entry has `bps > 0`, no account appears twice, the sum is `≤ 10000`; each payee gets `amount*bps/10000` and the remainder stays in the vault | `set_split`, `ft_on_transfer` |

## Methods

All amounts are U128 JSON strings. Timestamps are nanoseconds (`u64`).

| Method | Caller | Deposit | Notes |
|---|---|---|---|
| `new(owner, agent, token, per_tx_cap, daily_cap)` | deployer | – | `#[init]` |
| `ft_on_transfer(sender_id, amount, msg)` | `token` | – | Returns the refund amount: `"0"` when accepted |
| `request_payment(request_id, receiver_id, amount, purpose, reference)` | agent | – | Returns `"sent"` or `"pending"` |
| `approve(request_id)` | approver/owner | 1 yocto | pending → approved → `ft_transfer` |
| `reject(request_id, reason)` | approver/owner | 1 yocto | pending → rejected |
| `on_transfer(request_id)` | self | – | `#[private]` callback |
| `refund(order_id, amount)` | approver/owner (never the agent) | 1 yocto | Approver needs `limit ≥ amount` |
| `on_refund(order_id, amount)` | self | – | `#[private]` callback |
| `deliver_receipt(order_id, content_hash)` | agent | – | Can be set only once |
| `set_policy(per_tx_cap, daily_cap)` | owner | 1 yocto | |
| `add_counterparty(account_id, label)` / `remove_counterparty(account_id)` | owner | 1 yocto | |
| `set_approver(account_id, role, limit)` | owner | 1 yocto | `role: null` removes the approver; the agent can't be an approver |
| `set_split(split: [{account_id, bps}])` | owner | 1 yocto | |
| `set_agent(agent)` | owner | 1 yocto | |
| `freeze()` | owner, approver, or agent | – | Fast emergency stop |
| `unfreeze()` | owner | 1 yocto | |
| `get_policy()` | view | | `{owner, agent, token, per_tx_cap, daily_cap, spent_today, day, frozen, split, approvers:[{account_id, role, limit}]}` |
| `get_counterparty(account_id)` / `list_counterparties()` | view | | |
| `get_request(request_id)` / `list_requests(from_index, limit)` | view | | Insertion order; at most 100 per page |
| `get_order(order_id)` / `list_orders(from_index, limit)` | view | | Insertion order; at most 100 per page |

Request status values: `sent | pending | approved | rejected | failed`.

### Events (NEP-297)

`EVENT_JSON:{"standard":"aera-vault","version":"1.0.0","event":"<name>","data":[{...}]}`.
The event names are `order_paid`, `split_paid`, `payment_requested`, `payment_sent`,
`payment_pending`, `payment_approved`, `payment_rejected`, `payment_failed`, `refunded`,
`delivered`, `frozen`, `unfrozen`, `policy_set`, `counterparty_added` and
`counterparty_removed`. `payment_failed` carries `"kind":"refund"` when a refund transfer
fails.

## Build and test

You need Rust stable with the `wasm32-unknown-unknown` target (pinned in
`rust-toolchain.toml`) and [cargo-near](https://github.com/near/cargo-near) 0.23.

```bash
cd aera/contracts/aera-vault
cargo test                                  # unit tests (VMContextBuilder)
cargo near build non-reproducible-wasm      # -> target/near/aera_vault.wasm (+ ABI)

# End-to-end on a local near-sandbox (near-workspaces 0.24 + a mock NEP-141 in tests/mock-ft)
(cd tests/mock-ft && cargo near build non-reproducible-wasm --no-abi)
cargo test --features sandbox --test sandbox -- --ignored --nocapture   # set NEAR_SANDBOX_BIN_PATH if the auto-download fails
```

The sandbox test covers these flows: an order paid with `ft_transfer_call` and its split
paid out, a duplicate order refunded, an autonomous payment, pending → approve, a failed
transfer to an allowlisted receiver that isn't registered on the token (status `failed`,
`spent_today` rolled back), the `receiver not allowlisted` panic, the agent's refund being
refused while an approver's refund succeeds, and the agent freezing the vault while only
the owner can unfreeze.

## Deploy to testnet (near-cli-rs)

```bash
export OWNER=aera-owner.testnet          # your wallet account (full-access key stays in the wallet)
export VAULT=vault.$OWNER
export AGENT=agent.$VAULT
export USDC=3e2210e1184b45b64c8a434c0a7e7b23cc04ea7eb7a6c3c32520d03d4afcb8af  # testnet USDC; check the current id
export VENDOR=vendor.testnet

# 1. Vault account, then deploy and initialise (caps are in USDC base units, 6 decimals: 5 USDC / 20 USDC)
near account create-account fund-myself $VAULT '5 NEAR' autogenerate-new-keypair save-to-keychain sign-as $OWNER network-config testnet sign-with-keychain send
near contract deploy $VAULT use-file target/near/aera_vault.wasm \
  with-init-call new json-args "{\"owner\":\"$OWNER\",\"agent\":\"$AGENT\",\"token\":\"$USDC\",\"per_tx_cap\":\"5000000\",\"daily_cap\":\"20000000\"}" \
  prepaid-gas '30 Tgas' attached-deposit '0 NEAR' network-config testnet sign-with-keychain send

# 2. Agent sub-account that holds ONLY a function-call key, limited to the vault and three methods.
#    The key can't attach a deposit, so it can't call ft_transfer, approve, refund or any admin method.
near account create-account fund-myself $AGENT '0.5 NEAR' autogenerate-new-keypair save-to-keychain sign-as $VAULT network-config testnet sign-with-keychain send
near account add-key $AGENT grant-function-call-access \
  --allowance '0.5 NEAR' --contract-account-id $VAULT \
  --function-names 'request_payment, deliver_receipt, freeze' \
  autogenerate-new-keypair save-to-keychain network-config testnet sign-with-keychain send
#    Then delete the agent's full-access key so only the FC key is left:
near account list-keys $AGENT network-config testnet now
near account delete-keys $AGENT public-keys ed25519:<FULL_ACCESS_PUBKEY> network-config testnet sign-with-keychain send

# 3. Register storage on USDC for the vault, every counterparty, and every split payee
for A in $VAULT $VENDOR; do
  near contract call-function as-transaction $USDC storage_deposit json-args "{\"account_id\":\"$A\"}" \
    prepaid-gas '30 Tgas' attached-deposit '0.00125 NEAR' sign-as $OWNER network-config testnet sign-with-keychain send
done

# 4. Policy (owner signs, 1 yocto)
near contract call-function as-transaction $VAULT add_counterparty json-args "{\"account_id\":\"$VENDOR\",\"label\":\"API vendor\"}" \
  prepaid-gas '30 Tgas' attached-deposit '1 yoctoNEAR' sign-as $OWNER network-config testnet sign-with-keychain send
near contract call-function as-transaction $VAULT set_approver json-args '{"account_id":"finance.testnet","role":"finance","limit":"100000000"}' \
  prepaid-gas '30 Tgas' attached-deposit '1 yoctoNEAR' sign-as $OWNER network-config testnet sign-with-keychain send
near contract call-function as-transaction $VAULT set_split json-args "{\"split\":[{\"account_id\":\"$OWNER\",\"bps\":1000}]}" \
  prepaid-gas '30 Tgas' attached-deposit '1 yoctoNEAR' sign-as $OWNER network-config testnet sign-with-keychain send

# 5. A customer pays an order (allow ~10 Tgas per split payee on top of the base gas)
near contract call-function as-transaction $USDC ft_transfer_call \
  json-args "{\"receiver_id\":\"$VAULT\",\"amount\":\"10000000\",\"msg\":\"{\\\"order_id\\\":\\\"ord-1\\\",\\\"offering\\\":\\\"consult-1h\\\"}\"}" \
  prepaid-gas '100 Tgas' attached-deposit '1 yoctoNEAR' sign-as customer.testnet network-config testnet sign-with-keychain send

# 6. The agent pays a vendor (FC key, no deposit)
near contract call-function as-transaction $VAULT request_payment \
  json-args "{\"request_id\":\"pay-1\",\"receiver_id\":\"$VENDOR\",\"amount\":\"1000000\",\"purpose\":\"api credits\",\"reference\":\"payable-1\"}" \
  prepaid-gas '60 Tgas' attached-deposit '0 NEAR' sign-as $AGENT network-config testnet sign-with-keychain send

# Views
near contract call-function as-read-only $VAULT get_policy json-args '{}' network-config testnet now
near contract call-function as-read-only $VAULT list_requests json-args '{"from_index":0,"limit":20}' network-config testnet now
```

Gas: `request_payment` and `approve` use about 10 Tgas for `ft_transfer` plus 10 Tgas for the
callback, so attach 50–60 Tgas. The vault pays its own storage out of its NEAR balance, so
keep a few NEAR on it.
