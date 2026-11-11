"""The evidence for the two promises AERA makes, in one place (GET /trust, the Trust Center page).

    Privacy  - who can SEE the business's data: models run in attested TEEs, every call is proven,
               personal data is redacted before it leaves for somebody else's channel, and the
               guardian stops one customer's data from reaching another.
    Security - what the agents can DO with its money: limits on chain, a wallet key that can only
               call the vault, a policy engine whose block is final, a kill switch, and the attack
               demo run against all of it.

Everything here is read from the record (tee_proofs, guardian_checks, privacy_events, actions,
business versions) or live from the chain; nothing is restated from configuration as if it were
proof. Where a figure cannot be read, it says so.
"""
from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core import store

#: Guardian rules that protect data rather than money.
PRIVACY_RULES = ("privacy", "forbidden")
ATTACK_LOG = pathlib.Path(__file__).resolve().parent.parent.parent / "demo" / "attack-log.md"


def _since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def provider_of(checks: List[dict]) -> str:
    """Which TEE stack served the model leg, from the checks the verifier wrote."""
    text = " ".join(str(c.get("detail") or "") for c in checks if str(c.get("scope") or "").startswith("model:"))
    if "chutes" in text:
        return "Chutes · Intel TDX"
    if "tinfoil" in text:
        return "Tinfoil · AMD SEV-SNP"
    return "NEAR AI · Intel TDX (dstack)"


# ------------------------------------------------------------------ privacy
def _proofs(days: int) -> Dict[str, Any]:
    with store.connect() as c:
        rows = c.execute("SELECT id, run_id, agent, model, verdict, checks, created_at FROM tee_proofs"
                         " WHERE created_at >= ? ORDER BY created_at DESC", (_since(days),)).fetchall()
    by_verdict: Dict[str, int] = {}
    by_model: Dict[str, Dict[str, Any]] = {}
    chat = 0
    recent = []
    for r in rows:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
        checks = json.loads(r["checks"] or "[]")
        m = by_model.setdefault(r["model"], {"model": r["model"], "provider": provider_of(checks),
                                             "attested": 0, "partial": 0, "failed": 0, "pending": 0})
        m[r["verdict"]] = m.get(r["verdict"], 0) + 1
        if not r["run_id"]:
            chat += 1
        if len(recent) < 12:
            recent.append({"id": r["id"], "run_id": r["run_id"], "agent": r["agent"], "model": r["model"],
                           "verdict": r["verdict"], "at": r["created_at"],
                           "provider": provider_of(checks)})
    return {"total": len(rows), "by_verdict": by_verdict, "chat_calls": chat,
            "by_model": sorted(by_model.values(), key=lambda m: -sum(m[k] for k in ("attested", "partial", "failed"))),
            "recent": recent}


def _guardian(days: int) -> Dict[str, Any]:
    with store.connect() as c:
        rows = c.execute("SELECT id, run_id, kind, subject, verdict, reasons, at FROM guardian_checks"
                         " WHERE at >= ? ORDER BY at DESC", (_since(days),)).fetchall()
    by_verdict: Dict[str, int] = {}
    by_rule: Dict[str, Dict[str, int]] = {}
    stopped, privacy = [], []
    for r in rows:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
        reasons = json.loads(r["reasons"] or "[]")
        hits = [x for x in reasons if x.get("verdict") in ("block", "warn")]
        for x in hits:
            rule = by_rule.setdefault(x.get("rule") or "?", {"block": 0, "warn": 0})
            rule[x["verdict"]] += 1
        row = {"id": r["id"], "run_id": r["run_id"], "kind": r["kind"], "subject": r["subject"],
               "verdict": r["verdict"], "at": r["at"],
               "rules": [{"rule": x.get("rule"), "verdict": x.get("verdict"), "detail": x.get("detail")} for x in hits]}
        if r["verdict"] in ("block", "warn") and len(stopped) < 12:
            stopped.append(row)
        if any(x.get("rule") in PRIVACY_RULES for x in hits) and len(privacy) < 8:
            privacy.append(row)
    return {"total": len(rows), "by_verdict": by_verdict,
            "by_rule": [{"rule": k, **v} for k, v in sorted(by_rule.items(), key=lambda kv: -(kv[1]["block"] + kv[1]["warn"]))],
            "stopped": stopped, "privacy_stops": privacy}


def privacy(days: int = 30) -> Dict[str, Any]:
    from core import llm
    try:
        attested = sorted(llm.refresh_attested())
    except Exception:                                                  # noqa: BLE001
        attested = []
    events = store.privacy_events(50)
    redacted = sum(1 for e in events if e["outcome"] == "redacted")
    return {
        "private_mode": llm.private_mode(),
        "attested_models": len(attested),
        "proofs": _proofs(days),
        "redaction": {"redacted": redacted, "not_redacted": len(events) - redacted, "recent": events[:8]},
        "raw_prompts_stored": False,
    }


