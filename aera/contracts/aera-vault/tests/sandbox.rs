//! End-to-end test on a local near-sandbox (near-workspaces).
//!
//! Prerequisites (the test reads prebuilt wasm):
//!   cargo near build non-reproducible-wasm                         # vault
//!   (cd tests/mock-ft && cargo near build non-reproducible-wasm --no-abi)  # mock NEP-141
//! Run (ignored by default: it downloads/starts a near-sandbox node):
//!   cargo test --features sandbox --test sandbox -- --ignored --nocapture
//! If the automatic sandbox download fails, point NEAR_SANDBOX_BIN_PATH at a near-sandbox binary.

use near_workspaces::types::NearToken;
use near_workspaces::{Account, Contract};
use serde_json::{json, Value};

const VAULT_WASM: &str = "target/near/aera_vault.wasm";
const FT_WASM: &str = "tests/mock-ft/target/near/mock_ft.wasm";
const ONE_YOCTO: NearToken = NearToken::from_yoctonear(1);

fn read_wasm(path: &str) -> anyhow::Result<Vec<u8>> {
    std::fs::read(path).map_err(|e| anyhow::anyhow!("{path}: {e} (build it first, see file header)"))
}

async fn sub(root: &Account, name: &str) -> anyhow::Result<Account> {
    Ok(root
        .create_subaccount(name)
        .initial_balance(NearToken::from_near(20))
        .transact()
        .await?
        .into_result()?)
}

async fn register(ft: &Contract, payer: &Account, who: &str) -> anyhow::Result<()> {
    payer
        .call(ft.id(), "storage_deposit")
        .args_json(json!({ "account_id": who }))
        .deposit(NearToken::from_millinear(125))
        .transact()
        .await?
        .into_result()?;
    Ok(())
}

async fn balance(ft: &Contract, who: &str) -> anyhow::Result<u128> {
    let v: String = ft
        .view("ft_balance_of")
        .args_json(json!({ "account_id": who }))
        .await?
        .json()?;
    Ok(v.parse()?)
}

async fn request(vault: &Contract, id: &str) -> anyhow::Result<Value> {
    Ok(vault
        .view("get_request")
        .args_json(json!({ "request_id": id }))
        .await?
        .json()?)
}

async fn policy(vault: &Contract) -> anyhow::Result<Value> {
    Ok(vault.view("get_policy").await?.json()?)
}

