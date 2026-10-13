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
`AWS_REGION` is what turns the labels to `LIVE` and lets the agents reason.

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
| `AWS_REGION` | empty | Bedrock region, for example `ap-southeast-2`. Empty means the agents refuse to reason rather than guessing |
| `SIGAP_MODEL` | `anthropic.claude-opus-5` | Bedrock model id. `.env.example` suggests a Haiku cross-region id for cheap development |

AWS credentials themselves are **not** environment variables here. They come
from the standard AWS chain, so run `aws configure` and leave them out of
`.env`. See **AWS** below.

### Behaviour

| Variable | Default | What it does |
|---|---|---|
| `SIGAP_ENV` | `dev` | `prod` makes the service refuse to accept events unless both SAP and the model are connected |
| `SIGAP_DB` | `data/sigap.db` | SQLite file. Use an absolute path on a server. This file is the approval record, so it is the thing to back up |
| `SIGAP_WATCH` | `1` | `0` stops the BMKG and Vega watchers. Set it when you do not want the queue filling with live quakes, for example in the hour before a demo |
| `SIGAP_AUTONOMOUS_LIMIT_IDR` | `50000000` | Ceiling for acting without a person. Value is only half the test: every figure under the decision must also be trusted |
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
| `SIGAP_API` | `http://127.0.0.1:8787` | Where the web app proxies to. Point it at the EC2 address to run the interface against a deployed agent service |

### Set by the tooling, not by you

| Variable | Set by | Why it exists |
|---|---|---|
| `SIGAP_STORE_CHECK`, `SIGAP_GRAPH_CHECK`, `SIGAP_EXPOSURE_CHECK`, `SIGAP_PRECEDENT_CHECK`, `SIGAP_WATCH_CHECK` | the self-checks | Each check re-executes itself with `SAP_API_KEY` blank and `SIGAP_DB` pointed at a scratch file, so a check cannot depend on your keys or write a specimen event into the real record. The flag marks the second run |
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

---

## AWS

Bedrock needs two things and neither is a line in `.env`.

1. **Model access.** In the Bedrock console, Model access, request the Claude
   model, wait for *Access granted*. A region without granted access fails in a
   way that reads like a code bug.
2. **Credentials**, through the normal chain:

```bash
aws configure          # key id, secret, region
```

Then set `AWS_REGION` in `.env` to the region you granted access in.

Verify:

```bash
aws bedrock list-foundation-models --region "$AWS_REGION" \
  --query "modelSummaries[?contains(modelId,'claude')].modelId" --output text
```

An empty list means the region carries no Claude or access is not granted yet.
Fix that before touching the code.

**Never put AWS keys in `.env`.** `aws configure` writes them to `~/.aws`, which
is outside the repo and outside anything you might accidentally commit.

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
| `AWS_REGION is not set. The agent cannot reason.` | Expected until Bedrock is configured. Everything else still runs |
| Figures labelled `modelled`, `sap_ready: false` on `/health` | `SAP_API_KEY` is empty or not being read |
| `AWS_REGION` looks set but still reported missing | The value is commented out, or carries a trailing note that is not a `#` comment |
| `ModuleNotFoundError: No module named 'core'` | Missing `PYTHONPATH=.`, or you are not in `sigap/agent` |
| `a session token is required` | The endpoint needs a login. `POST /login` and send the token as `Authorization: Bearer …` |
| `OSError: [Errno 48] Address already in use` | An older service still holds 8787. Find it with `lsof -nP -iTCP:8787 -sTCP:LISTEN` |
| The queue fills with earthquakes you did not raise | The watchers are working. `SIGAP_WATCH=0` turns them off |

`PYTHONPATH=. python3 manage.py check` prints the state of all of it, including
which keys are missing, and is the fastest way to answer "is my setup right".
