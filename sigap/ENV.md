# Environment and credentials

> Everything the service reads from the environment, what it is for, where to
> get it, and how to tell it is working. Written for someone setting the
> project up for the first time on their own machine.
>
> `SETUP.md` is the walkthrough with the ordered steps. This file is the
> reference: one entry per variable, and the credential sections at the end.

---

## The one rule

**No real value belongs in this file, in any file tracked by git, or in a chat
message.** Values live in `sigap/agent/.env`, which is gitignored, or in
`sigap/agent/.secrets/`, which is gitignored and mode 700. Every value printed
below is a placeholder.

The hackathon manual puts it the same way: *"Keep these credentials private. Do
not commit them to git or paste them into shared chats."*

If a secret does reach a chat, a screenshot or a commit, treat it as burned and
rotate it. Rotating takes a minute; not rotating is a judge or a stranger
holding your SAP quota and your session-signing key.

---

## Fast path

Four lines get a working system on fixtures, with no account anywhere:

```bash
cd sigap/agent
cp .env.example .env
PYTHONPATH=. python3 manage.py secret        # prints: export SIGAP_SECRET="…"
PYTHONPATH=. python3 manage.py check
```

`manage.py secret` prints a whole `export SIGAP_SECRET="…"` line so it can be
sourced; in `.env` you want only the part inside the quotes.

That runs. Figures come from `fixtures/` and are labelled `MODELLED`, which the
interface shows and the calculator refuses to price. Adding `SAP_API_KEY` and
a model (see **Models** below) is what turns the labels to `LIVE` and lets the
agents reason.

---

## Every variable

Read by `core/config.py` unless the table says otherwise. A value with a `#`
after it has the comment stripped automatically, so
`SAP_API_KEY=abc   # from api.sap.com` stores `abc`. **A trailing note without
a `#` is kept as part of the value**, which is a quiet way to end up with a
region named `us-west-2    see below`.

### Required

| Variable | Example | What it does |
|---|---|---|
| `SIGAP_SECRET` | `a1b2…` (64 hex) | Signs session tokens. Identity comes only from this signature, so whoever holds it can mint an admin session. Generate per machine, never share, never commit |

### Connects the system to the outside

| Variable | Default | What it does |
|---|---|---|
| `SAP_API_KEY` | empty | SAP Business Accelerator Hub sandbox key. Empty means every read falls back to `fixtures/` and is labelled `MODELLED`. See **SAP key** below |
| `SAP_BASE_URL` | `https://sandbox.api.sap.com` | Where the OData calls go. Change this and the auth scheme for a real S/4HANA tenant, see `BUILD-SPEC.md` §5 |
| `SAP_TIMEOUT` | `30` | Seconds per SAP call. Read in `clients/sap_s4.py`, not through `CFG` |
| `AWS_REGION` | empty | Bedrock region, for example `ap-southeast-2`. Empty means no Bedrock model can be called |
| `SIGAP_MODEL` | `anthropic.claude-opus-5` | The deciders' model (Arya and Kira), and everyone's unless the next rows say otherwise. Format `provider:model`, see **Models** |
| `SIGAP_MODEL_SPECIALISTS` | empty | The other ten specialists. Empty means they run on `SIGAP_MODEL` |
| `SIGAP_MODEL_<CODE>` | empty | One agent on its own model, for example `SIGAP_MODEL_LOGISTICS=aicore:gpt-5.4` |
| `SIGAP_MODEL_FALLBACK` | empty | Tried once when an agent's model fails, then kept for the rest of that handling. Used by the aux model too |
| `SIGAP_AUX_MODEL` | `anthropic.claude-haiku-5-5` | Narration, summaries and titles. Never on a figure or a decision (`core/aux.py`) |
| `AWS_BEARER_TOKEN_BEDROCK` | empty | A Bedrock API key, instead of IAM credentials. An environment variable, read by the AWS SDK and by `core/llm.py`; not a `.env` line |
| `SIGAP_AICORE_KEY_FILE` | `.secrets/ai-core.json` | The SAP AI Core service key. `AICORE_SERVICE_KEY` (the JSON itself) wins when set, which is how Cloud Foundry passes it |
| `AICORE_RESOURCE_GROUP` | `default` | The AI Core resource group, `default` for the hackathon |
| `SIGAP_AICORE_DEPLOYMENTS` | empty | Pin deployment ids, `gpt-5.4=…,sap-rpt-1.6=…`. Empty means they are looked up by model name |
| `SIGAP_RPT_MODEL` | `sap-rpt-1.6` | The AI Core model Vega's `rank_po_slip_risk` predicts with |

