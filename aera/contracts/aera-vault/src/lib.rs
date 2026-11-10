//! AERA Vault — the on-chain "third brake" for an autonomous business.
//!
//! * Money in: customers pay orders with `ft_transfer_call` on the USDC token; the vault
//!   records the order and pays the configured revenue split.
//! * Money out: the AI agent (function-call key only) may `request_payment` to allowlisted
//!   counterparties. Small payments within per-tx / daily caps are sent autonomously;
//!   anything larger waits for a human approver whose role limit covers the amount.
//! * Refunds always need a human. Any approver can `freeze` the vault instantly.

use near_sdk::json_types::U128;
use near_sdk::serde::{Deserialize, Serialize};
use near_sdk::serde_json::{self, json};
use near_sdk::store::{IterableMap, Vector};
use near_sdk::{
    assert_one_yocto, env, ext_contract, near, require, AccountId, BorshStorageKey, Gas,
    NearToken, PanicOnDefault, Promise, PromiseOrValue,
};

mod events;
use events::emit;

#[cfg(test)]
mod tests;

pub const NS_PER_DAY: u64 = 86_400_000_000_000;
pub const MAX_BPS: u16 = 10_000;
pub const GAS_FT_TRANSFER: Gas = Gas::from_tgas(10);
pub const GAS_CALLBACK: Gas = Gas::from_tgas(10);
pub const ONE_YOCTO: NearToken = NearToken::from_yoctonear(1);
pub const MAX_PAGE: u64 = 100;

pub const STATUS_SENT: &str = "sent";
pub const STATUS_PENDING: &str = "pending";
pub const STATUS_APPROVED: &str = "approved";
pub const STATUS_REJECTED: &str = "rejected";
pub const STATUS_FAILED: &str = "failed";

#[ext_contract(ext_ft)]
#[allow(dead_code)]
trait FungibleToken {
    fn ft_transfer(&mut self, receiver_id: AccountId, amount: U128, memo: Option<String>);
}

#[derive(BorshStorageKey)]
#[near]
enum StorageKey {
    Approvers,
    Counterparties,
    Requests,
    RequestIds,
    Orders,
    OrderIds,
}

#[near(serializers = [borsh, json])]
#[derive(Clone, Debug, PartialEq)]
pub struct Approver {
    pub role: String,
    pub limit: U128,
}

#[near(serializers = [borsh, json])]
#[derive(Clone, Debug, PartialEq)]
pub struct Counterparty {
    pub label: String,
    pub added_at_ns: u64,
}

#[near(serializers = [json])]
#[derive(Clone, Debug, PartialEq)]
pub struct CounterpartyView {
    pub account_id: AccountId,
    pub label: String,
    pub added_at_ns: u64,
}

#[near(serializers = [borsh, json])]
#[derive(Clone, Debug, PartialEq)]
pub struct SplitEntry {
    pub account_id: AccountId,
    pub bps: u16,
}

#[near(serializers = [borsh, json])]
#[derive(Clone, Debug, PartialEq)]
pub struct Request {
    pub id: String,
    pub receiver_id: AccountId,
    pub amount: U128,
    pub purpose: String,
    pub reference: String,
    pub status: String,
    pub created_at_ns: u64,
    pub decided_by: Option<AccountId>,
    pub reason: Option<String>,
}

#[near(serializers = [borsh, json])]
#[derive(Clone, Debug, PartialEq)]
pub struct Order {
    pub order_id: String,
    pub payer: AccountId,
    pub amount: U128,
    pub offering: String,
    pub paid_at_ns: u64,
    pub delivered_hash: Option<String>,
    pub refunded: U128,
}

#[near(serializers = [json])]
#[derive(Clone, Debug, PartialEq)]
pub struct ApproverView {
    pub account_id: AccountId,
    pub role: String,
    pub limit: U128,
}

