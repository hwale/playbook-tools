import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.agent.graph import build_agent, run_agent
from app.agent.playbooks import PLAYBOOKS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/playbooks")
def list_playbooks():
    return [{"name": p.name, "description": p.description} for p in PLAYBOOKS.values()]


class AgentQueryRequest(BaseModel):
    question: str
    playbook_name: str = "game-design"
    document_id: str | None = None  # omit for web-search-only queries


@router.post("/query")
async def agent_query(req: AgentQueryRequest):
    """
    Run the ReACT agent for a given question.

    Returns:
        answer: The agent's final response
        steps: List of tool calls made during reasoning (for transparency/debugging)
    """
    try:
        return await run_agent(
            question=req.question,
            playbook_name=req.playbook_name,
            document_id=req.document_id,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Agent error")
        raise HTTPException(status_code=500, detail="Agent error.")


@router.post("/query/stream")
async def agent_query_stream(req: AgentQueryRequest):
    """
    Run the ReACT agent and stream events back as SSE.

    Event types emitted:
      {"type": "tool_start", "tool": "<name>", "input": {...}}
      {"type": "token",      "content": "<text>"}
      {"type": "error",      "message": "<text>"}
      {"type": "done"}

    LangGraph's astream_events(version="v2") emits granular lifecycle events
    for each node and model call. We filter for two:
      - on_tool_start: a tool is about to run (lets UI show live reasoning steps)
      - on_chat_model_stream: the LLM is emitting a token (streams the final answer)
    """
    async def event_stream():
        try:
            graph = build_agent(req.playbook_name, req.document_id)
            async for event in graph.astream_events(
                {"messages": [HumanMessage(content=req.question)]},
                config={"recursion_limit": 20},
                version="v2",
            ):
                kind = event["event"]

                if kind == "on_tool_start":
                    data = {
                        "type": "tool_start",
                        "tool": event["name"],
                        "input": event["data"].get("input", {}),
                    }
                    yield f"data: {json.dumps(data)}\n\n"

                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    # Only emit content tokens, not tool-call JSON fragments
                    content = chunk.content if isinstance(chunk.content, str) else ""
                    if content and not getattr(chunk, "tool_calls", None):
                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

        except Exception:
            logger.exception("Stream error")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Agent error'})}\n\n"
        finally:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
