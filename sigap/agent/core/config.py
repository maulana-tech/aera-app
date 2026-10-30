"""Configuration. Production refuses to run on modelled data."""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass
from typing import Mapping, Tuple


def _value(raw: str) -> str:
    """One .env value.

    A trailing comment is stripped from an unquoted value, because the example
    file documents each key beside it. Without this, uncommenting
    `SAP_API_KEY=   # free at api.sap.com` sets the key to the comment: a
    non-empty string, so the system reports itself ready and SAP answers 401,
    which reads as a SAP problem rather than the config error it is.
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
_ENV_FILES = (".env", ".secrets/bedrock.env", ".secrets/notify.env")


def _load_env() -> None:
    """Read .env when present. Convenient in dev; production uses real env vars."""
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
    sap_base_url: str
    sap_api_key: str
    aws_region: str
    model: str
    aux_model: str
    autonomous_limit_idr: int
    cost_cap_per_event_idr: int
    database: str
    #: Where people open SIGAP. Every alert links to the handling it is about.
    web_url: str = "http://localhost:3000"
    #: The rule pack Kira rules from (sigap/references/README.md). Company
    #: terms and certificates, so it is installed per deployment, not committed.
    rule_pack: str = ""

    @property
    def production(self) -> bool:
        return (self.env or "").strip().lower() in ("prod", "production")

    @property
    def sap_ready(self) -> bool:
        return bool(self.sap_api_key)

    @property
    def model_ready(self) -> bool:
        """The lead's model, or its fallback, can be called from here. It used
        to mean only "AWS_REGION is set", which stopped being the whole story
        once a model could also live on SAP AI Core (core/llm.py)."""
        from core import llm
        return llm.team_ready(self)

    @property
    def autonomous_limit_text(self) -> str:
        """The autonomy limit the way a prompt or a tool description says it."""
        n = self.autonomous_limit_idr
        if n and n % 1_000_000_000 == 0:
            return f"Rp {n // 1_000_000_000:,} billion"
        if n and n % 1_000_000 == 0:
            return f"Rp {n // 1_000_000:,} million"
        return f"Rp {n:,}"

    @property
    def may_use_modelled(self) -> bool:
        """Modelled data is a dev affordance. Production guesses at nothing."""
        return not self.production


def load() -> Config:
    c = Config(
        env=os.environ.get("SIGAP_ENV", "dev"),
        sap_base_url=os.environ.get("SAP_BASE_URL", "https://sandbox.api.sap.com"),
        sap_api_key=os.environ.get("SAP_API_KEY", ""),
        aws_region=os.environ.get("AWS_REGION", ""),
        model=os.environ.get("SIGAP_MODEL", "anthropic.claude-opus-5"),
        # The auxiliary model: a cheap, fast model for one-shot narration,
        # summaries and titles, so the expensive agent model is not spent on
        # boilerplate. Never sits on a decision or a figure (see core/aux.py).
        aux_model=os.environ.get("SIGAP_AUX_MODEL", "anthropic.claude-haiku-5-5"),
        autonomous_limit_idr=int(os.environ.get("SIGAP_AUTONOMOUS_LIMIT_IDR", "50000000")),
        cost_cap_per_event_idr=int(os.environ.get("SIGAP_COST_CAP_IDR", "500000")),
        database=os.environ.get("SIGAP_DB", "data/sigap.db"),
        web_url=(os.environ.get("SIGAP_WEB_URL", "").strip() or "http://localhost:3000").rstrip("/"),
        rule_pack=os.environ.get("SIGAP_RULE_PACK", "").strip()
        or str(pathlib.Path(__file__).resolve().parents[2] / "references" / "rule-pack.json"),
    )
    if c.production:
        from core import llm
        missing = (["SAP_API_KEY"] if not c.sap_api_key else []) + llm.production_gaps(c)
        if missing:
            raise InvalidConfig(
                "SIGAP_ENV=prod but incomplete: " + ", ".join(missing) +
                ". Production must not run on modelled data."
            )
    return c


CFG = load()


def fixtures_only(script: str, flag: str) -> None:
    """Re-exec a self-check on fixtures and a scratch database.

    Returns only in the child.

    A demo that asserts figures from `fixtures/` has to actually read fixtures,
    and `_load_env` above fills SAP_API_KEY from .env with setdefault, so
    an already-set key wins and an unset one gets refilled. Clearing it in the
    running process is too late because CFG is frozen at import. Starting again
    with it blank is the only honest way, the same move core/store.py makes for
    SIGAP_DB. Without this a check passes or fails depending on whose .env it
    ran on, which is worse than no check at all.

    SIGAP_DB is redirected for the same reason, one step further: a check that
    writes a specimen event into the operator's real database leaves a fake
    disruption sitting in the record the approvals are kept in.
    """
    import subprocess
    import sys
    import tempfile

    if os.environ.get(flag) == "1":
        return
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="sigap-check-")) / "check.db"
    env = {**os.environ, "SAP_API_KEY": "", "SIGAP_DB": str(scratch), flag: "1",
           "PYTHONPATH": os.environ.get("PYTHONPATH", ".")}
    sys.exit(subprocess.call([sys.executable, script, *sys.argv[1:]], env=env))


def bind_target(env: Mapping[str, str]) -> Tuple[str, int]:
    """Where the HTTP service should listen.

    Cloud Foundry sets PORT and routes traffic into the container from outside
    it, so the listener has to accept more than loopback or the health check
    fails and the app looks like a platform problem. Nothing sets PORT on a dev
    machine, and binding to loopback there keeps the API off the local network.
    SIGAP_HOST overrides both.
    """
    port = int(env.get("PORT") or 8787)
    host = env.get("SIGAP_HOST") or ("0.0.0.0" if env.get("PORT") else "127.0.0.1")
    return host, port


def demo() -> None:
    assert bind_target({}) == ("127.0.0.1", 8787), "a dev machine stays off the network"
    assert bind_target({"PORT": "8080"}) == ("0.0.0.0", 8080), "a platform port opens the bind"
    assert bind_target({"SIGAP_HOST": "127.0.0.1", "PORT": "8080"}) == ("127.0.0.1", 8080)
    assert bind_target({"SIGAP_HOST": "0.0.0.0"}) == ("0.0.0.0", 8787)
    print("  bind: loopback by default ✓ · opens only when the platform sets PORT ✓")

    assert _value("us-west-2") == "us-west-2"
    assert _value("  dev   # dev | staging | prod  ") == "dev"
    assert _value("   # free at api.sap.com") == "", "a key that is only a comment is empty"
    assert _value('"p#ssw0rd"') == "p#ssw0rd", "a quoted value keeps its hash"
    assert _value("'p#ssw0rd'") == "p#ssw0rd"
    assert _value("sk-abc#123") == "sk-abc#123", "only ' #' starts a comment, not any hash"
    print("  .env values: comments stripped ✓ · quotes respected ✓ · bare # kept ✓")

    from dataclasses import replace
    said = {n: replace(CFG, autonomous_limit_idr=n).autonomous_limit_text
            for n in (50_000_000, 20_500_000, 1_000_000_000)}
    assert said == {50_000_000: "Rp 50 million", 20_500_000: "Rp 20,500,000",
                    1_000_000_000: "Rp 1 billion"}, said
    print(f"  autonomy limit {CFG.autonomous_limit_text}, from SIGAP_AUTONOMOUS_LIMIT_IDR ✓")
    print("config ok")


if __name__ == "__main__":
    demo()
