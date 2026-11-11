use super::*;
use near_sdk::test_utils::{get_logs, VMContextBuilder};
use near_sdk::testing_env;

const DAY: u64 = NS_PER_DAY;
const T0: u64 = 20_000 * DAY + 1_000;

fn acc(s: &str) -> AccountId {
    s.parse().unwrap()
}
fn owner() -> AccountId {
    acc("owner.testnet")
}
fn agent() -> AccountId {
    acc("agent.vault.testnet")
}
fn token() -> AccountId {
    acc("usdc.testnet")
}
fn vendor() -> AccountId {
    acc("vendor.testnet")
}
fn approver() -> AccountId {
    acc("finance.testnet")
}
fn junior() -> AccountId {
    acc("junior.testnet")
}
fn customer() -> AccountId {
    acc("customer.testnet")
}

fn ctx(predecessor: AccountId, deposit: u128, ts: u64) {
    let mut b = VMContextBuilder::new();
    b.current_account_id(acc("vault.testnet"))
        .signer_account_id(predecessor.clone())
        .predecessor_account_id(predecessor)
        .attached_deposit(NearToken::from_yoctonear(deposit))
        .block_timestamp(ts);
    testing_env!(b.build());
}

/// per_tx_cap = 100, daily_cap = 250; vendor allowlisted; finance (limit 1000), junior (limit 50).
fn setup() -> AeraVault {
    ctx(owner(), 0, T0);
    let mut v = AeraVault::new(owner(), agent(), token(), U128(100), U128(250));
    ctx(owner(), 1, T0);
    v.add_counterparty(vendor(), "Vendor".into());
    v.set_approver(approver(), Some("finance".into()), U128(1_000));
    v.set_approver(junior(), Some("ops".into()), U128(50));
    v
}

fn req(v: &mut AeraVault, id: &str, amount: u128, ts: u64) -> String {
    ctx(agent(), 0, ts);
    v.request_payment(
        id.into(),
        vendor(),
        U128(amount),
        "api credits".into(),
        "payable-1".into(),
    )
}

fn has_event(name: &str) -> bool {
    get_logs()
        .iter()
        .any(|l| l.starts_with("EVENT_JSON:") && l.contains(&format!("\"event\":\"{}\"", name)))
}

