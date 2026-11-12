"""The Composer: a team that fits the business a person described.

    proposal = team.compose(profile)          # deterministic, no model
    diff     = team.diff(proposal)            # against the team on record
    team.apply(proposal, by="usr_1")          # write it; core roles always present

Composition is deterministic on purpose. The same profile always yields the
same team, so a person approving a team approves something stable, and a
self-check can pin it. A model is only involved for roles the library does not
have (`team.extra_roles`), and what it produces is a DRAFT: inactive until a
person approves it, and limited to capabilities from the catalogue, with the
locked ones (guardian, treasury, supervisor) stripped whatever it asked for.

How roles are chosen, in order:
  1. the three core roles, always;
  2. `team.preset` naming roles explicitly ("researcher,writer"), or "auto";
  3. on "auto", a library role is picked when the profile's offerings,
     channels, goals or mission mention one of its keywords; plus the rules
     below that keep a team able to do what the profile sells;
  4. `team.include` adds, `team.exclude` removes (never a core role);
  5. `team.extra_roles` become custom draft agents.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from agents import roles as R
from core import business

CORE_PROMPTS = {code: f"{code}.txt" for code in R.CORE}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:32]


def _core_prompt(code: str) -> str:
    import pathlib
    f = pathlib.Path(__file__).resolve().parent.parent / "prompts" / CORE_PROMPTS[code]
    return f.read_text()


def _haystack(p: Dict[str, Any]) -> str:
    parts = [p.get("mission", ""), p.get("customers", ""), " ".join(p.get("goals", [])),
             " ".join(p.get("channels", []))]
    for o in p.get("offerings", []):
        parts += [o.get("title", ""), o.get("description", ""), o.get("delivery", ""), " ".join(o.get("inputs", []))]
    return " ".join(parts).lower()


def pick_roles(p: Dict[str, Any]) -> List[str]:
    """Library role keys for this profile, in a stable order."""
    team = p.get("team") or {}
    preset = str(team.get("preset") or "auto").strip().lower()
    if preset and preset != "auto":
        picked = [_slug(x) for x in re.split(r"[,\s]+", preset) if _slug(x) in R.ROLES]
    else:
        text = _haystack(p)
        # Whole words (a short suffix allowed: "designs", "designer"): "ui" must not match "guide".
        picked = [k for k, r in R.ROLES.items()
                  if any(re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"[a-z]{0,3}(?![a-z0-9])", text) for kw in r["keywords"])]
        offers = p.get("offerings", [])
        documents = [o for o in offers if o.get("delivery") in ("pdf", "xlsx", "file")]
        # A business that sells something must be able to deliver it...
        if offers and "ops" not in picked:
            picked.append("ops")
        # ...and a document someone pays for is written and reviewed before it goes.
        if documents:
            for k in ("writer", "qa"):
                if k not in picked:
                    picked.append(k)
        # Talking to customers needs somebody whose job it is.
        if set(p.get("channels", [])) & {"email", "telegram", "chat"} and "support" not in picked:
            picked.append("support")
        # A business that takes money keeps books: receipts, the monthly report, the reconciliation.
        if offers and "finance" not in picked:
            picked.append("finance")
        # A business that keeps clients' own material (briefs, documents, plans), beyond a name and an e-mail,
        # needs somebody who knows what it holds and what it may say.
        held = [x for x in (p.get("privacy") or {}).get("sensitive") or [] if "contact" not in x.lower()]
        if offers and held and "compliance" not in picked:
            picked.append("compliance")
        # Money the team may spend on its own is money somebody has to source.
        if (p.get("constraints", {}).get("autonomous_spend_usd", {}).get("per_payment") or 0) > 0 \
                and "procurement" not in picked:
            picked.append("procurement")
    for k in team.get("include") or []:
        if k in R.ROLES and k not in picked:
            picked.append(k)
    excluded = set(team.get("exclude") or [])
    picked = [k for k in picked if k not in excluded]
    order = list(R.ROLES)
    return sorted(set(picked), key=order.index)


def _fill(template: str, **kw: str) -> str:
    for k, v in kw.items():
        template = template.replace("{" + k + "}", v)
    return template


def _custom(extra: Any, taken: set) -> Optional[Dict[str, Any]]:
    """A custom role from the profile, as a DRAFT the person must approve."""
    if isinstance(extra, str):
        title, brief, caps = extra.strip(), "", []
    elif isinstance(extra, dict):
        title = str(extra.get("title") or "").strip()
        brief = str(extra.get("brief") or "").strip()
        caps = list(extra.get("capabilities") or [])
    else:
        return None
    if not title:
        return None
    code = _slug(title)
    if not code or code in taken or code in R.CORE:
        return None
    caps = R.allowed_capabilities(code, caps or ["knowledge", "documents"])
    nick = title.split()[0].capitalize()
    brief = brief or f"Handles {title.lower()} work for the business."
    return {
        "code": code, "nickname": nick, "title": title, "brief": brief, "role": "custom",
        "core": False, "veto": False, "effort": "medium", "capabilities": caps,
        "prompt": _fill(R.CUSTOM_PROMPT, NICK=nick, TITLE=title, BRIEF=brief),
        "status": "draft", "origin": "person" if isinstance(extra, (str, dict)) else "model",
    }


def compose(profile: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """The proposed team: core roles first, then library roles, then drafts."""
    p = profile or business.current()
    out: List[Dict[str, Any]] = []
    for code, c in R.CORE_ROLES.items():
        out.append({"code": code, "nickname": c["nickname"], "title": c["title"], "brief": c["brief"],
                    "role": code, "core": True, "veto": c["veto"], "effort": c["effort"],
                    "capabilities": R.allowed_capabilities(code, c["capabilities"]),
                    "prompt": _core_prompt(code), "status": "active", "origin": "composer"})
    taken = set(R.CORE)
    for key in pick_roles(p):
        r = R.ROLES[key]
        out.append({"code": key, "nickname": r["nickname"], "title": r["title"], "brief": r["brief"],
                    "role": key, "core": False, "veto": False, "effort": "medium",
                    "capabilities": R.allowed_capabilities(key, r["capabilities"]),
                    "prompt": r["prompt"], "status": "active", "origin": "composer"})
        taken.add(key)
    for extra in (p.get("team") or {}).get("extra_roles") or []:
        a = _custom(extra, taken)
        if a:
            out.append(a)
            taken.add(a["code"])
    return out


def diff(proposal: List[Dict[str, Any]], current: Optional[List[Dict[str, Any]]] = None) -> Dict[str, List]:
    """What applying `proposal` would change, for a person to approve."""
    from core import store
    now = {a["code"]: a for a in (current if current is not None else store.list_agents(include_inactive=True))}
    new = {a["code"]: a for a in proposal}
    add = [a for c, a in new.items() if c not in now]
    remove = [a for c, a in now.items() if c not in new and not a.get("core") and a.get("status") != "disabled"]
    change = []
    for c, a in new.items():
        if c in now:
            fields = [k for k in ("title", "brief", "capabilities", "prompt")
                      if json.dumps(now[c].get(k), sort_keys=True) != json.dumps(a.get(k), sort_keys=True)]
            if fields:
                change.append({"code": c, "fields": fields})
    return {"add": add, "remove": remove, "change": change}


def apply(proposal: List[Dict[str, Any]], by: str, keep_edits: bool = True) -> List[Dict[str, Any]]:
    """Write the proposed team. Library agents a person already edited keep
    their prompt unless `keep_edits` is False; roles no longer proposed are
    disabled (not deleted, so the record of who did what keeps its names)."""
    from core import store
    now = {a["code"]: a for a in store.list_agents(include_inactive=True)}
    for a in proposal:
        old = now.get(a["code"])
        if old and keep_edits and old.get("origin") == "person":
            a = {**a, "prompt": old["prompt"], "capabilities": old["capabilities"], "origin": "person"}
        if old and old.get("status") == "draft" and a.get("status") == "draft":
            pass
        elif old and old.get("status") == "active" and a.get("status") == "draft":
            a = {**a, "status": "active"}
        store.upsert_agent(a, by=by)
    proposed = {a["code"] for a in proposal}
    for code, old in now.items():
        if code not in proposed and not old.get("core") and old.get("status") == "active":
            store.set_agent_status(code, "disabled", by=by)
    return store.list_agents(include_inactive=True)


def ensure_team(by: str = "system") -> List[Dict[str, Any]]:
    """A team on record, composing one from the current profile if there is none."""
    from core import store
    agents = store.list_agents(include_inactive=True)
    # Agents used to carry personal names; they are named by role now. A team
    # recorded under the old names is recomposed once (a person's edits kept).
    legacy = {"Arya", "Kira", "Tara", "Nova", "Wira", "Lina", "Sena", "Dewi", "Maya", "Odi", "Prita", "Desi", "Quin"}
    if any(a["nickname"] in legacy for a in agents):
        apply(compose(), by=by)
        agents = store.list_agents(include_inactive=True)
    if not any(a["code"] == "supervisor" for a in agents):
        apply(compose(), by=by)
        agents = store.list_agents(include_inactive=True)
    return agents


def demo() -> None:
    p, _ = business.normalise(business.EXAMPLE)
    team = compose(p)
    codes = [a["code"] for a in team]
    assert codes[:3] == ["supervisor", "guardian", "treasurer"], codes
    for want in ("researcher", "writer", "qa", "ops", "support", "procurement", "marketing"):
        assert want in codes, (want, codes)
    assert "designer" not in codes, "nothing in a research shop asks for a designer"
    assert compose(p) == team, "composition must be deterministic"
    print(f"  research shop -> {', '.join(codes)} ✓")

    # A different business, a different team.
    agency, _ = business.normalise({
        "name": "Pixel Forge", "mission": "Logo and brand identity for startups",
        "offerings": [{"title": "Logo pack", "price_usd": 120, "delivery": "file", "inputs": ["brand name"]}],
        "channels": ["telegram"],
        "team": {"exclude": ["qa"], "extra_roles": ["Illustrator", {"title": "Bookkeeper", "capabilities": ["treasury", "documents"]}]},
    })
    t2 = compose(agency)
    c2 = [a["code"] for a in t2]
    assert "designer" in c2 and "support" in c2 and "qa" not in c2, c2
    drafts = {a["code"]: a for a in t2 if a["status"] == "draft"}
    assert set(drafts) == {"illustrator", "bookkeeper"}, drafts
    assert "treasury" not in drafts["bookkeeper"]["capabilities"], "a custom role must never get the treasury"
    print(f"  brand studio -> {', '.join(c2)} (drafts: {', '.join(drafts)}) ✓")

    # Explicit preset, and the lock.
    t3 = compose(dict(agency, team={"preset": "writer, sales", "include": [], "exclude": [], "extra_roles": []}))
    assert [a["code"] for a in t3] == ["supervisor", "guardian", "treasurer", "writer", "sales"]
    for a in t3:
        for cap, owner in R.LOCKED.items():
            assert (cap in a["capabilities"]) == (a["code"] == owner), (a["code"], cap)
    print("  preset respected ✓ · locked capabilities only on their owners ✓")

    # Apply / diff against a scratch record.
    from core import store
    apply(team, by="check")
    d = diff(compose(agency))
    assert {a["code"] for a in d["add"]} >= {"designer"} and {a["code"] for a in d["remove"]} >= {"researcher"}
    apply(compose(agency), by="check")
    active = {a["code"] for a in store.list_agents()}
    assert "researcher" not in active and "designer" in active and "illustrator" not in active, active
    assert store.get_agent("researcher")["status"] == "disabled"
    print("  apply: removed roles disabled, drafts stay inactive ✓")
    print("team ok")


if __name__ == "__main__":
    from core.config import fixtures_only

    fixtures_only(__file__, "AERA_TEAM_CHECK")
    demo()
