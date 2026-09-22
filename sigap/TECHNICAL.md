# Technical notes

> An appendix to `PLAN.md`. Only the things that need exact function names and
> parameters live here — every conceptual explanation is in `PLAN.md`.

## Calling Claude through Bedrock

```python
from anthropic import AnthropicBedrockMantle

client = AnthropicBedrockMantle(aws_region="us-west-2")   # check the region first

resp = client.messages.create(
    model="anthropic.claude-opus-5",        # the "anthropic." prefix is required on Bedrock
    max_tokens=16000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},       # inside output_config, not top-level
    tools=TOOLS,
    messages=messages,
)
```

**Common mistakes:**

| Wrong | Right | Consequence |
|---|---|---|
| `AnthropicBedrock(...)` | `AnthropicBedrockMantle(...)` | The old one takes the InvokeModel path, not the Messages API |
| `model="claude-opus-5"` | `model="anthropic.claude-opus-5"` | Model name rejected on Bedrock |
| `thinking={"type":"enabled","budget_tokens":N}` | `thinking={"type":"adaptive"}` | **400 error** on Opus 5 |
| `effort="high"` at top level | inside `output_config` | Parameter silently ignored |

## Effort per agent

| Agent | Effort | Why |
|---|---|---|
| Supervisor | `high` | He picks the route and judges when the evidence is enough |
| Rules (Kira) | `high` | A veto decision must not be wrong |
| Everyone else | `medium` | Their task is narrow and well defined |

Use **streaming** for the supervisor — his turn is long, and without streaming it can
hit the HTTP timeout.

```python
with client.messages.stream(model=..., max_tokens=64000, ...) as stream:
    resp = stream.get_final_message()
```

## Keeping cost down: prompt caching

Order on the wire: `tools` → `system` → `messages`. Put what **does not change** first.
One changed byte near the front invalidates the cache for everything after it.

In the agent team the tool list and the instructions are re-sent on **every** specialist
turn — without caching, the cost multiplies by the number of agents.

```python
resp = client.messages.create(
    ...,
    cache_control={"type": "ephemeral"},
)
print(resp.usage.cache_read_input_tokens)   # always zero → something is busting the cache
```

The usual culprits: `datetime.now()` in the instructions, a tool list whose order varies,
or a random id near the front.

## If cost has to come down further

Specialists can move to `anthropic.claude-sonnet-5` while the supervisor and Kira stay
on Opus 5.

**Don't do this before measuring.** Two caveats: the cache is per-model, so running two
models throws away cache reuse; and a cheaper request that needs more rounds is not
actually cheaper.

## The data-origin label

One wrapper, used by every tool. It lives in `core/provenance.py`.

```python
class Origin(str, Enum):
    LIVE = "live"          # straight from SAP / an official API
    CACHED = "cached"      # was live once, carries its timestamp
    DERIVED = "derived"    # computed from something live
    MODELLED = "modelled"  # company profile / fixture — labelled in the open
    MISSING = "missing"    # the lead stops here rather than guessing

@dataclass
class Result:
    value: Any
    origin: Origin
    source: str            # "API_MATERIAL_STOCK_SRV" / "TKDN register"
    fetched_at: datetime
    note: str = ""
```

**The rule:** if an input on a critical path is `MISSING` or `MODELLED`, the cost
calculator **must not** emit a savings figure. The lead reports what is missing instead.
`engine/simulate.py` enforces this in code, not in a prompt.

## Limits that stop the team looping

These are in `graph.py` and were there from the second agent onwards:

- `MAX_SPECIALIST_ROUNDS` — tool rounds inside one specialist's turn
- `MAX_LEAD_ROUNDS` — total supervisor rounds
- `CFG.cost_cap_per_event_idr` — model spend per event, raises `BudgetExhausted`

Every agent-team system needs limits like these, for the same reason: without them they
can pass work back and forth indefinitely.

## Why one process, not cloud functions

```
# ponytail: one Python process; split into a Lambda per tool if you need scale or isolation
```

Twenty-three separate cloud functions on day one means every small change needs a
deploy. One ordinary program is enough for now. Move to cloud once the system is
actually in use.

## Installed

```bash
pip install anthropic boto3 strands-agents httpx pydantic
npm install                                   # Next.js 16, React 19, Tailwind v4, shadcn-ui
```
