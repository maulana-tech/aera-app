//! NEP-297 event helpers. Every log line looks like:
//! `EVENT_JSON:{"standard":"aera-vault","version":"1.0.0","event":"<name>","data":[{...}]}`

use near_sdk::env;
use near_sdk::serde_json::{json, Value};

pub const EVENT_STANDARD: &str = "aera-vault";
pub const EVENT_VERSION: &str = "1.0.0";

pub fn emit(event: &str, data: Value) {
    let payload = json!({
        "standard": EVENT_STANDARD,
        "version": EVENT_VERSION,
        "event": event,
        "data": [data],
    });
    env::log_str(&format!("EVENT_JSON:{}", payload));
}
