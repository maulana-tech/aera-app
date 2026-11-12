"""Capability `compliance`: review what goes out, keep the policy pages and the data register. Never publishes or decides.

The findings, the page list and the register are computed in core/compliance.py; the agent explains them and
drafts what is missing. Everything it files carries the not-legal-advice line.
"""
from __future__ import annotations

import json

from core import business, compliance, store
from core.provenance import Origin, Result
from core.registry import register


@register("review_for_compliance", "compliance",
          "Check a document (by id) or a text against the profile's forbidden claims and the standard checks: "
          "unconditional promises, advice that reads as final, another contact's details, instruction-like phrases. "
          "Every finding quotes the words that break the rule. `customer_email` is the recipient (their own details are fine).",
          {"document_id": {"type": "string"}, "text": {"type": "string"}, "customer_email": {"type": "string"}}, [])
def review_for_compliance(document_id: str = "", text: str = "", customer_email: str = "") -> Result:
    if document_id:
        f = store.get_file(document_id)
        if not f:
            return Result(None, Origin.MISSING, "documents", note=f"no document {document_id}")
        text = f["text"]
    if not (text or "").strip():
        return Result(None, Origin.MISSING, "compliance", note="give a document_id or a text")
    return Result(compliance.review(text, customer=customer_email), Origin.DERIVED, "compliance rules",
                  note="findings computed in code; quote them")


@register("legal_pages_status", "compliance",
          "Which policy pages the business needs (terms of service, privacy policy, refund policy), which exist among "
          "its files and documents, and why each is needed.", {}, [])
def legal_pages_status() -> Result:
    return Result(compliance.legal_pages(), Origin.CACHED, "business files")


@register("privacy_register", "compliance",
          "What personal data AERA holds: each kind, where, how many records, the oldest, why it is kept and who else "
          "sees it, counted from the tables. Also private mode and the profile's sensitive-data list.", {}, [])
def privacy_register() -> Result:
    return Result(compliance.register(), Origin.CACHED, "AERA records", note="counts from the tables; quote them")


@register("save_compliance_register", "compliance",
          "File the data and policy register as a PDF document: the counts and the page list are filled in by AERA; "
          "`commentary` is your explanation (what to decide, what to draft next, what a lawyer should look at).",
          {"commentary": {"type": "string"}}, ["commentary"], writes=True)
def save_compliance_register(commentary: str) -> Result:
    from core import registry
    p = business.current()
    md = compliance.register_markdown(compliance.register(p), compliance.legal_pages(p), commentary[:6000], p.get("name") or "the business")
    meta = {"title": "Data and policy register", "format": "pdf", "order_id": None,
            "run_id": registry.current_run(), "kind": "compliance_register"}
    f = store.save_file(f"doc:{meta['title']}", "text/markdown;" + json.dumps(meta), md,
                        by=f"agent:{registry.current_agent() or 'compliance'}")
    return Result({**f, "title": meta["title"]}, Origin.DERIVED, "documents")


def demo() -> None:
    from core import registry
    store.save_profile(business.EXAMPLE, by="check")
    assert review_for_compliance(text="We promise investment returns.").value["verdict"] == "block"
    assert review_for_compliance(text="Results guaranteed.").value["verdict"] == "warn"
    assert review_for_compliance().origin is Origin.MISSING
    assert "Refund policy" in legal_pages_status().value["missing"]
    assert privacy_register().value["raw_prompts_stored"] is False
    rid = store.start_run(store.record_work_item("request", "data register", "api", {}))
    with registry.bind_run(rid):
        saved = save_compliance_register("Draft the refund policy first.")
    text = store.get_file(saved.value["id"])["text"]
    assert "Not legal advice" in text and "Draft the refund policy first." in text
    assert review_for_compliance(document_id=saved.value["id"]).value["verdict"] in ("pass", "warn")
    print("tools/compliance ok: review by text or document ✓ · pages ✓ · register filed with the agent's notes only ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_TOOLS_COMPLIANCE_CHECK")
    demo()
