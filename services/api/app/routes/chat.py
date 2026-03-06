import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document

router = APIRouter(prefix="/chat", tags=["chat"])

_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


# --- Request / Response schemas ---


class CreateSessionRequest(BaseModel):
    document_id: str = Field(..., pattern=_UUID_PATTERN)


class SessionResponse(BaseModel):
    session_id: str
    document_id: str
    created_at: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


# --- Routes ---


@router.post("/sessions", status_code=201)
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a new chat session for a document.

    The frontend calls this when the user clicks "New Chat" on a document.
    Returns the session_id that should be passed to /query on subsequent questions.
    """
    # Verify the document exists and is ready to query.
    doc = await db.get(Document, uuid.UUID(req.document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.status != "complete":
        raise HTTPException(status_code=409, detail=f"Document is not ready (status: {doc.status}).")

    session = ChatSession(document_id=doc.id)
    db.add(session)
    await db.commit()

    return SessionResponse(
        session_id=str(session.id),
        document_id=str(session.document_id),
        created_at=str(session.created_at),
    )


@router.get("/sessions")
async def list_sessions(
    document_id: str = Query(..., pattern=_UUID_PATTERN),
    db: AsyncSession = Depends(get_db),
):
    """
    List all chat sessions for a document, newest first.

    The frontend calls this when the user opens a document to show their
    conversation history sidebar.
    """
    stmt = (
        select(ChatSession)
        .where(ChatSession.document_id == uuid.UUID(document_id))
        .order_by(ChatSession.created_at.desc())
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    return [
        SessionResponse(
            session_id=str(s.id),
            document_id=str(s.document_id),
            created_at=str(s.created_at),
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all messages in a session, ordered by creation time.

    The frontend calls this to render the chat history when the user
    opens an existing session.
    """
    # selectinload eagerly loads messages in a single query instead of
    # lazy-loading them one by one (the N+1 problem).
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
