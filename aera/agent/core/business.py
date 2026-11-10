"""The business a person defined, and what it means for the team.

The profile is the one source of truth. Everything the team does is checked
against it: what may be sold and at what price, what may be spent without a
person, which kinds of data are sensitive, which actions always need approval,
and the kill switch. The profile is written by a person (the onboarding
wizard, or POST /business); a model may DRAFT one from a paragraph, but a
draft is only a suggestion until a person saves it.

    profile = business.current()            # normalised, never None
    text    = business.context_block()      # what every agent prompt carries
    caps    = business.spend_caps()         # the stricter of profile and config
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from core.config import CFG

#: The demo business. Also what `manage.py demo` seeds and what the self-checks
#: compose a team from. Nothing about AERA depends on it.
EXAMPLE: Dict[str, Any] = {
    "name": "Lumen Research",
    "mission": "Short, sourced market briefs for founders and small businesses in Southeast Asia.",
    "language": "en",
    "offerings": [
        {"id": "brief", "title": "Market brief (5 pages)", "price_usd": 15.0, "delivery": "pdf",
         "sla_hours": 2, "inputs": ["industry", "country"],
         "description": "Market size signals, competitors, recent news and three opportunities, every claim sourced."},
        {"id": "pulse", "title": "Weekly competitor pulse", "price_usd": 5.0, "delivery": "message",
         "sla_hours": 24, "inputs": ["competitors"],
         "description": "What named competitors shipped, said and priced this week."},
    ],
    "customers": "Founders and SMEs in Southeast Asia",
    "channels": ["web_checkout", "email"],
    "goals": ["Publish one free sample brief each week to attract customers"],
    "team": {"preset": "auto", "include": [], "exclude": [], "extra_roles": []},
    "constraints": {
        "autonomous_spend_usd": {"per_payment": 5.0, "per_day": 20.0},
        "inference_max_usd_per_day": 3.0,
        "min_price_usd": 5.0,
        "forbidden": ["promise investment returns", "share one customer's data with another customer"],
        "approval_required": ["refund", "new_vendor", "discount", "message_to_new_contact"],
    },
    "revenue_split": [],
    "privacy": {"sensitive": ["customer inputs", "customer contact details", "unpublished briefs"],
                "tee_only": True},
    "kill_switch": False,
}

#: The empty shape. A missing key in a stored profile reads as this.
DEFAULTS: Dict[str, Any] = {
    "name": "",
    "mission": "",
    "language": "en",
    "offerings": [],
    "customers": "",
    "channels": [],
    "goals": [],
    "team": {"preset": "auto", "include": [], "exclude": [], "extra_roles": []},
    "constraints": {
        "autonomous_spend_usd": {"per_payment": 0.0, "per_day": 0.0},
        "inference_max_usd_per_day": 1.0,
        "min_price_usd": 0.0,
        "forbidden": [],
        "approval_required": ["refund", "new_vendor"],
    },
    "revenue_split": [],
    "privacy": {"sensitive": [], "tee_only": True},
    "kill_switch": False,
}

CHANNELS = ("web_checkout", "intents_checkout", "email", "telegram", "chat", "mcp")
DELIVERIES = ("pdf", "xlsx", "message", "file", "service")
#: Kinds of action a profile may insist a person approves, whatever the amount.
APPROVAL_KINDS = ("refund", "new_vendor", "discount", "message_to_new_contact", "payment", "message",
                  "deliver_order")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:40]


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, float(v))
    except (TypeError, ValueError):
        return default


def _strs(v: Any) -> List[str]:
    if isinstance(v, str):
        v = [x for x in re.split(r"[\n,]", v)]
    return [str(x).strip() for x in (v or []) if str(x).strip()]


def normalise(raw: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    """A profile with every key present and every value the right type, and
    the problems found. Problems do not stop a save; they are shown to the
    person, because a half-written business is still a business being written."""
    p = deepcopy(DEFAULTS)
    raw = dict(raw or {})
    errors: List[str] = []

    for k in ("name", "mission", "customers", "language"):
        if raw.get(k) is not None:
            p[k] = str(raw[k]).strip()
    if not p["name"]:
        errors.append("the business needs a name")

    offers = []
    seen = set()
    for i, o in enumerate(raw.get("offerings") or []):
        if not isinstance(o, dict):
            continue
        oid = _slug(o.get("id") or o.get("title") or f"offering_{i+1}") or f"offering_{i+1}"
        if oid in seen:
            errors.append(f"two offerings share the id '{oid}'")
            continue
        seen.add(oid)
        delivery = str(o.get("delivery") or "message").lower()
        if delivery not in DELIVERIES:
            errors.append(f"offering '{oid}': delivery '{delivery}' is not one of {', '.join(DELIVERIES)}")
            delivery = "message"
        offers.append({
            "id": oid,
            "title": str(o.get("title") or oid).strip(),
            "description": str(o.get("description") or "").strip(),
            "price_usd": round(_num(o.get("price_usd")), 2),
            "delivery": delivery,
            "sla_hours": _num(o.get("sla_hours"), 24.0),
            "inputs": _strs(o.get("inputs")),
        })
    p["offerings"] = offers

    p["channels"] = [c for c in _strs(raw.get("channels")) if c in CHANNELS]
    p["goals"] = _strs(raw.get("goals"))

    team = raw.get("team") or {}
    p["team"] = {
        "preset": str(team.get("preset") or "auto"),
        "include": [_slug(x) for x in _strs(team.get("include"))],
        "exclude": [_slug(x) for x in _strs(team.get("exclude"))],
        "extra_roles": [x for x in (team.get("extra_roles") or [])
                        if isinstance(x, (str, dict))],
    }

    c = raw.get("constraints") or {}
    spend = c.get("autonomous_spend_usd") or {}
    p["constraints"] = {
        "autonomous_spend_usd": {"per_payment": round(_num(spend.get("per_payment")), 2),
                                 "per_day": round(_num(spend.get("per_day")), 2)},
        "inference_max_usd_per_day": round(_num(c.get("inference_max_usd_per_day"), 1.0), 2),
        "min_price_usd": round(_num(c.get("min_price_usd")), 2),
        "forbidden": _strs(c.get("forbidden")),
        "approval_required": [x for x in _strs(c.get("approval_required")) if x in APPROVAL_KINDS]
        or list(DEFAULTS["constraints"]["approval_required"]),
    }
    if p["constraints"]["autonomous_spend_usd"]["per_payment"] > p["constraints"]["autonomous_spend_usd"]["per_day"] > 0:
        errors.append("per-payment autonomous spend is above the daily cap")
    for o in offers:
        if o["price_usd"] and o["price_usd"] < p["constraints"]["min_price_usd"]:
            errors.append(f"offering '{o['id']}' is priced below the minimum price")

    split, total = [], 0
    for s in raw.get("revenue_split") or []:
        if not isinstance(s, dict) or not s.get("account"):
            continue
        bps = int(_num(s.get("bps")))
        total += bps
        split.append({"account": str(s["account"]).strip(), "bps": bps,
                      "label": str(s.get("label") or "").strip()})
    if total > 10_000:
        errors.append("the revenue split adds up to more than 100%")
    p["revenue_split"] = split

    priv = raw.get("privacy") or {}
    p["privacy"] = {"sensitive": _strs(priv.get("sensitive")),
                    "tee_only": bool(priv.get("tee_only", True))}
    p["kill_switch"] = bool(raw.get("kill_switch", False))
    return p, errors


def current() -> Dict[str, Any]:
    """The profile in force, normalised. Before onboarding: the empty shape,
    with the kill switch ON - a business nobody described does nothing."""
    from core import store
    stored = store.active_profile()
    if not stored:
        p = deepcopy(DEFAULTS)
        p["kill_switch"] = True
        p["_version"] = None
        return p
    p, _ = normalise(stored)
    p["_version"] = stored.get("_version")
    return p


def offering(offering_id: str, profile: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    p = profile or current()
    return next((o for o in p["offerings"] if o["id"] == offering_id), None)


def spend_caps(profile: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """What the team may pay on its own authority. The profile may only make
    the service's limit (AERA_PAY_AUTONOMOUS_LIMIT_USD) stricter, never looser,
    and a kill switch makes it zero."""
    p = profile or current()
    s = p["constraints"]["autonomous_spend_usd"]
    if p.get("kill_switch"):
        return {"per_payment": 0.0, "per_day": 0.0}
    return {"per_payment": min(s["per_payment"], CFG.autonomous_limit_usd),
            "per_day": s["per_day"]}


def needs_approval(kind: str, profile: Optional[Dict[str, Any]] = None) -> bool:
    p = profile or current()
    return kind in p["constraints"]["approval_required"]


def context_block(profile: Optional[Dict[str, Any]] = None) -> str:
    """What every agent is told about the business, in its system prompt.

    Plain text, generated from the profile at call time, so an edit to the
    profile reaches the whole team on its next turn without re-composing it."""
    p = profile or current()
    if not p.get("name"):
        return ("THE BUSINESS: not described yet. Nothing may be sold, bought or sent "
                "until a person completes onboarding.")
    caps = spend_caps(p)
    lines = [f"THE BUSINESS: {p['name']}"]
    if p["mission"]:
        lines.append(f"Mission: {p['mission']}")
    if p["customers"]:
        lines.append(f"Customers: {p['customers']}")
    if p["offerings"]:
        lines.append("Offerings:")
        for o in p["offerings"]:
            lines.append(f"  - [{o['id']}] {o['title']}: ${o['price_usd']:.2f}, delivered as {o['delivery']}"
                         f" within {o['sla_hours']:g}h; needs: {', '.join(o['inputs']) or 'nothing'}."
                         + (f" {o['description']}" if o['description'] else ""))
    if p["channels"]:
        lines.append(f"Channels: {', '.join(p['channels'])}")
    if p["goals"]:
        lines.append("Standing goals: " + "; ".join(p["goals"]))
    lines.append(f"Language for customers: {p['language']}")
    c = p["constraints"]
    lines.append(f"Autonomous spend: up to ${caps['per_payment']:.2f} per payment and "
                 f"${caps['per_day']:.2f} per day without a person; anything above waits for approval.")
    lines.append(f"Minimum price: ${c['min_price_usd']:.2f}. Always needs a person: "
                 + ", ".join(c["approval_required"]) + ".")
    if c["forbidden"]:
        lines.append("Never: " + "; ".join(c["forbidden"]) + ".")
    if p["privacy"]["sensitive"]:
        lines.append("Sensitive data (never send outside the business, never to another customer): "
                     + ", ".join(p["privacy"]["sensitive"]) + ".")
    if p.get("kill_switch"):
        lines.append("KILL SWITCH IS ON: do not raise any payment, refund or outward message.")
    return "\n".join(lines)


DRAFT_SYSTEM = (
    "You turn a founder's description of their business into a JSON business profile for an "
    "autonomous agent team. Reply with ONE JSON object and nothing else, with keys: name, mission, "
    "language (ISO code), offerings (list of {id, title, description, price_usd, delivery one of "
    "pdf|xlsx|message|file|service, sla_hours, inputs: list of strings}), customers, channels (subset of "
    "web_checkout, intents_checkout, email, telegram, chat, mcp), goals (list), constraints "
    "({autonomous_spend_usd: {per_payment, per_day}, inference_max_usd_per_day, min_price_usd, "
    "forbidden: list, approval_required: subset of refund,new_vendor,discount,message_to_new_contact,"
    "payment,message,deliver_order}), privacy ({sensitive: list, tee_only: true}), team ({preset: 'auto', "
    "extra_roles: list of short role titles the description clearly needs beyond research, writing, "
    "analysis, sales, support, marketing, operations, procurement, design and review}). Be conservative "
    "with money: small autonomous caps. Do not invent facts the description does not support; leave "
    "fields empty instead."
)


def draft_from_text(text: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """A model's draft of a profile from a paragraph. Never saved here."""
    from core import aux
    out = aux.generate(DRAFT_SYSTEM, text.strip()[:6000], max_tokens=2000, timeout_s=60)
    if not out:
        return None, ["the drafting model is not available; fill the form by hand"]
    m = re.search(r"\{[\s\S]*\}", out)
    if not m:
        return None, ["the model did not return a profile"]
    try:
        raw = json.loads(m.group(0))
    except ValueError:
        return None, ["the model returned malformed JSON"]
    p, errors = normalise(raw)
    p["kill_switch"] = False
    return p, errors


