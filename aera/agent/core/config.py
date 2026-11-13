"""Configuration, read once from the environment (and .env in development)."""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass
from typing import Mapping, Tuple


def _value(raw: str) -> str:
    """One .env value.

    A trailing comment is stripped from an unquoted value, because the example
    file documents each key beside it. Without this, uncommenting
    `SMTP_PASSWORD=   # from the mail provider` sets the value to the comment:
    a non-empty string, which then fails somewhere far from the config error
    it is.
    A quoted value is taken whole, so a `#` inside a password survives.
    """
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.startswith("#"):                       # the whole value is a comment
        return ""
    return v.split(" #", 1)[0].split("\t#", 1)[0].strip()


#: Read in this order; the first to set a key wins, and a real environment
#: variable beats both. `.secrets/bedrock.env` holds a Bedrock API key
#: (AWS_BEARER_TOKEN_BEDROCK) in the gitignored, mode-700 secrets folder, so a
#: credential that is not an AWS access key still never sits in `.env`.
#: `.secrets/notify.env` holds the alert channels' secrets (SMTP password, bot
#: token, webhook URLs; clients/channels.py).
_ENV_FILES = (".env", ".secrets/bedrock.env", ".secrets/notify.env", ".secrets/near.env")


def _load_env() -> None:
    """Read .env when present. Convenient in dev; production uses real env vars.

    AERA_NO_ENV_FILES=1 reads none: a business the hub runs for someone else (hub.py) gets only the
    environment the hub hands it, never this install's own .env or .secrets (its vault key, its mail)."""
    if os.environ.get("AERA_NO_ENV_FILES") == "1":
        return
    root = pathlib.Path(__file__).resolve().parent.parent
    for name in _ENV_FILES:
        f = root / name
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), _value(v))


_load_env()


class InvalidConfig(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    env: str                 # "dev" | "staging" | "prod"
    aws_region: str
    model: str
    aux_model: str
    #: Money the team may move on its own authority, per payment (USD). At or
    #: over it a payment waits for a person, whatever the business profile says;
    #: the profile can only lower it. The vault holds its own cap on chain.
    autonomous_limit_usd: float
    #: What one handling may spend on model calls before it stops (USD).
    cost_cap_per_run_usd: float
    database: str
    #: Where people open AERA. Every alert links to the handling it is about.
    web_url: str = "http://localhost:3000"

    @property
    def production(self) -> bool:
        return (self.env or "").strip().lower() in ("prod", "production")

    @property
    def model_ready(self) -> bool:
        """The lead's model, or its fallback, can be called from here. It used
        to mean only "AWS_REGION is set", which is not the whole story
        (core/llm.py)."""
        from core import llm
        return llm.team_ready(self)

    @property
    def autonomous_limit_text(self) -> str:
        """The autonomy limit the way a prompt or a tool description says it."""
        return f"${self.autonomous_limit_usd:,.2f}"


def load() -> Config:
    c = Config(
        env=os.environ.get("AERA_ENV", "dev"),
        aws_region=os.environ.get("AWS_REGION", ""),
        model=os.environ.get("AERA_MODEL", "nearai:moonshotai/kimi-k3"),
        # The auxiliary model: a cheap, fast model for one-shot narration,
        # summaries and titles, so the expensive agent model is not spent on
        # boilerplate. Never sits on a decision or a figure (see core/aux.py).
        aux_model=os.environ.get("AERA_AUX_MODEL", "nearai:z-ai/glm-5.3-flash"),
        autonomous_limit_usd=float(os.environ.get("AERA_PAY_AUTONOMOUS_LIMIT_USD", "50")),
        cost_cap_per_run_usd=float(os.environ.get("AERA_COST_CAP_USD", "1.0")),
        database=os.environ.get("AERA_DB", "data/aera.db"),
        web_url=(os.environ.get("AERA_WEB_URL", "").strip() or "http://localhost:3000").rstrip("/"),
    )
    if c.production:
        from core import llm
        missing = llm.production_gaps(c)
        if missing:
            raise InvalidConfig("AERA_ENV=prod but incomplete: " + ", ".join(missing))
    return c


CFG = load()


# Self-checks are offline: blank (not unset) so _load_env's setdefault cannot fill them back in
# from .secrets/near.env. A check must never call the live vault or spend model credit.
OFFLINE_ENV = {"AERA_VAULT_CONTRACT": "", "AERA_NEAR_AGENT_ACCOUNT": "", "AERA_NEAR_AGENT_KEY": "",
               "NEARAI_API_KEY": ""}


def fixtures_only(script: str, flag: str) -> None:
    """Re-exec a self-check on fixtures and a scratch database.

    Returns only in the child.

    A self-check writes rows (a business, a run, an action). It must never
    write them into the operator's real record, and CFG is frozen at import,
    so only a fresh process pointed at a scratch database honours that.
    """
    import subprocess
    import sys
    import tempfile

    if os.environ.get(flag) == "1":
        return
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="aera-check-")) / "check.db"
    env = {**os.environ, **OFFLINE_ENV, "AERA_DB": str(scratch), flag: "1",
           "PYTHONPATH": os.environ.get("PYTHONPATH", ".")}
    sys.exit(subprocess.call([sys.executable, script, *sys.argv[1:]], env=env))


def bind_target(env: Mapping[str, str]) -> Tuple[str, int]:
    """Where the HTTP service should listen.

    Cloud Foundry sets PORT and routes traffic into the container from outside
    it, so the listener has to accept more than loopback or the health check
    fails and the app looks like a platform problem. Nothing sets PORT on a dev
    machine, and binding to loopback there keeps the API off the local network.
    AERA_HOST overrides both.
    """
    port = int(env.get("PORT") or 8787)
    host = env.get("AERA_HOST") or ("0.0.0.0" if env.get("PORT") else "127.0.0.1")
    return host, port


def demo() -> None:
    assert bind_target({}) == ("127.0.0.1", 8787), "a dev machine stays off the network"
    assert bind_target({"PORT": "8080"}) == ("0.0.0.0", 8080), "a platform port opens the bind"
    assert bind_target({"AERA_HOST": "127.0.0.1", "PORT": "8080"}) == ("127.0.0.1", 8080)
    assert bind_target({"AERA_HOST": "0.0.0.0"}) == ("0.0.0.0", 8787)
    print("  bind: loopback by default ✓ · opens only when the platform sets PORT ✓")

    assert _value("us-west-2") == "us-west-2"
    assert _value("  dev   # dev | staging | prod  ") == "dev"
    assert _value("   # from the mail provider") == "", "a key that is only a comment is empty"
    assert _value('"p#ssw0rd"') == "p#ssw0rd", "a quoted value keeps its hash"
    assert _value("'p#ssw0rd'") == "p#ssw0rd"
    assert _value("sk-abc#123") == "sk-abc#123", "only ' #' starts a comment, not any hash"
    print("  .env values: comments stripped ✓ · quotes respected ✓ · bare # kept ✓")

    from dataclasses import replace
    said = replace(CFG, autonomous_limit_usd=50).autonomous_limit_text
    assert said == "$50.00", said
    print(f"  autonomy limit {CFG.autonomous_limit_text}, from AERA_PAY_AUTONOMOUS_LIMIT_USD ✓")
    print("config ok")


if __name__ == "__main__":
    demo()