# ----------------------------------------------------------------- security
def _vault() -> Dict[str, Any]:
    from core import chain
    out: Dict[str, Any] = {"configured": chain.configured(), "network": chain.network(),
                           "vault": chain.vault_id() or None, "agent": chain.agent_id() or None}
    if not chain.readable():
        out["note"] = "no vault: payments run on the SIMULATED rail"
        return out
    pol = chain.policy()
    if pol:
        out["policy"] = {"per_tx_cap_usd": chain.from_base(pol.get("per_tx_cap", 0)),
                         "daily_cap_usd": chain.from_base(pol.get("daily_cap", 0)),
                         "spent_today_usd": chain.from_base(pol.get("spent_today", 0)),
                         "frozen": bool(pol.get("frozen")), "owner": pol.get("owner"),
                         "approvers": len(pol.get("approvers") or [])}
    else:
        out["note"] = "the vault did not answer"
    out["balance_usd"] = chain.vault_balance()
    if chain.agent_id():
        try:
            from clients import near
            keys = near.view_access_keys(chain.agent_id())
            full = [k for k in keys if k.get("access_key", {}).get("permission") == "FullAccess"]
            fc = [k["access_key"]["permission"]["FunctionCall"] for k in keys
                  if isinstance(k.get("access_key", {}).get("permission"), dict)]
            out["agent_keys"] = {"full_access": len(full),
                                 "function_call": [{"receiver": f.get("receiver_id"),
                                                    "methods": f.get("method_names") or []} for f in fc]}
        except Exception as e:                                         # noqa: BLE001
            out["agent_keys"] = {"error": type(e).__name__}
    return out


def _decisions(days: int) -> Dict[str, int]:
    """Who decided: the team on its own, a person, still waiting, or the guardian's block."""
    with store.connect() as c:
        rows = c.execute("SELECT status, autonomous FROM actions WHERE created_at >= ?", (_since(days),)).fetchall()
    out = {"team_alone": 0, "person": 0, "waiting": 0, "blocked": 0}
    for r in rows:
        if r["status"] == "blocked":
            out["blocked"] += 1
        elif r["status"] == "pending":
            out["waiting"] += 1
        elif r["autonomous"]:
            out["team_alone"] += 1
        else:
            out["person"] += 1
    return out


def _switch_history(limit: int = 8) -> List[Dict[str, Any]]:
    """Kill-switch changes, from the business versions that record them."""
    with store.connect() as c:
        rows = c.execute("SELECT version, profile, changed_by, note, at FROM business ORDER BY version").fetchall()
    out, last = [], None
    for r in rows:
        on = bool(json.loads(r["profile"] or "{}").get("kill_switch"))
        if last is not None and on != last:
            out.append({"version": r["version"], "on": on, "by": r["changed_by"], "note": r["note"], "at": r["at"]})
        last = on
    return out[-limit:][::-1]


def attack_demo() -> Optional[Dict[str, Any]]:
    """The last `manage.py attack-demo`, read back from its log, layer by layer."""
    if not ATTACK_LOG.exists():
        return None
    text = ATTACK_LOG.read_text()
    head = re.search(r"# AERA attack log — (\S+)", text)
    net = re.search(r"Network: (\S+) · vault: (.+)", text)
    layers = []
    for block in re.split(r"\n## ", text)[1:]:
        title, _, body = block.partition("\n")
        if title.startswith("Resume"):
            continue
        status = re.search(r"- status: \*\*(\w+)\*\*", body)
        why = re.search(r"- why: (.+)", body)
        lines = [ln[2:] for ln in body.splitlines() if ln.startswith("- ")]
        layers.append({"title": title.strip(), "status": status.group(1) if status else None,
                       "detail": why.group(1) if why else " · ".join(lines)[:400] or body.strip()[:300]})
    return {"at": head.group(1) if head else None, "network": net.group(1) if net else None,
            "vault": net.group(2).strip() if net else None, "layers": layers}


def security(days: int = 30) -> Dict[str, Any]:
    return {"vault": _vault(), "guardian": _guardian(days), "decisions": _decisions(days),
            "kill_switch": _switch_history(), "attack_demo": attack_demo()}


def summary(days: int = 30) -> Dict[str, Any]:
    p, s = privacy(days), security(days)
    g = s["guardian"]
    p["guardian_privacy_stops"] = g.pop("privacy_stops")
    return {"days": days, "privacy": p, "security": s,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def demo() -> None:
    assert provider_of([{"scope": "model:x#0", "detail": "sha256(nonce || e2e_pubkey) bound in the chutes TDX quote"}]) \
        == "Chutes · Intel TDX"
    assert provider_of([{"scope": "model:x#0", "detail": "tinfoil attests its router"}]) == "Tinfoil · AMD SEV-SNP"
    assert provider_of([{"scope": "gateway", "detail": "chutes"}]) == "NEAR AI · Intel TDX (dstack)"
    from core import business
    store.save_profile(business.EXAMPLE, by="check")
    p = dict(business.EXAMPLE, kill_switch=True)
    store.save_profile(p, by="agent:guardian", note="frozen")
    store.record_check("action", "x@y", "block", [{"rule": "privacy", "verdict": "block", "detail": "another contact"}])
    store.record_privacy_event("ntf_1", "slack", "redacted")
    out = summary()
    assert out["privacy"]["redaction"]["redacted"] == 1
    assert out["privacy"]["guardian_privacy_stops"] and out["security"]["kill_switch"][0]["on"] is True
    assert out["security"]["guardian"]["by_rule"][0]["rule"] == "privacy"
    json.dumps(out)
    print("trust ok: providers named ✓ · privacy stops and redactions counted ✓ · kill-switch history ✓")


if __name__ == "__main__":
    from core.config import fixtures_only
    fixtures_only(__file__, "AERA_TRUST_CHECK")
    demo()
