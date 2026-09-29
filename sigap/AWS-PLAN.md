# Getting SIGAP onto AWS

> Written 29 September 2026. Demo Day is 31 October, so this covers 32 days.
> Grounded in the *Building Agents on AWS* briefing and in what the code
> actually does today, not in the service catalogue.

---

## 1. The uncomfortable starting point

All eleven agents have instructions now, and `graph.py` runs: `python3 graph.py`
drives one event through the team against a scripted stand-in for Bedrock, which
exercises the routing, the tool execution, the shared board and the cost
accounting. That already found one real bug, a registry that was empty unless
something else imported the tool modules first.

What it has never done is talk to a real model, because `AWS_REGION` is empty.
The scripted client proves the plumbing. It proves nothing about judgement.

That matters for how this plan is ordered. Every AgentCore service below is
worth having, and every one of them is worthless until the loop runs once.
Wrapping code that has never executed in managed infrastructure produces a
deployment of nothing.

So: **make it run, then make it AWS-native.** Not the other way round, however
tempting the 20% "Technical Execution & Use of AWS/SAP" score makes it.

---

## 2. The one architectural decision

The briefing is explicit about when to use which:

> Start with Managed Harness. Move to Runtime only when you need to **own the
> orchestration loop entirely**, **multi-agent collaboration patterns**, graph
> or workflow-based architectures, bi-directional streaming, custom hooks.

SIGAP is all four of the first ones. The supervisor exposes ten specialists as
its own tools (`ask_<code>`), decides who to call from the last finding, and
stops when the evidence is enough. A managed harness runs the standard single
agent loop of reason, act, observe. It cannot host a supervisor of specialists.

**Decision: AgentCore Runtime, not Managed Harness.** This is also the answer
to give a judge who asks why we did not take the faster path, and it is a
better answer than "we preferred to build it ourselves".

The pattern we are running, in the briefing's vocabulary, is
**Orchestrator / Router**: hub dispatches to specialists, hub and spoke. Worth
knowing that the briefing lists its weakness as *"single point of failure;
cross-domain tasks need multiple sequential dispatches"*. Both are true of us.
Our answer is that a compliance veto has to be a single point, and that the
alternative patterns are worse here: a Swarm cannot guarantee Kira is consulted,
and Supervisor-plus-parallel pays for every specialist on every event when most
events need three.

---

## 3. What AgentCore replaces, and what it does not

We hand-rolled 745 lines that overlap with AgentCore. Not all of it should go.

| What we have | AgentCore offers | Verdict |
|---|---|---|
| `graph.py`, the supervisor loop | **Runtime** to host it | **Adopt.** This is the whole point of Runtime. |
| `core/registry.py`, 19 tools with schemas | **Gateway**, tools as MCP | **Adopt.** One registry already feeds the model and the executor, so exposing it over MCP is a shape change, not a rewrite. |
| `core/trace.py`, steps into SQLite | **Observability**, OTEL traces | **Adopt.** Ours records what we chose to record. OTEL records every model call, token count and latency, which is what "trace every agent decision" means. |
| nothing | **Memory** and **Managed Knowledge Base** | **Adopt, for Otto.** `search_past_incidents` returns MISSING today because there is no store behind it. Otto is a real agent with a real tool and nowhere to look. |
| nothing | **Evaluation** | **Adopt late.** The 14 scenarios in `DESIGN.md` §5 are unwritten. This is where they go. |
| `core/identity.py`, HMAC sessions | **Identity** | **Keep ours.** AgentCore Identity authenticates an agent to a tool. Ours authenticates a buyer to the approval endpoint. Different problems, and swapping ours for it would be confusing a judge, not impressing one. |
| Kira's veto in `tools/compliance.py` | **Guardrails** | **Keep ours.** Guardrails filter model output. Our veto is arithmetic in Python that the model cannot talk its way past, which is strictly stronger. Say so if asked. |
| nothing | Browser, Code Interpreter, Web Search, Payments | **Skip.** No use case. Wiring them up to score points is exactly the name-dropping the rubric punishes under "purposeful use". |

The honest line for the presentation: we adopted five AgentCore services
because they do something we could not, and declined four because they do not
fit. That is a better story than a slide with nine logos.

---

## 4. Order of work

