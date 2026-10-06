# Setup

> Getting SIGAP from a clone to a system that reasons against a real model and
> reads real SAP data. Written 29 September 2026.
>
> Every step ends with a test. If the test does not pass, do not move on: each
> step is what makes the next one diagnosable.

`AWS-PLAN.md` has the four-week order of work and the reasoning.
`BUILD-SPEC.md` has the service list. This is the keyboard.

---

## 0. Run it locally first, on nothing

Neither key is needed for this. The system runs on fixtures and says so.

```bash
cd sigap/agent
cp .env.example .env
python3 manage.py secret              # paste the output into SIGAP_SECRET in .env
python3 manage.py user you@example.com "Your Name" procurement_lead <a password>
python3 manage.py seed                # demo events, runs and actions
python3 api.py                        # :8787
```

In a second terminal:

```bash
npm install
SIGAP_API=http://127.0.0.1:8787 npm run dev
```

**Test.** `http://localhost:3000/dashboard` loads, you can sign in, and every
figure on screen carries an origin label reading `modelled`. That label is the
product working, not a placeholder.

> Open the app at **localhost**, not `127.0.0.1`. Next 16 treats them as
> different origins; `next.config.ts` allows both, but localhost is the one the
> dev server boots on.

---

## 1. SAP, the sandbox key

Fifteen minutes, free, self-service. **This does not wait for anyone at SAP.**

**SAP ID is not the hackathon IAS account.** Two different identity systems.
The organiser's account lives on `auisywroy.accounts.ondemand.com` and is only
for the hackathon tenant; api.sap.com wants an SAP ID, the universal SAP
account. Signing in there with the hackathon credentials fails with *we
couldn't authenticate you*, which reads like a wrong password. Register an SAP
ID, or use an older one if you already have a SAP Community or SAP Learning
login.

