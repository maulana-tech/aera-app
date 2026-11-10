"""The auxiliary LLM: a cheap, fast model for boilerplate generation.

Ported in spirit from  aux-llm.ts. The idea: the agent team runs on an
expensive frontier model (Opus), and spending that model on one-shot chores —
writing a report's summary prose, condensing a finding to one line, titling a
conversation — is waste that also slows and crowds the real reasoning. Those
chores go to a small model (Haiku by default, AERA_AUX_MODEL) through this one
helper, so the agents are left to decide.

Two rules carried straight from  hard-won experience:

  * BEST-EFFORT, FAIL-OPEN. Every call here can return None (model not ready,
    timeout, any error). A caller must degrade gracefully — the aux LLM is UX
    scaffolding, never load-bearing. In AERA this matters doubly: the aux model
    must never be on the path of a figure or a decision, only the prose around
    them (engine/report.py hands it the numbers as facts and asks only for
    words). So a missing aux model costs polish, never correctness.

  * BUDGET PER CALL SITE. SmartX found a blanket token floor made the aux spend
    starve the main agent (their proof: 3 findings vs 22 in the same hour). So
    `max_tokens` is set by each caller to what that one output needs, not a
    global default inflated for the worst case.

The aux model is meant to be quick, so it is asked not to think, where the
model allows that to be asked (Haiku 5.5 does; core/llm.py knows which do).
Without it Haiku 5.5 thinks by default and can spend a 120-token budget before
writing a word. Any leaked chain-of-thought is stripped before the text is
returned.

No `temperature` is sent. Haiku 5.5 refuses a non-default value with a 400,
and because this helper is fail-open, that refusal used to turn every summary
into a silent None.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Optional

from core import llm


def ready() -> bool:
    """The aux model (AERA_AUX_MODEL), or AERA_MODEL_FALLBACK, can be called
    from here. It is its own model, so it can be ready when the agents' is not,
    and the other way round."""
    try:
        return llm.usable(llm.aux_spec())
    except ValueError:                    # a malformed AERA_AUX_MODEL
        return False


_THINK = re.compile(r"<think>[\s\S]*?</think>", re.I)


def strip_reasoning(text: str) -> str:
    """Remove chain-of-thought a reasoning model may leak into visible text, so
    it never lands in a report or a title. Idempotent; safe on clean text."""
    if not text:
        return text
    text = _THINK.sub("", text)
    text = re.sub(r"^[\s\S]*?</think>\s*", "", text, flags=re.I)   # dangling close
    text = re.sub(r"<think>[\s\S]*$", "", text, flags=re.I)        # unclosed open
    return text.strip()


def generate(system: str, user: str, *,
             max_tokens: int = 512,
             timeout_s: float = 30.0) -> Optional[str]:
    """One-shot aux generation. Returns the trimmed text, or None on any
    failure (model not ready, timeout, transport error). Never raises — the
    caller decides how to degrade. `max_tokens` is the per-call-site budget."""
    if not ready():
        return None

    def _call() -> Optional[str]:
        spec = llm.aux_spec()
        fb = llm.fallback_for(primary=spec)
        r = llm.Router().create(
            model=spec,
            **({"fallback": fb} if fb else {}),
            max_tokens=max_tokens,
            thinking={"type": "disabled"},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(getattr(b, "text", "") for b in r.content
                       if getattr(b, "type", None) == "text")
        return strip_reasoning(text) or None

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(_call).result(timeout=timeout_s)
    except FutureTimeout:
        return None
    except Exception:                     # noqa: BLE001  — best-effort
        return None


def demo() -> None:
    # strip_reasoning cleans leaked chain-of-thought in every shape.
    assert strip_reasoning("<think>plan</think>Answer") == "Answer"
    assert strip_reasoning("noise</think> Real") == "Real"
    assert strip_reasoning("<think>cut to end") == ""
    assert strip_reasoning("  plain  ") == "plain"
    assert strip_reasoning("") == ""

    # Fail-open: with no model configured, aux returns None rather than raising,
    # so a caller (engine/report.py) falls back to its deterministic output.
    if not ready():
        assert ready() is False
        assert generate("sys", "write something", max_tokens=32) is None, \
            "aux must fail-open to None when the model is not ready"
    print("aux ok, strip_reasoning ✓ · fail-open to None when model unset ✓"
          + ("" if ready() else " (model not configured, fallback path verified)"))


if __name__ == "__main__":
    demo()
