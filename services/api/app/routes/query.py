import asyncio
import uuid

import openai
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document
from app.tools.embeddings import embed_query
from app.tools.llm import answer_with_context
from app.tools.vectorstore import search_document_chunks

router = APIRouter(prefix="/query", tags=["query"])

_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


class QueryRequest(BaseModel):
    document_id: str = Field(..., pattern=_UUID_PATTERN)
    question: str = Field(..., min_length=1)
    # Optional — if not provided, a new session is created automatically.
    session_id: str | None = Field(default=None, pattern=_UUID_PATTERN)
    top_k: int = Field(default=5, ge=1, le=20)
    model: str = Field(default="gpt-4o-mini")


@router.post("")
async def query(
    req: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        # --- 1. Validate document exists and is queryable ---
        doc = await db.get(Document, uuid.UUID(req.document_id))
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        if doc.status != "complete":
            raise HTTPException(
                status_code=409,
                detail=f"Document is not ready (status: {doc.status}).",
            )

        # --- 2. Resolve session (load existing or create new) ---
        if req.session_id:
            stmt = (
                select(ChatSession)
                .where(ChatSession.id == uuid.UUID(req.session_id))
                .options(selectinload(ChatSession.messages))
            )
            result = await db.execute(stmt)
            session = result.scalar_one_or_none()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found.")
        else:
            # Auto-create a session so the caller doesn't need two API calls.
            session = ChatSession(document_id=doc.id)
            db.add(session)
            await db.flush()  # assigns session.id without committing

        # --- 3. Build chat history from existing messages ---
        # For new sessions, messages haven't been loaded from the DB (and there
        # are none). Accessing session.messages would trigger a lazy load, which
        # SQLAlchemy async doesn't support — it raises MissingGreenlet.
        # Only read messages when we loaded an existing session with selectinload.
        if req.session_id and session.messages:
            chat_history = [
                {"role": m.role, "content": m.content}
                for m in session.messages
            ]
        else:
            chat_history = []

        # --- 4. Embed question + search FAISS ---
        qvec = await embed_query(req.question)

        hits = await asyncio.to_thread(
            search_document_chunks,
            document_id=req.document_id,
            query_embedding=qvec,
            top_k=req.top_k,
        )

        # --- 5. Call LLM with context + chat history ---
        chunks = [h["text"] for h in hits]
        answer = await answer_with_context(
            question=req.question,
            chunks=chunks,
            chat_history=chat_history,
            model=req.model,
        )

        # --- 6. Save user message + assistant message ---
        db.add(ChatMessage(session_id=session.id, role="user", content=req.question))
        db.add(ChatMessage(session_id=session.id, role="assistant", content=answer))
        await db.commit()

        # --- 7. Return answer + session_id ---
        return {
            "answer": answer,
            "session_id": str(session.id),
            "chunks_used": hits,
        }

    except HTTPException:
        raise
    except openai.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"LLM service error: {e.message}")
    except openai.APIConnectionError:
        raise HTTPException(status_code=503, detail="Could not reach LLM service. Try again shortly.")
    except openai.RateLimitError:
        raise HTTPException(status_code=429, detail="OpenAI rate limit reached. Slow down requests.")
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Unhandled error in /query")
        raise HTTPException(status_code=500, detail="Internal server error.")