#[near(serializers = [json])]
#[derive(Clone, Debug, PartialEq)]
pub struct PolicyView {
    pub owner: AccountId,
    pub agent: AccountId,
    pub token: AccountId,
    pub per_tx_cap: U128,
    pub daily_cap: U128,
    /// Autonomous spend for `day` (already rolled over: 0 if the stored day is stale).
    pub spent_today: U128,
    pub day: u64,
    pub frozen: bool,
    pub split: Vec<SplitEntry>,
    pub approvers: Vec<ApproverView>,
}

#[derive(Serialize, Deserialize)]
#[serde(crate = "near_sdk::serde")]
struct OrderMsg {
    order_id: String,
    offering: String,
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct AeraVault {
    owner: AccountId,
    agent: AccountId,
    token: AccountId,
    per_tx_cap: u128,
    daily_cap: u128,
    spent_today: u128,
    day: u64,
    frozen: bool,
    approvers: IterableMap<AccountId, Approver>,
    counterparties: IterableMap<AccountId, Counterparty>,
    split: Vec<SplitEntry>,
    requests: IterableMap<String, Request>,
    request_ids: Vector<String>,
    orders: IterableMap<String, Order>,
    order_ids: Vector<String>,
}

fn current_day() -> u64 {
    env::block_timestamp() / NS_PER_DAY
}

#[near]
impl AeraVault {
    #[init]
    pub fn new(
        owner: AccountId,
        agent: AccountId,
        token: AccountId,
        per_tx_cap: U128,
        daily_cap: U128,
    ) -> Self {
        require!(owner != agent, "owner and agent must differ");
        Self {
            owner,
            agent,
            token,
            per_tx_cap: per_tx_cap.0,
            daily_cap: daily_cap.0,
            spent_today: 0,
            day: current_day(),
            frozen: false,
            approvers: IterableMap::new(StorageKey::Approvers),
            counterparties: IterableMap::new(StorageKey::Counterparties),
            split: Vec::new(),
            requests: IterableMap::new(StorageKey::Requests),
            request_ids: Vector::new(StorageKey::RequestIds),
            orders: IterableMap::new(StorageKey::Orders),
            order_ids: Vector::new(StorageKey::OrderIds),
        }
    }

    // ------------------------------------------------------------------ money in

    /// NEP-141 receiver. Only the configured token is accepted. Returns the amount to refund.
    pub fn ft_on_transfer(
        &mut self,
        sender_id: AccountId,
        amount: U128,
        msg: String,
    ) -> PromiseOrValue<U128> {
        if env::predecessor_account_id() != self.token {
            env::log_str("aera-vault: unsupported token, refunding");
            return PromiseOrValue::Value(amount);
        }
        let parsed: OrderMsg = match serde_json::from_str(&msg) {
            Ok(m) => m,
            Err(_) => {
                env::log_str("aera-vault: invalid order msg, refunding");
                return PromiseOrValue::Value(amount);
            }
        };
        if parsed.order_id.is_empty() || amount.0 == 0 {
            env::log_str("aera-vault: empty order_id or zero amount, refunding");
            return PromiseOrValue::Value(amount);
        }
        if self.orders.contains_key(&parsed.order_id) {
            env::log_str("aera-vault: duplicate order_id, refunding");
            return PromiseOrValue::Value(amount);
        }

        let order = Order {
            order_id: parsed.order_id.clone(),
            payer: sender_id.clone(),
            amount,
            offering: parsed.offering.clone(),
            paid_at_ns: env::block_timestamp(),
            delivered_hash: None,
            refunded: U128(0),
        };
        self.orders.insert(parsed.order_id.clone(), order);
        self.order_ids.push(parsed.order_id.clone());
        emit(
            "order_paid",
            json!({
                "order_id": parsed.order_id,
                "payer": sender_id,
                "amount": amount,
                "offering": parsed.offering,
            }),
        );

        if self.frozen {
            // Kill switch: keep the revenue in the vault, pay no splits while frozen.
            env::log_str("aera-vault: frozen, revenue split skipped");
            return PromiseOrValue::Value(U128(0));
        }

        for (account_id, share) in split_amounts(&self.split, amount.0) {
            emit(
                "split_paid",
                json!({
                    "order_id": parsed.order_id,
                    "account_id": account_id,
                    "amount": U128(share),
                }),
            );
            ext_ft::ext(self.token.clone())
                .with_attached_deposit(ONE_YOCTO)
                .with_static_gas(GAS_FT_TRANSFER)
                .ft_transfer(
                    account_id,
                    U128(share),
                    Some(format!("aera split {}", parsed.order_id)),
                )
                .detach();
        }
        PromiseOrValue::Value(U128(0))
    }

