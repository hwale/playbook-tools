import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_optional_user
from app.db import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User

router = APIRouter(prefix="/chat", tags=["chat"])


# --- Request / Response schemas ---


class CreateSessionRequest(BaseModel):
    # None when auto-routing is active — playbook is determined by the agent router,
    # not the client. The session stores it as null until we know which playbook ran.
    playbook_name: str | None = None
    document_id: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    playbook_name: str | None
    document_id: str | None
    title: str | None
    created_at: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


# --- Routes ---


@router.post("/sessions", status_code=201, response_model=SessionResponse)
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """
    Start a new chat session for a playbook.

    Called when the user clicks "+ New Chat" or sends their first message.
    Returns session_id to be passed in subsequent /agent/query/stream calls.
    """
    session = ChatSession(
        id=uuid.uuid4(),
        playbook_name=req.playbook_name,
        document_id=uuid.UUID(req.document_id) if req.document_id else None,
        user_id=user.id if user else None,
    )
    db.add(session)
    await db.commit()

    return _session_response(session)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    playbook_name: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """
    List sessions, newest first.

    If playbook_name is provided, filters to that playbook only.
    If omitted, returns all sessions (used when auto-routing is active).
    Filters by user_id when authenticated so users only see their own sessions.
    """
    stmt = select(ChatSession).order_by(ChatSession.created_at.desc())

    if playbook_name is not None:
        stmt = stmt.where(ChatSession.playbook_name == playbook_name)

    if user:
        stmt = stmt.where(ChatSession.user_id == user.id)
    else:
        stmt = stmt.where(ChatSession.user_id.is_(None))

    result = await db.execute(stmt)
    sessions = result.scalars().all()
    return [_session_response(s) for s in sessions]


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all messages in a session ordered by creation time.

    Called when the user clicks an existing session in the sidebar.
    selectinload eagerly fetches messages in one query (avoids N+1).
    """
    stmt = (
        select(ChatSession)
        .where(ChatSession.id == uuid.UUID(session_id))
        .options(selectinload(ChatSession.messages))
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    return [
        MessageResponse(
            id=str(m.id),
            role=m.role,
            content=m.content,
            created_at=str(m.created_at),
        )
        for m in session.messages
    ]


# --- Helpers ---


def _session_response(s: ChatSession) -> SessionResponse:
    return SessionResponse(
        session_id=str(s.id),
        playbook_name=s.playbook_name,
        document_id=str(s.document_id) if s.document_id else None,
        title=s.title,
        created_at=str(s.created_at),
    )
