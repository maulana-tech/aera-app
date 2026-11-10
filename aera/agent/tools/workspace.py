"""Capabilities `knowledge`, `documents`, `contacts`, `memory` and the shared
`get_business_profile`: what the team knows and writes."""
from __future__ import annotations

import hashlib
import json

from core import business, store
from core.provenance import Origin, Result
from core.registry import SHARED, register

DOC_PREFIX = "doc:"


# ---------------------------------------------------------------- shared
@register("get_business_profile", SHARED,
          "The business profile in force: offerings, prices, limits, forbidden actions, sensitive data.",
          {}, [])
def get_business_profile() -> Result:
    p = business.current()
    return Result({k: v for k, v in p.items() if not k.startswith("_")}, Origin.CACHED,
                  f"business profile v{p.get('_version')}")


# ------------------------------------------------------------- knowledge
@register("list_business_files", "knowledge",
          "The business's own files (price lists, briefs, style guides) and saved documents.", {}, [])
def list_business_files() -> Result:
    rows = store.list_files()
    return Result([{**r, "kind": "document" if r["name"].startswith(DOC_PREFIX) else "file"} for r in rows],
                  Origin.CACHED, "business files")


@register("read_business_file", "knowledge",
          "Read one business file or saved document by id or name (first 20,000 characters).",
          {"file": {"type": "string"}}, ["file"])
def read_business_file(file: str) -> Result:
    f = store.get_file(file)
    if not f:
        return Result(None, Origin.MISSING, "business files", note=f"no file '{file}'")
    return Result({"id": f["id"], "name": f["name"], "text": f["text"][:20000],
                   "truncated": len(f["text"]) > 20000}, Origin.CACHED, f"file {f['name']}")


# ------------------------------------------------------------- documents
@register("write_document", "documents",
          "Save a document (markdown). format 'pdf' for a deliverable or 'draft' for working notes. "
          "Returns its id; pass the id to whoever reviews or delivers it.",
          {"title": {"type": "string"}, "markdown": {"type": "string"},
           "format": {"type": "string", "enum": ["pdf", "draft"]},
           "order_id": {"type": "string", "description": "the order this is for, or empty"}},
          ["title", "markdown", "format", "order_id"], writes=True)
def write_document(title: str, markdown: str, format: str = "draft", order_id: str = "") -> Result:
    if not (markdown or "").strip():
        return Result(None, Origin.MISSING, "documents", note="an empty document was not saved")
    meta = {"title": title.strip()[:120], "format": format, "order_id": order_id or None}
    f = store.save_file(f"{DOC_PREFIX}{meta['title']}", "text/markdown;" + json.dumps(meta),
                        markdown, by=_by())
    sha = hashlib.sha256(markdown.encode()).hexdigest()
    return Result({**f, "title": meta["title"], "format": format, "order_id": meta["order_id"], "sha256": sha},
                  Origin.DERIVED, "documents")


@register("read_document", "documents", "Read a saved document by id.",
          {"document_id": {"type": "string"}}, ["document_id"])
def read_document(document_id: str) -> Result:
    return read_business_file(document_id)


def _by() -> str:
    from core import registry
    return f"agent:{registry.current_agent() or 'unknown'}"


# -------------------------------------------------------------- contacts
def _public_contact(c: dict) -> dict:
    """A contact as an agent sees it. The payout fields are shown as present or
    not, never as values: an agent has no use for an address it cannot pay."""
    return {"id": c["id"], "name": c["name"], "role": c["role"], "email": c["email"] or None,
            "title": c.get("title"), "notes": c.get("notes"),
            "has_payout_account": bool(c.get("near_account") or c.get("payout_address"))}


@register("find_contact", "contacts", "Find contacts by name, email or id.",
          {"query": {"type": "string"}}, ["query"])
def find_contact(query: str) -> Result:
    rows = store.find_contact(query.strip())
    return Result([_public_contact(c) for c in rows], Origin.CACHED, "contacts")


@register("save_contact", "contacts",
          "Save a new customer or vendor contact (name, email). Payout details can only be added by a person.",
          {"name": {"type": "string"}, "email": {"type": "string"},
           "role": {"type": "string", "enum": ["customer", "vendor"]}, "notes": {"type": "string"}},
          ["name", "email", "role", "notes"], writes=True)
def save_contact(name: str, email: str, role: str, notes: str = "") -> Result:
    existing = [c for c in store.find_contact(email) if email and c["email"] == email.lower()]
    if existing:
        return Result(_public_contact(existing[0]), Origin.CACHED, "contacts", note="already on record")
    c = store.add_contact(name.strip(), role, email, notes=notes or None)
    return Result(_public_contact(c), Origin.DERIVED, "contacts", note="new contact saved")


# ---------------------------------------------------------------- memory
@register("search_past_work", "memory",
          "How earlier work items like this were handled: title, outcome, cost.",
          {"query": {"type": "string"}}, ["query"])
def search_past_work(query: str) -> Result:
    words = [w.lower() for w in query.split() if len(w) > 2]
    out = []
    for r in store.list_runs(limit=200):
        title = (r.get("title") or "").lower()
        if words and not any(w in title for w in words):
            continue
        d = r.get("decision") or {}
        out.append({"run_id": r["id"], "title": r["title"], "kind": r["kind"], "status": r["status"],
                    "outcome": (d.get("recommendation") or "")[:400], "cost_usd": r.get("cost_usd"),
                    "at": r["started_at"]})
        if len(out) >= 8:
            break
    return Result(out, Origin.CACHED, "run record",
                  note="" if out else "nothing similar on record yet; that is the record's youth, not evidence")


def demo() -> None:
    from core import registry
    with registry.bind_agent("writer"):
        d = write_document("Brief: coffee in Vietnam", "# Coffee\nGrowing fast [1].", "pdf", "ord_1").value
    assert d["id"] and d["format"] == "pdf"
    got = read_document(d["id"]).value
    assert "Growing fast" in got["text"]
    assert list_business_files().value[0]["kind"] == "document"
    c = save_contact("Ana", "ana@x.example", "customer").value
    assert not c["has_payout_account"] and "near_account" not in c
    assert save_contact("Ana", "ana@x.example", "customer").note == "already on record"
    print("workspace ok: documents ✓ · contacts hide payout details ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_WORKSPACE_CHECK")
    demo()
