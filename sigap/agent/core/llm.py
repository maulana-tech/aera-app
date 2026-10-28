"""One interface over the two wire formats the agents' models speak.

The agent loops in graph.py were written against the Anthropic Messages API:
they send `system`, `tools` with `input_schema`, and a transcript of content
blocks, and they read back `content` blocks, `stop_reason` and `usage`. That
stays the one shape the rest of the code knows. This module is what lets an
agent run on a model that speaks something else:

  provider         wire format                    where
  ---------------  -----------------------------  -----------------------------------------
  bedrock          Anthropic Messages             Claude on Bedrock: Mantle
                                                  (bedrock-mantle.{region}.api.aws/anthropic)
                                                  for `anthropic.claude-*` ids, the legacy
                                                  InvokeModel client for ARN-versioned and
                                                  inference-profile ids (`global.anthropic...-v1:0`)
  bedrock-openai   OpenAI Chat Completions        other Bedrock models on Mantle
                                                  (bedrock-mantle.{region}.api.aws/v1), e.g.
                                                  `minimax.minimax-m2.5`, `deepseek.v3.2`;
                                                  inference profiles (`global.moonshotai.kimi-k3`)
                                                  on bedrock-runtime's /openai/v1 instead
  aicore           OpenAI Chat Completions        SAP AI Core deployments, e.g. `gpt-5.4`;
                   Anthropic Messages             `anthropic--*` deployments, through AI
                                                  Core's Bedrock /invoke

A model is named `provider:model`. The provider can be left off for the ids
.env already carries: anything with `anthropic.` in it is bedrock, `gpt-*` and
`sap-*` are aicore, any other dotted id is bedrock-openai.

Which model each agent runs on (resolved per call). A choice made on the
Models page (`choose()`) wins over the variable at the same level, and a more
specific level wins over a broader one:

  SIGAP_MODEL_<CODE>        that one agent, e.g. SIGAP_MODEL_COMPLIANCE
  SIGAP_MODEL_SPECIALISTS   the ten specialists that neither lead nor hold the veto
  SIGAP_MODEL               the deciders (Arya, Kira), and everyone else not set above
  SIGAP_MODEL_FALLBACK      tried once when an agent's own model fails, then kept
                            for the rest of that handling

The translation is the whole of the difference, and it is deliberately dull:
`input_schema` ↔ `parameters`, `tool_use` ↔ `tool_calls`, `tool_result` ↔ a
role `tool` message, the usage counts. What a model cannot take is dropped
here, per model, rather than tested for at the call site: adaptive thinking and
effort go only to the Claude models that accept them. Nothing about the
guarantees moves with the model. Kira's veto, Tara's figures and every origin
label are Python, so a cheaper specialist cannot weaken them.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import core.config as _config

PROVIDERS = ("bedrock", "bedrock-openai", "aicore")

#: The exchange rate the original single rate was worked out at (Opus 5 list
#: price, $5/$25, is 82,000/410,000 IDR per million). One constant, so the
#: per-model rates below stay comparable with every cost already on record.
#: SIGAP_IDR_PER_USD moves it: the rupiah has moved since (about 18,100 on the
#: ECB reference in late October 2026), so the default understates spend by
#: about a tenth.
#: `manage.py ready` compares it with the live rate.
IDR_PER_USD = int(os.environ.get("SIGAP_IDR_PER_USD") or 16_400)

#: USD per million tokens (input, output), on demand. From the AWS Price List
#: for ap-southeast-2 (pricing.us-east-1.amazonaws.com, offers AmazonBedrock and
#: AmazonBedrockFoundationModels, read 2026-10-24), rounded up to the cent.
#: Claude and Kimi K3 are at the global-profile rate, which is what the
#: `global.` ids bill at; a regional profile costs 10% more. Checked in order,
#: so a longer id comes before its prefix.
_USD_PER_MTOK: Tuple[Tuple[str, float, float], ...] = (
    ("claude-opus-5-5", 4.00, 20.00),
    ("claude-opus-5", 5.00, 25.00),
    ("claude-opus-4-6", 5.00, 25.00),
    ("claude-sonnet-5-5", 2.00, 10.00),
    ("claude-sonnet-4-6", 3.00, 15.00),
    ("claude-haiku-5-5", 0.10, 0.50),     # prompts of 100K tokens or fewer
    ("claude-haiku-4-5", 1.00, 5.00),
    ("minimax-m2", 0.31, 1.24),           # M2, M2.1 and M2.5 alike
    ("deepseek.v3.2", 0.64, 1.91),
    ("deepseek.v3.1", 0.60, 1.74),
    ("kimi-k3", 3.00, 15.00),
    ("kimi-k2-thinking", 0.62, 2.58),
    ("kimi-k2.5", 0.62, 3.09),
    ("qwen3-235b", 0.23, 0.91),
    ("glm-4.7-flash", 0.07, 0.41),
    ("glm-4.7", 0.62, 2.27),
    ("glm-5", 1.03, 3.30),
    ("gpt-oss-120b", 0.16, 0.62),
    ("mistral-large-3", 0.52, 1.55),
    # The small ones.
    ("gpt-oss-20b", 0.08, 0.31),
    ("qwen3-32b", 0.16, 0.62),
    ("qwen3-next-80b", 0.15, 1.24),
    ("ministral-3-14b", 0.21, 0.21),
    ("ministral-3-8b", 0.16, 0.16),
    ("nemotron-nano-3-30b", 0.07, 0.25),
)
#: A model not in the table is priced as Opus 5, the dearest model SIGAP runs.
#: Overstating spend trips the cap early. Understating it is how a cap fails.
DEFAULT_USD_PER_MTOK = (5.00, 25.00)


class ModelUnavailable(RuntimeError):
    """The model cannot be called from here: no region, no key, no SDK."""


class ModelCallFailed(RuntimeError):
    def __init__(self, spec: "Spec", status: int, detail: str):
        super().__init__(f"{spec} answered {status}: {detail[:400]}")
        self.status = status


#: The SDK retries temporary Bedrock failures before the optional second AWS
#: account is used. The fallback account is for capacity, not a second model.
BEDROCK_MAX_RETRIES = 3


def is_rate_limited(error: BaseException) -> bool:
    """Whether an error represents a temporary provider quota response."""
    return (
        getattr(error, "status", None) == 429
        or getattr(error, "status_code", None) == 429
        or type(error).__name__ == "RateLimitError"
    )


def _fallback_aws_options(cfg) -> Optional[dict[str, str]]:
    """The second-account credentials for Bedrock, or None if there is no second
    account.

    The primary account remains the instance's normal AWS credential chain, and
    it is the only one a call needs: the fallback is reached solely when the
    primary answers 429, after the SDK has already retried. So one account is a
    complete configuration, and demanding two made Bedrock unreachable for every
    deployment that has one.

    A *partial* fallback is still an error. Two of the three names set means
    someone meant to configure failover and mistyped, and silently running
    without the failover they think they have is worse than refusing. Session
    tokens stay optional because long-lived IAM keys do not use them.
    """
    access = os.environ.get("AWS_FALLBACK_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("AWS_FALLBACK_SECRET_ACCESS_KEY", "").strip()
    region = os.environ.get("AWS_FALLBACK_REGION", "").strip()
    token = os.environ.get("AWS_FALLBACK_SESSION_TOKEN", "").strip()
    if not cfg.aws_region:
        raise ModelUnavailable("AWS_REGION is not set")
    named = (
        ("AWS_FALLBACK_ACCESS_KEY_ID", access),
        ("AWS_FALLBACK_SECRET_ACCESS_KEY", secret),
        ("AWS_FALLBACK_REGION", region),
    )
    missing = [name for name, value in named if not value]
    if len(missing) == len(named):
        return None
    if missing:
        raise ModelUnavailable(
            "a Bedrock fallback account is half-configured; set or clear all of: "
            + ", ".join(missing)
        )
    options = {"aws_access_key": access, "aws_secret_key": secret, "aws_region": region}
    if token:
        options["aws_session_token"] = token
    return options


# --------------------------------------------------------------------- naming
@dataclass(frozen=True)
class Spec:
    provider: str
    model: str

    def __str__(self) -> str:
        return f"{self.provider}:{self.model}"


def parse(raw: str) -> Spec:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("empty model name")
    head, sep, rest = raw.partition(":")
    if sep and head in PROVIDERS:
        if not rest.strip():
            raise ValueError(f"'{raw}' names a provider and no model")
        return Spec(head, rest.strip())
    if sep and "." not in head and "/" not in head:
        # `openai:gpt-5.4`, `aws:...`: a provider that does not exist. Guessing
        # here would send the request somewhere the operator never meant.
        raise ValueError(f"unknown provider '{head}' in '{raw}' (one of: {', '.join(PROVIDERS)})")
    if "anthropic." in raw:
        return Spec("bedrock", raw)
    if raw.startswith(("gpt-", "sap-", "anthropic--")):
        return Spec("aicore", raw)
    return Spec("bedrock-openai", raw)


def _deciding(code: str, veto: bool) -> bool:
    """Arya decides what to do, Kira decides what may be done. They get the
    strong model. The other ten gather and compute."""
    return code == "supervisor" or veto


#: What was picked on the Models page. Keys are "lead", "specialists",
#: "fallback", "aux", or one agent's code. api.py loads them from the database
#: at start and replaces them on every save. Anything not chosen falls through
#: to the environment, so a deployment that never opens the page runs as before.
_chosen: Dict[str, str] = {}

#: The fallback can be switched off from the page, which an empty value cannot
#: say: empty means "not chosen, use SIGAP_MODEL_FALLBACK".
NO_FALLBACK = "none"


def choose(picked: Dict[str, str]) -> None:
    """Replace the choice. Every value is parsed first, so a bad one is refused
    here, whole, and never in the middle of a handling."""
    clean = {k: v.strip() for k, v in picked.items() if v and v.strip()}
    for k, v in clean.items():
        if not (k == "fallback" and v == NO_FALLBACK):
            parse(v)
    global _chosen
    _chosen = clean                       # one assignment: a reader sees old or new


def chosen() -> Dict[str, str]:
    return dict(_chosen)


def resolve(code: str, veto: bool = False) -> Tuple[Spec, str]:
    """The agent's model, and what set it: `page:<key>` for a choice on the
    Models page, or the name of the environment variable."""
    levels = [(code, f"SIGAP_MODEL_{code.upper()}")]
    if not _deciding(code, veto):
        levels.append(("specialists", "SIGAP_MODEL_SPECIALISTS"))
    for key, var in levels:
        if _chosen.get(key):
            return parse(_chosen[key]), f"page:{key}"
        if os.environ.get(var, "").strip():
            return parse(os.environ[var]), var
    if _chosen.get("lead"):
        return parse(_chosen["lead"]), "page:lead"
    return parse(_config.CFG.model), "SIGAP_MODEL"


def spec_for_code(code: str, veto: bool = False) -> Spec:
    return resolve(code, veto)[0]


def spec_for(agent) -> Spec:
    return spec_for_code(agent.code, getattr(agent, "veto", False))


def fallback_for(agent=None, primary: Optional[Spec] = None) -> Optional[Spec]:
    raw = (_chosen.get("fallback") or os.environ.get("SIGAP_MODEL_FALLBACK", "")).strip()
    if not raw or raw == NO_FALLBACK:
        return None
    fb = parse(raw)
    primary = primary or (spec_for(agent) if agent is not None else None)
    return None if fb == primary else fb


def aux_spec() -> Spec:
    return parse(_chosen.get("aux") or _config.CFG.aux_model)


# --------------------------------------------------------------- capabilities
@dataclass(frozen=True)
class Caps:
    thinking: bool                  # takes {"type": "adaptive"} and output_config.effort
    max_output: int
    #: How to ask this model not to think, or None when it cannot be asked
    #: (Opus 5.5 always thinks) or does not think to begin with.
    thinking_off: Optional[dict] = None
    #: Reads images. MiniMax M2.5 is text only.
    images: bool = True


def _claude_name(spec: Spec) -> str:
    """`claude-sonnet-4-6` for a Claude model whatever the route calls it (AI
    Core says `anthropic--claude-4.6-sonnet`), and '' for any other model."""
    m = spec.model.lower()
    if spec.provider == "aicore":
        a = re.search(r"anthropic--claude-(\d+)(?:\.(\d+))?-([a-z]+)", m)
        if not a:
            return ""
        return f"claude-{a[3]}-{a[1]}" + (f"-{a[2]}" if a[2] else "")
    return m if spec.provider == "bedrock" else ""


def caps(spec: Spec) -> Caps:
    m = spec.model.lower()
    claude = _claude_name(spec)
    if claude:
        if re.search(r"claude-(opus|sonnet|haiku|fable|mythos)-(5|4-[6-9])", claude):
            off = {"type": "disabled"} if re.search(r"claude-(haiku-5-5|opus-5(?!-5))", claude) else None
            return Caps(thinking=True, max_output=128_000, thinking_off=off)
        return Caps(thinking=False, max_output=64_000)
    if "minimax" in m:
        return Caps(thinking=False, max_output=8_192, images=False)
    if spec.provider == "bedrock-openai":
        # The open-weight models on Bedrock read text. The vision ones say so in
        # their name, and an image sent to the others is a 400, not a guess.
        return Caps(thinking=False, max_output=128_000, images="-vl" in m)
    return Caps(thinking=False, max_output=128_000)


def _runtime_id(model: str) -> bool:
    """ARN-versioned ids and inference profiles live on bedrock-runtime: Claude
    through InvokeModel, the rest through its /openai/v1 path. Mantle takes the
    bare ids (`anthropic.claude-opus-5`, `deepseek.v3.2`)."""
    m = model.lower()
    return bool(m.startswith("arn:")
                or re.match(r"(global|us|eu|apac|jp|au)\.", m)
                or re.search(r"-v\d+(:\d+)?$", m))


def route_of(spec: Spec) -> str:
    """Where a call to this model goes, in words, for the Models page."""
    if spec.provider == "aicore":
        return "SAP AI Core"
    if spec.provider == "bedrock":
        return "Bedrock InvokeModel" if _runtime_id(spec.model) else "Bedrock Mantle"
    return "Bedrock runtime (chat)" if _runtime_id(spec.model) else "Bedrock Mantle (chat)"


# ------------------------------------------------------------------ readiness
def ready(spec: Spec, cfg=None) -> Tuple[bool, str]:
    """Whether a call to this model can even be attempted from here. It cannot
    prove access (only a call does), but it catches the configuration gaps that
    otherwise surface as a stack trace in the middle of a handling."""
    cfg = cfg or _config.CFG
    if spec.provider in ("bedrock", "bedrock-openai"):
        if not cfg.aws_region:
            return False, "AWS_REGION is not set"
        try:
            import anthropic  # noqa: F401
            import botocore   # noqa: F401
        except ImportError:
            return False, "the Bedrock SDK is not installed: pip install -r requirements.txt"
        try:
            _fallback_aws_options(cfg)
        except ModelUnavailable as e:
            return False, str(e)
        return True, ""
    if spec.provider == "aicore":
        from clients import aicore
        try:
            aicore.service_key()
            return True, ""
        except aicore.MissingServiceKey as e:
            return False, str(e)
    return False, f"unknown provider {spec.provider}"


def usable(spec: Spec, cfg=None) -> bool:
    """Ready itself, or the fallback is."""
    if ready(spec, cfg)[0]:
        return True
    fb = fallback_for(primary=spec)
    return bool(fb and ready(fb, cfg)[0])


def team_ready(cfg=None) -> bool:
    """The lead has to be able to think, or nothing runs. A specialist whose
    model is missing is isolated by graph.py like any other failing specialist."""
    return usable(spec_for_code("supervisor", veto=False), cfg)


def production_gaps(cfg) -> List[str]:
    """What production would be missing. Called by config.load() with the
    config it is building, before CFG exists."""
    lead = parse(os.environ.get("SIGAP_MODEL_SUPERVISOR", "").strip() or cfg.model)
    ok, why = ready(lead, cfg)
    return [] if ok else [f"the lead's model {lead} ({why})"]


def describe(agents: Iterable) -> List[dict]:
    """Per agent: which model, whether it can be called, and the fallback."""
    out = []
    for a in agents:
        s, source = resolve(a.code, getattr(a, "veto", False))
        ok, why = ready(s)
        fb = fallback_for(a, s)
        out.append({"agent": a.code, "name": a.nickname, "model": str(s), "source": source,
                    "ready": ok, "why": why or None, "fallback": str(fb) if fb else None,
                    "fallback_ready": ready(fb)[0] if fb else None})
    return out


# ---------------------------------------------------------------------- price
def usd_per_mtok(spec: Optional[Spec], input_tokens: int = 0) -> Tuple[float, float]:
    if spec is None:
        return DEFAULT_USD_PER_MTOK
    if spec.provider == "aicore":
        # Organiser-provided capacity, billed to nobody on this team. Counted
        # in tokens (Cost keeps them), priced at zero. The round and time
        # limits still bound a handling that runs on it.
        return (0.0, 0.0)
    m = spec.model.lower()
    if "claude-haiku-5-5" in m and input_tokens > 100_000:
        return (0.50, 2.50)
    for key, i, o in _USD_PER_MTOK:
        if key in m:
            return (i, o)
    return DEFAULT_USD_PER_MTOK


def price_idr(usage) -> float:
    """Rupiah for one call's usage, at the rate of the model that served it.
    Cache reads and writes are priced as input: overstated, never understated."""
    spec = getattr(usage, "spec", None)
    inp = ((getattr(usage, "input_tokens", 0) or 0)
           + (getattr(usage, "cache_read_input_tokens", 0) or 0)
           + (getattr(usage, "cache_creation_input_tokens", 0) or 0))
    out = getattr(usage, "output_tokens", 0) or 0
    i, o = usd_per_mtok(spec, inp)
    return (inp / 1e6 * i + out / 1e6 * o) * IDR_PER_USD


# ----------------------------------------------------- the shape loops read
class TextBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class ThinkingBlock:
    """Reasoning a chat model returned. Shown in the trail; never sent to a
    Claude model, which would refuse a thinking block it did not sign."""
    type = "thinking"

    def __init__(self, thinking: str):
        self.thinking = thinking


class ToolUseBlock:
    type = "tool_use"

    def __init__(self, id: str, name: str, input: dict):   # noqa: A002  (the SDK's names)
        self.id, self.name, self.input = id, name, input


@dataclass
class Usage:
    spec: Optional[Spec] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


class Reply:
    def __init__(self, content: list, stop_reason: str, usage: Usage, spec: Spec):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage
        self.model = str(spec)
        #: (model that failed, why) when a configured model fallback answered instead.
        self.fell_back_from: Optional[Tuple[str, str]] = None
        #: Why the same model was served through explicit fallback AWS credentials.
        self.account_failover: Optional[str] = None


def _get(b: Any, key: str, default: Any = None) -> Any:
    return b.get(key, default) if isinstance(b, dict) else getattr(b, key, default)


def _blocks(content: Any) -> List[Any]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return list(content or [])


def _text_of(content: Any) -> str:
    """The text inside a tool_result or system field, which may be a string or
    a list of text blocks."""
    if isinstance(content, str):
        return content
    return "\n".join(_get(b, "text", "") for b in _blocks(content)
                     if _get(b, "type") == "text")


# ---------------------------------------------------- Anthropic Messages side
def _anthropic_block(b: Any) -> Optional[Any]:
    """A block fit to send to Claude. The SDK's own response objects pass
    through as they always did (a thinking block keeps its signature). Blocks
    this module made from a chat model are rewritten as plain dicts; their
    thinking is dropped, since Claude accepts only thinking it signed."""
    if isinstance(b, dict) or hasattr(b, "model_dump"):
        return b
    t = getattr(b, "type", None)
    if t == "text":
        return {"type": "text", "text": b.text} if b.text else None
    if t == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
    return None


def _anthropic_messages(messages: List[dict]) -> List[dict]:
    out = []
    for m in messages:
        c = m["content"]
        if not isinstance(c, str):
            c = [x for x in (_anthropic_block(b) for b in c) if x is not None] \
                or [{"type": "text", "text": "(no text)"}]
        out.append({"role": m["role"], "content": c})
    return out


def _anthropic_body(spec: Spec, req: dict) -> dict:
    """The request as this Claude takes it: clamped to what it can return, with
    thinking and effort only where it accepts them."""
    cap = caps(spec)
    body = {**req, "model": spec.model,
            "max_tokens": min(int(req["max_tokens"]), cap.max_output),
            "messages": _anthropic_messages(req["messages"])}
    thinking = body.pop("thinking", None)
    effort = (body.pop("output_config", None) or {}).get("effort")
    if cap.thinking and thinking:
        if thinking.get("type") == "disabled":
            if cap.thinking_off:
                body["thinking"] = cap.thinking_off
        else:
            body["thinking"] = thinking
            if effort:
                body["output_config"] = {"effort": effort}
    return body


def _anthropic_usage(spec: Spec, u: Any) -> Usage:
    return Usage(spec, _get(u, "input_tokens", 0) or 0, _get(u, "output_tokens", 0) or 0,
                 _get(u, "cache_read_input_tokens", 0) or 0,
                 _get(u, "cache_creation_input_tokens", 0) or 0)


class _AnthropicBackend:
    def __init__(self, spec: Spec, cfg):
        self.spec = spec
        self._cfg = cfg
        self._sdk = self._new_client()
        options = _fallback_aws_options(cfg)
        self._sdk_fallback = self._new_client(options) if options else None

    def _new_client(self, options: Optional[dict[str, str]] = None):
        kwargs = {"aws_region": self._cfg.aws_region, "max_retries": BEDROCK_MAX_RETRIES}
        kwargs.update(options or {})
        if _runtime_id(self.spec.model):
            from anthropic import AnthropicBedrock
            return AnthropicBedrock(**kwargs)
        from anthropic import AnthropicBedrockMantle
        return AnthropicBedrockMantle(**kwargs)

    def create(self, req: dict) -> Reply:
        body = _anthropic_body(self.spec, req)
        try:
            r = self._sdk.messages.create(**body)
        except Exception as error:                                  # noqa: BLE001
            if not is_rate_limited(error) or self._sdk_fallback is None:
                raise
            r = self._sdk_fallback.messages.create(**body)
            reply = Reply(list(r.content), r.stop_reason, _anthropic_usage(self.spec, r.usage), self.spec)
            reply.account_failover = f"primary Bedrock account rate-limited ({type(error).__name__})"
            return reply
        return Reply(list(r.content), r.stop_reason, _anthropic_usage(self.spec, r.usage), self.spec)


class _AICoreAnthropicBackend:
    """Claude deployed on SAP AI Core. AI Core fronts it with Bedrock's
    InvokeModel, so the body is the Messages request in Bedrock's form, and the
    reply is read back into the SDK's own types: a thinking block keeps its
    signature, and goes back to Claude on the next round as it came."""

    def __init__(self, spec: Spec, cfg):
        from clients import aicore
        self.spec = spec
        self._ai = aicore.shared()

    def create(self, req: dict) -> Reply:
        from anthropic.types import Message
        from clients.aicore import AICoreError
        body = _anthropic_body(self.spec, req)
        del body["model"]                     # the deployment is the model
        body["anthropic_version"] = "bedrock-2023-05-31"
        body = json.loads(json.dumps(body, ensure_ascii=False,
                                     default=lambda o: o.model_dump(exclude_none=True)))
        try:
            data = self._ai.invoke(self.spec.model, body)
        except AICoreError as e:
            raise ModelCallFailed(self.spec, e.status, str(e)) from None
        r = Message.model_validate({"id": "", "type": "message", "role": "assistant",
                                    "model": self.spec.model, **data})
        return Reply(list(r.content), r.stop_reason, _anthropic_usage(self.spec, r.usage), self.spec)


# ----------------------------------------------- OpenAI Chat Completions side
_THINK = re.compile(r"<think>([\s\S]*?)</think>", re.I)


def _split_think(text: str) -> Tuple[str, str]:
    """(reasoning, visible text). Reasoning models on the chat endpoint can put
    their chain of thought inline as <think>...</think>."""
    if not text:
        return "", ""
    thoughts = [t.strip() for t in _THINK.findall(text)]
    visible = _THINK.sub("", text)
    if "</think>" in visible.lower():                     # dangling close
        head, _, visible = re.split(r"(</think>)", visible, maxsplit=1, flags=re.I)
        thoughts.insert(0, head.replace("<think>", "").strip())
    if "<think>" in visible.lower():                      # unclosed open
        visible, _, tail = re.split(r"(<think>)", visible, maxsplit=1, flags=re.I)
        thoughts.append(tail.strip())
    return "\n\n".join(t for t in thoughts if t), visible.strip()


def _chat_user(m: dict, spec: Spec) -> List[dict]:
    out: List[dict] = []
    parts: List[dict] = []
    for b in _blocks(m["content"]):
        t = _get(b, "type")
        if t == "tool_result":
            body = _text_of(_get(b, "content", ""))
            out.append({"role": "tool", "tool_call_id": _get(b, "tool_use_id"),
                        "content": ("ERROR: " + body) if _get(b, "is_error") else body})
        elif t == "text":
            parts.append({"type": "text", "text": _get(b, "text", "")})
        elif t == "image":
            src = _get(b, "source", {}) or {}
            if caps(spec).images and src.get("type") == "base64":
                parts.append({"type": "image_url", "image_url": {
                    "url": f"data:{src.get('media_type')};base64,{src.get('data')}"}})
            else:
                parts.append({"type": "text", "text": "[an image was attached; this model "
                                                      "reads text only, so it was not passed on]"})
        elif t == "document":
            parts.append({"type": "text", "text": "[a PDF was attached; this model cannot read "
                                                  "PDFs, so it was not passed on]"})
    if parts:
        only_text = all(p["type"] == "text" for p in parts)
        out.append({"role": "user", "content": "\n\n".join(p["text"] for p in parts)
                    if only_text else parts})
    return out


def _chat_assistant(m: dict, spec: Spec) -> dict:
    text, thinking, calls = [], [], []
    for b in _blocks(m["content"]):
        t = _get(b, "type")
        if t == "text" and _get(b, "text"):
            text.append(_get(b, "text"))
        elif t == "thinking" and _get(b, "thinking"):
            thinking.append(_get(b, "thinking"))
        elif t == "tool_use":
            calls.append({"id": _get(b, "id"), "type": "function", "function": {
                "name": _get(b, "name"),
                "arguments": json.dumps(_get(b, "input", {}) or {}, ensure_ascii=False)}})
    content = "\n\n".join(text)
    if thinking and "minimax" in spec.model.lower():
        # MiniMax asks for its own reasoning back in the history, inline, or
        # its multi-step tool use degrades. Other chat models do not want it.
        content = "".join(f"<think>{x}</think>\n" for x in thinking) + content
    msg: Dict[str, Any] = {"role": "assistant", "content": content or None}
    if calls:
        msg["tool_calls"] = calls
    elif msg["content"] is None:
        msg["content"] = ""
    return msg


def to_chat(req: dict, spec: Spec) -> dict:
    """An Anthropic Messages request as an OpenAI Chat Completions body."""
    msgs: List[dict] = []
    system = _text_of(req.get("system") or "")
    if system:
        msgs.append({"role": "system", "content": system})
    for m in req["messages"]:
        if m["role"] == "assistant":
            msgs.append(_chat_assistant(m, spec))
        else:
            msgs.extend(_chat_user(m, spec))
    body: Dict[str, Any] = {"messages": msgs}
    n = min(int(req.get("max_tokens") or 4096), caps(spec).max_output)
    if spec.provider == "aicore":
        body["max_completion_tokens"] = n        # gpt-5.x refuses max_tokens
    else:
        body["model"] = spec.model
        body["max_tokens"] = n
    if req.get("tools"):
        body["tools"] = [{"type": "function", "function": {
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
        }} for t in req["tools"]]
    return body


def from_chat(data: dict, spec: Spec) -> Reply:
    """An OpenAI Chat Completions response as the Messages shape."""
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    raw = msg.get("content") or ""
    if isinstance(raw, list):
        raw = "".join(p.get("text", "") for p in raw if isinstance(p, dict))
    inline, text = _split_think(raw)
    reasoning = "\n\n".join(x for x in (msg.get("reasoning_content") or msg.get("reasoning") or "",
                                        inline) if x)
    blocks: List[Any] = []
    if reasoning:
        blocks.append(ThinkingBlock(reasoning))
    if text:
        blocks.append(TextBlock(text))
    calls = msg.get("tool_calls") or []
    for c in calls:
        fn = c.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError:
            # Unparseable arguments run as no arguments. The tool then refuses
            # for want of a parameter, and that refusal goes back to the model
            # as an error it can correct, rather than a crash here.
            args = {}
        # gpt-oss can leak its harmony channel markers into the name
        # ("get_bom_explosion<|channel|>json"). The name is the tool's name up
        # to the first marker; anything after it was never part of it.
        name = re.split(r"<\|", fn.get("name") or "", maxsplit=1)[0].strip()
        blocks.append(ToolUseBlock(c.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                                   name, args if isinstance(args, dict) else {}))
    finish = choice.get("finish_reason")
    stop = "tool_use" if calls else {"length": "max_tokens",
                                      "content_filter": "refusal"}.get(finish, "end_turn")
    u = data.get("usage") or {}
    cached = int(((u.get("prompt_tokens_details") or {}).get("cached_tokens")) or 0)
    usage = Usage(spec, max(0, int(u.get("prompt_tokens") or 0) - cached),
                  int(u.get("completion_tokens") or 0), cached, 0)
    return Reply(blocks, stop, usage, spec)


_BOTO_LOCK = threading.Lock()
_BOTO_SESSION = None


def _aws_credentials():
    global _BOTO_SESSION
    with _BOTO_LOCK:
        if _BOTO_SESSION is None:
            import botocore.session
            _BOTO_SESSION = botocore.session.Session()
        return _BOTO_SESSION.get_credentials()


def _post_json(spec: Spec, url: str, body: dict, headers_for: Callable[[bytes], dict],
               timeout: int = 180) -> dict:
    """POST, retrying twice on 429 and 5xx with a short backoff."""
    data = json.dumps(body, ensure_ascii=False).encode()
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, method="POST", headers=headers_for(data))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise ModelCallFailed(spec, e.code, detail) from None
        except urllib.error.URLError:
            if attempt == 2:
                raise
        time.sleep(1.5 * (attempt + 1))
    raise AssertionError("unreachable")


class _BedrockChatBackend:
    """Chat Completions on Bedrock, with optional account-level failover."""

    def __init__(self, spec: Spec, cfg):
        self.spec = spec
        self.region = cfg.aws_region
        self.url, self._service = self._endpoint(self.region, "SIGAP_BEDROCK_OPENAI_BASE_URL")
        options = _fallback_aws_options(cfg)
        self._fallback_url = None
        if options:
            from botocore.credentials import Credentials
            self._fallback_credentials = Credentials(
                options["aws_access_key"], options["aws_secret_key"],
                options.get("aws_session_token"),
            )
            self._fallback_region = options["aws_region"]
            self._fallback_url, self._fallback_service = self._endpoint(
                self._fallback_region, "SIGAP_FALLBACK_BEDROCK_OPENAI_BASE_URL"
            )

    def _endpoint(self, region: str, override: str) -> Tuple[str, str]:
        if _runtime_id(self.spec.model):
            base, service = f"https://bedrock-runtime.{region}.amazonaws.com/openai/v1", "bedrock"
        else:
            base = os.environ.get(override, f"https://bedrock-mantle.{region}.api.aws/v1")
            service = "bedrock-mantle"
        return base.rstrip("/") + "/chat/completions", service

    def _headers_for(self, data: bytes, *, url: str, region: str, service: str, credentials=None) -> dict:
        if credentials is None:
            token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip()
            if token:
                return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            credentials = _aws_credentials()
        if credentials is None:
            raise ModelUnavailable("no AWS credentials: run `aws configure`, set AWS_PROFILE, "
                                   "or set AWS_BEARER_TOKEN_BEDROCK")
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        request = AWSRequest(method="POST", url=url, data=data,
                             headers={"Content-Type": "application/json"})
        SigV4Auth(credentials.get_frozen_credentials(), service, region).add_auth(request)
        return dict(request.headers.items())

    def _headers(self, data: bytes) -> dict:
        return self._headers_for(data, url=self.url, region=self.region, service=self._service)

    def _fallback_headers(self, data: bytes) -> dict:
        return self._headers_for(data, url=self._fallback_url, region=self._fallback_region,
                                 service=self._fallback_service, credentials=self._fallback_credentials)

    def create(self, req: dict) -> Reply:
        body = to_chat(req, self.spec)
        try:
            return from_chat(_post_json(self.spec, self.url, body, self._headers), self.spec)
        except Exception as error:                                  # noqa: BLE001
            if not is_rate_limited(error) or self._fallback_url is None:
                raise
            reply = from_chat(_post_json(self.spec, self._fallback_url, body, self._fallback_headers),
                              self.spec)
            reply.account_failover = f"primary Bedrock account rate-limited ({type(error).__name__})"
            return reply


class _AICoreChatBackend:
    def __init__(self, spec: Spec, cfg):
        from clients import aicore
        self.spec = spec
        self._ai = aicore.shared()

    def create(self, req: dict) -> Reply:
        from clients.aicore import AICoreError
        try:
            data = self._ai.chat(self.spec.model, to_chat(req, self.spec))
        except AICoreError as e:
            raise ModelCallFailed(self.spec, e.status, str(e)) from None
        return from_chat(data, self.spec)


def _make_backend(spec: Spec, cfg):
    if spec.provider == "aicore" and _claude_name(spec):
        return _AICoreAnthropicBackend(spec, cfg)
    return {"bedrock": _AnthropicBackend, "bedrock-openai": _BedrockChatBackend,
            "aicore": _AICoreChatBackend}[spec.provider](spec, cfg)


# -------------------------------------------------------------------- catalog
@dataclass(frozen=True)
class Listing:
    spec: str
    label: str
    vendor: str
    note: str = ""


#: What the Models page offers. Every one ran a two-round tool loop (call, result,
#: answer) through this module from ap-southeast-2 on 2026-10-24. Left out:
#: Gemma (answers without calling the tool), Qwen3 Coder 480B and Nemotron Super
#: (timed out at 180 s), and the Claude 5 family, which Mantle does not serve in
#: ap-southeast-2. Whether a given AWS account may call a model is a separate
#: question that only a call answers: `manage.py models --ping`, or Test on the
#: page. A model that is not listed can still be named in .env, and the page
#: shows it as configured.
CATALOG: Tuple[Listing, ...] = (
    Listing("bedrock:global.anthropic.claude-opus-4-6-v1", "Claude Opus 4.6", "Anthropic"),
    Listing("bedrock:global.anthropic.claude-sonnet-4-6", "Claude Sonnet 4.6", "Anthropic"),
    Listing("bedrock:global.anthropic.claude-haiku-4-5-20251001-v1:0", "Claude Haiku 4.5", "Anthropic",
            "no adaptive thinking"),
    Listing("aicore:anthropic--claude-4.6-sonnet", "Claude Sonnet 4.6", "Anthropic"),
    Listing("aicore:gpt-5.4", "GPT-5.4", "OpenAI"),
    Listing("bedrock-openai:openai.gpt-oss-120b", "gpt-oss-120b", "OpenAI", "open weights"),
    Listing("bedrock-openai:deepseek.v3.2", "DeepSeek V3.2", "DeepSeek"),
    Listing("bedrock-openai:deepseek.v3.1", "DeepSeek V3.1", "DeepSeek"),
    Listing("bedrock-openai:global.moonshotai.kimi-k3", "Kimi K3", "Moonshot AI"),
    Listing("bedrock-openai:moonshotai.kimi-k2.5", "Kimi K2.5", "Moonshot AI"),
    Listing("bedrock-openai:moonshotai.kimi-k2-thinking", "Kimi K2 Thinking", "Moonshot AI",
            "reasoning model"),
    Listing("bedrock-openai:qwen.qwen3-235b-a22b-2507", "Qwen3 235B", "Qwen"),
    Listing("bedrock-openai:zai.glm-5", "GLM-5", "Z.ai"),
    Listing("bedrock-openai:zai.glm-4.7", "GLM-4.7", "Z.ai"),
    Listing("bedrock-openai:mistral.mistral-large-3-675b-instruct", "Mistral Large 3", "Mistral AI"),
    Listing("bedrock-openai:minimax.minimax-m2.5", "MiniMax M2.5", "MiniMax", "text only"),
    # Small and cheap. Each also gathered with two tools and divided correctly.
    Listing("bedrock-openai:zai.glm-4.7-flash", "GLM-4.7 Flash", "Z.ai", "small"),
    Listing("bedrock-openai:openai.gpt-oss-20b", "gpt-oss-20b", "OpenAI", "small, open weights"),
    Listing("bedrock-openai:qwen.qwen3-32b", "Qwen3 32B", "Qwen", "small"),
    Listing("bedrock-openai:qwen.qwen3-next-80b-a3b-instruct", "Qwen3 Next 80B A3B", "Qwen", "small"),
    Listing("bedrock-openai:mistral.ministral-3-14b-instruct", "Ministral 14B", "Mistral AI", "small"),
    Listing("bedrock-openai:mistral.ministral-3-8b-instruct", "Ministral 8B", "Mistral AI", "small"),
    Listing("bedrock-openai:nvidia.nemotron-nano-3-30b", "Nemotron Nano 3 30B", "NVIDIA", "small"),
)


def listed(raw: str) -> Optional[Listing]:
    try:
        s = str(parse(raw))
    except ValueError:
        return None
    return next((x for x in CATALOG if x.spec == s), None)


def catalog() -> List[dict]:
    """The catalog as the Models page shows it: route, rate, and whether a call
    can be attempted from here."""
    out = []
    for x in CATALOG:
        s = parse(x.spec)
        ok, why = ready(s)
        i, o = usd_per_mtok(s)
        out.append({"model": x.spec, "label": x.label, "vendor": x.vendor, "note": x.note or None,
                    "via": route_of(s), "usd_per_mtok": [i, o], "ready": ok, "why": why or None})
    return out


# --------------------------------------------------------------------- router
class Router:
    """What graph.client() hands out: the SDK client's shape,
    `messages.create(**request)`, with the model named per request. One Router
    lives for one handling, so a model that failed once stays failed for the
    rest of it instead of costing a timeout on every round.

    `fallback=` names the model to try when the request's own one fails. The
    reply then carries `fell_back_from`, which the loops write to the trail:
    an answer from a different model than the one configured is something a
    person reading the record should be able to see."""

    def __init__(self, cfg=None, make_backend: Callable[[Spec, Any], Any] = _make_backend,
                 ready_fn: Callable[..., Tuple[bool, str]] = ready):
        self.messages = self
        self._cfg = cfg or _config.CFG
        self._make = make_backend
        self._ready = ready_fn
        self._backends: Dict[Spec, Any] = {}
        self._down: Dict[Spec, str] = {}
        self._lock = threading.Lock()

    def _backend(self, spec: Spec):
        with self._lock:
            b = self._backends.get(spec)
            if b is None:
                ok, why = self._ready(spec, self._cfg)
                if not ok:
                    raise ModelUnavailable(f"{spec}: {why}")
                b = self._backends[spec] = self._make(spec, self._cfg)
            return b

    def create(self, **req) -> Reply:
        model = req.pop("model")
        primary = model if isinstance(model, Spec) else parse(model)
        fb = req.pop("fallback", None)
        fb = parse(fb) if isinstance(fb, str) and fb else (fb or None)
        if fb is None or fb == primary or primary not in self._down:
            try:
                return self._backend(primary).create(req)
            except Exception as e:                                   # noqa: BLE001
                if fb is None or fb == primary:
                    raise
                self._down[primary] = f"{type(e).__name__}: {e}"[:300]
        reply = self._backend(fb).create(req)
        reply.fell_back_from = (str(primary), self._down[primary])
        return reply


def ping(spec: Spec, cfg=None) -> Tuple[bool, str, float]:
    """One tiny real call: (worked, what came back or why not, seconds)."""
    t = time.monotonic()
    try:
        r = Router(cfg).create(model=spec, max_tokens=256,
                               system="Answer with the single word: ready.",
                               messages=[{"role": "user", "content": "Are you there?"}])
        text = "".join(getattr(b, "text", "") for b in r.content
                       if getattr(b, "type", None) == "text").strip()
        return True, (text or f"(no text, stop_reason={r.stop_reason})")[:80], time.monotonic() - t
    except Exception as e:                                           # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"[:300], time.monotonic() - t


# ----------------------------------------------------------------- self-check
def demo() -> None:
    # Naming: what .env already carries keeps meaning what it meant.
    assert parse("anthropic.claude-opus-5") == Spec("bedrock", "anthropic.claude-opus-5")
    legacy = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert parse(legacy) == Spec("bedrock", legacy), "a colon inside an id is not a provider"
    assert parse("minimax.minimax-m2.5") == Spec("bedrock-openai", "minimax.minimax-m2.5")
    assert parse("aicore:gpt-5.4") == Spec("aicore", "gpt-5.4")
    assert parse("gpt-5.4") == Spec("aicore", "gpt-5.4")
    for bad in ("openai:gpt-5.4", "", "aicore:"):
        try:
            parse(bad)
            raise AssertionError(f"{bad!r} must be refused")
        except ValueError:
            pass
    assert _runtime_id(legacy) and not _runtime_id("anthropic.claude-opus-5")
    assert _runtime_id("global.moonshotai.kimi-k3") and not _runtime_id("deepseek.v3.2")
    assert route_of(parse("global.moonshotai.kimi-k3")) == "Bedrock runtime (chat)"
    assert route_of(parse("deepseek.v3.2")) == "Bedrock Mantle (chat)"
    print("  naming: bare ids infer their provider ✓ · a made-up provider refused ✓ "
          "· profiles routed to bedrock-runtime ✓")

    # Resolution: one SIGAP_MODEL still runs the whole team on one model; the
    # split only happens when asked for.
    keys = ("SIGAP_MODEL_SPECIALISTS", "SIGAP_MODEL_COMPLIANCE", "SIGAP_MODEL_LOGISTICS",
            "SIGAP_MODEL_FALLBACK", "SIGAP_MODEL_SUPERVISOR")
    saved = {k: os.environ.pop(k, None) for k in keys}
    try:
        lead = spec_for_code("supervisor")
        assert spec_for_code("logistics") == lead == spec_for_code("compliance", veto=True)
        os.environ["SIGAP_MODEL_SPECIALISTS"] = "minimax.minimax-m2.5"
        assert spec_for_code("logistics").provider == "bedrock-openai"
        assert spec_for_code("compliance", veto=True) == lead, "the veto stays on the strong model"
        assert spec_for_code("supervisor") == lead
        os.environ["SIGAP_MODEL_LOGISTICS"] = "aicore:gpt-5.4"
        assert spec_for_code("logistics") == Spec("aicore", "gpt-5.4"), "per agent wins"
        os.environ["SIGAP_MODEL_FALLBACK"] = "aicore:gpt-5.4"
        assert fallback_for(primary=Spec("aicore", "gpt-5.4")) is None, "no fallback to itself"
        assert fallback_for(primary=lead) == Spec("aicore", "gpt-5.4")

        # The Models page: a choice beats the variable at its own level, and a
        # narrower level still beats a broader one, whoever set it.
        before = chosen()
        try:
            choose({"specialists": "deepseek.v3.2", "lead": "aicore:anthropic--claude-4.6-sonnet",
                    "fallback": NO_FALLBACK, "aux": "zai.glm-4.7", "inventory": ""})
            assert resolve("inventory") == (Spec("bedrock-openai", "deepseek.v3.2"), "page:specialists")
            assert resolve("logistics") == (Spec("aicore", "gpt-5.4"), "SIGAP_MODEL_LOGISTICS"), \
                "an agent's own variable is narrower than the page's specialists"
            assert resolve("supervisor") == (Spec("aicore", "anthropic--claude-4.6-sonnet"), "page:lead")
            assert spec_for_code("compliance", veto=True) == spec_for_code("supervisor")
            assert fallback_for(primary=lead) is None, "the page can switch the fallback off"
            assert aux_spec() == Spec("bedrock-openai", "zai.glm-4.7")
            choose({"logistics": "moonshotai.kimi-k2.5"})
            assert resolve("logistics")[1] == "page:logistics"
            try:
                choose({"lead": "openai:gpt-5.4"})
                raise AssertionError("a bad choice must be refused")
            except ValueError:
                assert resolve("logistics")[1] == "page:logistics", "and leave the old one standing"
        finally:
            choose(before)
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    print("  resolution: one SIGAP_MODEL runs everyone ✓ · specialists split off ✓ "
          "· Kira stays with the deciders ✓ · per-agent override ✓ · page choice layered ✓")

    # Capabilities, which replace the old `"haiku" not in model` test.
    assert caps(Spec("bedrock", "anthropic.claude-opus-5")).thinking
    assert caps(Spec("bedrock", "anthropic.claude-haiku-5-5")).thinking_off == {"type": "disabled"}
    assert caps(Spec("bedrock", "anthropic.claude-opus-5-5")).thinking_off is None, \
        "Opus 5.5 cannot be told not to think"
    assert not caps(Spec("bedrock", legacy)).thinking, "Haiku 4.5 takes no adaptive thinking"
    assert caps(Spec("bedrock-openai", "minimax.minimax-m2.5")).max_output == 8_192
    sonnet_on_aicore = Spec("aicore", "anthropic--claude-4.6-sonnet")
    assert _claude_name(sonnet_on_aicore) == "claude-sonnet-4-6"
    assert caps(sonnet_on_aicore).thinking, "Claude on AI Core is still Claude"
    assert not _claude_name(Spec("aicore", "gpt-5.4")) and not caps(Spec("aicore", "gpt-5.4")).thinking
    assert not caps(Spec("bedrock-openai", "deepseek.v3.2")).images
    assert caps(Spec("bedrock-openai", "qwen.qwen3-vl-235b-a22b-instruct")).images

    # Price: per model, aicore free, an unknown model at the dearest rate.
    def rp(spec, i, o):
        return round(price_idr(Usage(spec, i, o)))
    assert rp(Spec("bedrock", "anthropic.claude-opus-5"), 10**6, 10**6) == 82_000 + 410_000
    assert rp(Spec("bedrock", "anthropic.claude-opus-5-5"), 10**6, 0) == 65_600
    assert rp(Spec("bedrock-openai", "minimax.minimax-m2.5"), 10**6, 10**6) == round(1.55 * 16_400)
    assert rp(Spec("aicore", "gpt-5.4"), 10**6, 10**6) == 0
    assert rp(Spec("bedrock-openai", "somebody.new-model"), 10**6, 0) == 82_000
    assert rp(None, 10**6, 0) == 82_000, "usage of unknown origin is priced high"
    assert usd_per_mtok(Spec("bedrock-openai", "deepseek.v3.2")) == (0.64, 1.91)
    assert usd_per_mtok(Spec("bedrock-openai", "zai.glm-4.7-flash")) == (0.07, 0.41), "longer id first"
    assert usd_per_mtok(Spec("bedrock", "global.anthropic.claude-sonnet-4-6")) == (3.00, 15.00)
    # Every Bedrock model the page offers has a rate of its own. One that fell
    # through to the default would still cap safely, but every figure shown
    # for it would be wrong.
    for x in CATALOG:
        s = parse(x.spec)
        assert str(s) == x.spec, f"{x.spec} is not written the way parse() writes it"
        if s.provider != "aicore":
            assert any(k in s.model.lower() for k, _, _ in _USD_PER_MTOK), f"no rate for {x.spec}"
    assert listed("deepseek.v3.2") and not listed("somebody.new-model") and not listed("openai:x")
    print("  capabilities per model ✓ · price per model ✓ · unknown priced as Opus ✓ "
          "· every listed model priced ✓")

    # Translation, both ways, on the exact transcript shape graph.py builds.
    spec = Spec("bedrock-openai", "minimax.minimax-m2.5")
    req = {"max_tokens": 16000, "system": "You are Iris.",
           "thinking": {"type": "adaptive"}, "output_config": {"effort": "high"},
           "tools": [{"name": "get_material_stock", "description": "Stock.", "strict": True,
                      "input_schema": {"type": "object", "properties": {"material": {"type": "string"}},
                                       "required": ["material"], "additionalProperties": False}}],
           "messages": [
               {"role": "user", "content": "Cover for M-4471?"},
               {"role": "assistant", "content": [ThinkingBlock("check stock"),
                                                 TextBlock("Reading stock."),
                                                 ToolUseBlock("call_1", "get_material_stock",
                                                              {"material": "M-4471"})]},
               {"role": "user", "content": [
                   {"type": "tool_result", "tool_use_id": "call_1", "content": '{"value": 84}'},
                   {"type": "tool_result", "tool_use_id": "call_2", "content": "boom",
                    "is_error": True}]},
           ]}
    body = to_chat(req, spec)
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user", "assistant", "tool", "tool"], roles
    assert body["max_tokens"] == 8_192, "clamped to what MiniMax can return"
    assert "thinking" not in body and "output_config" not in body
    a = body["messages"][2]
    assert a["tool_calls"][0]["function"] == {"name": "get_material_stock",
                                              "arguments": '{"material": "M-4471"}'}
    assert a["content"].startswith("<think>check stock</think>"), "MiniMax gets its reasoning back"
    assert body["messages"][4]["content"] == "ERROR: boom"
    assert body["tools"][0]["function"]["parameters"]["required"] == ["material"]
    assert "max_completion_tokens" in to_chat(req, Spec("aicore", "gpt-5.4"))
    assert "<think>" not in (to_chat(req, Spec("aicore", "gpt-5.4"))["messages"][2]["content"] or "")

    r = from_chat({"choices": [{"finish_reason": "tool_calls", "message": {
        "content": "<think>need stock</think>Checking.",
        "tool_calls": [{"id": "c9", "type": "function", "function": {
            "name": "get_material_stock", "arguments": '{"material": "M-4471"}'}}]}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 50,
                  "prompt_tokens_details": {"cached_tokens": 200}}}, spec)
    assert r.stop_reason == "tool_use"
    assert [b.type for b in r.content] == ["thinking", "text", "tool_use"]
    assert r.content[1].text == "Checking." and r.content[2].input == {"material": "M-4471"}
    assert (r.usage.input_tokens, r.usage.cache_read_input_tokens) == (800, 200), \
        "cached tokens are not counted twice"
    r = from_chat({"choices": [{"finish_reason": "stop", "message": {
        "content": "x", "tool_calls": [{"id": "c1", "function": {"name": "t",
                                                                  "arguments": "{not json"}}]}}]}, spec)
    assert r.stop_reason == "tool_use" and r.content[-1].input == {}, \
        "a tool call is a tool call whatever the finish reason; bad JSON runs as no arguments"
    leaked = from_chat({"choices": [{"message": {"tool_calls": [{"id": "c2", "function": {
        "name": "get_bom_explosion<|channel|>json", "arguments": "{}"}}]}}]}, spec)
    assert leaked.content[-1].name == "get_bom_explosion", "harmony markers are not part of a name"
    assert _split_think("plan</think> answer") == ("plan", "answer")
    assert _split_think("answer <think>cut off") == ("cut off", "answer")
    # A transcript a chat model wrote can still be sent to Claude.
    back = _anthropic_messages(req["messages"])
    assert [b["type"] for b in back[1]["content"]] == ["text", "tool_use"], \
        "an unsigned thinking block never reaches Claude"
    print("  translation: tools ↔ functions ✓ · tool_result ↔ role tool ✓ · errors kept ✓ "
          "· reasoning split out ✓ · usage not double-counted ✓")

    assert is_rate_limited(ModelCallFailed(Spec("bedrock", "x"), 429, "slow down"))
    assert not is_rate_limited(ModelCallFailed(Spec("bedrock", "x"), 403, "denied"))

    class FakeMessages:
        def __init__(self, response=None, error=None):
            self.response, self.error, self.calls = response, error, 0

        def create(self, **_req):
            self.calls += 1
            if self.error:
                raise self.error
            return self.response

    class FakeClient:
        def __init__(self, messages):
            self.messages = messages

    response = type("Response", (), {
        "content": [TextBlock("ok")], "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 1},
    })()
    backend = object.__new__(_AnthropicBackend)
    backend.spec = Spec("bedrock", "anthropic.claude-haiku-4-5")
    primary_messages = FakeMessages(error=ModelCallFailed(backend.spec, 429, "slow down"))
    fallback_messages = FakeMessages(response=response)
    backend._sdk = FakeClient(primary_messages)
    backend._sdk_fallback = FakeClient(fallback_messages)
    account_reply = backend.create({"max_tokens": 10, "system": "s",
                                    "messages": [{"role": "user", "content": "q"}]})
    assert primary_messages.calls == fallback_messages.calls == 1
    assert account_reply.account_failover and account_reply.model == str(backend.spec), \
        "a 429 uses the second AWS account without changing the configured model"

    # One AWS account is a whole configuration. Requiring two made Bedrock
    # unreachable for every deployment that has one, which is most of them.
    fallback_names = ("AWS_FALLBACK_ACCESS_KEY_ID", "AWS_FALLBACK_SECRET_ACCESS_KEY",
                      "AWS_FALLBACK_REGION", "AWS_FALLBACK_SESSION_TOKEN")
    kept = {k: os.environ.pop(k, None) for k in fallback_names}
    one_account = type("Cfg", (), {"aws_region": "ap-southeast-3"})()
    try:
        assert _fallback_aws_options(one_account) is None, "no second account is not an error"
        os.environ["AWS_FALLBACK_ACCESS_KEY_ID"] = "AKIAEXAMPLE"
        try:
            _fallback_aws_options(one_account)
            raise AssertionError("a half-configured fallback must be refused, not ignored")
        except ModelUnavailable as e:
            assert "AWS_FALLBACK_REGION" in str(e), e
        os.environ.update({"AWS_FALLBACK_SECRET_ACCESS_KEY": "s", "AWS_FALLBACK_REGION": "us-east-1"})
        assert _fallback_aws_options(one_account) == {
            "aws_access_key": "AKIAEXAMPLE", "aws_secret_key": "s", "aws_region": "us-east-1"}
        try:
            _fallback_aws_options(type("Cfg", (), {"aws_region": ""})())
            raise AssertionError("the primary region is still required")
        except ModelUnavailable:
            pass
    finally:
        for k, v in kept.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    # And with no second account, a 429 is the answer — not an AttributeError.
    backend._sdk_fallback = None
    primary_messages.calls = 0
    try:
        backend.create({"max_tokens": 10, "system": "s",
                        "messages": [{"role": "user", "content": "q"}]})
        raise AssertionError("a 429 with no second account must surface")
    except ModelCallFailed as e:
        assert e.status == 429
    assert primary_messages.calls == 1, "and it is not retried into nothing"
    print("  rate-limit classification ✓ · second AWS account failover ✓ "
          "· one account is enough ✓ · half-configured failover refused ✓")

    # Routing and fallback, with stand-in backends.
    calls: List[str] = []

    class Fake:
        def __init__(self, spec, cfg):
            self.spec = spec

        def create(self, req):
            calls.append(str(self.spec))
            if self.spec.model == "broken":
                raise ModelCallFailed(self.spec, 403, "no access to this model")
            return Reply([TextBlock("ok")], "end_turn", Usage(self.spec, 10, 1), self.spec)

    class Cfg:
        aws_region = "ap-southeast-3"

    def region_only(spec, cfg):           # readiness without needing the SDK installed
        return (True, "") if cfg.aws_region else (False, "AWS_REGION is not set")

    router = Router(Cfg(), make_backend=Fake, ready_fn=region_only)
    base = {"max_tokens": 10, "system": "s", "messages": [{"role": "user", "content": "q"}]}
    r1 = router.create(model="bedrock:broken", fallback="bedrock-openai:minimax.minimax-m2.5", **base)
    r2 = router.create(model="bedrock:broken", fallback="bedrock-openai:minimax.minimax-m2.5", **base)
    assert r1.fell_back_from and r1.fell_back_from[0] == "bedrock:broken" and "403" in r1.fell_back_from[1]
    assert r2.fell_back_from and calls.count("bedrock:broken") == 1, \
        "a failed model is not retried on every round of the same handling"
    assert r1.usage.spec == Spec("bedrock-openai", "minimax.minimax-m2.5"), "priced at who answered"
    try:
        Router(Cfg(), make_backend=Fake, ready_fn=region_only).create(model="bedrock:broken", **base)
        raise AssertionError("no fallback configured: the failure must surface")
    except ModelCallFailed:
        pass

    class NoRegion:
        aws_region = ""
    try:
        Router(NoRegion(), make_backend=Fake, ready_fn=region_only).create(
            model="bedrock:anthropic.claude-opus-5", **base)
        raise AssertionError("a model that cannot be reached must say why, not be attempted")
    except ModelUnavailable as e:
        assert "AWS_REGION" in str(e)
    print("  routing: fallback answers ✓ · a failed model stays failed for the handling ✓ "
          "· no fallback means the error surfaces ✓ · an unreachable model says why ✓")
    print("llm ok")


if __name__ == "__main__":
    demo()
