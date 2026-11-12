"""Business templates for onboarding: a starting point per kind of business, every field editable.

Each template is a complete profile (offerings, limits, rules, private data, goals) that makes sense for
that kind of business, so a person can start from something close and change it, instead of from a blank
form. The Composer builds the team from the profile like any other, which is the point of showing them
side by side: a design studio gets a Designer, a translation agency that buys nothing gets no
Procurement, an advisory practice that sells sessions gets no Writer.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from core import business

_BASE_RULES = ["share one customer's data with another customer"]
_APPROVE = ["refund", "new_vendor", "discount", "message_to_new_contact"]


def _profile(**kw: Any) -> Dict[str, Any]:
    p = copy.deepcopy(business.DEFAULTS)
    p.update({k: v for k, v in kw.items() if k not in ("spend", "forbidden", "approve", "sensitive", "min_price", "ai")})
    p["constraints"] = {
        "autonomous_spend_usd": {"per_payment": kw.get("spend", (0, 0))[0], "per_day": kw.get("spend", (0, 0))[1]},
        "inference_max_usd_per_day": kw.get("ai", 2.0),
        "min_price_usd": kw.get("min_price", 0.0),
        "forbidden": kw.get("forbidden", []) + _BASE_RULES,
        "approval_required": kw.get("approve", _APPROVE),
    }
    p["privacy"] = {"sensitive": kw.get("sensitive", ["customer contact details"]), "tee_only": True}
    return p


TEMPLATES: List[Dict[str, Any]] = [
    {"id": "research", "title": "Market research studio", "icon": "search",
     "blurb": "Sourced market briefs and competitor updates, written and checked by the team.",
     "profile": copy.deepcopy(business.EXAMPLE)},
    {"id": "design", "title": "Logo & brand studio", "icon": "palette",
     "blurb": "Logo concepts and social media kits for small businesses, delivered as files.",
     "profile": _profile(
         name="Northpaw Design",
         mission="Logo concepts and brand kits for small businesses that need to look professional fast.",
         customers="Small businesses and new founders",
         offerings=[
             {"id": "logo-pack", "title": "Logo concept pack", "price_usd": 49.0, "delivery": "file", "sla_hours": 48,
              "inputs": ["business name", "industry", "style you like"],
              "description": "Three logo directions with colour and type suggestions, ready to choose from."},
             {"id": "social-kit", "title": "Social media kit", "price_usd": 29.0, "delivery": "file", "sla_hours": 24,
              "inputs": ["business name", "brand colours"],
              "description": "Profile picture, cover images and five post templates in your brand."},
         ],
         channels=["web_checkout", "email"],
         goals=["Post one portfolio piece each week to attract clients"],
         spend=(10.0, 30.0), min_price=20.0,
         forbidden=["use another company's logo or trademark", "promise trademark registration"],
         sensitive=["client brand briefs", "unreleased designs", "customer contact details"])},
    {"id": "translation", "title": "Translation agency", "icon": "languages",
     "blurb": "Document translation and website localisation, reviewed before delivery. Buys nothing.",
     "profile": _profile(
         name="Bahasa Bridge",
         mission="Accurate translation between English and Southeast Asian languages, reviewed before it is delivered.",
         customers="Businesses expanding into Southeast Asia",
         offerings=[
             {"id": "doc-1000", "title": "Document translation (up to 1,000 words)", "price_usd": 25.0, "delivery": "file",
              "sla_hours": 24, "inputs": ["source language", "target language", "the text"],
              "description": "A translated document, checked by a second pass for meaning and tone."},
             {"id": "site-local", "title": "Website localisation (up to 5 pages)", "price_usd": 99.0, "delivery": "file",
              "sla_hours": 72, "inputs": ["website address", "target language"],
              "description": "Page-by-page translation adapted to local wording, with a list of terms to keep consistent."},
         ],
         channels=["web_checkout", "email"],
         goals=[],
         spend=(0.0, 0.0), min_price=10.0,
         forbidden=["deliver a translation that was not reviewed", "keep a client's text after delivery for other work"],
         sensitive=["client documents", "customer contact details"])},
    {"id": "social", "title": "Social media content studio", "icon": "megaphone",
     "blurb": "Monthly content calendars and caption packs for brands that post every week.",
     "profile": _profile(
         name="Pulsepost",
         mission="Ready-to-post social media content for small brands that have no time to plan it.",
         customers="Small consumer brands and creators",
         offerings=[
             {"id": "calendar", "title": "Monthly content calendar", "price_usd": 39.0, "delivery": "xlsx", "sla_hours": 48,
              "inputs": ["brand", "audience", "platforms"],
              "description": "Twelve posts planned across the month: topic, caption, hashtags and the best day to post."},
             {"id": "captions", "title": "Caption pack (10 posts)", "price_usd": 19.0, "delivery": "message", "sla_hours": 24,
              "inputs": ["brand", "what the posts are about"],
              "description": "Ten captions in your brand's voice, each with a call to action."},
         ],
         channels=["web_checkout", "email", "telegram"],
         goals=["Publish three posts a week on our own account to show our work"],
         spend=(5.0, 15.0), min_price=10.0,
         forbidden=["buy followers or engagement", "post about a client without their approval"],
         sensitive=["client brand plans", "customer contact details"])},
    {"id": "advisory", "title": "Business advisory", "icon": "briefcase",
     "blurb": "Strategy sessions and business-plan reviews for founders. Sells time and judgement.",
     "profile": _profile(
         name="Clearpath Advisory",
         mission="Practical strategy advice for founders: one focused session or a written review of the plan.",
         customers="First-time founders and small business owners",
         offerings=[
             {"id": "session", "title": "Strategy session (60 minutes)", "price_usd": 80.0, "delivery": "service", "sla_hours": 72,
              "inputs": ["topic", "preferred time"],
              "description": "A call on one question that matters now, with a short follow-up note of what was agreed."},
             {"id": "plan-review", "title": "Business plan review", "price_usd": 60.0, "delivery": "pdf", "sla_hours": 72,
              "inputs": ["the plan", "what you want feedback on"],
              "description": "A written review: what is strong, what is risky, and three things to do next."},
         ],
         channels=["web_checkout", "email", "chat"],
         goals=[],
         spend=(0.0, 0.0), min_price=40.0, approve=_APPROVE + ["deliver_order"],
         forbidden=["promise investment returns", "give legal or tax advice as if it were final"],
         sensitive=["client business plans", "client financials", "customer contact details"])},
    {"id": "digital", "title": "Digital product shop", "icon": "shopping-bag",
     "blurb": "Templates and e-books sold instantly, paid from any chain, with a chat for buyers.",
     "profile": _profile(
         name="Shelfware",
         mission="Practical templates and short guides that save small teams hours of setup.",
         customers="Freelancers and small teams",
         offerings=[
             {"id": "notion-pack", "title": "Notion operations template pack", "price_usd": 12.0, "delivery": "file", "sla_hours": 1,
              "inputs": [], "description": "Ten linked templates for projects, clients and invoices."},
             {"id": "ebook", "title": "Pricing your services (e-book)", "price_usd": 9.0, "delivery": "pdf", "sla_hours": 1,
              "inputs": [], "description": "A 40-page guide with worksheets to set and raise your prices."},
         ],
         channels=["web_checkout", "intents_checkout", "chat", "email"],
         goals=["Draft one new product idea each month from what buyers ask about"],
         spend=(5.0, 20.0), min_price=5.0,
         forbidden=["sell content the business does not own"],
         sensitive=["customer contact details"])},
]


def listing() -> List[Dict[str, Any]]:
    """Templates with the team each one would get, for the onboarding picker."""
    from core import team
    out = []
    for t in TEMPLATES:
        p, _ = business.normalise(t["profile"])
        agents = team.compose(p)
        out.append({"id": t["id"], "title": t["title"], "blurb": t["blurb"], "icon": t["icon"],
                    "team": [a["nickname"] for a in agents if not a.get("core")], "profile": p})
    return out


def demo() -> None:
    rows = listing()
    assert len(rows) == 6 and all(r["profile"]["name"] and r["profile"]["offerings"] for r in rows)
    for t in TEMPLATES:
        _, problems = business.normalise(t["profile"])
        assert not problems, (t["id"], problems)
    teams = {r["id"]: set(r["team"]) for r in rows}
    assert "Designer" in teams["design"] and "Designer" not in teams["translation"], teams
    assert "Procurement" not in teams["translation"] and "Procurement" in teams["design"], teams
    assert len({frozenset(v) for v in teams.values()}) >= 5, "templates should give different teams"
    print("templates ok: 6 valid profiles ✓ · " + " · ".join(f"{k}: {len(v)} specialists" for k, v in teams.items()))


if __name__ == "__main__":
    demo()