    /// Agent records the hash of the delivered document (once per order).
    pub fn deliver_receipt(&mut self, order_id: String, content_hash: String) {
        self.assert_agent();
        require!(!content_hash.is_empty(), "empty content_hash");
        let mut order = self.orders.get(&order_id).cloned().expect("order not found");
        require!(order.delivered_hash.is_none(), "receipt already delivered");
        order.delivered_hash = Some(content_hash.clone());
        self.orders.insert(order_id.clone(), order);
        emit(
            "delivered",
            json!({ "order_id": order_id, "content_hash": content_hash }),
        );
    }

    /// Human-only refund of (part of) an order back to the payer.
    #[payable]
    pub fn refund(&mut self, order_id: String, amount: U128) -> Promise {
        assert_one_yocto();
        let caller = env::predecessor_account_id();
        require!(caller != self.agent, "agent cannot refund");
        self.assert_human_limit(&caller, amount.0);
        require!(amount.0 > 0, "amount must be > 0");
        let mut order = self.orders.get(&order_id).cloned().expect("order not found");
        let remaining = order.amount.0 - order.refunded.0;
        require!(amount.0 <= remaining, "refund exceeds paid amount");
        order.refunded = U128(order.refunded.0 + amount.0);
        let payer = order.payer.clone();
        self.orders.insert(order_id.clone(), order);
        emit(
            "refunded",
            json!({
                "order_id": order_id,
                "payer": payer,
                "amount": amount,
                "by": caller,
            }),
        );
        ext_ft::ext(self.token.clone())
            .with_attached_deposit(ONE_YOCTO)
            .with_static_gas(GAS_FT_TRANSFER)
            .ft_transfer(payer, amount, Some(format!("aera refund {}", order_id)))
            .then(
                Self::ext(env::current_account_id())
                    .with_static_gas(GAS_CALLBACK)
                    .on_refund(order_id, amount),
            )
    }

    /// Callback for `refund`: if the transfer failed, give the refundable amount back.
    #[private]
    pub fn on_refund(&mut self, order_id: String, amount: U128) -> bool {
        let ok = near_sdk::is_promise_success();
        if !ok {
            if let Some(mut order) = self.orders.get(&order_id).cloned() {
                order.refunded = U128(order.refunded.0.saturating_sub(amount.0));
                self.orders.insert(order_id.clone(), order);
            }
            emit(
                "payment_failed",
                json!({ "order_id": order_id, "amount": amount, "kind": "refund" }),
            );
        }
        ok
    }

    // ----------------------------------------------------------------- money out