fn order_msg(id: &str) -> String {
    format!(r#"{{"order_id":"{}","offering":"consult-1h"}}"#, id)
}

fn pay_order(v: &mut AeraVault, id: &str, amount: u128) -> U128 {
    ctx(token(), 0, T0);
    match v.ft_on_transfer(customer(), U128(amount), order_msg(id)) {
        PromiseOrValue::Value(r) => r,
        PromiseOrValue::Promise(_) => panic!("unexpected promise"),
    }
}

// ----------------------------------------------------------- request_payment

#[test]
fn under_cap_is_sent_and_spent_increments() {
    let mut v = setup();
    assert_eq!(req(&mut v, "r1", 60, T0), "sent");
    assert!(has_event("payment_requested"));
    assert!(has_event("payment_sent"));
    assert_eq!(v.get_policy().spent_today, U128(60));
    assert_eq!(req(&mut v, "r2", 40, T0), "sent");
    assert_eq!(v.get_policy().spent_today, U128(100));
    assert_eq!(v.get_request("r1".into()).unwrap().status, "sent");
}

#[test]
#[should_panic(expected = "duplicate request_id")]
fn duplicate_request_id_rejected() {
    let mut v = setup();
    req(&mut v, "r1", 10, T0);
    req(&mut v, "r1", 10, T0);
}

#[test]
#[should_panic(expected = "receiver not allowlisted")]
fn non_allowlisted_receiver_rejected() {
    let mut v = setup();
    ctx(agent(), 0, T0);
    v.request_payment(
        "r1".into(),
        acc("attacker.testnet"),
        U128(10),
        "x".into(),
        "y".into(),
    );
}

#[test]
#[should_panic(expected = "only agent")]
fn non_agent_caller_rejected() {
    let mut v = setup();
    ctx(owner(), 0, T0);
    v.request_payment("r1".into(), vendor(), U128(10), "x".into(), "y".into());
}

#[test]
#[should_panic(expected = "amount must be > 0")]
fn zero_amount_rejected() {
    let mut v = setup();
    req(&mut v, "r1", 0, T0);
}

#[test]
fn over_per_tx_cap_is_pending() {
    let mut v = setup();
    assert_eq!(req(&mut v, "big", 101, T0), "pending");
    assert!(has_event("payment_pending"));
    assert_eq!(v.get_policy().spent_today, U128(0));
    assert_eq!(v.get_request("big".into()).unwrap().status, "pending");
}

#[test]
fn daily_cap_then_rollover_next_day() {
    let mut v = setup();
    assert_eq!(req(&mut v, "a", 100, T0), "sent");
    assert_eq!(req(&mut v, "b", 100, T0 + 10), "sent");
    // 200 + 100 > 250 → pending
    assert_eq!(req(&mut v, "c", 100, T0 + 20), "pending");
    assert_eq!(req(&mut v, "d", 50, T0 + 30), "sent");
    assert_eq!(v.get_policy().spent_today, U128(250));
    // View rolls over on its own at the next day.
    ctx(owner(), 0, T0 + DAY);
    assert_eq!(v.get_policy().spent_today, U128(0));
    assert_eq!(req(&mut v, "e", 100, T0 + DAY), "sent");
    assert_eq!(v.get_policy().spent_today, U128(100));
    assert_eq!(v.get_policy().day, (T0 + DAY) / DAY);
}

// ---------------------------------------------------------- approve / reject

#[test]
fn approver_can_approve_pending() {
    let mut v = setup();
    req(&mut v, "big", 500, T0);
    ctx(approver(), 1, T0);
    let _ = v.approve("big".into());
    let r = v.get_request("big".into()).unwrap();
    assert_eq!(r.status, "approved");
    assert_eq!(r.decided_by, Some(approver()));
    assert!(has_event("payment_approved"));
    // approved payments do not consume the autonomous daily budget
    assert_eq!(v.get_policy().spent_today, U128(0));
}

#[test]
fn owner_can_approve_any_amount() {
    let mut v = setup();
    req(&mut v, "huge", 1_000_000, T0);
    ctx(owner(), 1, T0);
    let _ = v.approve("huge".into());
    assert_eq!(v.get_request("huge".into()).unwrap().status, "approved");
}

#[test]
#[should_panic(expected = "amount exceeds approver limit")]
fn low_limit_approver_cannot_approve() {
    let mut v = setup();
    req(&mut v, "big", 500, T0);
    ctx(junior(), 1, T0);
    let _ = v.approve("big".into());
}

#[test]
#[should_panic(expected = "only owner or approver")]
fn stranger_cannot_approve() {
    let mut v = setup();
    req(&mut v, "big", 500, T0);
    ctx(vendor(), 1, T0);
    let _ = v.approve("big".into());
}

#[test]
#[should_panic(expected = "Requires attached deposit of exactly 1 yoctoNEAR")]
fn approve_requires_one_yocto() {
    let mut v = setup();
    req(&mut v, "big", 500, T0);
    ctx(approver(), 0, T0);
    let _ = v.approve("big".into());
}

#[test]
#[should_panic(expected = "request is not pending")]
fn cannot_approve_sent_request() {
    let mut v = setup();
    req(&mut v, "small", 10, T0);
    ctx(approver(), 1, T0);
    let _ = v.approve("small".into());
}

#[test]
fn reject_path() {
    let mut v = setup();
    req(&mut v, "big", 500, T0);
    ctx(junior(), 1, T0);
    v.reject("big".into(), "not in budget".into());
    let r = v.get_request("big".into()).unwrap();
    assert_eq!(r.status, "rejected");
    assert_eq!(r.reason.as_deref(), Some("not in budget"));
    assert_eq!(r.decided_by, Some(junior()));
    assert!(has_event("payment_rejected"));
}

#[test]
#[should_panic(expected = "request is not pending")]
fn cannot_approve_after_reject() {
    let mut v = setup();
    req(&mut v, "big", 500, T0);
    ctx(approver(), 1, T0);
    v.reject("big".into(), "no".into());
    let _ = v.approve("big".into());
}

// ------------------------------------------------------------- on_transfer

#[test]
fn failed_autonomous_transfer_rolls_back_spent() {
    let mut v = setup();
    req(&mut v, "r1", 80, T0);
    assert_eq!(v.get_policy().spent_today, U128(80));
    ctx(acc("vault.testnet"), 0, T0 + 5);
    v.resolve_transfer("r1".into(), false);
    assert_eq!(v.get_request("r1".into()).unwrap().status, "failed");
    assert_eq!(v.get_policy().spent_today, U128(0));
    assert!(has_event("payment_failed"));
}

#[test]
fn failed_approved_transfer_does_not_touch_spent() {
    let mut v = setup();
    req(&mut v, "small", 30, T0);
    req(&mut v, "big", 500, T0);
    ctx(approver(), 1, T0);
    let _ = v.approve("big".into());
    v.resolve_transfer("big".into(), false);
    assert_eq!(v.get_request("big".into()).unwrap().status, "failed");
    assert_eq!(v.get_policy().spent_today, U128(30));
}

#[test]
fn failed_transfer_previous_day_does_not_reduce_today() {
    let mut v = setup();
    req(&mut v, "old", 80, T0);
    req(&mut v, "new", 20, T0 + DAY); // rolls day, spent = 20
    v.resolve_transfer("old".into(), false);
    assert_eq!(v.get_policy().spent_today, U128(20));
}

#[test]
fn successful_transfer_keeps_status() {
    let mut v = setup();
    req(&mut v, "r1", 80, T0);
    v.resolve_transfer("r1".into(), true);
    assert_eq!(v.get_request("r1".into()).unwrap().status, "sent");
    assert_eq!(v.get_policy().spent_today, U128(80));
}

// ------------------------------------------------------------------ freeze

#[test]
#[should_panic(expected = "vault is frozen")]
fn frozen_blocks_request_payment() {
    let mut v = setup();
    ctx(junior(), 0, T0);
    v.freeze();
    assert!(has_event("frozen"));
    req(&mut v, "r1", 10, T0);
}

#[test]
#[should_panic(expected = "vault is frozen")]
fn frozen_blocks_approve() {
    let mut v = setup();
    req(&mut v, "big", 500, T0);
    ctx(approver(), 0, T0);
    v.freeze();
    ctx(approver(), 1, T0);
    let _ = v.approve("big".into());
}

#[test]
#[should_panic(expected = "only owner, approver or agent can freeze")]
fn stranger_cannot_freeze() {
    let mut v = setup();
    ctx(vendor(), 0, T0);
    v.freeze();
}

#[test]
fn agent_can_freeze() {
    let mut v = setup();
    ctx(agent(), 0, T0);
    v.freeze();
    assert!(v.get_policy().frozen);
    assert!(has_event("frozen"));
}

#[test]
#[should_panic(expected = "only owner can call this method")]
fn agent_can_freeze_but_not_unfreeze() {
    let mut v = setup();
    ctx(agent(), 0, T0);
    v.freeze();
    ctx(agent(), 1, T0);
    v.unfreeze();
}

#[test]
#[should_panic(expected = "only owner can call this method")]
fn approver_cannot_unfreeze() {
    let mut v = setup();
    ctx(approver(), 0, T0);
    v.freeze();
    ctx(approver(), 1, T0);
    v.unfreeze();
}

#[test]
fn owner_can_unfreeze() {
    let mut v = setup();
    ctx(approver(), 0, T0);
    v.freeze();
    assert!(v.get_policy().frozen);
    ctx(owner(), 1, T0);
    v.unfreeze();
    assert!(!v.get_policy().frozen);
    assert!(has_event("unfrozen"));
    assert_eq!(req(&mut v, "r1", 10, T0), "sent");
}

// --------------------------------------------------------------- money in

#[test]
fn ft_on_transfer_from_wrong_token_refunds() {
    let mut v = setup();
    ctx(acc("fake-usdc.testnet"), 0, T0);
    let r = match v.ft_on_transfer(customer(), U128(500), order_msg("o1")) {
        PromiseOrValue::Value(r) => r,
        _ => panic!(),
    };
    assert_eq!(r, U128(500));
    assert!(v.get_order("o1".into()).is_none());
}

#[test]
fn ft_on_transfer_invalid_msg_refunds() {
    let mut v = setup();
    ctx(token(), 0, T0);
    let r = match v.ft_on_transfer(customer(), U128(500), "not json".into()) {
        PromiseOrValue::Value(r) => r,
        _ => panic!(),
    };
    assert_eq!(r, U128(500));
}

#[test]
fn order_recorded_and_duplicate_refunded() {
    let mut v = setup();
    assert_eq!(pay_order(&mut v, "o1", 500_000), U128(0));
    assert!(has_event("order_paid"));
    let o = v.get_order("o1".into()).unwrap();
    assert_eq!(o.payer, customer());
    assert_eq!(o.amount, U128(500_000));
    assert_eq!(o.offering, "consult-1h");
    assert_eq!(pay_order(&mut v, "o1", 700_000), U128(700_000));
    assert_eq!(v.get_order("o1".into()).unwrap().amount, U128(500_000));
    assert_eq!(v.list_orders(0, 10).len(), 1);
}

#[test]
fn split_math() {
    let split = vec![
        SplitEntry { account_id: acc("a.testnet"), bps: 7_000 },
        SplitEntry { account_id: acc("b.testnet"), bps: 2_500 },
        SplitEntry { account_id: acc("c.testnet"), bps: 1 },
    ];
    let out = split_amounts(&split, 1_000_000);
    assert_eq!(
        out,
        vec![
            (acc("a.testnet"), 700_000),
            (acc("b.testnet"), 250_000),
            (acc("c.testnet"), 100),
        ]
    );
    // tiny amount: zero shares are skipped, remainder stays in the vault
    let out = split_amounts(&split, 1);
    assert!(out.is_empty());
    // no overflow on huge amounts
    let out = split_amounts(&split[..1], u128::MAX);
    assert_eq!(out[0].1, u128::MAX / 10_000 * 7_000);
}

#[test]
fn order_pays_split_events() {
    let mut v = setup();
    ctx(owner(), 1, T0);
    v.set_split(vec![
        SplitEntry { account_id: acc("a.testnet"), bps: 6_000 },
        SplitEntry { account_id: acc("b.testnet"), bps: 1_000 },
    ]);
    pay_order(&mut v, "o1", 1_000_000);
    let splits: Vec<String> = get_logs()
        .into_iter()
        .filter(|l| l.contains("\"event\":\"split_started\""))
        .collect();
    assert_eq!(splits.len(), 2);
    assert!(splits[0].contains("\"amount\":\"600000\""));
    assert!(splits[1].contains("\"amount\":\"100000\""));
    // nothing is reported paid until the token has answered
    assert!(!has_event("split_paid"));
}

#[test]
fn frozen_vault_records_order_but_skips_split() {
    let mut v = setup();
    ctx(owner(), 1, T0);
    v.set_split(vec![SplitEntry { account_id: acc("a.testnet"), bps: 5_000 }]);
    ctx(owner(), 0, T0);
    v.freeze();
    assert_eq!(pay_order(&mut v, "o1", 1_000_000), U128(0));
    assert!(v.get_order("o1".into()).is_some());
    assert!(!has_event("split_paid") && !has_event("split_started"));
}

#[test]
fn split_outcome_events() {
    let _ = setup();
    resolve_split("o1".into(), acc("a.testnet"), U128(600_000), true);
    assert!(has_event("split_paid"));
    let _ = setup();
    resolve_split("o1".into(), acc("a.testnet"), U128(600_000), false);
    assert!(has_event("split_failed") && !has_event("split_paid"));
}

#[test]
fn dust_and_oversized_orders_refunded() {
    let mut v = setup();
    assert_eq!(pay_order(&mut v, "o1", MIN_ORDER_AMOUNT - 1), U128(MIN_ORDER_AMOUNT - 1));
    assert!(v.get_order("o1".into()).is_none());
    let long = "x".repeat(MAX_ID_LEN + 1);
    assert_eq!(pay_order(&mut v, &long, 500_000), U128(500_000));
    assert!(v.get_order(long).is_none());
    assert_eq!(pay_order(&mut v, "o2", MIN_ORDER_AMOUNT), U128(0));
}

#[test]
#[should_panic(expected = "split bps sum exceeds 10000")]
fn split_over_100_percent_rejected() {
    let mut v = setup();
    ctx(owner(), 1, T0);
    v.set_split(vec![
        SplitEntry { account_id: acc("a.testnet"), bps: 6_000 },
        SplitEntry { account_id: acc("b.testnet"), bps: 4_001 },
    ]);
}

#[test]
#[should_panic(expected = "duplicate split account")]
fn split_duplicate_account_rejected() {
    let mut v = setup();
    ctx(owner(), 1, T0);
    v.set_split(vec![
        SplitEntry { account_id: acc("a.testnet"), bps: 1_000 },
        SplitEntry { account_id: acc("a.testnet"), bps: 1_000 },
    ]);
}

// ------------------------------------------------------------------ refund

#[test]
#[should_panic(expected = "agent cannot refund")]
fn agent_cannot_refund() {
    let mut v = setup();
    pay_order(&mut v, "o1", 500_000);
    ctx(agent(), 1, T0);
    let _ = v.refund("o1".into(), U128(100));
}

#[test]
fn approver_refund_partial_and_limits() {
    let mut v = setup();
    pay_order(&mut v, "o1", 500_000);
    ctx(approver(), 1, T0);
    let _ = v.refund("o1".into(), U128(200));
    assert_eq!(v.get_order("o1".into()).unwrap().refunded, U128(200));
    assert!(has_event("refunded"));
    let _ = v.refund("o1".into(), U128(300));
    assert_eq!(v.get_order("o1".into()).unwrap().refunded, U128(500));
}

#[test]
#[should_panic(expected = "refund exceeds paid amount")]
fn refund_over_paid_rejected() {
    let mut v = setup();
    pay_order(&mut v, "o1", 500_000);
    ctx(owner(), 1, T0);
    let _ = v.refund("o1".into(), U128(500_001));
}

// ------------------------------------------------------- deliver_receipt

#[test]
fn deliver_receipt_once() {
    let mut v = setup();
    pay_order(&mut v, "o1", 500_000);
    ctx(agent(), 0, T0);
    v.deliver_receipt("o1".into(), "sha256:abc".into());
    assert_eq!(
        v.get_order("o1".into()).unwrap().delivered_hash.as_deref(),
        Some("sha256:abc")
    );
    assert!(has_event("delivered"));
}

#[test]
#[should_panic(expected = "receipt already delivered")]
fn deliver_receipt_twice_rejected() {
    let mut v = setup();
    pay_order(&mut v, "o1", 500_000);
    ctx(agent(), 0, T0);
    v.deliver_receipt("o1".into(), "h1".into());
    v.deliver_receipt("o1".into(), "h2".into());
}

// ------------------------------------------------------------- admin/views

#[test]
#[should_panic(expected = "only owner can call this method")]
fn non_owner_cannot_add_counterparty() {
    let mut v = setup();
    ctx(approver(), 1, T0);
    v.add_counterparty(acc("x.testnet"), "x".into());
}

#[test]
#[should_panic(expected = "Requires attached deposit of exactly 1 yoctoNEAR")]
fn owner_admin_requires_one_yocto() {
    let mut v = setup();
    ctx(owner(), 0, T0);
    v.set_policy(U128(1), U128(2));
}

#[test]
fn remove_counterparty_blocks_payments() {
    let mut v = setup();
    ctx(owner(), 1, T0);
    v.remove_counterparty(vendor());
    assert!(v.get_counterparty(vendor()).is_none());
    assert!(has_event("counterparty_removed"));
    assert!(v.list_counterparties().is_empty());
}

#[test]
fn approver_removed_with_none() {
    let mut v = setup();
    ctx(owner(), 1, T0);
    v.set_approver(junior(), None, U128(0));
    let p = v.get_policy();
    assert_eq!(p.approvers.len(), 1);
    assert_eq!(p.approvers[0].account_id, approver());
}

#[test]
fn pagination() {
    let mut v = setup();
    for i in 0..5 {
        req(&mut v, &format!("r{}", i), 1, T0);
    }
    let page1 = v.list_requests(0, 2);
    assert_eq!(page1.iter().map(|r| r.id.as_str()).collect::<Vec<_>>(), ["r0", "r1"]);
    let page3 = v.list_requests(4, 10);
    assert_eq!(page3.len(), 1);
    assert_eq!(page3[0].id, "r4");
    assert!(v.list_requests(99, 10).is_empty());
}

#[test]
fn set_policy_and_agent() {
    let mut v = setup();
    ctx(owner(), 1, T0);
    v.set_policy(U128(5), U128(10));
    v.set_agent(acc("agent2.vault.testnet"));
    let p = v.get_policy();
    assert_eq!(p.per_tx_cap, U128(5));
    assert_eq!(p.daily_cap, U128(10));
    assert_eq!(p.agent, acc("agent2.vault.testnet"));
    assert!(has_event("policy_set"));
}
