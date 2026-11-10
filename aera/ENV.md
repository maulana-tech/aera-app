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
message.** Values live in `aera/agent/.env`, which is gitignored, or in
`aera/agent/.secrets/`, which is gitignored and mode 700. Every value printed
below is a placeholder.

The hackathon manual puts it the same way: *"Keep these credentials private. Do
not commit them to git or paste them into shared chats."*

If a secret does reach a chat, a screenshot or a commit, treat it as burned and
rotate it. Rotating takes a minute; not rotating is a judge or a stranger
holding your model credit and your session-signing key.

---

## Fast path

Four lines get a working system on fixtures, with no account anywhere:

```bash
cd aera/agent
cp .env.example .env
PYTHONPATH=. python3 manage.py secret        # prints: export AERA_SECRET="…"
PYTHONPATH=. python3 manage.py check
```

`manage.py secret` prints a whole `export AERA_SECRET="…"` line so it can be
sourced; in `.env` you want only the part inside the quotes.

That runs. Figures come from `fixtures/` and are labelled `MODELLED`, which the
interface shows and the calculator refuses to price. Uploading your own data
(see **Company data** below) turns the labels to `CACHED`, and a model (see
**Models** below) is what lets the agents reason.

---

## Every variable

Read by `core/config.py` unless the table says otherwise. A value with a `#`
after it has the comment stripped automatically, so
`AWS_REGION=ap-southeast-2   # Sydney` stores `ap-southeast-2`. **A trailing note without
a `#` is kept as part of the value**, which is a quiet way to end up with a
region named `us-west-2    see below`.

### Required

| Variable | Example | What it does |
|---|---|---|
| `AERA_SECRET` | `a1b2…` (64 hex) | Signs session tokens. Identity comes only from this signature, so whoever holds it can mint an admin session. Generate per machine, never share, never commit |

### Connects the system to the outside

| Variable | Default | What it does |
|---|---|---|
| `AWS_REGION` | empty | Bedrock region, for example `ap-southeast-2`. Empty means no Bedrock model can be called |
| `AERA_MODEL` | `anthropic.claude-opus-5` | The deciders' model (Arya and Kira), and everyone's unless the next rows say otherwise. Format `provider:model`, see **Models** |
| `AERA_MODEL_SPECIALISTS` | empty | The other ten specialists. Empty means they run on `AERA_MODEL` |
| `AERA_MODEL_<CODE>` | empty | One agent on its own model, for example `AERA_MODEL_LOGISTICS=bedrock-openai:openai.gpt-oss-120b` |
| `AERA_MODEL_FALLBACK` | empty | Tried once when an agent's model fails, then kept for the rest of that handling. Used by the aux model too |
| `AERA_AUX_MODEL` | `anthropic.claude-haiku-5-5` | Narration, summaries and titles. Never on a figure or a decision (`core/aux.py`) |
| `AWS_BEARER_TOKEN_BEDROCK` | empty | A Bedrock API key, instead of IAM credentials. An environment variable, read by the AWS SDK and by `core/llm.py`; not a `.env` line |
| `AWS_FALLBACK_ACCESS_KEY_ID` · `AWS_FALLBACK_SECRET_ACCESS_KEY` · `AWS_FALLBACK_REGION` | required with Bedrock | Second AWS account used when the primary Bedrock account is rate-limited. The session token is required only for temporary STS credentials. Store all values in the deployment secret manager; never commit them |
| `AERA_REASONING_WORKERS` | `1` | Maximum concurrent event reasonings. This bounds request bursts before they reach Bedrock |

AWS credentials themselves are **not** `.env` lines. They come from the
standard AWS chain, so run `aws configure` and leave them out of `.env`. See
**Models** below.

### Behaviour

