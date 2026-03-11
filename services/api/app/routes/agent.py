import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_agent, run_agent
from app.agent.playbooks import PLAYBOOKS
from app.core.deps import get_optional_user
from app.db import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/playbooks")
def list_playbooks():
    return [{"name": p.name, "description": p.description} for p in PLAYBOOKS.values()]


class AgentQueryRequest(BaseModel):
    question: str
    playbook_name: str = "game-design"
    document_id: str | None = None
    session_id: str | None = None  # if provided, loads chat history + saves messages


@router.post("/query")
async def agent_query(req: AgentQueryRequest):
    """
    Run the ReACT agent for a given question (non-streaming).
    Does not persist messages — use /query/stream for production use.
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
async def agent_query_stream(
    req: AgentQueryRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """
    Run the ReACT agent and stream events back as SSE.

    If session_id is provided:
      - Loads prior chat messages as context (so the agent has memory)
      - Saves the new user message + assistant response to the DB
      - Sets the session title from the first user message

    Event types emitted:
      {"type": "tool_start", "tool": "<name>", "input": {...}}
      {"type": "token",      "content": "<text>"}
      {"type": "error",      "message": "<text>"}
      {"type": "done"}
    """
    # Load chat history outside the generator so we have a DB session.
    # SSE generators run asynchronously and can't share the request's DB session.
    prior_messages: list = []
    session: ChatSession | None = None

    if req.session_id:
        try:
            session_id = uuid.UUID(req.session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid session_id format.")

        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if session:
            # Load history ordered by created_at
            msg_stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at)
            )
            msg_result = await db.execute(msg_stmt)
            history = msg_result.scalars().all()

            # Convert DB rows to LangChain message objects.
            # The agent sees these as prior context, enabling multi-turn conversation.
            for msg in history:
                if msg.role == "user":
                    prior_messages.append(HumanMessage(content=msg.content))
                else:
                    prior_messages.append(AIMessage(content=msg.content))

    # Capture full assistant response to save after streaming completes.
    # We collect tokens as they arrive, then persist as one DB row.
    accumulated: list[str] = []

    async def event_stream():
        try:
            graph = build_agent(req.playbook_name, req.document_id)

            # Build the full message list: prior history + current question
            messages = prior_messages + [HumanMessage(content=req.question)]

            async for event in graph.astream_events(
                {"messages": messages},
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
                    content = chunk.content if isinstance(chunk.content, str) else ""
                    if content and not getattr(chunk, "tool_calls", None):
                        accumulated.append(content)
                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

        except Exception:
            logger.exception("Stream error")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Agent error'})}\n\n"
        finally:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # Wrap in an outer async generator that persists messages AFTER streaming ends.
    # We can't use the request's db session inside event_stream() because it may
    # have been released by the time the finally block runs.
    async def event_stream_with_persistence():
        async for chunk in event_stream():
            yield chunk

        # Persist only if we have a valid session
        if session is not None:
            full_answer = "".join(accumulated)
            try:
                # Use a fresh DB call — the request session is still valid here
                # because we're still in the same request context.
                user_msg = ChatMessage(
                    id=uuid.uuid4(),
                    session_id=session.id,
                    role="user",
                    content=req.question,
                )
                asst_msg = ChatMessage(
                    id=uuid.uuid4(),
                    session_id=session.id,
                    role="assistant",
                    content=full_answer,
                )
                db.add(user_msg)
                db.add(asst_msg)

                # Set session title from the first user message (truncated)
                if session.title is None:
                    session.title = req.question[:60]

                await db.commit()
            except Exception:
                logger.exception("Failed to persist chat messages")

    return StreamingResponse(
        event_stream_with_persistence(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
