import asyncio

from langchain_core.tools import tool

from app.tools.embeddings import embed_query
from app.tools.vectorstore import search_document_chunks


def make_rag_tool(document_id: str):
    """
    Returns a LangChain tool with document_id bound via closure.

    Why a closure instead of a parameter in the tool schema:
      The LLM should not need to know or remember the document_id — that's
      infrastructure context, not a reasoning decision. By binding it here,
      the LLM only sees `query` in the tool's input schema, which keeps the
      tool description clean and prevents the LLM from getting confused about
      what to pass.

    Interview note: "We separate agent-visible interface from system context.
    The LLM reasons about WHAT to search, not WHERE the index lives."
    """
    @tool
    async def rag_retrieve(query: str, top_k: int = 5) -> str:
        """
        Search the uploaded game design document for information relevant to the query.
        Use this whenever you need to understand the game's specific systems, mechanics,
        or design decisions before giving advice or generating content.

        Args:
            query: What to search for. Be specific — e.g. "sniper rifle charge system"
                   rather than just "weapons".
            top_k: Number of document chunks to retrieve (default 5).

        Returns:
            Relevant text excerpts from the GDD, separated by ---
        """
        vec = await embed_query(query)

        # search_document_chunks is synchronous (FAISS is CPU-bound).
        # asyncio.to_thread runs it in a thread pool so we don't block the event loop.
        hits = await asyncio.to_thread(
            search_document_chunks,
            document_id=document_id,
            query_embedding=vec,
            top_k=top_k,
        )

        if not hits:
            return "No relevant content found in the document."

        chunks = [h["text"] for h in hits]
        return "\n\n---\n\n".join(chunks)

    return rag_retrieve
