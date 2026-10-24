# SIGAP in Joule: the A2A shim and the capability

Joule is the front door inside SAP: a person asks, SIGAP answers. This folder
holds both halves of that door:

- an **A2A server** (`server.py`) that Joule calls through a BTP destination, and
  which calls SIGAP's API as a service user;
- the **Joule capability** (`joule/`): scenarios Joule matches the user's words
  against, and functions that call the A2A server.

```
Joule ─ agent-request ─▶ BTP destination (NoAuthentication)
      ─▶ this shim (Cloud Foundry) ─▶ SIGAP API (EC2), as a `planner` user
```

The plan behind it is `../JOULE-BEDROCK-PLAN.md` §2 and §3.

## What it does, and what it cannot do

| Skill | The user says | The shim calls | Answer |
|---|---|---|---|
| `investigate_disruption` | "Investigate: Ningbo port closed for 6 days" | `GET /runs` (duplicate check), then `POST /events` | The run id and a link to it, **at once** |
| `disruption_status` | "How is the Ningbo investigation going?", "status of run_…" | `GET /runs` (to pick the run) and `GET /runs/{id}` | Status, agents, recommendation, what is not yet trusted, what waits for approval |
| `risk_scan` | "What is about to break this week?" | `GET /exposure` | Vega's exposure scan and the RPT-1.6 slip ranking, with their origin labels |

**It cannot approve.** Joule carries no user identity: the destination is
`NoAuthentication`, and principal propagation is out of scope for the
hackathon. An approval through Joule would be an approval with no approver. So:

- no skill approves, and a message asking to approve gets the help text;
- the shim signs in as a user whose role is `planner`, which
  `ROLE_LIMITS` in `sigap/agent/core/identity.py` gives a limit of 0. Even a
  shim that sent an approval would be refused by the server;
- every answer that mentions an action links to SIGAP web, where a signed-in
  person approves it.

**Why investigating returns immediately.** Joule waits 60 seconds for an
answer. A SIGAP handling can run for up to ten minutes
(`MAX_SECONDS_PER_EVENT` = 600 s). So investigating raises the event and links
to it, and following it is the status skill. That keeps every exchange well
inside the 60 seconds, without the `a2a_multiturn_async` pattern.

**How the skill is chosen.** Joule picks a scenario by its `description`, then
sends the agent the user's message and nothing else. All three scenarios reach
this one agent, so `skills.py` reads the skill from the same words again
(English and Indonesian). A message that names none of the three gets the help
text, never an event: a misread question must cost nothing. A JSON message
`{"skill": "risk_scan"}` names the skill outright, which is handy in the A2A
Editor.

**Guards, because the URL is public.** `NoAuthentication` means anyone who
finds the shim's URL can call it, and every investigation spends model credit.

- A disruption already raised in the last 24 hours (same title, or the same
  port and kind) is answered from its run instead of being raised twice.
  "Investigate again: …" overrides that.
- At most `SHIM_MAX_EVENTS_PER_HOUR` investigations an hour (default 10).
- Optional: `SHIM_TOKEN` (see Hardening).

## Files

| File | Holds |
|---|---|
| `server.py` | The A2A application. Same stack and task lifecycle as the organisers' Python sample |
| `skills.py` | Intent, the event built from the user's words, the markdown answers, the guards |
| `sigap_client.py` | Sign-in, token cache, re-login on 401, direct or bridge mode |
| `manifest.yml`, `requirements.txt`, `runtime.txt`, `.cfignore` | Cloud Foundry |
| `shim.env.example` | Every setting, with no values |
| `joule/` | The capability: `da.sapdas.yaml`, `sigap_capability/`, `render.py`, `joule.env.example` |

`skills.py` and `sigap_client.py` are standard library only and self-check on
any Python 3.9+: `python3 skills.py && python3 sigap_client.py`.

## Settings

| Name | Meaning |
|---|---|
| `SIGAP_API` | Where SIGAP is. The agent service (`http://127.0.0.1:8797`) or the public web app (`https://sigap.lumbungstack.dev`) |
| `SIGAP_API_MODE` | `direct`: token in `Authorization: Bearer`, paths as in `api.py`. `bridge`: paths under `/api/sigap`, token **only** in the `sigap_session` cookie, because the Next bridge drops `Authorization`. Default: `direct` for localhost, `bridge` otherwise |
| `SIGAP_SHIM_EMAIL`, `SIGAP_SHIM_PASSWORD` | The planner service user |
| `SIGAP_WEB_URL` | Base for links (`…/disruptions/<run_id>`). Defaults to `SIGAP_API` in bridge mode |
| `SHIM_PUBLIC_URL` | The URL the agent card advertises. Cloud Foundry sets it through `VCAP_APPLICATION` |
| `SHIM_MAX_EVENTS_PER_HOUR` | Investigations allowed per hour. Default 10 |
| `SHIM_TOKEN` | Optional shared secret, see Hardening |
| `PORT`, `HOST` | Listener. Default `8080` on `0.0.0.0` |

