"""SIGAP's A2A agent: the door Joule knocks on.

Joule ─ agent-request ─▶ BTP destination (NoAuthentication) ─▶ this server
      ─▶ SIGAP's API, as a `planner` service user.

Shaped after the organisers' Python sample (`joule_a2a/project/Python-LangGraph/
solution/server.py`), the one Joule is known to accept: the same a2a-sdk
version, the same FastAPI application, the same task lifecycle (working, one
artifact, completed), so `apiResponse.body.artifacts[0].parts[0].text` in the
Joule function reads the answer.

What it does is in skills.py: three skills, none of which can approve. This file
only wires them to A2A. The SIGAP calls are blocking, so they run in a thread
and the event loop stays free for the next request.

Every answer comes back within Joule's 60 seconds, because the slow work never
happens here: an investigation is raised and linked, not waited for.

Optional hardening, off unless SHIM_TOKEN is set: JSON-RPC calls must carry
`X-Sigap-Shim-Token`. A BTP destination can send a fixed header through the
additional property `URL.headers.X-Sigap-Shim-Token`; whether Joule's
agent-request forwards destination headers is not confirmed, so test it in the
A2A Editor before relying on it. The agent card stays public either way, since
Joule reads it before it calls.
"""
import asyncio
import hmac
import json
import logging
import os
import time

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps.jsonrpc import A2AFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Artifact,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import skills
from sigap_client import NotConfigured, SigapClient

log = logging.getLogger("sigap-shim")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

#: Where a person approves. Defaults to the API's own host in bridge mode,
#: where SIGAP_API already is the web app.
WEB = (os.environ.get("SIGAP_WEB_URL") or "").rstrip("/") or None

LIMITER = skills.RateLimit(int(os.environ.get("SHIM_MAX_EVENTS_PER_HOUR", "10")))

_client = None


def client():
    """Built on first use, so the agent card is served even before SIGAP is
    configured, and a missing setting reads as an answer, not a crash."""
    global _client, WEB
    if _client is None:
        _client = SigapClient.from_env()
        if WEB is None and _client.mode == "bridge":
            WEB = _client.base
    return _client


def respond(text: str) -> tuple:
    started = time.monotonic()
    skill, _ = skills.classify(text)
    try:
        c = client()
    except NotConfigured as e:
        return skill, f"The SIGAP connection is not configured on this agent: {e}."
    out = skills.answer(text, c, WEB, LIMITER)
    log.info("skill=%s %.1fs", skill, time.monotonic() - started)
    return skill, out


class SigapExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            )
        )

        skill, text = await asyncio.to_thread(respond, context.get_user_input())

        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                artifact=Artifact(
                    artifactId=f"{skill}_result",
                    parts=[TextPart(text=text)],
                    name=f"{skill}_result",
                ),
            )
        )
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.canceled),
                final=True,
            )
        )


# Resolve the public URL from Cloud Foundry's VCAP_APPLICATION; SHIM_PUBLIC_URL
# overrides it (a tunnel, a custom route); fall back to localhost.
vcap_application = json.loads(os.environ.get("VCAP_APPLICATION", "{}"))
application_uris = vcap_application.get("application_uris", [])
if os.environ.get("SHIM_PUBLIC_URL"):
    app_url = os.environ["SHIM_PUBLIC_URL"].rstrip("/")
elif application_uris:
    app_url = f"https://{application_uris[0]}"
else:
    app_url = f"http://localhost:{os.environ.get('PORT', '8080')}"

agent_card = AgentCard(
    name="SIGAP",
    description=(
        "SIGAP, the supply disruption assistant. Starts an investigation of a "
        "supply disruption, reports how an investigation is going, and scans for "
        "supply risk that has not happened yet. Read and raise only: approvals "
        "happen on SIGAP web."
    ),
    url=app_url,
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=False),
    skills=[
        AgentSkill(
            id="investigate_disruption",
            name="Investigate a supply disruption",
            description=(
                "Raises a disruption (a port closure, a supplier failure, a customs or "
                "quality hold) with SIGAP's agent team and answers at once with the run "
                "id and a link. The investigation itself runs on SIGAP."
            ),
            tags=["supply chain", "disruption", "port closure", "supplier", "customs"],
            examples=["Investigate: Ningbo port closed for 6 days"],
            inputModes=["text/plain"],
            outputModes=["text/markdown"],
        ),
        AgentSkill(
            id="disruption_status",
            name="Status of an investigation",
            description=(
                "Reports a SIGAP run: its status, which agents worked on it, the "
                "recommendation, what is not yet trusted, and which actions wait for "
                "approval on SIGAP web."
            ),
            tags=["status", "recommendation", "approval"],
            examples=["What is the status of the Ningbo investigation?"],
            inputModes=["text/plain"],
            outputModes=["text/markdown"],
        ),
        AgentSkill(
            id="risk_scan",
            name="Scan for supply risk",
            description=(
                "Vega's exposure scan (single sources, concentrated lanes, cover below "
                "policy) and the purchase orders SAP RPT-1.6 ranks as likely to slip."
            ),
            tags=["risk", "exposure", "single source", "prevent"],
            examples=["What is about to break this week?"],
            inputModes=["text/plain"],
            outputModes=["text/markdown"],
        ),
    ],
    defaultInputModes=["text/plain"],
    defaultOutputModes=["text/markdown"],
)
handler = DefaultRequestHandler(
    agent_executor=SigapExecutor(),
    task_store=InMemoryTaskStore(),
)
app = A2AFastAPIApplication(agent_card=agent_card, http_handler=handler).build()

SHIM_TOKEN = os.environ.get("SHIM_TOKEN", "")


@app.middleware("http")
async def require_shim_token(request: Request, call_next):
    if SHIM_TOKEN and request.method == "POST":
        sent = request.headers.get("x-sigap-shim-token", "")
        if not hmac.compare_digest(sent, SHIM_TOKEN):
            return JSONResponse({"error": "missing or wrong X-Sigap-Shim-Token"}, status_code=401)
    return await call_next(request)


# Open CORS so the browser-based A2A Editor can reach this server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", 8080)))
