import logging

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.agent.playbooks import PLAYBOOKS

logger = logging.getLogger(__name__)

# Confidence threshold below which we fall back to the "general" playbook.
# 0.6 means: "I'm at least 60% sure this matches" — below that, be safe.
_CONFIDENCE_THRESHOLD = 0.6
_FALLBACK_PLAYBOOK = "general"


class _PlaybookSelection(BaseModel):
    playbook: str = Field(description="The name of the most appropriate playbook.")
    confidence: float = Field(
        description="Confidence score between 0.0 (no match) and 1.0 (perfect match).",
        ge=0.0,
        le=1.0,
    )


async def classify_playbook(query: str) -> str:
    """
    Uses a fast LLM call (gpt-4o-mini) to select the best playbook for the query.

    Interview-ready mental model:
      This is a single-label classifier with a confidence gate. We pass the
      query and a list of (name, description) pairs to the LLM and ask it to
      return structured JSON. If confidence is below the threshold, we fall back
      to the 'general' playbook rather than risk a bad tool-set being loaded.

    Why LLM classification instead of embedding cosine similarity:
      Playbook descriptions are short (1-2 sentences). Semantic similarity on
      short text is noisy. An LLM can reason about intent — e.g., "analyze this
      P&L statement" maps to a finance playbook even if 'finance' isn't in the
      query. The extra ~200ms latency is acceptable for a routing call.

    Why not hardcode a keyword map:
      Keywords break as soon as domain vocabulary overlaps (e.g. 'balance' in
      game design vs. 'balance sheet' in finance). LLM intent classification
      is more robust.
    """
    if not PLAYBOOKS:
        return _FALLBACK_PLAYBOOK

    # Build the option list shown to the classifier LLM.
    descriptions = "\n".join(
        f"- {name}: {p.description or 'No description.'}"
        for name, p in PLAYBOOKS.items()
        if name != _FALLBACK_PLAYBOOK  # exclude the fallback from selection options
    )

    if not descriptions.strip():
        # Only the fallback playbook is available — nothing to classify against.
        return _FALLBACK_PLAYBOOK

    prompt = (
        "You are a routing agent. Select the most appropriate playbook for the "
        "user's query based on the descriptions below. If no playbook is a good "
        "match, use 'general'.\n\n"
        f"Available playbooks:\n{descriptions}\n\n"
        f"User query: \"{query}\"\n\n"
        "Return the playbook name and your confidence (0.0–1.0)."
    )

    try:
        model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured = model.with_structured_output(_PlaybookSelection)
        result: _PlaybookSelection = await structured.ainvoke(prompt)

        # Validate: the returned name must be a real registered playbook.
        if result.playbook not in PLAYBOOKS:
            logger.warning(
                "Classifier returned unknown playbook %r — falling back to general",
                result.playbook,
            )
            return _FALLBACK_PLAYBOOK

        if result.confidence < _CONFIDENCE_THRESHOLD:
            logger.debug(
                "Classifier confidence %.2f below threshold for %r — using general",
                result.confidence,
                result.playbook,
            )
            return _FALLBACK_PLAYBOOK

        logger.debug("Routed query to playbook %r (confidence %.2f)", result.playbook, result.confidence)
        return result.playbook

    except Exception:
        logger.exception("Playbook classification failed — falling back to general")
        return _FALLBACK_PLAYBOOK