    pub fn request_payment(
        &mut self,
        request_id: String,
        receiver_id: AccountId,
        amount: U128,
        purpose: String,
        reference: String,
    ) -> String {
        self.assert_agent();
        require!(!self.frozen, "vault is frozen");
        require!(!request_id.is_empty(), "empty request_id");
        require!(
            !self.requests.contains_key(&request_id),
            "duplicate request_id"
        );
        require!(
            self.counterparties.contains_key(&receiver_id),
            "receiver not allowlisted"
        );
        require!(amount.0 > 0, "amount must be > 0");

        self.roll_day();
        let autonomous = amount.0 <= self.per_tx_cap
            && self
                .spent_today
                .checked_add(amount.0)
                .map_or(false, |s| s <= self.daily_cap);

        let status = if autonomous { STATUS_SENT } else { STATUS_PENDING };
        let req = Request {
            id: request_id.clone(),
            receiver_id: receiver_id.clone(),
            amount,
            purpose: purpose.clone(),
            reference: reference.clone(),
            status: status.to_string(),
            created_at_ns: env::block_timestamp(),
            decided_by: None,
            reason: None,
        };
        self.requests.insert(request_id.clone(), req);
        self.request_ids.push(request_id.clone());
        emit(
            "payment_requested",
            json!({
                "request_id": request_id,
                "receiver_id": receiver_id,
                "amount": amount,
                "purpose": purpose,
                "reference": reference,
            }),
        );

        if autonomous {
            self.spent_today += amount.0;
            emit(
                "payment_sent",
                json!({
                    "request_id": request_id,
                    "receiver_id": receiver_id,
                    "amount": amount,
                    "spent_today": U128(self.spent_today),
                }),
            );
            self.transfer_with_callback(request_id, receiver_id, amount)
                .detach();
        } else {
            emit(
                "payment_pending",
                json!({
                    "request_id": request_id,
                    "receiver_id": receiver_id,
                    "amount": amount,
                }),
            );
        }
        status.to_string()
    }

    #[payable]
    pub fn approve(&mut self, request_id: String) -> Promise {
        assert_one_yocto();
        require!(!self.frozen, "vault is frozen");
        let caller = env::predecessor_account_id();
        let mut req = self
            .requests
            .get(&request_id)
            .cloned()
            .expect("request not found");
        require!(req.status == STATUS_PENDING, "request is not pending");
        self.assert_human_limit(&caller, req.amount.0);
        req.status = STATUS_APPROVED.to_string();
        req.decided_by = Some(caller.clone());
        let receiver_id = req.receiver_id.clone();
        let amount = req.amount;
        self.requests.insert(request_id.clone(), req);
        emit(
            "payment_approved",
            json!({
                "request_id": request_id,
                "receiver_id": receiver_id,
                "amount": amount,
                "by": caller,
            }),
        );
        self.transfer_with_callback(request_id, receiver_id, amount)
    }

    #[payable]
    pub fn reject(&mut self, request_id: String, reason: String) {
        assert_one_yocto();
        let caller = env::predecessor_account_id();
        self.assert_human(&caller);
        let mut req = self
            .requests
            .get(&request_id)
            .cloned()
            .expect("request not found");
        require!(req.status == STATUS_PENDING, "request is not pending");
        req.status = STATUS_REJECTED.to_string();
        req.decided_by = Some(caller.clone());
        req.reason = Some(reason.clone());
        self.requests.insert(request_id.clone(), req);
        emit(
            "payment_rejected",
            json!({ "request_id": request_id, "by": caller, "reason": reason }),
        );
    }

    /// Callback after an outgoing `ft_transfer`.
    #[private]
    pub fn on_transfer(&mut self, request_id: String) -> bool {
        let ok = near_sdk::is_promise_success();
        self.resolve_transfer(request_id, ok);
        ok
    }

    // ------------------------------------------------------------- owner admin

    #[payable]
    pub fn set_policy(&mut self, per_tx_cap: U128, daily_cap: U128) {
        self.assert_owner_yocto();
        self.per_tx_cap = per_tx_cap.0;
        self.daily_cap = daily_cap.0;
        emit(
            "policy_set",
            json!({ "per_tx_cap": per_tx_cap, "daily_cap": daily_cap }),
        );
    }

    #[payable]
    pub fn add_counterparty(&mut self, account_id: AccountId, label: String) {
        self.assert_owner_yocto();
        let party = Counterparty {
            label: label.clone(),
            added_at_ns: env::block_timestamp(),
        };
        self.counterparties.insert(account_id.clone(), party);
        emit(
            "counterparty_added",
            json!({ "account_id": account_id, "label": label }),
        );
    }