1. Register an SAP ID account at <https://api.sap.com>
2. Open any API page, for example
   [Material Stock](https://api.sap.com/api/API_MATERIAL_STOCK_SRV/overview)
3. Click **Show API Key**, then copy it
4. Put it in `sigap/agent/.env` as `SAP_API_KEY`
5. Restart `api.py`

**Test.**

```bash
cd sigap/agent && PYTHONPATH=. python3 manage.py check
```

`SAP_API_KEY` should no longer appear under "keys not set". On the dashboard,
figures that came from SAP now read `live` or `cached` instead of `modelled`.

What this unlocks: the ten read services in `BUILD-SPEC.md` §4. The sandbox is a
real S/4HANA Cloud system with sample data, so the shapes, the pagination and the
error messages are the ones a customer system produces.

### 1b. Verify the three write entity names

The write path is complete but its entity names have never been checked. This is
the one item in `BUILD-SPEC.md` §8 that the sandbox key alone can close.

```bash
cd sigap/agent && PYTHONPATH=. python3 - <<'PY'
from clients import sap_s4
from sender import TARGETS
for kind, (service, entity) in TARGETS.items():
    try:
        sap_s4.get(service, entity, {"$top": "1"})
        print(f"  ok       {kind:22} {service}/{entity}")
    except Exception as e:
        print(f"  CHECK    {kind:22} {service}/{entity}  {type(e).__name__}: {e}")
PY
```

**Test.** Three `ok` lines. Anything else means the entity name is wrong; find
the right one on that service's page at api.sap.com and correct `sender.py`.

> Nothing here writes. It reads one row to prove the entity exists. Do not run
> `sender.send_approved` until all three come back `ok`.

---

## 2. AWS, Bedrock

This is the real blocker. Until it is done, `graph.py` has never spoken to a
model and nothing about the system's judgement has been tested.

### 2a. Model access

1. Open the **Bedrock** console and pick a region. Not every region carries
   Claude, so check the model list before committing. `us-west-2` is the
   fallback.
2. **Model access** in the left nav, request access to the Claude models, wait
   for the status to read *Access granted*.

### 2b. Credentials on the machine

The SDK uses the standard AWS credential chain, so any of these works:

```bash
aws configure                  # or
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
```

**Test.**

```bash
aws bedrock list-foundation-models --region <your region> \
  --query "modelSummaries[?contains(modelId, 'claude')].modelId" --output text
```

An empty result means the region does not carry Claude, or access is not
granted yet. Fix that before continuing; every later failure will otherwise look
like a code problem.

### 2c. Install the SDK

The agent service runs on the standard library alone until this point.

```bash
cd sigap/agent && python3 -m pip install -r requirements.txt
```

### 2d. Set the region

Put the region in `sigap/agent/.env` as `AWS_REGION`, then restart `api.py`.

**Test.**

```bash
cd sigap/agent && PYTHONPATH=. python3 manage.py check
```

Nothing should remain under "keys not set". `/health` now reports
`"model_ready": true`.

---

## 3. The first real run

Everything before this proved plumbing. This is the first time judgement is
involved.

```bash
curl -X POST http://127.0.0.1:8787/events \
  -H 'content-type: application/json' \
  -d '{"kind":"port_closure",
       "title":"Ningbo-Zhoushan closed 8-13 September",
       "trigger":"typhoon",
       "source":"manual",
       "payload":{"port":"Ningbo","days":6}}'
```

**Test.** Open `/log`. It should show real agent steps with agent names and tool
names, instead of the empty state it shows today. The run reaches
`status: done` with a recommendation.

**Expect this to break.** `AWS-PLAN.md` budgets two days for it, not one. The
guards that stop a break becoming an expensive break are already in place:
`MAX_SPECIALIST_ROUNDS = 8`, `MAX_LEAD_ROUNDS = 14`,
`MAX_SECONDS_PER_EVENT = 600`, and `CFG.cost_cap_per_event_idr`, which raises
`BudgetExhausted` rather than running on.

> The token cost rates in `graph.py` are placeholders from a reference sheet,
> not from Bedrock's price list. Replace them once the region is chosen. The
> dashboard shows that figure to a user, and a product whose whole claim is that
> it does not invent numbers should not invent that one.

---

## 4. Ask an agent directly

With the model running, the conversation pages work. Conversations are kept per
user and survive a refresh.

- `/chat` asks Arya, who routes to whichever specialist the question needs
- `/agents/<code>` has an **Ask** drawer for one specialist, with the same tools

**Test.** Ask Dara *"What is daily consumption of M-4471 at KRW1?"*. The answer
should say the plant runs near 10.33 TON a day against a planned 9.2, and the
reply should carry the tool names it used underneath.

---

## 5. SAP BTP, the hackathon tenant

A separate thing from §1. That key reads **business data** from the S/4HANA
sandbox. This tenant has **no ERP in it**: what it carries is AI Core, Joule,
and a Cloud Foundry space. The two do not substitute for each other.

Team slug is **`stoiksm-team`**, confirmed against the keybroker. Everything
below takes it as given.

| | |
|---|---|
| IAS logon | `https://auisywroy.accounts.ondemand.com` |
| Cockpit | `https://apac.cockpit.btp.cloud.sap/cockpit/?idp=auisywroy.accounts.ondemand.com/` |
| CF API | `https://api.cf.ap10.hana.ondemand.com` |
| CF org | `SEAIO_aws-sap-hackathon-si4ykj9d` |
| CF space | `hackathon-stoiksm-team` |
| CF origin key | `auisywroy-platform` |
| Joule auth | `https://auisywroy.authentication.ap10.hana.ondemand.com` |
| Joule API | `https://aws-sap-hackathon-si4ykj9d.ap10.sapdas.cloud.sap` |

### Activate the IAS account first

Nothing else in this section works until this is done, and nothing says so:
`cf login --sso` and `joule login` both fail in ways that point elsewhere.

1. Open `https://auisywroy.accounts.ondemand.com`
2. Username is the registered email, **lowercase**
3. Password is the organiser's temporary one
4. Set a new password when prompted
5. You are activated once you land on the profile page

That new password is the one used for the cockpit, `cf login --sso` and
`joule login`. Only one of the addresses a team registered will be the one
IAS knows.

### Credentials

Three endpoints on
`https://hackathon-keybroker.cfapps.ap10.hana.ondemand.com`:

| Path | Returns | Secret |
|---|---|---|
| `/ai-core/stoiksm-team-key` | clientid, clientsecret, url, AI_API_URL | **yes** |
| `/joule/stoiksm-team-key` | `uaa.clientid`, `uaa.clientsecret` | **yes** |
| `/group/stoiksm-team` | the IAS group UUID for `visibility_condition` | no |

Pull them straight to disk rather than to a screen. `agent/.secrets/` is
gitignored and exists for this. Neither command prints anything:

```bash
BROKER=https://hackathon-keybroker.cfapps.ap10.hana.ondemand.com
mkdir -p sigap/agent/.secrets && chmod 700 sigap/agent/.secrets
curl -s "$BROKER/joule/stoiksm-team-key"   -o sigap/agent/.secrets/joule.json
curl -s "$BROKER/ai-core/stoiksm-team-key" -o sigap/agent/.secrets/ai-core.json
chmod 600 sigap/agent/.secrets/*.json
```

Then log in without the secret ever reaching the terminal or shell history.
**The `--authurl` here is not the one the manual gives**, for the reason below:

```bash
cd sigap/agent
J=.secrets/joule.json
joule login --no-app-tid \
  --authurl "$(python3 -c "import json;print(json.load(open('$J'))['uaa']['url'])")" \
  --apiurl  'https://aws-sap-hackathon-si4ykj9d.ap10.sapdas.cloud.sap' \
  -c "$(python3 -c "import json;print(json.load(open('$J'))['uaa']['clientid'])")" \
  -s "$(python3 -c "import json;print(json.load(open('$J'))['uaa']['clientsecret'])")"
joule status        # expect: Logged in
```

Three things that cost time here.

**The manual's `--authurl` is wrong and fails with a message that never says
so.** It gives `https://auisywroy.authentication.ap10.hana.ondemand.com`.
`auisywroy` is the IAS tenant subdomain; the XSUAA subdomain is
`aws-sap-hackathon-si4ykj9d`. The CLI detects `authType: XSUAA`, asks the
authurl for `/.well-known/openid-configuration`, gets a 404, and reports
`loading authentication properties failed (code: AUTH_LOAD_FAILED)`, which
mentions neither the URL nor the 404. Use `uaa.url` from the key file, as the
command above does. Checked directly: the key file's URL answers 200 on that
path and the manual's answers 404.

`joule -d login ...` is what finds this. It writes a `debug-login-*.json` next
to you with the real inner error. That pattern is gitignored, because the dump
holds the request detail.

`--apiurl` is the DAS URL above, and it is the one the manual gives. The key
file also has a `uaa.apiurl`, which is a different thing again:
`https://api.authentication.ap10.hana.ondemand.com`. Passing that one fails
too. So: `authurl` from the key file, `apiurl` from the manual.

**Run this at your own keyboard.** Once the URL is right, the CLI prompts
`? Username:` and then for a password: your IAS email in lowercase, and the
password you set at activation. The client credentials alone are not enough,
and a non-interactive shell dies at that prompt.

The CLI declares `node >=22 <25` and warns `EBADENGINE` on v26. It ran anyway
here, so that warning was not the cause of anything above.

Do not use `--sso`. The manual says it causes a `redirect_uri` mismatch on this
tenant.

Nothing in SIGAP reads AI Core or Joule credentials today, so there is no
`.env` entry for them and none should be added until something needs one.

### Deploy the agent service

`agent/manifest.yml` carries the commands, and the warning about SQLite on a
filesystem Cloud Foundry resets. Read that warning before trusting anything the
deployed app writes.

```bash
cf login -a https://api.cf.ap10.hana.ondemand.com --sso   # origin key: auisywroy-platform
cf target -o "SEAIO_aws-sap-hackathon-si4ykj9d" -s "hackathon-stoiksm-team"
cd sigap/agent && cf push
cf set-env sigap-agent SIGAP_SECRET "$(python3 manage.py secret)"
cf restart sigap-agent
cf app sigap-agent        # the route is the endpoint a Joule capability calls
```

**Test.** `curl https://<route>/health` returns the same JSON as the local
service, with `sap_ready` and `model_ready` reflecting whatever is set in the
CF environment rather than your laptop's `.env`.

---

## What is still not set up after all this

Honest list, so nothing is discovered during a demo.

| | Why |
|---|---|
| `references/tkdn-rules.md`, `references/lartas-procedure.md` | Absent. Kira judges from parameters and labels the result `MODELLED`. Domain work, not code, and it waits on nobody |
| Scenario eval suite | Absent. `RESEARCH-AWS-SAP.md` §6 has the four-level shape to build it against |
| Foreign typhoon signal | BMKG covers Indonesia only, so the Ningbo trigger has no live source. `DATA-SOURCES.md` §5 |
| AgentCore deployment | Local only so far. `AWS-PLAN.md` week 2, and deliberately not before §3 above passes |
| Joule capability | The SAP half of the demo. Needs the agent service on a public endpoint first: `sigap/agent/manifest.yml` has the `cf push` commands for the hackathon space, and the warning about SQLite on that platform |

---

## If something is wrong

| Symptom | Cause |
|---|---|
| Every figure still reads `modelled` after setting the key | `api.py` was not restarted. `.env` is read once, at import |
| SAP returns 401 with a key that looks right | The value picked up a trailing comment. `core/config.py` strips these now; run `PYTHONPATH=. python3 core/config.py` to confirm |
| Buttons do nothing, the theme toggle is dead | The app was opened at an origin the dev server does not allow, so the client bundle never hydrated. Use `localhost` |
| `ModelNotReady` | `AWS_REGION` is empty or the region does not carry Claude |
| `400` from Bedrock on the first call | Usually `thinking` or `effort` in the wrong place. `TECHNICAL.md` has the four common mistakes |
| `PromptMissing` | An agent has no file in `prompts/`. By design: a missing prompt raises rather than sending the model a placeholder |
