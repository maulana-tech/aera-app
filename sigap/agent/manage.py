"""Admin tooling.

    python3 manage.py user budi@kpn.co.id "Budi Santoso" buyer secret123
    python3 manage.py secret            # generate SIGAP_SECRET
    python3 manage.py check             # what is still missing
    python3 manage.py seed              # demo events, runs and actions
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


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "check":
        check()
    elif cmd == "seed":
        seed()
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
