"""Sends approved actions to SAP.

Kept apart from the agents on purpose: the agents propose, a human approves,
this file sends. Run it on a schedule.

    python3 sender.py                # one pass
"""
from __future__ import annotations

import json
import sys

from clients import sap_s4
from core import store

TARGETS = {
    "draft_po": ("API_PURCHASEREQ_PROCESS_SRV", "A_PurchaseRequisitionHeader"),
    "stock_transfer": ("API_STOCK_TRANSFER_SRV", "A_StockTransfer"),
    "create_sourcing_event": ("API_SOURCING_PROJECT_SRV", "A_SourcingProject"),
}


def send_approved() -> int:
    if not sap_s4.available():
        print("SAP_API_KEY is not set — nothing sent.")
        return 0

    with store.connect() as c:
        queued = c.execute("SELECT * FROM actions WHERE status='approved'").fetchall()

    sent = 0
    for a in queued:
        kind = a["kind"]
        if kind not in TARGETS:
            print(f"  skip {a['id']}: kind '{kind}' is not mapped to SAP yet")
            continue
        service, entity = TARGETS[kind]
        try:
            r = sap_s4.post(service, entity, json.loads(a["payload"]),
                            idempotency_key=a["idempotency_key"])
            ref = ((r.get("d") or {}).get("PurchaseRequisition")
                   or (r.get("d") or {}).get("MaterialDocument") or "sent")
            store.mark_sent(a["id"], str(ref))
            print(f"  ✓ {a['id']} → {service} · {ref}")
            sent += 1
        except Exception as e:                                       # noqa: BLE001
            # A failure does NOT change the status. The action stays 'approved'
            # and is retried later — the idempotency key prevents a double order.
            print(f"  ✗ {a['id']}: {type(e).__name__}: {e}", file=sys.stderr)
    return sent


if __name__ == "__main__":
    n = send_approved()
    print(f"{n} action(s) sent.")