AWS credentials themselves are **not** `.env` lines. They come from the
standard AWS chain, so run `aws configure` and leave them out of `.env`. See
**Models** below.

### Behaviour

| Variable | Default | What it does |
|---|---|---|
| `SIGAP_ENV` | `dev` | `prod` makes the service refuse to accept events unless both SAP and the model are connected |
| `SIGAP_DB` | `data/sigap.db` | SQLite file. Use an absolute path on a server. This file is the approval record, so it is the thing to back up |
| `SIGAP_WATCH` | `1` | `0` stops the four watchers (BMKG, hazards, weather, Vega), so nothing raises an event on its own. Alerts, the SAP sender and the digest keep running. Set it when you do not want the queue filling with live events, for example in the hour before a demo. See **Schedule** |
| `SIGAP_SCHEDULE` | `1` | `0` stops everything that runs on its own, including alert delivery. A job can still be run by hand from the Schedule page |
| `SIGAP_WEB_URL` | `http://localhost:3000` | Where people open SIGAP. Every alert links to the handling there, so on a server this is the public address |
| `SIGAP_IDR_PER_USD` | `16400` | The rate model spend is priced at. The default is the rate the first prices were set at; `manage.py ready` compares it with the ECB reference rate and says when it is more than 5% off |
| `SIGAP_AUTONOMOUS_LIMIT_IDR` | `50000000` | Ceiling for acting without a person. Value is only half the test: every figure under the decision must also be trusted. `tools/execution.py` enforces it, and the tool descriptions and the prompts of Bram and Vega quote it from here |
| `SIGAP_RULE_PACK` | `../references/rule-pack.json` | Kira's rule pack: contract terms, licensing time, collective leave, supplier certificates, each with its source. Installed per deployment, never committed. Format in `references/README.md`. Absent, every ruling is labelled modelled |
| `SIGAP_COST_CAP_IDR` | `500000` | Model spend per event before the handling stops |

### Where it listens

| Variable | Default | What it does |
|---|---|---|
| `PORT` | `8787` | Set by the platform on Cloud Foundry. Setting it also flips the bind address to `0.0.0.0` |
| `SIGAP_HOST` | `127.0.0.1`, or `0.0.0.0` when `PORT` is set | Override the bind address directly. Loopback by default on purpose: the service opens to a network only when something asks it to |

### Front end

Read by Next.js, so they belong in a `.env.local` at the repo root, not in
`sigap/agent/.env`.

| Variable | Default | What it does |
|---|---|---|
| `SIGAP_API` | `http://127.0.0.1:8787` | Where the web app proxies to. The repo's `.env.example` points it at the shared dev agent on EC2; for a local agent, set it to the local address (**Run it locally** below) |

### Set by the tooling, not by you

| Variable | Set by | Why it exists |
|---|---|---|
| `SIGAP_STORE_CHECK`, `SIGAP_GRAPH_CHECK`, `SIGAP_EXPOSURE_CHECK`, `SIGAP_PRECEDENT_CHECK`, `SIGAP_WATCH_CHECK`, `SIGAP_SCHEDULE_CHECK`, `SIGAP_JOBS_CHECK`, `SIGAP_NOTIFY_CHECK` | the self-checks | Each check re-executes itself with `SAP_API_KEY` blank and `SIGAP_DB` pointed at a scratch file, so a check cannot depend on your keys or write a specimen event into the real record. The flag marks the second run |
| `BEDROCK_READY` | you, only in `main.py`'s scripted demo | Not read by the service |
| `PYTHONPATH` | you | Must be `.` from `sigap/agent`, or imports of `core` fail |