    #[payable]
    pub fn remove_counterparty(&mut self, account_id: AccountId) {
        self.assert_owner_yocto();
        require!(
            self.counterparties.remove(&account_id).is_some(),
            "counterparty not found"
        );
        emit("counterparty_removed", json!({ "account_id": account_id }));
    }

    /// `role = None` removes the approver.
    #[payable]
    pub fn set_approver(&mut self, account_id: AccountId, role: Option<String>, limit: U128) {
        self.assert_owner_yocto();
        require!(account_id != self.agent, "agent cannot be an approver");
        match role {
            Some(role) => {
                self.approvers.insert(
                    account_id.clone(),
                    Approver {
                        role: role.clone(),
                        limit,
                    },
                );
                emit(
                    "policy_set",
                    json!({ "approver": account_id, "role": role, "limit": limit }),
                );
            }
            None => {
                self.approvers.remove(&account_id);
                emit(
                    "policy_set",
                    json!({ "approver": account_id, "role": null, "removed": true }),
                );
            }
        }
    }

    #[payable]
    pub fn set_split(&mut self, split: Vec<SplitEntry>) {
        self.assert_owner_yocto();
        validate_split(&split);
        emit("policy_set", json!({ "split": split }));
        self.split = split;
    }

    #[payable]
    pub fn set_agent(&mut self, agent: AccountId) {
        self.assert_owner_yocto();
        require!(agent != self.owner, "owner and agent must differ");
        require!(
            !self.approvers.contains_key(&agent),
            "agent cannot be an approver"
        );
        self.agent = agent.clone();
        emit("policy_set", json!({ "agent": agent }));
    }

    /// Emergency stop: owner, any approver, or the agent (guardian pulls the brake when it
    /// detects an attack). No deposit required. Only the owner can `unfreeze`.
    pub fn freeze(&mut self) {
        let caller = env::predecessor_account_id();
        require!(
            caller == self.owner || caller == self.agent || self.approvers.contains_key(&caller),
            "only owner, approver or agent can freeze"
        );
        self.frozen = true;
        emit("frozen", json!({ "by": caller }));
    }

    #[payable]
    pub fn unfreeze(&mut self) {
        self.assert_owner_yocto();
        self.frozen = false;
        emit("unfrozen", json!({ "by": env::predecessor_account_id() }));
    }

    // -------------------------------------------------------------------- views

    pub fn get_policy(&self) -> PolicyView {
        let today = current_day();
        let spent = if self.day == today { self.spent_today } else { 0 };
        PolicyView {
            owner: self.owner.clone(),
            agent: self.agent.clone(),
            token: self.token.clone(),
            per_tx_cap: U128(self.per_tx_cap),
            daily_cap: U128(self.daily_cap),
            spent_today: U128(spent),
            day: today,
            frozen: self.frozen,
            split: self.split.clone(),
            approvers: self
                .approvers
                .iter()
                .map(|(a, v)| ApproverView {
                    account_id: a.clone(),
                    role: v.role.clone(),
                    limit: v.limit,
                })
                .collect(),
        }
    }

    pub fn get_counterparty(&self, account_id: AccountId) -> Option<Counterparty> {
        self.counterparties.get(&account_id).cloned()
    }

    pub fn list_counterparties(&self) -> Vec<CounterpartyView> {
        self.counterparties
            .iter()
            .map(|(a, c)| CounterpartyView {
                account_id: a.clone(),
                label: c.label.clone(),
                added_at_ns: c.added_at_ns,
            })
            .collect()
    }

    pub fn get_request(&self, request_id: String) -> Option<Request> {
        self.requests.get(&request_id).cloned()
    }

    pub fn list_requests(&self, from_index: u64, limit: u64) -> Vec<Request> {
        page(&self.request_ids, from_index, limit)
            .filter_map(|id| self.requests.get(id).cloned())
            .collect()
    }

    pub fn get_order(&self, order_id: String) -> Option<Order> {
        self.orders.get(&order_id).cloned()
    }

