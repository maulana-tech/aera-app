# How AWS and SAP say to build this

> Read on 29 September 2026, from AWS and SAP's own published architectures.
> Every claim here carries the page it came from. Where a source is silent, this
> document says so rather than filling the gap.
>
> The last section is the only one about SIGAP. The rest is what other people built.

---

## 1. The split both vendors assume

Neither vendor treats this as one system. Both draw the same line:

| | AWS | SAP |
|---|---|---|
| Owns | where the agent **thinks**, and where its tools run | where the **record** lives and where an action **takes effect** |
| Protocol at the boundary | MCP | OData |
| Governs | model access, tool authorisation, tracing | licensing, metering, who may call a business API |

This is the line `PLAN.md` §4 already drew. Nothing found contradicts it.

---

## 2. AgentCore, the six primitives

`docs.aws.amazon.com/sap` lists them as a toolkit, usable together or separately,
and explicitly model-agnostic.

| Primitive | What it is |
|---|---|
| **Runtime** | Serverless host for a long-running agent, with session isolation |
| **Gateway** | Turns existing APIs and Lambda functions into MCP tools |
| **Memory** | Short-term conversation context and long-term memory, managed |
| **Identity** | Auth for agents, inbound and outbound, against existing IdPs |
| **Built-in Tools** | Code Interpreter and a Browser tool, both sandboxed |
| **Observability** | Traces and dashboards through CloudWatch, OpenTelemetry supported |

---

## 3. The piece that did not exist when we planned: AWS for SAP MCP Server

This is the most important finding. AWS now ships a **container image, at no cost**,
that exposes SAP OData as MCP tools and runs on AgentCore Runtime.

