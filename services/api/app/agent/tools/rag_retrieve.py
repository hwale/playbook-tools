"""
RAG retrieval tool with multi-step search.

For simple questions, behaves like a single-pass search.
For complex questions (multi-faceted, comparisons), decomposes the query
into sub-queries, searches for each independently, and merges results
using Reciprocal Rank Fusion (RRF).

Why RRF over raw distance merging: Sub-queries may have different distance
distributions (one topic might cluster tightly, another might be spread out).
RRF normalizes by rank position, making it robust to scale differences.

Interview note: "This is scatter-gather retrieval. Fan out N sub-queries
in parallel, gather results, merge with rank fusion. Same pattern as
federated search in Elasticsearch or multi-index queries in Solr."
"""
import asyncio
from collections import defaultdict

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.tools.embeddings import embed_query, embed_texts
from app.tools.query_decompose import decompose_query
from app.tools.vectorstore import search_document_chunks


class _RagInput(BaseModel):
    query: str = Field(
        description="What to search for. Be specific — e.g. 'sniper rifle charge system' rather than 'weapons'."
    )
    top_k: int = Field(default=5, description="Number of document chunks to retrieve.")


def _reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion.

    RRF score for a document d = sum over all lists of 1 / (k + rank(d))
    where k is a smoothing constant (default 60, standard in literature).

    Returns results sorted by descending RRF score, deduplicated by chunk text.
    """
    scores: dict[str, float] = defaultdict(float)
    chunks: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, hit in enumerate(ranked_list):
            text = hit["text"]
            scores[text] += 1.0 / (k + rank + 1)
            # Keep the hit with the best (lowest) distance for metadata.
            if text not in chunks or hit["distance"] < chunks[text]["distance"]:
                chunks[text] = hit

    # Sort by RRF score descending.
    sorted_texts = sorted(scores.keys(), key=lambda t: scores[t], reverse=True)

    return [chunks[t] for t in sorted_texts]


def make_rag_tool(document_id: str, document_description: str = "the uploaded document") -> StructuredTool:
    """
    Returns a LangChain StructuredTool with multi-step search capability.

    For simple queries: single embedding search (no extra latency).
    For complex queries: decompose → parallel search → RRF merge.
    """
    description = (
        f"Search {document_description} for information relevant to the query. "
        "Use this when the question is about THIS document's specific content — "
        "its systems, data, decisions, or anything documented in the uploaded file. "
        "Do NOT use this for questions about external sources or general knowledge. "
        "Returns relevant text excerpts from the document, separated by ---"
    )

    async def rag_retrieve(query: str, top_k: int = 5) -> str:
        # Step 1: Decompose the query into sub-queries.
        sub_queries = await decompose_query(query)

        if len(sub_queries) == 1:
            # Simple query — single-pass search, no extra overhead.
            vec = await embed_query(sub_queries[0])
            hits = await asyncio.to_thread(
                search_document_chunks,
                document_id=document_id,
                query_embedding=vec,
                top_k=top_k,
            )
        else:
            # Multi-step: embed all sub-queries in one batch, search each,
            # merge with RRF.
            embeddings = await embed_texts(sub_queries)

            # Fan out searches in parallel via thread pool.
            search_tasks = [
                asyncio.to_thread(
                    search_document_chunks,
                    document_id=document_id,
                    query_embedding=emb,
                    # Over-fetch per sub-query so RRF has enough candidates.
                    top_k=top_k * 2,
                )
                for emb in embeddings
            ]
            ranked_lists = await asyncio.gather(*search_tasks)

            # Merge and deduplicate via Reciprocal Rank Fusion.
            hits = _reciprocal_rank_fusion(ranked_lists)[:top_k]

        if not hits:
            return "No relevant content found in the document."

        chunks = [h["text"] for h in hits]
        return "\n\n---\n\n".join(chunks)

    return StructuredTool.from_function(
        coroutine=rag_retrieve,
        name="rag_retrieve",
        description=description,
        args_schema=_RagInput,
    )
