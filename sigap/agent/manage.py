"""Admin tooling.

    python3 manage.py user budi@kpn.co.id "Budi Santoso" buyer secret123
    python3 manage.py secret            # generate SIGAP_SECRET
    python3 manage.py check             # what is still missing
    python3 manage.py seed              # demo events, runs and actions
    python3 manage.py docs              # regenerate ../AGENT-REFERENCE.md from the registry
"""
import os
import secrets
import subprocess
import sys

from core import identity

# Files that carry their own self-check in a __main__ block.
CHECKS = [
    "core/provenance.py", "core/registry.py", "core/identity.py",
    "engine/simulate.py", "tools/compliance.py", "tools/execution.py",
    "agents/definitions.py",
]


def check() -> None:
    """Run every self-check, then name what is not there yet."""
    failed = []
    for f in CHECKS:
        r = subprocess.run([sys.executable, f], capture_output=True, text=True,
                           env={**os.environ, "PYTHONPATH": "."})
        print(f"  {'ok    ' if r.returncode == 0 else 'FAILED'} {f}")
        if r.returncode:
            failed.append(f)
            print("        " + (r.stderr.strip().splitlines() or [""])[-1])

    from agents.definitions import ALL
    from core import config, registry
    import tools.impact, tools.demand, tools.inventory, tools.sourcing, tools.logistics   # noqa: F401
    import tools.compliance, tools.simulation, tools.precedent, tools.execution, tools.supervisor  # noqa: F401

    installed = registry.all_tools()
    no_prompt = [a for a in ALL.values() if not a.ready]
    missing_tools = {a.nickname: [t for t in a.tools if t not in installed]
                     for a in ALL.values() if any(t not in installed for t in a.tools)}
    declared = sum(len(a.tools) for a in ALL.values())

    print(f"\n  agents  : {len(ALL)}")
    print(f"  tools   : {len(installed)}/{declared} installed")
    print(f"  prompts : {len(ALL) - len(no_prompt)}/{len(ALL)} written")

    if no_prompt:
        print("\n  instructions not written yet:")
        for a in no_prompt:
            print(f"    · prompts/{a.code}.txt — {a.nickname} ({a.title})")
    if missing_tools:
        print("\n  tools not written yet:")
        for who, names in missing_tools.items():
            print(f"    · {who}: {', '.join(names)}")

    cfg = config.CFG
    absent = [n for n, v in (("SAP_API_KEY", cfg.sap_api_key),
                             ("AWS_REGION", cfg.aws_region)) if not v]
    if absent:
        print(f"\n  keys not set: {', '.join(absent)}"
              "\n    without these the system refuses to decide anything — by design.")

    if failed:
        sys.exit(1)


def seed() -> None:
    """Reproducible demo data: the Ningbo scenario and its two siblings.

    Runs land as 'held' rather than 'done' because AWS_REGION is not set — the
    system does not pretend an agent reasoned when none did.
    """
    from core import store
    from tools.execution import idempotency_key

    events = [
        ("port_closure", "Typhoon closes the Port of Ningbo",
         "Maritime advisory: Ningbo-Zhoushan closed 8-13 Sep 2026",
         {"port": "CNNGB", "days": 6}),
        ("quality_hold", "M-4471 batch fails inspection, 80 t held",
         "Inbound inspection lot rejected at KRW1", {"material": "M-4471", "qty": 80}),
        ("customs_hold", "COO paperwork disputed, held at Priok",
         "Customs flagged the certificate of origin", {"port": "IDTPP"}),
    ]

    for kind, title, trigger, payload in events:
        eid = store.record_event(kind, title, trigger, payload, "seed")
        rid = store.start_run(eid, "guided")
        store.close_run(rid, "held", decision={
            "status": "held",
            "reason": "AWS_REGION is not set - the agent team cannot reason. "
                      "No decision was made.",
        })
        if kind == "port_closure":
            for k, autonomous, body in (
                ("stock_transfer", True,
                 {"material": "M-4471", "from_plant": "SBY1", "to_plant": "KRW1",
                  "qty": 22.0, "cost_idr": 22_000_000}),
                ("draft_po", False,
                 {"supplier": "SUP-4417", "material": "M-4471", "qty": 85.0,
                  "needed_by": "2026-09-12", "cost_idr": 94_000_000}),
            ):
                store.record_action(rid, idempotency_key(k, **body), k, autonomous, body)

    print(f"seeded {len(events)} events with their runs and actions")


