"""
Query decomposition — breaks complex questions into simpler sub-queries
for multi-step retrieval.

Why decompose: A single embedding search for "compare Google's revenue growth
to their R&D spending trend" won't match chunks about both topics well.
Splitting into ["Google revenue growth", "Google R&D spending trend"] lets
us search for each independently and merge the results.

When NOT to decompose: Simple, focused questions ("What was total revenue?")
don't benefit from decomposition — they'd just produce one sub-query identical
to the original. The LLM is instructed to return the original query as-is
for simple questions.

Interview note: "This is query fan-out — the same principle as scatter-gather
in distributed systems. Fan out N sub-queries, gather results, merge with
rank fusion. The tradeoff is N extra embedding calls + one LLM call for
decomposition, but the retrieval quality improvement is substantial for
multi-faceted questions."
"""
import logging

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DecomposedQueries(BaseModel):
    """Structured output: list of sub-queries."""
    queries: list[str] = Field(
        description="1-3 focused sub-queries that together cover the original question. "
                    "For simple questions, return a single-element list with the original query."
    )


_DECOMPOSE_PROMPT = """\
You are a search query optimizer. Given a user's question, break it into 1-3 \
focused sub-queries that will retrieve the most relevant document chunks.

Rules:
- If the question is simple and focused, return it as-is (single query).
- If the question asks about multiple topics, split into separate sub-queries.
- If the question involves comparison, create one sub-query per item being compared.
- Each sub-query should be a short, specific search phrase (not a full sentence).
- Max 3 sub-queries to keep retrieval cost bounded.

Examples:
- "What was the total revenue?" → ["total revenue"]
- "Compare revenue growth to profit margins" → ["revenue growth", "profit margins"]
- "What are the risk factors and how do they affect guidance?" → ["risk factors", "guidance outlook"]
- "Tell me about the weapons system" → ["weapons system"]"""


async def decompose_query(question: str) -> list[str]:
    """
    Use a cheap LLM call to split a complex question into sub-queries.
    Falls back to the original question on any error.
    """
    try:
        model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured = model.with_structured_output(DecomposedQueries)
        result: DecomposedQueries = await structured.ainvoke([
            {"role": "system", "content": _DECOMPOSE_PROMPT},
            {"role": "user", "content": question},
        ])
        queries = [q.strip() for q in result.queries if q.strip()]
        if not queries:
            return [question]
        logger.info("Decomposed '%s' into %d sub-queries: %s", question, len(queries), queries)
        return queries
    except Exception:
        logger.exception("Query decomposition failed, using original query")
        return [question]
