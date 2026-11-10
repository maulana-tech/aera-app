# Setup

> Getting AERA from a clone to a system that reasons against a real model and
> reads your own uploaded data. Written 29 September 2026.
>
> Every step ends with a test. If the test does not pass, do not move on: each
> step is what makes the next one diagnosable.

---

## 0. Run it locally first, on nothing

No key is needed for this. The system runs on fixtures and says so.

```bash
cd aera/agent
cp .env.example .env
python3 manage.py secret              # paste the output into AERA_SECRET in .env
python3 manage.py user you@example.com "Your Name" procurement_lead <a password>
python3 manage.py seed                # demo events, runs and actions
python3 api.py                        # :8787
```

In a second terminal:

```bash
npm install
AERA_API=http://127.0.0.1:8787 npm run dev
```

**Test.** `http://localhost:3000/dashboard` loads, you can sign in, and every
figure on screen carries an origin label reading `modelled`. That label is the
product working, not a placeholder.

> Open the app at **localhost**, not `127.0.0.1`. Next 16 treats them as
> different origins; `next.config.ts` allows both, but localhost is the one the
> dev server boots on.

---

## 1. Your own data, by upload

Company data comes only from CSV uploads. Anything not uploaded keeps reading
the shipped fixtures, labelled `modelled`.

1. Open **Upload data** (`/uploads`)
2. Download the template for an entity, for example `MaterialStock`
3. Fill it with your rows and upload it (or `POST /uploads`)

**Test.** On the dashboard, figures for that entity now read `cached` instead of
`modelled`. `PYTHONPATH=. python3 manage.py ready` says how many tables are
uploaded; the Upload data page lists them.

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
cd aera/agent && python3 -m pip install -r requirements.txt
```

### 2d. Set the region

Put the region in `aera/agent/.env` as `AWS_REGION`, then restart `api.py`.
`ENV.md`, under **Models**, has the full Bedrock setup and the model split;
`python3 manage.py models --ping` confirms each model answers.

**Test.**

```bash
cd aera/agent && PYTHONPATH=. python3 manage.py check
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

**Expect this to break.** Budget two days for it, not one. The
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

## What is still not set up after all this

Honest list, so nothing is discovered during a demo.

| | Why |
|---|---|
| Rule pack (`references/rule-pack.json`) | Not installed. Kira judges from built-in parameters and labels the result `MODELLED`. Format in `references/README.md`. Domain work, not code, and it waits on nobody |
| Scenario eval suite | Absent |
| Foreign typhoon signal | BMKG covers Indonesia only, so the Ningbo trigger has no live source. `DATA-SOURCES.md` §5 |
| AgentCore deployment | Local only so far, and deliberately not before §3 above passes |

---

## If something is wrong

| Symptom | Cause |
|---|---|
| Every figure still reads `modelled` after an upload | Only the entity that was uploaded changes; the rest stay on the fixtures. The Upload data page lists what is uploaded |
| A setting in `.env` is ignored | `api.py` was not restarted (`.env` is read once, at import), or the value picked up a trailing note without a `#`. Run `PYTHONPATH=. python3 core/config.py` to confirm |
| Buttons do nothing, the theme toggle is dead | The app was opened at an origin the dev server does not allow, so the client bundle never hydrated. Use `localhost` |
| `ModelNotReady` | Neither the lead's model nor `AERA_MODEL_FALLBACK` can be called. `manage.py models` says which and why |
| `400` from Bedrock on the first call | Usually `thinking` or `effort` in the wrong place. `TECHNICAL.md` has the four common mistakes |
| `PromptMissing` | An agent has no file in `prompts/`. By design: a missing prompt raises rather than sending the model a placeholder |
