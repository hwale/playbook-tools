import asyncio
import logging

import openai

from app.core.config import get_openai_client

logger = logging.getLogger(__name__)

# Rough token budget for the context window.
# gpt-4o-mini has a 128K context window, but we cap usage to control cost
# and latency. 12K chars ≈ 3K tokens for chat history is a safe default.
_MAX_HISTORY_CHARS = 12_000


def _trim_chat_history(
    chat_history: list[dict],
    max_chars: int = _MAX_HISTORY_CHARS,
) -> list[dict]:
    """
    Truncate chat history from the oldest messages first to stay within budget.

    Why oldest first: recent messages are more relevant to the current question.
    The user's last few exchanges should always be preserved.

    Returns a new list — doesn't mutate the original.
    """
    if not chat_history:
        return []

    # Walk backwards (newest first), accumulating chars until we hit the limit.
    trimmed: list[dict] = []
    total = 0
    for msg in reversed(chat_history):
        msg_len = len(msg.get("content", ""))
        if total + msg_len > max_chars:
            break
        trimmed.append(msg)
        total += msg_len

    # Reverse back to chronological order.
    trimmed.reverse()
    return trimmed


async def answer_with_context(
    *,
    question: str,
    chunks: list[str],
    chat_history: list[dict] | None = None,
    model: str = "gpt-4o-mini",
    max_retries: int = 1,
) -> str:
    """
    Generate an answer using retrieved chunks and optional chat history.

    The messages array sent to OpenAI looks like:
      [system, *chat_history, user (with context + question)]

    Chat history gives the LLM conversational memory — it can reference
    previous answers and follow-up questions naturally.
    """
    client = get_openai_client()
    context = "\n\n---\n\n".join(chunks)

    system = (
        "You are a helpful assistant. Answer using ONLY the provided context. "
        "If the answer is not in the context, say you don't know. "
        "When referencing information, be specific about where it came from in the context."
    )

    user_msg = f"""CONTEXT:
{context}

QUESTION:
{question}
"""

    # Build the messages array: system → chat history → current question.
    messages: list[dict] = [{"role": "system", "content": system}]

    if chat_history:
        trimmed = _trim_chat_history(chat_history)
        messages.extend(trimmed)

    messages.append({"role": "user", "content": user_msg})

    # Retry loop — one retry on transient failures (network, rate limit).
    # Non-transient errors (bad key, model not found) fail immediately.
    last_error: Exception | None = None
    for attempt in range(1 + max_retries):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
            )
            return resp.choices[0].message.content or ""

        except (openai.APIConnectionError, openai.RateLimitError) as e:
            last_error = e
            if attempt < max_retries:
                # Exponential backoff: wait 1s before retry.
                logger.warning("LLM call failed (attempt %d), retrying: %s", attempt + 1, e)
                await asyncio.sleep(1)
            continue

    # All retries exhausted — re-raise so the route handler can convert to HTTP error.
    raise last_error  # type: ignore[misc]
