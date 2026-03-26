"""
Cross-session long-term memory service.

Orchestrates two flows:
  Write: question → embed → FAISS memory index (with msg ID pointers)
  Read:  question → embed → search FAISS → hydrate Q&A from PostgreSQL → format

The memory store holds vectors + metadata pointers (message IDs).
The actual Q&A content lives in PostgreSQL (single source of truth).
This separation keeps the FAISS sidecar file small and avoids data duplication.
"""
import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage
from app.tools.embeddings import embed_query
from app.tools.memory_store import search_memory, upsert_memory

logger = logging.getLogger(__name__)


async def store_qa_memory(
    db: AsyncSession,
    *,
    user_id: str,
    session_id: str,
    question: str,
    user_msg_id: str,
    asst_msg_id: str,
) -> None:
    """Embed the user's question and store it in the memory FAISS index."""
    embedding = await embed_query(question)
    await asyncio.to_thread(
        upsert_memory,
        user_id=user_id,
        session_id=session_id,
        question=question,
        user_msg_id=user_msg_id,
        asst_msg_id=asst_msg_id,
        embedding=embedding,
    )


async def retrieve_long_term_memory(
    db: AsyncSession,
    *,
    user_id: str,
    question: str,
    current_session_id: str | None = None,
    top_k: int = 3,
) -> list[dict]:
    """
    Search the memory index for similar past questions, then hydrate the
    full Q&A pairs from PostgreSQL.

    Returns: [{"question": str, "answer": str, "distance": float}, ...]

    Excludes hits from current_session_id to avoid self-referencing
    (the agent already has this session's history in context).
    """
    embedding = await embed_query(question)

    # Over-request so we still have top_k after filtering out current session.
    hits = await asyncio.to_thread(
        search_memory,
        user_id=user_id,
        query_embedding=embedding,
        top_k=top_k + 2,
    )

    if current_session_id:
        hits = [h for h in hits if h["session_id"] != current_session_id]
    hits = hits[:top_k]

    if not hits:
        return []

    # Batch-fetch all referenced messages in one query.
    msg_ids = []
    for h in hits:
        msg_ids.append(uuid.UUID(h["user_msg_id"]))
        msg_ids.append(uuid.UUID(h["asst_msg_id"]))

    stmt = select(ChatMessage).where(ChatMessage.id.in_(msg_ids))
    result = await db.execute(stmt)
    messages_by_id = {str(m.id): m for m in result.scalars().all()}

    memories = []
    for h in hits:
        user_msg = messages_by_id.get(h["user_msg_id"])
        asst_msg = messages_by_id.get(h["asst_msg_id"])
        if user_msg and asst_msg:
            memories.append({
                "question": user_msg.content,
                "answer": asst_msg.content,
                "distance": h["distance"],
            })

    return memories


def format_memory_context(memories: list[dict]) -> str:
    """Format retrieved memories as a system prompt section."""
    if not memories:
        return ""

    lines = [
        "## Long-Term Memory (from past conversations)",
        "The following are relevant Q&A pairs from your previous sessions "
        "with this user. Use them as context if helpful, but prioritize "
        "the current document and conversation.\n",
    ]
    for i, m in enumerate(memories, 1):
        lines.append(f"### Memory {i}")
        lines.append(f"**User asked:** {m['question']}")
        lines.append(f"**Answer was:** {m['answer']}\n")

    return "\n".join(lines)