| Variable | Default | What it does |
|---|---|---|
| `AERA_ENV` | `dev` | `prod` makes the service refuse to accept events unless the model is reachable |
| `AERA_DB` | `data/sigap.db` | SQLite file. Use an absolute path on a server. This file is the approval record, so it is the thing to back up |
| `AERA_WATCH` | `1` | `0` stops the four watchers (BMKG, hazards, weather, Vega), so nothing raises an event on its own. Alerts, the action sender and the digest keep running. Set it when you do not want the queue filling with live events, for example in the hour before a demo. See **Schedule** |
| `AERA_SCHEDULE` | `1` | `0` stops everything that runs on its own, including alert delivery. A job can still be run by hand from the Schedule page |
| `AERA_WEB_URL` | `http://localhost:3000` | Where people open AERA. Every alert links to the handling there, so on a server this is the public address |
| `AERA_IDR_PER_USD` | `16400` | The rate model spend is priced at. The default is the rate the first prices were set at; `manage.py ready` compares it with the ECB reference rate and says when it is more than 5% off |
| `AERA_AUTONOMOUS_LIMIT_IDR` | `50000000` | Ceiling for acting without a person. Value is only half the test: every figure under the decision must also be trusted. `tools/execution.py` enforces it, and the tool descriptions and the prompts of Bram and Vega quote it from here |
| `AERA_RULE_PACK` | `../references/rule-pack.json` | Kira's rule pack: contract terms, licensing time, collective leave, supplier certificates, each with its source. Installed per deployment, never committed. Format in `references/README.md`. Absent, every ruling is labelled modelled |
| `AERA_COST_CAP_IDR` | `500000` | Model spend per event before the handling stops |

### Where it listens

| Variable | Default | What it does |
|---|---|---|
| `PORT` | `8787` | Set by the platform on Cloud Foundry. Setting it also flips the bind address to `0.0.0.0` |
| `AERA_HOST` | `127.0.0.1`, or `0.0.0.0` when `PORT` is set | Override the bind address directly. Loopback by default on purpose: the service opens to a network only when something asks it to |

### Front end

Read by Next.js, so they belong in a `.env.local` at the repo root, not in
`aera/agent/.env`.

| Variable | Default | What it does |
|---|---|---|
| `AERA_API` | `http://127.0.0.1:8787` | Where the web app proxies to. The repo's `.env.example` points it at the shared dev agent on EC2; for a local agent, set it to the local address (**Run it locally** below) |

### Set by the tooling, not by you

| Variable | Set by | Why it exists |
|---|---|---|
| `AERA_STORE_CHECK`, `AERA_GRAPH_CHECK`, `AERA_EXPOSURE_CHECK`, `AERA_PRECEDENT_CHECK`, `AERA_WATCH_CHECK`, `AERA_SCHEDULE_CHECK`, `AERA_JOBS_CHECK`, `AERA_NOTIFY_CHECK` | the self-checks | Each check re-executes itself with `AERA_DB` pointed at a scratch file, so a check reads the fixtures rather than your uploads or write a specimen event into the real record. The flag marks the second run |
| `BEDROCK_READY` | you, only in `main.py`'s scripted demo | Not read by the service |
| `PYTHONPATH` | you | Must be `.` from `aera/agent`, or imports of `core` fail |

---

## Company data

Company data comes from CSV uploads (the **Upload data** page, or `POST /uploads`),
one file per entity, with downloadable templates. The latest upload of an entity
is what the tools read, labelled `cached` (or `modelled` when the uploader
declared it generated sample data). An entity nobody uploaded falls back to the
shipped `fixtures/`, labelled `modelled`, which the calculator refuses to price.

Some reads have no source beyond an upload: approved substitutes come only from
a `MaterialSubstitute` upload, partner email addresses only from a
`PartnerContact` upload. Quality holds, the MRP safety-stock policy and a demand
plan are not connected at all, so those tools say so (`missing`) rather than
guess. `DATA-SOURCES.md` has the detail.

---

## Models

Each agent's model is named `provider:model`, resolved per call by
`core/llm.py`:

| Provider | Speaks | Where | Example |
|---|---|---|---|
| `bedrock` | Anthropic Messages | Claude on Bedrock: Mantle (`bedrock-mantle.{region}.api.aws/anthropic`) for bare ids, InvokeModel for inference profiles | `global.anthropic.claude-opus-4-6-v1` |
| `bedrock-openai` | OpenAI Chat Completions | Other Bedrock models: Mantle (`bedrock-mantle.{region}.api.aws/v1`) for bare ids, `bedrock-runtime.{region}.amazonaws.com/openai/v1` for inference profiles | `deepseek.v3.2`, `global.moonshotai.kimi-k3` |

A bare `anthropic.*` id means `bedrock`, so values written before this table
keep working. An id with a profile prefix (`global.`, `us.`, `apac.`, `au.`…)
or a `-v1:0` version goes to bedrock-runtime; everything else to Mantle.

The default, checked from `ap-southeast-2` on 2026-10-24: one small, cheap
model for every agent, a smaller one for summaries, and a fallback behind both.

```bash
AWS_REGION=ap-southeast-2                                       # Sydney
AERA_MODEL=bedrock-openai:minimax.minimax-m2.5                 # all twelve agents
AERA_MODEL_FALLBACK=bedrock-openai:openai.gpt-oss-120b         # when it fails
AERA_AUX_MODEL=bedrock-openai:zai.glm-4.7-flash                # report summaries
```

What the same Ningbo closure cost to handle, on fixture data (nothing
uploaded), one run each, priced at Rp 16,400 to the dollar (about a tenth
more at the October 2026 rate; `AERA_IDR_PER_USD`):

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
`AERA_MODEL=global.anthropic.claude-opus-4-6-v1` with
`AERA_MODEL_SPECIALISTS=bedrock-openai:minimax.minimax-m2.5`, about 3.5× the
cost.

The Claude 5 family (`anthropic.claude-opus-5`, `anthropic.claude-haiku-5-5`)
is served by Mantle, and Mantle in `ap-southeast-2` does not carry it. Where an
account has it, set the bare ids and nothing else changes.

`python3 manage.py models` shows what each agent will run on, what set it, and
whether it can be reached. `python3 manage.py models --ping` makes one small real
call to each model in use, which is the only proof that access was granted;
`--catalog` does the same for every model the Models page offers.

### Choosing from the app

**Settings → Models** (`/models`) picks the model per role (lead and veto,
specialists, fallback, summaries) and per agent, from a list of models that
have each run a full tool loop through `core/llm.py`: Claude Opus 4.6, Sonnet
4.6 and Haiku 4.5; gpt-oss-120b,
DeepSeek V3.2 and V3.1, Kimi K3, K2.5 and K2 Thinking, Qwen3 235B, GLM-5 and
GLM-4.7, Mistral Large 3, MiniMax M2.5. Each shows its route and its rate.
**Test** makes one real call.

- Only `admin` and `procurement_lead` can save or test. Everyone signed in can
  see what the team runs on.
- A choice is stored in the `settings` table and loaded when the service
  starts. It wins over the environment variable at the same level; a narrower
  level still wins over a broader one, so `AERA_MODEL_LOGISTICS` beats a
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

---

## Alerts

When a handling finishes, is held, or fails, AERA tells people (`notify.py`).
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
`aera/agent/.secrets/notify.env`, mode 600, which the service reads the way
it reads `.env`:

| Channel | Variables | Notes |
|---|---|---|
| Email over SMTP | `AERA_SMTP_HOST`, `AERA_MAIL_FROM`; and `AERA_SMTP_PORT` (587), `AERA_SMTP_USER`, `AERA_SMTP_PASSWORD`, `AERA_SMTP_SECURITY` (`starttls`, `ssl` or `none`) | Any SMTP server. AWS SES: `email-smtp.ap-southeast-2.amazonaws.com`, SMTP credentials from the SES console, a verified sender. Gmail or Workspace: `smtp.gmail.com`, an app password, not the account password |
| Email through Composio | `COMPOSIO_API_KEY`; and `AERA_COMPOSIO_USER_ID` (`aera`), `AERA_COMPOSIO_ACCOUNT`, `AERA_COMPOSIO_AUTH_CONFIG` | Mail leaves from a real Gmail mailbox, so a reply comes back to a person. After the key is in, an admin or lead presses **Connect Gmail** on the Contacts page and signs in to that mailbox. See below |
| Slack | `AERA_SLACK_WEBHOOK_URL` | An incoming webhook for the team's channel (Slack app → Incoming Webhooks) |
| Telegram | `AERA_TELEGRAM_BOT_TOKEN`, `AERA_TELEGRAM_CHAT_ID` | A bot from @BotFather; the chat id of a person who has messaged it, or a group it is in |
| Webhook | `AERA_WEBHOOK_URL` | The message as JSON (`subject`, `text`, `kind`, `run_id`, `url`), for whatever routes it on: Microsoft Teams through Power Automate, n8n, a ticket queue |

