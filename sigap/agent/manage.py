"""Admin tooling.

    python3 manage.py user budi@kpn.co.id "Budi Santoso" buyer secret123
    python3 manage.py secret            # generate SIGAP_SECRET
    python3 manage.py check             # what is still missing
    python3 manage.py seed              # demo events, runs and actions
    python3 manage.py docs              # regenerate ../AGENT-REFERENCE.md from the registry
    python3 manage.py models            # which model each agent runs on, and if it can be reached
    python3 manage.py models --ping     # and make one tiny real call to each (costs a few tokens)
    python3 manage.py models --catalog  # one real call to every model the Models page offers
    python3 manage.py ready             # is this install ready to be relied on? (--ping: call the models)
"""
import os
import secrets
import subprocess
import sys

from core import identity

# Files that carry their own self-check in a __main__ block.
CHECKS = [
    "core/config.py", "core/provenance.py", "core/registry.py", "core/identity.py",
    "core/store.py", "core/exploration.py", "core/admission.py", "core/aux.py", "core/schema.py",
    "core/llm.py", "core/topology.py", "clients/aicore.py",
    "engine/simulate.py", "engine/audit.py", "engine/matching.py",
    "engine/forecast.py", "engine/planner.py", "engine/dispatch.py",
    "engine/report.py", "engine/export.py", "engine/allocate.py", "fixtures/generate.py",
    "tools/compliance.py", "tools/execution.py", "tools/logistics.py", "tools/sourcing.py",
    "tools/simulation.py", "tools/exposure.py", "tools/precedent.py",
    "agents/definitions.py", "graph.py", "mcp.py",
    "signals/bmkg.py", "signals/watch.py",
    "clients/feeds.py", "clients/web_data.py", "clients/sap_map.py",
    "signals/places.py", "signals/hazards.py", "signals/weather.py",
    "clients/composio.py", "clients/channels.py", "core/schedule.py", "notify.py --check",
    "outreach.py --check", "sender.py --check", "jobs.py",
]


def check() -> None:
    """Run every self-check, then name what is not there yet."""
    failed = []
    for f in CHECKS:
        r = subprocess.run([sys.executable, *f.split()], capture_output=True, text=True,
                           env={**os.environ, "PYTHONPATH": "."})
        print(f"  {'ok    ' if r.returncode == 0 else 'FAILED'} {f}")
        if r.returncode:
            failed.append(f)
            print("        " + (r.stderr.strip().splitlines() or [""])[-1])

    from agents.definitions import ALL
    from core import config, registry
    import tools  # noqa: F401  (registers every tool)

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
            print(f"    · prompts/{a.code}.txt, {a.nickname} ({a.title})")
    if missing_tools:
        print("\n  tools not written yet:")
        for who, names in missing_tools.items():
            print(f"    · {who}: {', '.join(names)}")

    cfg = config.CFG
    absent = (["SAP_API_KEY"] if not cfg.sap_api_key else []) + \
             ([] if cfg.model_ready else ["a model the lead can reach (manage.py models)"])
    if absent:
        print(f"\n  not set: {', '.join(absent)}"
              "\n    without these the system refuses to decide anything, by design.")

    if failed:
        sys.exit(1)


def models(ping: bool = False, catalog: bool = False) -> None:
    """Per agent: the model, what set it, whether it can be called from here,
    the fallback. With --ping, one real call to each distinct model, which is
    the only way to learn that access was granted (a region and a key prove
    nothing). With --catalog, one call to every model the Models page offers."""
    from agents.definitions import ALL
    from core import llm, store

    llm.choose(store.model_choices())     # what the Models page saved, as api.py runs it
    rows = llm.describe(ALL.values())
    width = max(len(r["model"]) for r in rows)
    def state(ok: bool, fb_ok) -> str:
        # "fallbk": its own model cannot be called, so the fallback will answer.
        return "ready " if ok else ("fallbk" if fb_ok else "NOT   ")

    for r in rows:
        fb = f"  fallback {r['fallback']}" if r["fallback"] else ""
        why = f"  ({r['why']})" if r["why"] else ""
        print(f"  {state(r['ready'], r['fallback_ready'])} {r['name']:<6} "
              f"{r['model']:<{width}}  [{r['source']}]{fb}{why}")
    aux = llm.aux_spec()
    ok, why = llm.ready(aux)
    afb = llm.fallback_for(primary=aux)
    print(f"  {state(ok, afb and llm.ready(afb)[0])} {'aux':<6} {str(aux):<{width}}"
          f"{f'  fallback {afb}' if afb else ''}{'' if ok else f'  ({why})'}")

    if not (ping or catalog):
        return
    seen = []
    for r in rows:
        for m in (r["model"], r["fallback"]):
            if m and m not in seen:
                seen.append(m)
    if str(aux) not in seen:
        seen.append(str(aux))
    if catalog:
        seen = [x.spec for x in llm.CATALOG]
    print("\n  one real call each:")
    failed = False
    for m in seen:
        spec = llm.parse(m)
        if not llm.ready(spec)[0]:
            print(f"    skip   {m}  (not configured here)")
            continue
        ok, what, secs = llm.ping(spec)
        failed |= not ok
        print(f"    {'ok    ' if ok else 'FAILED'} {m}  {secs:.1f}s  {what}")
    if failed:
        sys.exit(1)