#[tokio::test]
#[ignore = "needs near-sandbox; run with --features sandbox -- --ignored"]
async fn vault_end_to_end() -> anyhow::Result<()> {
    let worker = near_workspaces::sandbox().await?;
    let root = worker.root_account()?;

    let owner = sub(&root, "owner").await?;
    let agent = sub(&root, "agent").await?;
    let finance = sub(&root, "finance").await?;
    let customer = sub(&root, "customer").await?;
    let vendor = sub(&root, "vendor").await?;
    let payee = sub(&root, "payee").await?;
    // allowlisted on the vault but never registered on the token -> ft_transfer fails
    let ghost = sub(&root, "ghost").await?;

    // --- token
    let ft_acc = sub(&root, "usdc").await?;
    let ft = ft_acc.deploy(&read_wasm(FT_WASM)?).await?.into_result()?;
    ft.call("new")
        .args_json(json!({ "owner_id": customer.id(), "total_supply": "10000000" }))
        .transact()
        .await?
        .into_result()?;

    // --- vault
    let vault_acc = sub(&root, "vault").await?;
    let vault = vault_acc.deploy(&read_wasm(VAULT_WASM)?).await?.into_result()?;
    vault
        .call("new")
        .args_json(json!({
            "owner": owner.id(), "agent": agent.id(), "token": ft.id(),
            "per_tx_cap": "100", "daily_cap": "250"
        }))
        .transact()
        .await?
        .into_result()?;

    for a in [vault.id(), vendor.id(), payee.id()] {
        register(&ft, &owner, a.as_str()).await?;
    }

    // --- policy (owner, 1 yocto)
    for (m, args) in [
        ("add_counterparty", json!({ "account_id": vendor.id(), "label": "vendor" })),
        ("add_counterparty", json!({ "account_id": ghost.id(), "label": "ghost" })),
        ("set_approver", json!({ "account_id": finance.id(), "role": "finance", "limit": "10000" })),
        ("set_split", json!({ "split": [{ "account_id": payee.id(), "bps": 1000 }] })),
    ] {
        owner
            .call(vault.id(), m)
            .args_json(args)
            .deposit(ONE_YOCTO)
            .transact()
            .await?
            .into_result()?;
    }

    // --- 1. order payment via ft_transfer_call -> split paid
    let out = customer
        .call(ft.id(), "ft_transfer_call")
        .args_json(json!({
            "receiver_id": vault.id(), "amount": "1000000",
            "msg": json!({ "order_id": "ord-1", "offering": "consult-1h" }).to_string()
        }))
        .deposit(ONE_YOCTO)
        .max_gas()
        .transact()
        .await?;
    assert!(out.is_success(), "{:?}", out.failures());
    assert!(out.logs().iter().any(|l| l.contains("\"event\":\"order_paid\"")));
    assert_eq!(balance(&ft, payee.id().as_str()).await?, 100_000);
    assert!(out.logs().iter().any(|l| l.contains("\"event\":\"split_paid\"")));
    assert_eq!(balance(&ft, vault.id().as_str()).await?, 900_000);
    let order: Value = vault
        .view("get_order")
        .args_json(json!({ "order_id": "ord-1" }))
        .await?
        .json()?;
    assert_eq!(order["amount"], "1000000");
    assert_eq!(order["payer"], customer.id().as_str());

    // duplicate order id is refunded in full by the token's resolve step
    let out = customer
        .call(ft.id(), "ft_transfer_call")
        .args_json(json!({
            "receiver_id": vault.id(), "amount": "500000",
            "msg": json!({ "order_id": "ord-1", "offering": "x" }).to_string()
        }))
        .deposit(ONE_YOCTO)
        .max_gas()
        .transact()
        .await?;
    assert!(out.is_success());
    assert_eq!(balance(&ft, vault.id().as_str()).await?, 900_000);

    // --- 2. autonomous payment
    let out = agent
        .call(vault.id(), "request_payment")
        .args_json(json!({
            "request_id": "pay-1", "receiver_id": vendor.id(), "amount": "50",
            "purpose": "api", "reference": "p1"
        }))
        .max_gas()
        .transact()
        .await?;
    assert!(out.is_success(), "{:?}", out.failures());
    assert_eq!(out.json::<String>()?, "sent");
    assert_eq!(balance(&ft, vendor.id().as_str()).await?, 50);
    assert_eq!(request(&vault, "pay-1").await?["status"], "sent");
    assert_eq!(policy(&vault).await?["spent_today"], "50");

    // --- 3. pending -> approve
    let out = agent
        .call(vault.id(), "request_payment")
        .args_json(json!({
            "request_id": "pay-2", "receiver_id": vendor.id(), "amount": "500",
            "purpose": "vendor job", "reference": "p2"
        }))
        .max_gas()
        .transact()
        .await?;
    assert_eq!(out.json::<String>()?, "pending");
    assert_eq!(balance(&ft, vendor.id().as_str()).await?, 50);
    let out = finance
        .call(vault.id(), "approve")
        .args_json(json!({ "request_id": "pay-2" }))
        .deposit(ONE_YOCTO)
        .max_gas()
        .transact()
        .await?;
    assert!(out.is_success(), "{:?}", out.failures());
    assert_eq!(balance(&ft, vendor.id().as_str()).await?, 550);
    let r = request(&vault, "pay-2").await?;
    assert_eq!(r["status"], "approved");
    assert_eq!(r["decided_by"], finance.id().as_str());
    assert_eq!(policy(&vault).await?["spent_today"], "50");

    // --- 4. failed transfer (receiver not registered on token) -> rollback
    let out = agent
        .call(vault.id(), "request_payment")
        .args_json(json!({
            "request_id": "pay-3", "receiver_id": ghost.id(), "amount": "30",
            "purpose": "x", "reference": "p3"
        }))
        .max_gas()
        .transact()
        .await?;
    assert_eq!(out.json::<String>()?, "sent");
    assert_eq!(request(&vault, "pay-3").await?["status"], "failed");
    assert_eq!(policy(&vault).await?["spent_today"], "50");
    assert_eq!(balance(&ft, vault.id().as_str()).await?, 900_000 - 50 - 500);

    // --- 5. not allowlisted -> contract panics
    let out = agent
        .call(vault.id(), "request_payment")
        .args_json(json!({
            "request_id": "pay-4", "receiver_id": customer.id(), "amount": "1",
            "purpose": "x", "reference": "x"
        }))
        .max_gas()
        .transact()
        .await?;
    assert!(out.is_failure());
    assert!(format!("{:?}", out.failures()).contains("receiver not allowlisted"));

    // --- 6. agent cannot refund; approver can
    let out = agent
        .call(vault.id(), "refund")
        .args_json(json!({ "order_id": "ord-1", "amount": "100" }))
        .deposit(ONE_YOCTO)
        .max_gas()
        .transact()
        .await?;
    assert!(out.is_failure());
    let before = balance(&ft, customer.id().as_str()).await?;
    let out = finance
        .call(vault.id(), "refund")
        .args_json(json!({ "order_id": "ord-1", "amount": "100" }))
        .deposit(ONE_YOCTO)
        .max_gas()
        .transact()
        .await?;
    assert!(out.is_success(), "{:?}", out.failures());
    assert_eq!(balance(&ft, customer.id().as_str()).await? - before, 100);

    // --- 7. agent pulls the brake; requests are blocked; only owner unfreezes
    agent
        .call(vault.id(), "freeze")
        .transact()
        .await?
        .into_result()?;
    let out = agent
        .call(vault.id(), "request_payment")
        .args_json(json!({
            "request_id": "pay-5", "receiver_id": vendor.id(), "amount": "1",
            "purpose": "x", "reference": "x"
        }))
        .max_gas()
        .transact()
        .await?;
    assert!(format!("{:?}", out.failures()).contains("vault is frozen"));
    let out = agent
        .call(vault.id(), "unfreeze")
        .deposit(ONE_YOCTO)
        .transact()
        .await?;
    assert!(out.is_failure());
    owner
        .call(vault.id(), "unfreeze")
        .deposit(ONE_YOCTO)
        .transact()
        .await?
        .into_result()?;
    assert_eq!(policy(&vault).await?["frozen"], false);

    let reqs: Vec<Value> = vault
        .view("list_requests")
        .args_json(json!({ "from_index": 0, "limit": 10 }))
        .await?
        .json()?;
    assert_eq!(reqs.len(), 3);
    Ok(())
}