```bash
cd aera/agent
install -m 600 /dev/null .secrets/notify.env
$EDITOR .secrets/notify.env          # the lines for one channel
# restart api.py, then on the Contacts page: Send a test alert
.venv/bin/python notify.py --test    # or from the shell
```

With both SMTP and Composio configured, SMTP is used; `AERA_EMAIL_VIA=smtp` or
`composio` chooses.

**Files.** Email carries files; a team channel carries the link. A handling's
alert carries its report as a PDF (`AERA_ALERT_ATTACH`: `pdf`, the default,
`xlsx`, `pdf,xlsx` or `none`). From a report page, **Send by email** sends that
report, or the operations report, to contacts on the Contacts page as a PDF, a
workbook or both, with a note. Only to contacts, or to the sender: a report
carries what was decided and what it is worth. Files are rendered when the
message goes, from the record as it then stands.

**Composio.** `clients/composio.py` calls Composio's REST API (v3.1) with the
project key, and Composio holds the mailbox's OAuth grant: AERA never sees the
Gmail password or token. One Composio project can hold other applications and
other users' mailboxes, so AERA only ever sends from a connection that belongs
to its own Composio user id (`AERA_COMPOSIO_USER_ID`, default `aera`), and
refuses a pinned `AERA_COMPOSIO_ACCOUNT` that belongs to anybody else. Whoever
signs in through the Connect Gmail link becomes the mailbox AERA sends from,
so open it yourself and do not pass it on. A message, its attachments and the
recipient's address pass through Composio on the way out; their Zero Data
Retention option keeps payloads off their storage. Prefer a Composio project of
AERA's own: the key reaches every mailbox connected in the project.

### Messages to suppliers and customers

Bram drafts a supplier request (`request_supplier_update`) or a customer notice
(`draft_customer_notice`) as the email itself: subject, body, and the address
the record holds for the partner, read from an uploaded `PartnerContact`
list. The decision queue shows all of it. A
buyer approves a supplier request; a procurement lead a customer notice. Only
then does `outreach.py` queue it in the same outbox, and once the mailbox has
taken it, the action is marked sent with the message id. A send that fails is
tried three times and the action stays approved, with **Send again**.

| Variable | Default | Meaning |
|---|---|---|
| `AERA_EXTERNAL_REDIRECT` | unset | Outside production (`AERA_ENV` not `prod`), the one address every supplier or customer message goes to instead, marked `[TEST]` and naming the address it was meant for. Unset, outside production nothing is sent |
| `AERA_EXTERNAL_DOMAINS` | unset | In production, when set, the only domains a supplier or customer message may go to, comma-separated |

## Schedule

What AERA does on its own, in one list (`jobs.py`), run by one loop
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
| `send` | 10 min | Issue approved actions as documents (`sender.py`): a stable number derived from the idempotency key, marked `sent` |
| `digest` | 07:30 WIB | The morning summary: last 24 hours, and everything still waiting for approval |

The first four raise events, and every event starts a handling that spends
model credit: `AERA_WATCH=0` turns those four off and leaves the rest.
`AERA_SCHEDULE=0` turns everything off. A job never overlaps itself, a job
that fails keeps its error for the page and runs again next time, and a digest
missed by more than two hours (the server was down at 07:30) is skipped, not
sent late.