def ready(ping: bool = False) -> None:
    """Is this install ready to be relied on? `check` asks whether the code
    works; this asks whether the deployment around it does. Each line is
    something a person would otherwise find out during a disruption."""
    from clients import channels
    from core import llm, store
    from core.config import CFG

    llm.choose(store.model_choices())
    blocking: list = []

    def line(ok: bool, what: str, fix: str = "", block: bool = True) -> None:
        mark = "ok    " if ok else ("TODO  " if block else "note  ")
        print(f"  {mark} {what}")
        if not ok and fix:
            print(f"         → {fix}")
        if not ok and block:
            blocking.append(what)

    print("\n  data")
    line(CFG.sap_ready, "SAP S/4HANA is connected" if CFG.sap_ready else
         "SAP is not connected: stock, orders and suppliers come from uploads or fixtures",
         "SAP_API_KEY (and SAP_BASE_URL) in .env; see ENV.md, SAP")
    if not CFG.sap_ready:
        ups = store.list_uploads()
        line(bool(ups), f"{len({u['entity'] for u in ups})} table(s) uploaded on the Upload data page",
             "upload the company's CSVs, or connect SAP; until then every figure is a fixture",
             block=False)
    line(not CFG.may_use_modelled, f"SIGAP_ENV={CFG.env}"
         + ("" if not CFG.may_use_modelled else ": modelled data may stand in for live data"),
         "SIGAP_ENV=prod once SAP is connected; production refuses to decide on modelled data",
         block=False)

    print("\n  models")
    lead = llm.spec_for_code("supervisor")
    ok, why = llm.ready(lead)
    line(CFG.model_ready, f"the lead can be called: {lead}" + ("" if ok else f" ({why})"),
         "manage.py models; ENV.md, Models")
    if ping:
        seen = []
        for spec in (lead, llm.spec_for_code("impact"), llm.aux_spec(), llm.fallback_for(primary=lead)):
            if spec and str(spec) not in seen:
                seen.append(str(spec))
                good, said, secs = llm.ping(spec)
                line(good, f"{spec} answered in {secs:.1f}s" if good else f"{spec}: {said}",
                     "check access on the Models page (Test)")
    try:
        from clients import web_data
        r = web_data.exchange_rate("USD")
        live = r.value and r.value["rate"]
    except Exception:                                                # noqa: BLE001
        live = None
    if live:
        off = abs(llm.IDR_PER_USD - live) / live
        line(off < 0.05, f"costs are priced at Rp {llm.IDR_PER_USD:,}/USD; ECB says {live:,.0f}"
             + (f" ({off:.0%} off)" if off >= 0.05 else ""),
             f"SIGAP_IDR_PER_USD={round(live)} in .env", block=False)

    print("\n  people")
    with store.connect() as c:
        roles = dict(c.execute("SELECT role, COUNT(*) FROM users WHERE active=1 GROUP BY role")
                     .fetchall())
    line(bool(roles.get("admin") or roles.get("procurement_lead")),
         "users: " + (", ".join(f"{n} {r}" for r, n in sorted(roles.items())) or "none"),
         'manage.py user <email> "<Name>" procurement_lead "<password>"')
    line(bool(roles.get("buyer")), "a buyer can approve the everyday actions",
         'manage.py user <email> "<Name>" buyer "<password>"', block=False)
    line(len(identity.SECRET) >= 32, "SIGAP_SECRET signs the session tokens",
         "manage.py secret, into the service's environment")

    print("\n  alerts")
    st = channels.status()
    ready_ch = [c for c, v in st.items() if v["ready"]]
    line(bool(ready_ch), f"channels set up: {', '.join(ready_ch) or 'none'}",
         "one of SMTP, Slack, Telegram or a webhook in .secrets/notify.env; see ENV.md, Alerts")
    contacts = store.list_contacts()
    line(bool(contacts) or bool([c for c in ready_ch if c != "email"]),
         f"{len(contacts)} contact(s) on the Contacts page",
         "add the people who must hear about a disruption")
    if contacts and "email" not in ready_ch:
        line(False, "contacts are listed but email is not set up, so they are told nothing",
             f"set {', '.join(st['email']['missing'])}")
    line(not CFG.web_url.startswith("http://localhost"), f"links in alerts open {CFG.web_url}",
         "SIGAP_WEB_URL=https://<where people open SIGAP>", block=False)

    print("\n  schedule")
    on = os.environ.get("SIGAP_SCHEDULE", "1") != "0"
    line(on, "the schedule runs (jobs.py)" if on else "nothing runs on its own (SIGAP_SCHEDULE=0)",
         "unset SIGAP_SCHEDULE")
    watch = os.environ.get("SIGAP_WATCH", "1") != "0"
    line(watch, "the watchers raise events on their own" if watch else
         "the watchers are off (SIGAP_WATCH=0): no feed raises an event by itself",
         "unset SIGAP_WATCH (each event a watcher raises spends model credit)", block=False)

    print(f"\n  {'ready' if not blocking else f'not ready: {len(blocking)} to do'}")
    if blocking:
        sys.exit(1)