## The service user

In `sigap/agent`, on the machine whose database the shim will talk to:

```bash
PYTHONPATH=. python3 manage.py user <email> "Joule shim" planner <password>
```

Use a long random password, and keep it out of git: it goes in `shim.env`
locally and in `cf set-env` on Cloud Foundry.

## Run it locally

The A2A SDK needs Python 3.10 or newer (the sample pins 3.13). The agent
service itself stays on its own Python.

```bash
cd sigap/joule
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp shim.env.example shim.env       # fill in SIGAP_API and the service user
set -a; . ./shim.env; set +a
python server.py                   # listens on HOST:PORT from shim.env
```

## Test it without Joule

The agent card, the way Joule discovers the agent:

```bash
curl -s http://127.0.0.1:8799/.well-known/agent-card.json
```

One message, the way Joule sends it:

```bash
curl -s http://127.0.0.1:8799/ -H 'content-type: application/json' -d '{
  "jsonrpc": "2.0", "id": "1", "method": "message/send",
  "params": {"message": {"role": "user", "kind": "message", "messageId": "m1",
    "parts": [{"kind": "text", "text": "What is about to break this week?"}]}}}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["artifacts"][0]["parts"][0]["text"])'
```

The answer Joule shows is exactly that path: `artifacts[0].parts[0].text`.

The A2A Editor the organisers' exercise uses
([open-resource-discovery.github.io/a2a-editor](https://open-resource-discovery.github.io/a2a-editor/playground/))
runs in the browser, so it reaches whatever the browser can reach: the Cloud
Foundry URL, or a local shim through an SSH tunnel
(`ssh -L 8799:127.0.0.1:8799 <server>`, then `http://localhost:8799`). Paste
`<url>/.well-known/agent-card.json`, open the chat, and try each skill.

This is also the fallback for the demo if the destination is not in place by
28 October (`JOULE-BEDROCK-PLAN.md` §7).

## Deploy the shim to Cloud Foundry

```bash
cd sigap/joule
cf login -a <cf-api-endpoint>      # the organisers' BTP instructions
cf push                            # reads manifest.yml
cf set-env sigap-a2a-shim SIGAP_SHIM_EMAIL '<email>'
cf set-env sigap-a2a-shim SIGAP_SHIM_PASSWORD '<password>'
cf restage sigap-a2a-shim
curl -s https://<app-route>/health
curl -s https://<app-route>/.well-known/agent-card.json
```

`manifest.yml` points the shim at the public web app in bridge mode. If the
route is taken on the shared space, suffix the app name with the team.

## The BTP destination

BTP cockpit → the subaccount → Connectivity → Destinations → New Destination:

| Field | Value |
|---|---|
| Name | `SIGAP_AGENT_<team>`, unique on the shared subaccount |
| Type | HTTP |
| URL | `https://<app-route>` |
| Proxy Type | Internet |
| Authentication | NoAuthentication |

Participants have read-only subaccount access, so this may need the
organisers. It is the one open question in `JOULE-BEDROCK-PLAN.md` §3.

## Deploy the capability to Joule

The YAML in `joule/sigap_capability/` is in git and the repo is public, so it
carries two placeholders: the destination name and the team's IAS group UUID
(from the organisers' BTP instructions, "Visibility Conditions"). Every
scenario is gated on that group, so other teams on the shared tenant do not see
it. `render.py` fills them from `joule/joule.env` (gitignored) into
`joule/build/` (gitignored):

```bash
cd sigap/joule/joule
cp joule.env.example joule.env      # fill in SIGAP_DESTINATION and TEAM_IAS_GROUP_ID
python3 render.py

npm install -g @sap/joule-studio-cli
joule login                         # interactive: the team's Joule/DAS credentials and your IAS password
cd build
joule deploy -c -n "sigap_assistant_<team>"
```

Then open `<joule-api-url>/webclient/standalone/sigap_assistant_<team>` and
ask each of the three. After any group change, log out of the Joule CLI and the
web client and back in, so the token carries the group.

A template deployed by mistake fails safe: no destination is named
`__SIGAP_DESTINATION__` and nobody is in the group `__TEAM_IAS_GROUP_ID__`.

## Hardening

`SHIM_TOKEN`, when set, makes every JSON-RPC call carry
`X-Sigap-Shim-Token: <token>`; the agent card stays public, because Joule reads
it before calling. A BTP destination can send a fixed header with the
additional property `URL.headers.X-Sigap-Shim-Token`. **Not confirmed:**
whether Joule's `agent-request` forwards destination headers. Try it in Joule
before relying on it; without it, the rate limit and the duplicate guard are
the protection, and the planner role means the worst case is spent credit,
never an approval.

## Not verified here

- A real Joule tenant: `joule deploy`, scenario matching, `visibility_condition`
  placement (taken from the organisers' BTP instructions), the card rendering.
- `cf push` on the hackathon space, and the destination.
- Against the real SIGAP API: the shim was tested against a stub with the same
  shapes as `api.py`, including `GET /exposure`.