## Ready

`manage.py check` asks whether the code works. `manage.py ready` asks whether
the install around it does, and names the fix for each gap:

```bash
.venv/bin/python manage.py ready          # add --ping to make one call to each model
```

It looks at uploaded data, `AERA_ENV`, the lead's model, the exchange
rate, users and their roles, `AERA_SECRET`, the alert channels, the contacts,
`AERA_WEB_URL`, and the schedule. It exits 1 while anything blocking is left,
so a deploy can run it as a gate.

---

## Run it locally

The agent service and the web interface on your own machine, instead of the
shared dev agent on EC2:

```bash
cd aera/agent
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py user you@example.com "Your Name" admin 'a-long-password'
.venv/bin/python manage.py models --ping
.venv/bin/python api.py                      # http://127.0.0.1:8787

# a second terminal, at the repo root
echo 'AERA_API=http://127.0.0.1:8787' > .env.local
npm ci && npm run dev                        # http://localhost:3000
```

`AERA_WATCH=0` in `.env` keeps the watchers from raising events, and
spending model calls, while you work. Alerts still go out to whatever channel
is set up.

On a machine where 8787 or 3000 is taken, move both: `PORT=8797` with
`AERA_HOST=127.0.0.1` in `.env` (setting `PORT` alone opens the bind to the
network), `AERA_API=http://127.0.0.1:8797` in `.env.local`, and
`npm run dev -- -p 3107`. On a remote server, reach it with an SSH tunnel
rather than opening a port: `ssh -L 3107:127.0.0.1:3107 you@server`.

`POST /events` needs a session. Sign in on the web page, or take a token from
`POST /login` and send it as `Authorization: Bearer …`.

---

## Accounts, roles and passwords

Application users are rows in the database, not environment variables. There is
no sign-up page: accounts are created with the admin tool.

```bash
cd aera/agent
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
`aera/agent/.secrets/`, which is gitignored:

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

- `AERA_SECRET`, with `manage.py secret`. Sharing one means anyone holding it
  can forge an admin session against any environment that uses it
- Their own AWS credentials through `aws configure`
- Their own local user account and password

What is safe to send in the clear, because none of it is secret:

- `AWS_REGION`, `AERA_MODEL`, `AERA_ENV`, `AERA_DB`, the
  limits, and the EC2 address

If a shared credential genuinely has to move between people, send it through
something that is not a group chat and rotate it afterwards. Do not zip `.env`
files: a zip is a chat attachment that outlives the conversation.

---

## When it does not work

| What you see | What it means |
|---|---|
| `…'s model bedrock:… cannot be called: AWS_REGION is not set` | Expected until a model is configured. Set Bedrock up. Everything else still runs |
| A `fallback` step in a handling's trail | The agent's own model failed once (the step says why), so the fallback answered for the rest of that handling |
| `no material '…' on record` from a tool | The model passed something that is not a material id. It gets the error back and corrects itself; repeated, it is a prompt to look at |
| `403` on the first Bedrock call | Model access not granted in that region, or the identity lacks `AmazonBedrockMantleInferenceAccess` |
| Figures labelled `modelled` | Nothing was uploaded for that entity, so it reads the fixture. Upload it on the Upload data page |
| `AWS_REGION` looks set but still reported missing | The value is commented out, or carries a trailing note that is not a `#` comment |
| `ModuleNotFoundError: No module named 'core'` | Missing `PYTHONPATH=.`, or you are not in `aera/agent` |
| `a session token is required` | The endpoint needs a login, `POST /events` included. `POST /login` and send the token as `Authorization: Bearer …` |
| `OSError: [Errno 48] Address already in use` | An older service still holds 8787. Find it with `lsof -nP -iTCP:8787 -sTCP:LISTEN` |
| The queue fills with earthquakes you did not raise | The watchers are working. `AERA_WATCH=0` turns them off |

`PYTHONPATH=. python3 manage.py check` prints the state of all of it, including
which keys are missing, and is the fastest way to answer "is my setup right".
