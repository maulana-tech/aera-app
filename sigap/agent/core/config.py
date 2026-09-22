"""Configuration. Production refuses to run on modelled data."""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass


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
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


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