---

## SAP key

Free, personal, and about five minutes.

1. Make an account at <https://api.sap.com>. This is an **SAP ID account**, not
   the hackathon IAS tenant and not XSUAA. Three separate identity systems with
   similar login screens; signing in to one does not sign you in to another.
2. Open any sandbox API, for example *Material Stock*, and find **Show API Key**
   on the right.
3. Copy it into `SAP_API_KEY` in `sigap/agent/.env`.

Verify it rather than assuming:

```bash
cd sigap/agent
PYTHONPATH=. python3 -c "
from core import registry; import tools
r = registry.run('get_material_stock', {})
print(r.origin.value, len(r.value or []))
"
```

`live` and a row count means it works. `modelled` means the key is not being
read: check for a stray trailing note on the line, and that you edited `.env`
and not `.env.example`.

**Each person uses their own key.** It is free, it is tied to your account, and
sharing one means one person's quota limits everybody.

### What a live read looks like

`clients/sap_map.py` does the joins SAP needs (order item + header + schedule
line, stock by stock type, goods movements for consumption) and hands the tools
the same flat rows the fixtures use. Origins: stock and sales are `derived`
(consumption is computed, sales are converted to rupiah), info-record options
are `derived`, the rest `live`.

SAP holds no column for these. With SAP on they come from the latest **upload**
of the entity when it has them (the result is then labelled with the upload's
origin and its note says how many rows were filled), otherwise they stay empty
and the tools say so:

| Entity | Field | Without an upload |
|---|---|---|
| MaterialStock | `DailyConsumption` | Derived from 90 days of goods issues (201/221/261/281/291/601, net of reversals) |
| PurchaseOrder | `LoadingPort` | Read from the incoterms location when it names a known port, else empty |
| SalesOrder | `LatePenaltyPctPerDay`, `LatePenaltyCapPct` | Empty |
| Supplier | `TkdnCertifiedPct` | Empty |
| AlternateSource | `Quantity`, `ExtraCostIDR`, `TkdnAfterPct`, `NewOrigin` | Empty: Kira does not clear an option whose TKDN is unknown, and Tara refuses to cost options without quantity and cost |