### Week 1, 29 Sep to 5 Oct. Make it run.

1. **Enable Bedrock, confirm the region carries Claude.** `us-west-2` is the
   fallback. Set `AWS_REGION`, and `manage.py check` should stop listing it.
2. **Run the Ningbo scenario end to end, locally, against Bedrock.** `POST /events`, watch
   `graph.py` route, fix what breaks. Expect it to break. Budget two days for
   breakage, not one.

Exit test: one run reaches `status: done` with a recommendation, and `/log`
shows real agent steps instead of the empty state it shows today.

### Week 2, 6 to 12 Oct. Make it AWS-native.

4. **Package for Runtime.** Docker image to ECR, the AgentCore runtime
   decorator around the entry point, observability and identity config. The
   briefing claims deploy in under a minute once the image is there.
5. **Tools onto Gateway.** `registry.schemas_for_model()` already emits the
   schema the model sees; Gateway wants the same shape as MCP. This also
   answers FAQ Q1 from the briefing, which explicitly allows our own stack
   integrating over MCP.
6. **Observability on.** Traces per specialist call, token cost per event.
   Feeds the dashboard's model-cost figure with real numbers rather than the
   estimate in `graph.py`.

Exit test: an event posted to the deployed Runtime endpoint produces the same
answer as the local run, and the trace is visible in the console.

### Week 3, 13 to 19 Oct. Give Otto a memory, give ourselves evidence.

7. **Knowledge Base for precedent.** Seed it with the handled runs we have.
   `search_past_incidents` starts returning rows instead of MISSING, and Otto
   becomes a working agent rather than a declared one.
8. **Eval suite into Evaluation.** Start with scenarios 1, 6 and 10 from
   `DESIGN.md` §5: the baseline, the quality hold, and the mid-flight TKDN
   change. Three that pass are worth more than fourteen that are listed.

### Week 4, 20 to 31 Oct. Rehearse.

9. **SAP side.** Request the BAIP sub-account, which the briefing says is
   available on request through the AWS team. That unlocks AI Core and is the
   only route to a defensible SAP answer beyond the S/4HANA sandbox we already
   read from.
10. **Cut the demo to 15 minutes including Q&A.** Live, not slides. The
    briefing is blunt that a working demo beats slides.
11. **Rehearse the three questions we will be asked**, in §6 below.

---

## 5. Cost

Bedrock is pay as you go and the personal AWS account carries USD 100 of Free
Tier credit. `graph.py` already caps spend per event through
`CFG.cost_cap_per_event_idr`, default Rp 500,000, and raises `BudgetExhausted`
rather than running on.

The rates in `graph.py` are placeholders taken from a reference sheet, not from
Bedrock's price list. Replace them from `aws.amazon.com/bedrock/pricing` once
the region is chosen, because the dashboard shows the resulting figure to a
user and we should not show an invented number in a product whose whole claim
is that it does not invent numbers.

Prompt caching matters more here than in most systems: the tool list and
instructions are re-sent on every specialist turn, so without caching the cost
multiplies by the number of agents called. `TECHNICAL.md` has the ordering
rule.

---

## 6. The three questions to have an answer for

**"Why not Managed Harness?"** Because we own the orchestration loop, and the
briefing's own guidance says Runtime for multi-agent collaboration. Show
`graph.py` routing.

**"Your router is a single point of failure."** Correct, and deliberate. A
compliance veto that can be routed around is not a veto. The cost is that
cross-domain events need sequential dispatches, which is why there is a round
cap and a spend cap.

**"Is this real or is it mock data?"** The origin label is on every figure on
every screen. Today most of it reads `modelled` and the calculator refuses to
produce savings from it. Set `SAP_API_KEY` and the same screens read `live`.
That is a stronger answer than a demo where everything is green.

---

## 7. What would be a mistake

- Adopting Browser, Code Interpreter or Payments to lengthen the AWS list.
- Replacing `core/identity.py` with AgentCore Identity to say we use it. They
  solve different problems and the swap would weaken the approval trail.
- Moving to AgentCore before step 2 passes. Deploying a loop that has never run
  is deploying nothing, and it burns the week we would need to fix it.
- Rewriting the deterministic calculator to use a model. It is the thing that
  makes the savings figure survive a question.