def seed() -> None:
    """Reproducible demo data: the Ningbo scenario and its two siblings.

    If the model is ready (AWS_REGION is set), runs the agent team on each event
    so they are reasoned with live AI. Otherwise lands as 'held'.
    """
    from core import config, registry, store
    from tools.execution import idempotency_key
    import tools  # noqa: F401

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
        mode = "autonomous" if config.CFG.model_ready else "guided"
        rid = store.start_run(eid, mode)
        event_dict = {"id": eid, "kind": kind, "title": title, "trigger": trigger, **payload}

        if config.CFG.model_ready:
            print(f"Reasoning on {title}...")
            seq = {"n": 0}

            def report(k: str, d: dict) -> None:
                seq["n"] += 1
                name = d.get("name") or d.get("agent", "-")
                store.save_step(rid, {
                    "seq": seq["n"],
                    "stage": {"specialist_start": "DELEGATE", "specialist_done": "FINDING",
                              "tool": "TOOL"}.get(k, k.upper()),
                    "agent": d.get("agent", "supervisor"),
                    "agent_name": name,
                    "summary": d.get("summary") or d.get("task") or d.get("name", ""),
                    "tools": [d["name"]] if k == "tool" else [],
                    "detail": d,
                    "at": store._now(),
                })

            try:
                import graph
                with registry.bind_run(rid):
                    result = graph.run(event_dict, report)
                store.close_run(rid, "done", result, cost_idr=result.get("cost_idr", 0))
                print(f"  done: {title} (cost: Rp {result.get('cost_idr', 0):,})")
            except Exception as e:
                store.close_run(rid, "failed", error=f"{type(e).__name__}: {e}")
                print(f"  failed: {title}: {e}")
        else:
            store.close_run(rid, "held", decision={
                "status": "held",
                "reason": "No model the lead can call (manage.py models) - the agent "
                          "team cannot reason. No decision was made.",
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
            print(f"  held: {title} (AWS_REGION not set)")

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
    import tools  # noqa: F401  (registers every tool; a hand-kept list here dropped Vega's and Prita's)

    installed = registry.all_tools()
    declared = sum(len(a.tools) for a in ALL.values())
    out = [
        "# The agents",
        "",
        "> Generated by `python3 manage.py docs`. Do not edit by hand, it is derived",
        "> from the registry, so it can never disagree with the code.",
        "",
        f"{len(ALL)} agents · {len(installed)}/{declared} tools installed · "
        f"{sum(1 for a in ALL.values() if a.ready)}/{len(ALL)} prompts written",
        "",
        "The supervisor decides who to call from what the last specialist found; there is",
        "no fixed pipeline. Specialists are exposed to the supervisor as tools named",
        "`ask_<code>`.",
        "",
        "| Agent | Who | Effort | Tools | Prompt |",
        "|---|---|---|---|---|",
    ]
    for code, a in ALL.items():
        have = sum(1 for t in a.tools if t in installed)
        out.append(
            f"| `{code}` | **{a.nickname}**, {a.title}"
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
        out += ["", "---", "", f"## {a.nickname}, {a.title}", "",
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
                out += [f"- `{name}`, **not written yet**"]
                continue
            params = tool.schema.get("properties", {})
            required = set(tool.schema.get("required", []))
            sig = ", ".join(
                f"{k}{'' if k in required else '?'}" for k in params) or "no arguments"
            out += [f"- **`{name}`**({sig})", f"  <br>{tool.description}"]
        out.append("")

    target = pathlib.Path(__file__).resolve().parent.parent / "AGENT-REFERENCE.md"
    target.write_text("\n".join(out) + "\n")
    print(f"wrote {target}, {len(out)} lines")


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
    elif cmd == "models":
        models(ping="--ping" in sys.argv[2:], catalog="--catalog" in sys.argv[2:])
    elif cmd == "ready":
        ready(ping="--ping" in sys.argv[2:])
    elif cmd == "secret":
        print(f'export SIGAP_SECRET="{secrets.token_hex(32)}"')
    elif cmd == "user":
        if len(sys.argv) != 6:
            # The command people are told to run on their first day should not
            # answer a mistake with a stack trace.
            print('usage: python3 manage.py user <email> "<Full Name>" <role> "<password>"')
            print(f"  roles: {', '.join(identity.ROLE_LIMITS)}")
            sys.exit(2)
        email, name, role, password = sys.argv[2:6]
        try:
            u = identity.add_user(email, name, role, password)
        except ValueError as e:
            print(f"{e}\n  roles: {', '.join(identity.ROLE_LIMITS)}")
            sys.exit(2)
        print(f"created: {u.email} · {u.role} · limit Rp {u.limit_idr:,}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