def demo() -> None:
    p, errors = normalise(EXAMPLE)
    assert not errors, errors
    assert [o["id"] for o in p["offerings"]] == ["brief", "pulse"]

    # A messy form still becomes a well-typed profile, with the problems named.
    messy, errs = normalise({"offerings": [{"title": "Logo Pack", "price_usd": "x", "delivery": "fax"},
                                           {"title": "Logo pack"}],
                             "constraints": {"autonomous_spend_usd": {"per_payment": 50, "per_day": 10},
                                             "forbidden": "lie, spam"},
                             "revenue_split": [{"account": "a.near", "bps": 9000}, {"account": "b.near", "bps": 2000}],
                             "channels": ["email", "fax"]})
    assert messy["offerings"][0]["id"] == "logo_pack" and messy["offerings"][0]["price_usd"] == 0
    assert messy["offerings"][0]["delivery"] == "message"
    assert messy["channels"] == ["email"]
    assert messy["constraints"]["forbidden"] == ["lie", "spam"]
    for want in ("needs a name", "share the id", "delivery 'fax'", "above the daily cap", "more than 100%"):
        assert any(want in e for e in errs), (want, errs)
    print("  normalise: types fixed, problems named ✓")

    # The profile can only tighten the service limit, and the kill switch zeroes it.
    loose = dict(p, constraints=dict(p["constraints"], autonomous_spend_usd={"per_payment": 10_000, "per_day": 10_000}))
    assert spend_caps(loose)["per_payment"] == CFG.autonomous_limit_usd
    assert spend_caps(dict(p, kill_switch=True)) == {"per_payment": 0.0, "per_day": 0.0}
    print("  spend caps: profile can only tighten ✓ · kill switch zeroes ✓")

    text = context_block(p)
    assert "Lumen Research" in text and "[brief]" in text and "Never:" in text and "Sensitive" in text
    assert "not described yet" in context_block(dict(DEFAULTS))
    assert "KILL SWITCH" in context_block(dict(p, kill_switch=True))
    print("  context block: business, offers, limits, forbidden, privacy ✓")
    print("business ok")


if __name__ == "__main__":
    demo()
