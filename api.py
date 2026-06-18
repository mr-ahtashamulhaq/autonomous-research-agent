# ─── Autonomous Research Agent - FastAPI Server ───────────────────────────────
#
# Exposes the LangGraph agent over HTTP with Server-Sent Events (SSE) so the
# frontend can display live progress as each node completes.
#
# Run:
#   uvicorn api:app --reload --port 5000
#
# Endpoints:
#   POST /research   - stream research progress + final report as SSE
#   GET  /health     - quick liveness check
#   GET  /docs       - auto-generated Swagger UI (FastAPI built-in)
# ──────────────────────────────────────────────────────────────────────────────

import json
import asyncio
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import the compiled agent and state from agent.py
# agent.invoke() is a synchronous call, so we'll run it in a thread pool
# to avoid blocking FastAPI's async event loop.
from agent import agent

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Autonomous Research Agent",
    description=(
        "A LangGraph-powered agent that autonomously researches any topic using "
        "Tavily web search + Groq LLM inference. "
        "Built with: LangGraph · LangChain · Groq (llama-3.3-70b) · Tavily."
    ),
    version="1.0.0",
)

# Allow the frontend (running on any origin during dev, or on Vercel in prod)
# to call this API. In production, replace "*" with your Vercel domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten this to your Vercel URL in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Request schema (Pydantic validates this automatically) ────────────────────

class ResearchRequest(BaseModel):
    topic: str

    class Config:
        json_schema_extra = {
            "example": {"topic": "Impact of AI on healthcare in 2024"}
        }

# ── SSE helper ────────────────────────────────────────────────────────────────

def make_sse_event(event_type: str, data: dict) -> str:
    """Format a single Server-Sent Event string.

    SSE wire format (each field ends with \\n, event ends with \\n\\n):
        event: <type>\\n
        data: <json>\\n
        \\n
    The browser's EventSource API parses this automatically.
    """
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# Node names in execution order - used to report progress percentage to the UI
NODE_ORDER = ["plan", "search", "read", "synthesise", "review"]


async def research_stream(topic: str) -> AsyncGenerator[str, None]:
    """Run the LangGraph agent and yield SSE events as each node completes.

    LangGraph's agent.stream() yields incremental state updates - one dict
    per completed node - so we can emit a progress event after each step
    without any polling.
    """
    # Yield a "started" event immediately so the UI can show a loading state
    yield make_sse_event("started", {"topic": topic, "total_steps": len(NODE_ORDER)})

    completed_nodes = []

    try:
        # agent.stream() yields {"node_name": {...updated state keys...}} for each node
        # We run this synchronously in the default thread pool via asyncio.to_thread
        # so we don't block the event loop during the long LLM/API calls.

        # Build a queue to bridge the sync generator and async SSE stream
        queue: asyncio.Queue = asyncio.Queue()

        async def run_agent():
            """Run agent.stream() in a thread and push updates into the queue."""
            loop = asyncio.get_event_loop()

            def _stream():
                # agent.stream() is a synchronous generator from LangGraph
                for chunk in agent.stream({"topic": topic, "progress": []}):
                    # chunk is {"node_name": {state_updates}}
                    node_name = list(chunk.keys())[0]
                    state_update = chunk[node_name]
                    loop.call_soon_threadsafe(queue.put_nowait, (node_name, state_update))
                # Signal completion
                loop.call_soon_threadsafe(queue.put_nowait, None)

            await loop.run_in_executor(None, _stream)

        # Start the agent in the background
        agent_task = asyncio.create_task(run_agent())

        final_report = ""

        while True:
            item = await queue.get()
            if item is None:
                break  # agent finished

            node_name, state_update = item
            completed_nodes.append(node_name)

            step_index = NODE_ORDER.index(node_name) + 1 if node_name in NODE_ORDER else len(completed_nodes)
            progress_pct = int((step_index / len(NODE_ORDER)) * 100)

            # Send a progress event so the frontend can update its progress bar
            yield make_sse_event("progress", {
                "node":        node_name,
                "step":        step_index,
                "total":       len(NODE_ORDER),
                "percent":     progress_pct,
                "label":       _node_label(node_name),
            })

            # Capture the final report when the review node completes
            if node_name == "review" and "final_report" in state_update:
                final_report = state_update["final_report"]

        await agent_task  # ensure background task is cleaned up

        # Send the finished event with the complete report
        yield make_sse_event("done", {
            "report": final_report,
            "topic":  topic,
        })

    except Exception as exc:
        # Surface errors to the frontend so they can display a friendly message
        yield make_sse_event("error", {"message": str(exc)})


def _node_label(node_name: str) -> str:
    """Human-readable label for each node - shown in the frontend progress bar."""
    labels = {
        "plan":       "Generating search queries…",
        "search":     "Searching the web…",
        "read":       "Reading articles…",
        "synthesise": "Synthesising report…",
        "review":     "Fact-checking & finalising…",
    }
    return labels.get(node_name, node_name.capitalize())


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post(
    "/research",
    summary="Run the research agent on a topic",
    response_description="Server-Sent Events stream: started → progress (×5) → done | error",
)
async def research_endpoint(request: ResearchRequest):
    """
    Stream the research agent's progress as Server-Sent Events.

    The client receives these event types in order:
    - **started** - immediately, with topic + total step count
    - **progress** - once per LangGraph node (5 total)
    - **done** - final event carrying the complete markdown report
    - **error** - if anything goes wrong mid-stream
    """
    return StreamingResponse(
        research_stream(request.topic),
        media_type="text/event-stream",
        headers={
            # Disable buffering so events reach the browser immediately
            "Cache-Control":      "no-cache",
            "X-Accel-Buffering":  "no",
            "Connection":         "keep-alive",
        },
    )


@app.get("/health", summary="Health check")
async def health():
    """Returns 200 OK - used by deployment platforms to verify the server is up."""
    return {"status": "ok", "service": "autonomous-research-agent"}