Two entities have no SAP source at all and come only from an upload: `CustomsDeclaration`
(customs status, and the history dwell is measured on) and `MaterialSubstitute`
(engineering's approved substitutes). With SAP on and no upload they are `missing`, never
the fixture. `DATA-SOURCES.md` §1 and §3a.

| Variable | Default | Meaning |
|---|---|---|
| `SIGAP_SAP_ROWS` | `2000` | Rows per SAP read. A capped read says so in its note |
| `SAP_TIMEOUT` | `30` | Seconds per OData call |
| `SAP_QUOTA_COOLDOWN` | `300` | Seconds to stop calling SAP after it reports the rate quota spent. Calls in that window fail at once, labelled `missing` |

**The sandbox has a rate quota.** A page that fans out one read per material
spends it fast; on 24 October 2026 about a thousand calls in a few minutes
locked the key out with `policies.ratelimit.QuotaViolation`. Reads are cached
for two minutes, the demand view forecasts only the twelve pairs that consume
most, and after a quota error SIGAP stops calling for `SAP_QUOTA_COOLDOWN`.

**The sandbox is SAP's demo company, not yours.** Plants 1710, 1010, US30 and
the like, materials such as `TG11` and `MZ-*`, almost no Asian loading ports
and schedule lines mostly years old. A Ningbo scenario finds nothing there;
that is the data, not a fault.

---

## Models

Each agent's model is named `provider:model`, resolved per call by
`core/llm.py`:

| Provider | Speaks | Where | Example |
|---|---|---|---|
| `bedrock` | Anthropic Messages | Claude on Bedrock: Mantle (`bedrock-mantle.{region}.api.aws/anthropic`) for bare ids, InvokeModel for inference profiles | `global.anthropic.claude-opus-4-6-v1` |
| `bedrock-openai` | OpenAI Chat Completions | Other Bedrock models: Mantle (`bedrock-mantle.{region}.api.aws/v1`) for bare ids, `bedrock-runtime.{region}.amazonaws.com/openai/v1` for inference profiles | `deepseek.v3.2`, `global.moonshotai.kimi-k3` |
| `aicore` | OpenAI Chat Completions, or Anthropic Messages for `anthropic--*` (through AI Core's `/invoke`) | SAP AI Core deployments | `gpt-5.4`, `anthropic--claude-4.6-sonnet` |

A bare `anthropic.*` id means `bedrock`, so values written before this table
keep working. An id with a profile prefix (`global.`, `us.`, `apac.`, `au.`…)
or a `-v1:0` version goes to bedrock-runtime; everything else to Mantle.

The default, checked from `ap-southeast-2` on 2026-10-24: one small, cheap
model for every agent, a smaller one for summaries, and AI Core behind both.

```bash
AWS_REGION=ap-southeast-2                                       # Sydney
SIGAP_MODEL=bedrock-openai:minimax.minimax-m2.5                 # all twelve agents
SIGAP_MODEL_FALLBACK=aicore:gpt-5.4                             # when it fails
SIGAP_AUX_MODEL=bedrock-openai:zai.glm-4.7-flash                # report summaries
```

What the same Ningbo closure cost to handle, on fixture data (SAP not
connected), one run each, priced at Rp 16,400 to the dollar (about a tenth
more at the October 2026 rate; `SIGAP_IDR_PER_USD`):

| Lead and veto | The other ten | Time | Cost | What came back |
|---|---|---|---|---|
| Claude Opus 4.6 | MiniMax M2.5 | 278 s | Rp 5,106 | A sound recommendation |
| **MiniMax M2.5** | **MiniMax M2.5** | **281 s** | **Rp 1,435** | **A sound recommendation; every specialist read its data; the transfer waits for approval because the stock figures were modelled** |
| MiniMax M2.5 | GLM-4.7 Flash | 291 s | Rp 852 | Bram wrote "here's what I'm executing" and called no tool; the lead reported the transfers as done |
| gpt-oss-120b | GLM-4.7 Flash | 99 s | Rp 249 | Invented plant codes, read nothing, asked the user for the stock |

So the smallest models are cheaper still and not yet trustworthy as
specialists: they describe a tool call instead of making it. Two guards in
code now catch exactly that, whatever the model: a plant or material that is
not on record is refused out loud (`tools/fetcher.py`), and a specialist that
called no tool has its answer labelled unverified before the lead reads it
(`graph.py`). The alert says what the record holds, not what the lead wrote.
For the strongest recommendations, put the lead back on Claude:
`SIGAP_MODEL=global.anthropic.claude-opus-4-6-v1` with
`SIGAP_MODEL_SPECIALISTS=bedrock-openai:minimax.minimax-m2.5`, about 3.5× the
cost.

The Claude 5 family (`anthropic.claude-opus-5`, `anthropic.claude-haiku-5-5`)
is served by Mantle, and Mantle in `ap-southeast-2` does not carry it. Where an
account has it, set the bare ids and nothing else changes.

With `AWS_REGION` empty and the fallback set, the whole team runs on AI Core's
`gpt-5.4`, and every handling's trail says so with a `fallback` step. That is a
working system with no AWS account at all.

`python3 manage.py models` shows what each agent will run on, what set it, and
whether it can be reached. `python3 manage.py models --ping` makes one small real
call to each model in use, which is the only proof that access was granted;
`--catalog` does the same for every model the Models page offers.

### Choosing from the app

**Settings → Models** (`/models`) picks the model per role (lead and veto,
specialists, fallback, summaries) and per agent, from a list of models that
have each run a full tool loop through `core/llm.py`: Claude Opus 4.6, Sonnet
4.6 and Haiku 4.5; GPT-5.4 and Claude Sonnet 4.6 on AI Core; gpt-oss-120b,
DeepSeek V3.2 and V3.1, Kimi K3, K2.5 and K2 Thinking, Qwen3 235B, GLM-5 and
GLM-4.7, Mistral Large 3, MiniMax M2.5. Each shows its route and its rate.
**Test** makes one real call.

- Only `admin` and `procurement_lead` can save or test. Everyone signed in can
  see what the team runs on.
- A choice is stored in the `settings` table and loaded when the service
  starts. It wins over the environment variable at the same level; a narrower
  level still wins over a broader one, so `SIGAP_MODEL_LOGISTICS` beats a
  specialists choice made on the page. "From .env" hands a role back.
- A change applies to the next model call, including the remaining rounds of a
  handling already running.
- A model that is not on the list can still be named in `.env`; the page shows
  it as configured. The list is `CATALOG` in `core/llm.py`, and the rates are
  from the AWS Price List for `ap-southeast-2`.

### Bedrock, step by step

1. **Pick the region.** `ap-southeast-2` (Sydney) serves Claude 4.6 and Haiku
   4.5 through `global.` inference profiles, and DeepSeek, Kimi, Qwen, GLM,
   gpt-oss, Mistral and MiniMax on Mantle. `ap-southeast-3` (Jakarta) is an
   opt-in region: an account that has not enabled it gets 403 "security token
   invalid" there, whatever the credentials.
2. **Grant the models.** Bedrock console, in that region, **Model access**
   (or **Model catalog**): Claude Opus 4.6, Claude Haiku 4.5, MiniMax M2.5, and
   whatever else the Models page should offer.
   Anthropic models ask for a one-time use-case form per account. A model
   without granted access fails with a 403 that reads like a code bug.
3. **Give an identity permission.** Attach the AWS managed policy
   `AmazonBedrockMantleInferenceAccess` to the IAM user or role. It carries
   `bedrock-mantle:CreateInference` and the Marketplace subscription a
   third-party model such as MiniMax needs on first use. Only the older
   InvokeModel ids (the EC2's Haiku 4.5) need `bedrock:InvokeModel` as well.
4. **Put credentials on the machine**, one of:
   - `aws configure` (key id, secret, region), which writes `~/.aws/credentials`;
   - without the AWS CLI, write `~/.aws/credentials` yourself and
     `chmod 600` it:
     ```ini
     [default]
     aws_access_key_id = AKIA…
     aws_secret_access_key = …
     # aws_session_token = …   only for temporary credentials, which expire
     ```
   - or a Bedrock API key: `AWS_BEARER_TOKEN_BEDROCK=…` in
     `.secrets/bedrock.env` (gitignored, `chmod 600`), which the service reads
     at start, or exported in the shell that starts it.
5. **Set the models** in `.env` as above, restart the service, and run
   `python3 manage.py models --ping`. Every line should say `ok`.

**Never put AWS keys in `.env`** or in a chat. `~/.aws` is outside the repo and
outside anything you might accidentally commit.

### SAP AI Core

The service key goes in `.secrets/ai-core.json` (gitignored, mode 600), or in
`AICORE_SERVICE_KEY` on Cloud Foundry. It gives two things: `gpt-5.4`, the
fallback brain, and `sap-rpt-1.6`, which Vega's `rank_po_slip_risk` predicts
with. `python3 clients/aicore.py` checks the key's shape without a network call;
`manage.py models --ping` makes the real one.

---

## Alerts

When a handling finishes, is held, or fails, SIGAP tells people (`notify.py`).
Nobody has to open the app to learn that Ningbo closed.

**Who is told.** Every contact on the Contacts page whose kinds include the
event's kind (none ticked means every kind and the morning digest), by email;
and every team channel that is set up, once. Only an admin or a procurement
lead can add a contact, because a contact receives what was decided and what
it is worth.

**What they are told.** The title and status; the lead's recommendation,
quoted and clipped, and labelled as the lead's words; then, from the record and
never from the model: what was actually carried out, what waits for approval,
its value and the lowest role that may approve it, what Bram asked to be told
to a role, how much of the evidence was modelled rather than live, and a link
to the handling. A handling that recorded no action says so in as many words,
whatever its prose claims.

**How it is delivered.** Through an outbox: the message is written to the
`notifications` table first, then the `notify` job delivers it (every 30 s,
and straight away after a handling). A delivery that fails is tried three
times. A channel that is not set up marks its messages `skipped` with what it
lacks, so turning a channel on later does not deliver last month's alerts at
once. The same handling never tells the same person twice. The Contacts page
lists the last alerts, and whether each arrived.

**Channels.** Any one is enough. The values are secrets (a webhook URL is a
credential: whoever holds it can post), so they go in
`sigap/agent/.secrets/notify.env`, mode 600, which the service reads the way
it reads `.env`:

| Channel | Variables | Notes |
|---|---|---|
| Email over SMTP | `SIGAP_SMTP_HOST`, `SIGAP_MAIL_FROM`; and `SIGAP_SMTP_PORT` (587), `SIGAP_SMTP_USER`, `SIGAP_SMTP_PASSWORD`, `SIGAP_SMTP_SECURITY` (`starttls`, `ssl` or `none`) | Any SMTP server. AWS SES: `email-smtp.ap-southeast-2.amazonaws.com`, SMTP credentials from the SES console, a verified sender. Gmail or Workspace: `smtp.gmail.com`, an app password, not the account password |
| Email through Composio | `COMPOSIO_API_KEY`; and `SIGAP_COMPOSIO_USER_ID` (`sigap`), `SIGAP_COMPOSIO_ACCOUNT`, `SIGAP_COMPOSIO_AUTH_CONFIG` | Mail leaves from a real Gmail mailbox, so a reply comes back to a person. After the key is in, an admin or lead presses **Connect Gmail** on the Contacts page and signs in to that mailbox. See below |
| Slack | `SIGAP_SLACK_WEBHOOK_URL` | An incoming webhook for the team's channel (Slack app → Incoming Webhooks) |
| Telegram | `SIGAP_TELEGRAM_BOT_TOKEN`, `SIGAP_TELEGRAM_CHAT_ID` | A bot from @BotFather; the chat id of a person who has messaged it, or a group it is in |
| Webhook | `SIGAP_WEBHOOK_URL` | The message as JSON (`subject`, `text`, `kind`, `run_id`, `url`), for whatever routes it on: Microsoft Teams through Power Automate, n8n, a ticket queue |

```bash
cd sigap/agent
install -m 600 /dev/null .secrets/notify.env
$EDITOR .secrets/notify.env          # the lines for one channel
# restart api.py, then on the Contacts page: Send a test alert
.venv/bin/python notify.py --test    # or from the shell
```

With both SMTP and Composio configured, SMTP is used; `SIGAP_EMAIL_VIA=smtp` or
`composio` chooses.

**Files.** Email carries files; a team channel carries the link. A handling's
alert carries its report as a PDF (`SIGAP_ALERT_ATTACH`: `pdf`, the default,
`xlsx`, `pdf,xlsx` or `none`). From a report page, **Send by email** sends that
report, or the operations report, to contacts on the Contacts page as a PDF, a
workbook or both, with a note. Only to contacts, or to the sender: a report
carries what was decided and what it is worth. Files are rendered when the
message goes, from the record as it then stands.

**Composio.** `clients/composio.py` calls Composio's REST API (v3.1) with the
project key, and Composio holds the mailbox's OAuth grant: SIGAP never sees the
Gmail password or token. One Composio project can hold other applications and
other users' mailboxes, so SIGAP only ever sends from a connection that belongs
to its own Composio user id (`SIGAP_COMPOSIO_USER_ID`, default `sigap`), and
refuses a pinned `SIGAP_COMPOSIO_ACCOUNT` that belongs to anybody else. Whoever
signs in through the Connect Gmail link becomes the mailbox SIGAP sends from,
so open it yourself and do not pass it on. A message, its attachments and the
recipient's address pass through Composio on the way out; their Zero Data
Retention option keeps payloads off their storage. Prefer a Composio project of
SIGAP's own: the key reaches every mailbox connected in the project.

### Messages to suppliers and customers

Bram drafts a supplier request (`request_supplier_update`) or a customer notice
(`draft_customer_notice`) as the email itself: subject, body, and the address
the record holds for the partner, read from its business partner in SAP
(`API_BUSINESS_PARTNER`, the address's email, the default one first), else
from an uploaded `PartnerContact` list. The decision queue shows all of it. A
buyer approves a supplier request; a procurement lead a customer notice. Only
then does `outreach.py` queue it in the same outbox, and once the mailbox has
taken it, the action is marked sent with the message id. A send that fails is
tried three times and the action stays approved, with **Send again**.

| Variable | Default | Meaning |
|---|---|---|
| `SIGAP_EXTERNAL_REDIRECT` | unset | Outside production (`SIGAP_ENV` not `prod`), the one address every supplier or customer message goes to instead, marked `[TEST]` and naming the address it was meant for. Unset, outside production nothing is sent. The SAP sandbox's business partners carry real people's addresses |
| `SIGAP_EXTERNAL_DOMAINS` | unset | In production, when set, the only domains a supplier or customer message may go to, comma-separated |

## Schedule

What SIGAP does on its own, in one list (`jobs.py`), run by one loop
(`core/schedule.py`) inside `api.py`. The Schedule page shows each job's last
run, its result and its next run, and lets an admin or a procurement lead run
one now or switch it off. A job's memory is the `jobs` table, so a restart does
not re-run a weekly scan that ran yesterday.

| Job | Cadence | What it does |
|---|---|---|
| `bmkg` | 5 min | Earthquakes near a plant, from BMKG |
| `hazards` | 30 min | Cyclones, floods, quakes, eruptions near a port or a plant: GDACS, NASA EONET, USGS |
| `weather` | 3 h | Gales, high seas and heavy rain forecast at a watched port or plant: Open-Meteo |
| `exposure` | weekly | Vega's scan of our own data for risk that has not happened yet |
| `notify` | 30 s | Deliver queued alerts |
| `sap_send` | 10 min | Send approved actions to SAP (`sender.py`); says so and sends nothing while SAP is not connected |
| `digest` | 07:30 WIB | The morning summary: last 24 hours, and everything still waiting for approval |

The first four raise events, and every event starts a handling that spends
model credit: `SIGAP_WATCH=0` turns those four off and leaves the rest.
`SIGAP_SCHEDULE=0` turns everything off. A job never overlaps itself, a job
that fails keeps its error for the page and runs again next time, and a digest
missed by more than two hours (the server was down at 07:30) is skipped, not
sent late.

## Ready

`manage.py check` asks whether the code works. `manage.py ready` asks whether
the install around it does, and names the fix for each gap:

```bash
.venv/bin/python manage.py ready          # add --ping to make one call to each model
```

It looks at SAP, uploaded data, `SIGAP_ENV`, the lead's model, the exchange
rate, users and their roles, `SIGAP_SECRET`, the alert channels, the contacts,
`SIGAP_WEB_URL`, and the schedule. It exits 1 while anything blocking is left,
so a deploy can run it as a gate.

---

## Run it locally

The agent service and the web interface on your own machine, instead of the
shared dev agent on EC2:

```bash
cd sigap/agent
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py user you@example.com "Your Name" admin 'a-long-password'
.venv/bin/python manage.py models --ping
.venv/bin/python api.py                      # http://127.0.0.1:8787

# a second terminal, at the repo root
echo 'SIGAP_API=http://127.0.0.1:8787' > .env.local
npm ci && npm run dev                        # http://localhost:3000
```

`SIGAP_WATCH=0` in `.env` keeps the watchers from raising events, and
spending model calls, while you work. Alerts still go out to whatever channel
is set up.

On a machine where 8787 or 3000 is taken, move both: `PORT=8797` with
`SIGAP_HOST=127.0.0.1` in `.env` (setting `PORT` alone opens the bind to the
network), `SIGAP_API=http://127.0.0.1:8797` in `.env.local`, and
`npm run dev -- -p 3107`. On a remote server, reach it with an SSH tunnel
rather than opening a port: `ssh -L 3107:127.0.0.1:3107 you@server`.

`POST /events` needs a session. Sign in on the web page, or take a token from
`POST /login` and send it as `Authorization: Bearer …`.

---

## Accounts, roles and passwords

Application users are rows in the database, not environment variables. There is
no sign-up page: accounts are created with the admin tool.

```bash
cd sigap/agent
PYTHONPATH=. python3 manage.py user <email> "<Full Name>" <role> "<password>"
```

Run it with no arguments and it prints that line back with the roles, rather
than a stack trace.

Passwords are stored as PBKDF2-SHA256 with 200,000 iterations and a per-user
salt. The plain password is never written anywhere, which also means it cannot
be recovered: create a new user if one is lost.

| Role | May approve up to | Meaning |
|---|---|---|
| `planner` | Rp 0 | Read only. Can look, cannot approve |
| `buyer` | Rp 500,000,000 | Day to day purchasing |
| `procurement_lead` | Rp 10,000,000,000 | Signs off on the large ones |
| `admin` | Rp 10,000,000,000 | Same ceiling, plus administration |

The ceiling is enforced on the server against the identity in the session
token, never against anything in the request body, so a client cannot raise its
own limit by asking.

For local work, make yourself a throwaway account and keep the password in
`sigap/agent/.secrets/`, which is gitignored:

```bash
mkdir -p .secrets && chmod 700 .secrets
PW=$(python3 -c "import secrets; print(secrets.token_urlsafe(18))")
PYTHONPATH=. python3 manage.py user you@example.com "You" procurement_lead "$PW"
printf 'you@example.com\n%s\n' "$PW" > .secrets/local-cred && chmod 600 .secrets/local-cred
```

---

## Sharing this with a teammate

Send them **this file and `.env.example`**. Both are in the repo already, so in
practice send them the repo and this paragraph.

What they generate themselves, every time:

- `SIGAP_SECRET`, with `manage.py secret`. Sharing one means anyone holding it
  can forge an admin session against any environment that uses it
- Their own `SAP_API_KEY` from their own api.sap.com account
- Their own AWS credentials through `aws configure`
- Their own local user account and password

What is safe to send in the clear, because none of it is secret:

- `AWS_REGION`, `SIGAP_MODEL`, `SAP_BASE_URL`, `SIGAP_ENV`, `SIGAP_DB`, the
  limits, and the EC2 address

If a shared credential genuinely has to move between people, send it through
something that is not a group chat and rotate it afterwards. Do not zip `.env`
files: a zip is a chat attachment that outlives the conversation.

---

## When it does not work

| What you see | What it means |
|---|---|
| `…'s model bedrock:… cannot be called: AWS_REGION is not set` | Expected until a model is configured. Set Bedrock up, or `SIGAP_MODEL_FALLBACK=aicore:gpt-5.4`. Everything else still runs |
| A `fallback` step in a handling's trail | The agent's own model failed once (the step says why), so the fallback answered for the rest of that handling |
| `no material '…' on record` from a tool | The model passed something that is not a material id. It gets the error back and corrects itself; repeated, it is a prompt to look at |
| `403` on the first Bedrock call | Model access not granted in that region, or the identity lacks `AmazonBedrockMantleInferenceAccess` |
| Figures labelled `modelled`, `sap_ready: false` on `/health` | `SAP_API_KEY` is empty or not being read |
| `AWS_REGION` looks set but still reported missing | The value is commented out, or carries a trailing note that is not a `#` comment |
| `ModuleNotFoundError: No module named 'core'` | Missing `PYTHONPATH=.`, or you are not in `sigap/agent` |
| `a session token is required` | The endpoint needs a login, `POST /events` included. `POST /login` and send the token as `Authorization: Bearer …` |
| `OSError: [Errno 48] Address already in use` | An older service still holds 8787. Find it with `lsof -nP -iTCP:8787 -sTCP:LISTEN` |
| The queue fills with earthquakes you did not raise | The watchers are working. `SIGAP_WATCH=0` turns them off |

`PYTHONPATH=. python3 manage.py check` prints the state of all of it, including
which keys are missing, and is the fastest way to answer "is my setup right".