![AWS for SAP MCP Server on Bedrock AgentCore, with SAP ERP connectivity via SAP BTP](https://d2908q01vomqb2.cloudfront.net/17ba0791499db908433b80f37c5fbc89b870084b/2026/05/27/SAP-MCP-Arch-1.png)

*Figure 1, AWS for SAP MCP Server Architecture on Amazon Bedrock AgentCore with SAP ERP Connectivity via SAP BTP. Source: AWS for SAP blog.*

**What it does**

1. Agent discovers which OData services exist, through a catalog discovery tool.
   Two modes, remote catalog (queries SAP's own catalog service) or local.
2. Agent pulls "service hints" from configuration held in S3, for context on how a
   given service behaves.
3. Agent calls CRUD operations on business objects: sales orders, purchase orders,
   and so on.
4. The server performs the OData call over whichever connectivity path is configured.

**Three connectivity topologies**

| Topology | Path | Where traffic goes |
|---|---|---|
| SAP BTP API Management | HTTPS, OAuth 2.0 | Egresses to internet, TLS |
| SAP Cloud ERP Private (RISE on AWS) | VPC Peering or Transit Gateway | Stays on the AWS backbone |
| SAP ERP on AWS | Same VPC or cross-VPC | Never leaves AWS |

**Authentication is two-sided**, through AgentCore Identity:

- Inbound, MCP client to server: IAM, Cognito, Microsoft Entra ID, or Okta
- Outbound, server to SAP: OAuth 2.0

**Stated limits.** The page documents OData **V2** compatibility and does not mention
V4. Service hints are a manual S3 configuration unless the remote catalog is reachable.

---

## 4. The closest published build to ours: Smart Procurement Assistant

AWS for Industries published a procurement agent against SAP S/4HANA on EC2. It is
the nearest thing to SIGAP in the public record, which makes both its choices and its
omissions useful.

![Smart Procurement Assistant Architecture](https://d2908q01vomqb2.cloudfront.net/c5b76da3e608d34edb07244cd9b875ee86906328/2026/02/18/Figure-1.png)

*Figure 2, Smart Procurement Assistant Architecture. Source: AWS for Industries blog.*

**Shape**

- **Orchestration**: Strands Agents SDK on AgentCore Runtime, containers on ECS/Fargate
- **Data plane**: S3 holds structured procurement data, Glue Data Catalog holds metadata,
  Athena runs the SQL, OpenSearch does document search
- **SAP write path**: AgentCore Gateway gives an MCP bridge, a Lambda executes the MCP
  client call, Secrets Manager holds the credentials
- **Edge**: Cognito for JWT and RBAC, WAF, API Gateway for a WebSocket so replies stream
- **Eight tools**, including schema lookup, natural language to SQL, financial analysis,
  quality metrics, compliance validation against REACH / RoHS / CMRT / RBA, RFQ creation
  through SAP OData, and a sandboxed visualisation tool

**Two things it does not have.** Worth naming, because they are the two things SIGAP
was built around:

1. **No approval gate.** The article describes RFQ creation as user-directed tool
   invocation and documents no review or authorisation step before a write reaches SAP.
2. **No stated evaluation.** Outcomes are given qualitatively, "reduces cycle times",
   "cost savings". No benchmark, no metric, no dataset.

---

## 5. The SAP side: Joule, the Agent Hub, and A2A

SAP does not expose its agents directly. Its published pattern is **A2O**,
agent-to-orchestrator: an external agent talks to Joule, and Joule talks to SAP agents.

| Layer | Role |
|---|---|
| **Joule** | The central orchestrator. Governs how agents interact and how tasks are planned and delegated |
| **Agent Hub** | Protocol adapter. Translates A2A and MCP into SAP's internal agent APIs, and enforces security, licensing and metering centrally |
| **A2A** | SAP's preferred standard for agent to agent work. Discovery by role or capability, task delegation, artifact exchange |
| **MCP** | The universal interface for an agent to reach tools and data |

A pro-code agent that runs in **its own runtime** integrates through A2A. That is
exactly the shape of a system like ours.

**Timing worth knowing.** General availability of the enhanced A2A capabilities in
Joule is reported as **Q4 2026**. Demo day is 31 October 2026, so this is a roadmap
item to speak about, not one to depend on.

---

## 6. AgentOps: how AWS says to evaluate and operate an agent

This is the richest source, and it lands directly on our largest known gap.

### 6.1 Evaluation has four levels, not one

| Level | What is judged | Example metrics |
|---|---|---|
| **Tool (span)** | One tool call | Deterministic tools: unit tests, latency, error rate. Model-backed tools: correctness, relevance. Plus tool **selection** accuracy and parameter extraction |
| **Turn (trace)** | One question and its answer | Correctness, faithfulness, relevance, coherence, instruction following |
| **Session outcome** | Did the whole conversation achieve the goal | Task completion rate, goal accuracy, efficiency, memory consistency |
| **System** | The service | End to end latency, throughput, tool error rate, cost per task, compliance adherence |

### 6.2 Three modes, each with a gate

| Mode | Runs | Gate |
|---|---|---|
| On-demand | During development, against a reference dataset with ground truth | Must pass before pre-production |
| CI/CD | Automated, pre-production | Must pass before production |
| Online | Continuously, on sampled live traffic | Automated rollback on degradation |

![On-demand versus online evaluation](https://d2908q01vomqb2.cloudfront.net/f1f836cb4ea6efb2a0b1b99f41ad8b103eff4b59/2026/05/19/ml-19465-image-6.png)

*Figure 3, multi-agent memory access with separate and shared long-term memory under IAM control. Source: AWS AgentOps blog.*

### 6.3 Observability has four instrumentation layers

1. **Agent and framework**: reasoning steps, model calls, tool invocations
2. **Service**: memory reads and writes, gateway auth, identity policy evaluation
3. **Infrastructure**: container and Lambda metrics
4. **Application**: business metrics across a multi-agent system

Correlation is done with **W3C Trace Context** for a shared trace ID across agents,
and **OpenTelemetry Baggage** to carry a session ID across separate traces.

Signals AWS calls out specifically: token spend per session, per agent and per task;
memory extraction quality; toxicity, bias, hallucination rate and PII leakage.

### 6.4 Authorisation happens at four checkpoints

![Security authorization checkpoints](https://d2908q01vomqb2.cloudfront.net/f1f836cb4ea6efb2a0b1b99f41ad8b103eff4b59/2026/05/19/ml-19465-image-1.png)

*Figure 4, user identity verification, then agent access validation, then context, memory and tool access, then output authorization. Source: AWS AgentOps blog.*

Tool access is evaluated deterministically with **Cedar** policy, enforced through
AgentCore Gateway, on top of least-privilege IAM.

![AgentCore services integration](https://d2908q01vomqb2.cloudfront.net/f1f836cb4ea6efb2a0b1b99f41ad8b103eff4b59/2026/05/20/ml-19465-image-4-1.png)

*Figure 5, Identity for inbound auth, Gateway for tool routing, Policy for Cedar rules, then Memory resources. Source: AWS AgentOps blog.*

### 6.5 Four repositories, not one

Infrastructure, agents, tools, and the consuming application are versioned separately.
Tools get their own CI/CD and are deployed behind MCP servers. Agent versions are
immutable, promoted by alias, and rolled back by pointing the alias back.

---

## 7. What this means for SIGAP

The honest read: the shape we chose matches what both vendors publish. Two specific
pieces are worth adopting, one gap is now clearly defined, and two of our decisions
look **better** than the closest published build rather than merely different.

| Their pattern | SIGAP today | Verdict |
|---|---|---|
| AgentCore Runtime hosts the orchestration loop | `graph.py` owns the loop | **Aligned.** `AWS-PLAN.md` §2 already chose Runtime over Managed Harness for this reason |
| AWS for SAP MCP Server for OData reads | `clients/` is a hand-rolled connector | **Reconsider.** This shipped after we wrote ours. Free container, catalog discovery and OAuth already handled |
| Gateway plus Lambda for SAP writes | `sender.py` posts directly, handles CSRF | **Keep for now.** Ours works and is auditable. Gateway's gain is MCP tool schemas for free, not correctness |
| AgentCore Memory | `conversations` and `messages` in SQLite | **Keep ours.** Ours is owner-scoped and is part of the record. Memory is agent working context, a different job |
| AgentCore Identity | `core/identity.py`, HMAC sessions | **Keep ours**, as already decided. Theirs authenticates an agent to a tool, ours authenticates a buyer to an approval endpoint |
| Cedar policy on tool access | Role caps and a cost cap, in business terms | **Real gap, different layer.** We authorise *people*, nobody authorises *the agent* per tool |
| Four-level evaluation hierarchy | Absent | **Biggest gap**, and now it has a shape. This is PLAN item 7 |
| W3C Trace Context, OpenTelemetry | `core/trace.py` plus the `steps` table | **Partly aligned.** We record every step with provenance. We do not export OTel, so nothing correlates outside our own database |
| Online evaluation on sampled traffic | Absent | Post-demo. Needs production traffic to exist first |
| SAP A2A through Joule | Not addressed | We are a pro-code agent in our own runtime, which is precisely the A2A integration shape SAP documents. Worth one slide, not code |

### Where we are ahead of the published reference

Both are worth saying out loud, because the nearest comparable build does not do them:

1. **Every action waits for authority it is entitled to.** Bounded autonomy to Rp 50m,
   role caps checked server-side, one-shot approvals, idempotent actions. The Smart
   Procurement Assistant writes an RFQ into SAP with no documented approval gate.
2. **Every figure carries where it came from.** `Origin` on every tool result, and a
   calculator that refuses to produce rupiah when its inputs are not trustworthy.
   Neither published architecture labels provenance at all.

### What to do about it

| # | Work | Why now |
|---|---|---|
| 1 | Build the eval suite against §6.1's four levels, starting at tool and turn level | Already PLAN item 7, now with a published shape to copy |
| 2 | Evaluate AWS for SAP MCP Server against `clients/` before writing more connector code | It may delete work we have not done yet |
| 3 | Emit OpenTelemetry spans from `core/trace.py`, carrying a session id | Cheap, and it is what makes the trace legible outside our own UI |
| 4 | Decide whether agent-level tool authorisation is in scope | We have no equivalent. It may be correctly out of scope at this size |

---

## Sources

- [Building Agentic Enterprises on AWS with the AWS for SAP MCP Server on Amazon Bedrock AgentCore](https://aws.amazon.com/blogs/awsforsap/building-agentic-enterprises-on-aws-using-aws-for-sap-mcp-server-on-amazon-bedrock-agentcore/)
- [Automate Procurement Workflows with AI Agents using Amazon Bedrock AgentCore](https://aws.amazon.com/blogs/industries/automate-procurement-workflows-with-ai-agents-using-amazon-bedrock-agentcore/)
- [AgentOps: Operationalize agentic AI at scale with Amazon Bedrock AgentCore](https://aws.amazon.com/blogs/machine-learning/agentops-operationalize-agentic-ai-at-scale-with-amazon-bedrock-agentcore/)
- [Amazon Bedrock AgentCore, General SAP Guides](https://docs.aws.amazon.com/sap/latest/general/rise-agenticai-bedrock-agentcore.html)
- [Enabling Interoperability for AI Agents, SAP Learning](https://learning.sap.com/courses/boosting-ai-driven-business-transformation-with-joule-agents/enabling-interoperability-for-ai-agents)
- [Agentic AI & AI Agents, SAP Architecture Center](https://architecture.learning.sap.com/docs/ref-arch/98efa0) (not readable from here, listed for completeness)
- [Bring Your Own Agent, SAP Architecture Center](https://architecture.learning.sap.com/docs/ref-arch/7b6426) (not readable from here)

Diagrams are hotlinked to the publishers' CDN, checked live on 29 September 2026.
They are not mirrored into this repository.