    pub fn list_orders(&self, from_index: u64, limit: u64) -> Vec<Order> {
        page(&self.order_ids, from_index, limit)
            .filter_map(|id| self.orders.get(id).cloned())
            .collect()
    }
}

// ------------------------------------------------------------------ internals

impl AeraVault {
    fn assert_agent(&self) {
        require!(
            env::predecessor_account_id() == self.agent,
            "only agent can call this method"
        );
    }

    fn assert_owner_yocto(&self) {
        assert_one_yocto();
        require!(
            env::predecessor_account_id() == self.owner,
            "only owner can call this method"
        );
    }

    fn assert_human(&self, caller: &AccountId) {
        require!(
            *caller == self.owner || self.approvers.contains_key(caller),
            "only owner or approver can call this method"
        );
    }

    /// Owner has no limit; approvers need `limit >= amount`.
    fn assert_human_limit(&self, caller: &AccountId, amount: u128) {
        if *caller == self.owner {
            return;
        }
        match self.approvers.get(caller) {
            Some(a) => require!(a.limit.0 >= amount, "amount exceeds approver limit"),
            None => env::panic_str("only owner or approver can call this method"),
        }
    }

    fn roll_day(&mut self) {
        let today = current_day();
        if self.day != today {
            self.day = today;
            self.spent_today = 0;
        }
    }

    fn transfer_with_callback(
        &self,
        request_id: String,
        receiver_id: AccountId,
        amount: U128,
    ) -> Promise {
        ext_ft::ext(self.token.clone())
            .with_attached_deposit(ONE_YOCTO)
            .with_static_gas(GAS_FT_TRANSFER)
            .ft_transfer(receiver_id, amount, Some(format!("aera {}", request_id)))
            .then(
                Self::ext(env::current_account_id())
                    .with_static_gas(GAS_CALLBACK)
                    .on_transfer(request_id),
            )
    }

    /// Shared by `on_transfer`; separated so unit tests can drive both outcomes.
    pub(crate) fn resolve_transfer(&mut self, request_id: String, ok: bool) {
        if ok {
            return;
        }
        let Some(mut req) = self.requests.get(&request_id).cloned() else {
            return;
        };
        let was_autonomous = req.status == STATUS_SENT;
        req.status = STATUS_FAILED.to_string();
        let amount = req.amount;
        let created_day = req.created_at_ns / NS_PER_DAY;
        self.requests.insert(request_id.clone(), req);
        if was_autonomous && created_day == self.day {
            self.spent_today = self.spent_today.saturating_sub(amount.0);
        }
        emit(
            "payment_failed",
            json!({ "request_id": request_id, "amount": amount }),
        );
    }
}

fn page<'a>(
    ids: &'a Vector<String>,
    from_index: u64,
    limit: u64,
) -> impl Iterator<Item = &'a String> + 'a {
    let len = ids.len() as u64;
    let start = from_index.min(len);
    let end = start.saturating_add(limit.min(MAX_PAGE)).min(len);
    (start..end).filter_map(move |i| ids.get(i as u32))
}

pub(crate) fn validate_split(split: &[SplitEntry]) {
    let mut total: u32 = 0;
    for (i, e) in split.iter().enumerate() {
        require!(e.bps > 0, "split bps must be > 0");
        require!(
            !split[..i].iter().any(|p| p.account_id == e.account_id),
            "duplicate split account"
        );
        total += e.bps as u32;
    }
    require!(total <= MAX_BPS as u32, "split bps sum exceeds 10000");
}

/// `amount * bps / 10000` per entry, zero shares skipped. The remainder stays in the vault.
pub(crate) fn split_amounts(split: &[SplitEntry], amount: u128) -> Vec<(AccountId, u128)> {
    split
        .iter()
        .filter_map(|e| {
            let share = amount
                .checked_mul(e.bps as u128)
                .map(|v| v / MAX_BPS as u128)
                .unwrap_or_else(|| amount / MAX_BPS as u128 * e.bps as u128);
            (share > 0).then(|| (e.account_id.clone(), share))
        })
        .collect()
}