def docs() -> None:
    """Regenerate ../AGENT-REFERENCE.md from the live registry.

    This file used to be maintained by hand, and it went stale the moment a
    tool was renamed. It is derived now, so it cannot disagree with the code.
    """
    import pathlib

    from agents.definitions import ALL
    from core import registry
    from core.identity import ROLE_LIMITS
    import tools.impact, tools.demand, tools.inventory, tools.sourcing, tools.logistics  # noqa: F401
    import tools.compliance, tools.simulation, tools.precedent, tools.execution, tools.supervisor  # noqa: F401

    installed = registry.all_tools()
    declared = sum(len(a.tools) for a in ALL.values())
    out = [
        "# The agents",
        "",
        "> Generated by `python3 manage.py docs`. Do not edit by hand — it is derived",
        "> from the registry, so it can never disagree with the code.",
        "",
        f"{len(ALL)} agents · {len(installed)}/{declared} tools installed · "
        f"{sum(1 for a in ALL.values() if a.ready)}/{len(ALL)} prompts written",
        "",
        "One supervisor and ten specialists. The supervisor decides who to call from what",
        "the last specialist found; there is no fixed pipeline. Specialists are exposed to",
        "the supervisor as tools named `ask_<code>`.",
        "",
        "| Agent | Who | Effort | Tools | Prompt |",
        "|---|---|---|---|---|",
    ]
    for code, a in ALL.items():
        have = sum(1 for t in a.tools if t in installed)
        out.append(
            f"| `{code}` | **{a.nickname}** — {a.title}"
            + (" ⚖️ veto" if a.veto else "") + (" 👑 lead" if code == "supervisor" else "")
            + f" | `{a.effort}` | {have}/{len(a.tools)} |"
            + (" ✅" if a.ready else " ❌ missing") + " |"
        )

    out += ["", "## Approval limits", "",
            "Enforced server-side in `core/identity.py`, never in the UI.", "",
            "| Role | May approve up to |", "|---|---|"]
    for role, limit in ROLE_LIMITS.items():
        out.append(f"| `{role}` | " + ("read only" if limit == 0 else f"Rp {limit:,}") + " |")

    for code, a in ALL.items():
        out += ["", "---", "", f"## {a.nickname} — {a.title}", "",
                f"`{code}` · effort `{a.effort}`"
                + (" · **has veto: a rejection here cannot be overturned on cost**"
                   if a.veto else ""),
                "", a.brief, ""]
        if not a.ready:
            out += [f"> ⚠️ `prompts/{code}.txt` is not written yet. Calling this agent "
                    "raises `PromptMissing` rather than running on an empty prompt.", ""]
        out.append(f"### Tools ({sum(1 for t in a.tools if t in installed)}/{len(a.tools)})")
        out.append("")
        for name in a.tools:
            tool = installed.get(name)
            if not tool:
                out += [f"- `{name}` — **not written yet**"]
                continue
            params = tool.schema.get("properties", {})
            required = set(tool.schema.get("required", []))
            sig = ", ".join(
                f"{k}{'' if k in required else '?'}" for k in params) or "no arguments"
            out += [f"- **`{name}`**({sig})", f"  <br>{tool.description}"]
        out.append("")

    target = pathlib.Path(__file__).resolve().parent.parent / "AGENT-REFERENCE.md"
    target.write_text("\n".join(out) + "\n")
    print(f"wrote {target} — {len(out)} lines")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "check":
        check()
    elif cmd == "seed":
        seed()
    elif cmd == "docs":
        docs()
    elif cmd == "secret":
        print(f'export SIGAP_SECRET="{secrets.token_hex(32)}"')
    elif cmd == "user":
        email, name, role, password = sys.argv[2:6]
        u = identity.add_user(email, name, role, password)
        print(f"created: {u.email} · {u.role} · limit Rp {u.limit_idr:,}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
