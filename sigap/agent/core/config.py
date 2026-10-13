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


def _load_env() -> None:
    """Read .env when present. Convenient in dev; production uses real env vars."""
    f = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if not f.exists():
        return
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
    autonomous_limit_idr: int
    cost_cap_per_event_idr: int
    database: str

    @property
    def production(self) -> bool:
        return self.env == "prod"

    @property
    def sap_ready(self) -> bool:
        return bool(self.sap_api_key)

    @property
    def model_ready(self) -> bool:
        return bool(self.aws_region)

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
        autonomous_limit_idr=int(os.environ.get("SIGAP_AUTONOMOUS_LIMIT_IDR", "50000000")),
        cost_cap_per_event_idr=int(os.environ.get("SIGAP_COST_CAP_IDR", "500000")),
        database=os.environ.get("SIGAP_DB", "data/sigap.db"),
    )
    if c.production:
        missing = [n for n, v in (("SAP_API_KEY", c.sap_api_key),
                                  ("AWS_REGION", c.aws_region)) if not v]
        if missing:
            raise InvalidConfig(
                "SIGAP_ENV=prod but incomplete: " + ", ".join(missing) +
                ". Production must not run on modelled data."
            )
    return c


CFG = load()


def fixtures_only(script: str, flag: str) -> None:
    """Re-exec a self-check with SAP_API_KEY blank. Returns only in the child.

    A demo that asserts figures from `fixtures/` has to actually read fixtures,
    and `_load_env` above fills SAP_API_KEY from .env with setdefault, so
    an already-set key wins and an unset one gets refilled. Clearing it in the
    running process is too late because CFG is frozen at import. Starting again
    with it blank is the only honest way, the same move core/store.py makes for
    SIGAP_DB. Without this a check passes or fails depending on whose .env it
    ran on, which is worse than no check at all.
    """
    import subprocess
    import sys

    if os.environ.get(flag) == "1":
        return
    env = {**os.environ, "SAP_API_KEY": "", flag: "1",
           "PYTHONPATH": os.environ.get("PYTHONPATH", ".")}
    sys.exit(subprocess.call([sys.executable, script], env=env))


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
    print("config ok")


if __name__ == "__main__":
    demo()
