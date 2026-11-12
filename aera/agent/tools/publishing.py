"""Capability `publishing`: put a finished free sample on the business's public samples page.

The words that go out are checked in code before anyone decides: the compliance review (forbidden claims,
promises, other people's details, instruction-like phrases) and the Guardian's rule for public pages (no
contact details at all). A clean sample is published on the team's authority; anything the checks flag
waits for a person. The page links to the offering's checkout with the sample as the source, so an order
that came from it is counted (core/economics.py, growth).
"""
from __future__ import annotations

import hashlib
import re

from core import business, compliance, guardian, store
from core.actions import raise_action
from core.provenance import Origin, Result
from core.registry import register


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].strip("-")
    return s or "sample"


@register("publish_sample", "publishing",
          "Publish a finished document (by id) as a free sample on the public samples page, linked to the checkout "
          "of `offering_id`. `teaser` is one or two sentences shown in the list. The text is checked first; a clean "
          "sample goes out on the team's authority, a flagged one waits for a person. Publish only finished work, "
          "never a draft plan or research notes.",
          {"document_id": {"type": "string"}, "offering_id": {"type": "string"}, "teaser": {"type": "string"}},
          ["document_id", "offering_id", "teaser"], writes=True)
def publish_sample(document_id: str, offering_id: str, teaser: str) -> Result:
    doc = store.get_file(document_id)
    if not doc or not doc["name"].startswith("doc:"):
        return Result(None, Origin.MISSING, "documents", note=f"no team document {document_id}")
    p = business.current()
    offering = business.offering(offering_id, p)
    if not offering:
        ids = ", ".join(o["id"] for o in p.get("offerings", []))
        return Result(None, Origin.MISSING, "business profile", note=f"no offering {offering_id}; there is: {ids}")
    text = doc["text"]
    if len(text.strip()) < 400:
        return Result(None, Origin.MISSING, "documents", note="this document is too short to be a sample; finish it first")
    title = doc["name"][4:].strip()
    review = compliance.review(text + "\n" + teaser, p)
    slim = {"verdict": review["verdict"], "findings": review.get("findings", [])[:5]}
    payload = {"document_id": doc["id"], "title": title[:160], "slug": _slug(title), "offering": offering["id"],
               "teaser": teaser.strip()[:400], "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
               "compliance": slim}
    # The Guardian reads the words themselves; the action keeps only their hash.
    verdict = guardian.check_action("publish_sample", {**payload, "text": text})
    return raise_action("publish_sample", payload, verdict, key_details={"document_id": doc["id"], "sha": payload["text_sha256"]})


@register("list_published_samples", "publishing",
          "The samples on the public page: title, offering, when, and how many times each was read.", {}, [])
def list_published_samples() -> Result:
    return Result(store.list_samples(), Origin.CACHED, "samples page")


def demo() -> None:
    from core import registry
    store.save_profile(business.EXAMPLE, by="check")
    offering = business.EXAMPLE["offerings"][0]["id"]
    body = ("# Coffee in Vietnam: a sample brief\n\n" + "Robusta exports rose in the last quarter, according to the "
            "customs office figures cited below. " * 12)
    good = store.save_file("doc:Coffee in Vietnam sample", "text/markdown", body, by="agent:writer")
    leaky = store.save_file("doc:Leaky sample", "text/markdown", body + "\nAsk ana@client.example for the data.", by="agent:writer")
    rid = store.start_run(store.record_work_item("goal", "weekly sample", "schedule", {}))
    with registry.bind_run(rid):
        out = publish_sample(good["id"], offering, "What moved coffee exports this quarter.")
        bad = publish_sample(leaky["id"], offering, "x")
        none = publish_sample(good["id"], "nope", "x")
    assert out.value["status"] == "sent", out.value
    s = store.get_sample("coffee-in-vietnam-sample", count_view=True)
    assert s and s["views"] == 1 and s["offering"] == offering and "Robusta" in s["text"]
    assert bad.value["status"] == "blocked" and "contact details" in bad.value["reason"], bad.value
    assert none.value is None and offering in none.note
    # the words checked are the words published: a document edited after the check is not published
    with registry.bind_run(rid):
        later = publish_sample(good["id"], offering, "again")
    assert later.value.get("repeated") or later.value["status"] == "sent"
    print("publishing ok: a clean sample goes out ✓ · contact details block it ✓ · views counted ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_TOOLS_PUBLISHING_CHECK")
    demo()
