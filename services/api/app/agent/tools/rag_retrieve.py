import asyncio

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.tools.embeddings import embed_query
from app.tools.vectorstore import search_document_chunks


class _RagInput(BaseModel):
    query: str = Field(
        description="What to search for. Be specific — e.g. 'sniper rifle charge system' rather than 'weapons'."
    )
    top_k: int = Field(default=5, description="Number of document chunks to retrieve.")


def make_rag_tool(document_id: str, document_description: str = "the uploaded document") -> StructuredTool:
    """
    Returns a LangChain StructuredTool with document_id bound via closure and
    a description that is dynamically built from the playbook's document_description.

    Why StructuredTool instead of @tool:
      @tool reads the function docstring at decoration time — you can't inject a
      runtime string into it. StructuredTool.from_function accepts an explicit
      `description` parameter, so we can build it from the playbook's context.

    Why document_id is not in the tool schema:
      The LLM reasons about WHAT to search, not WHERE the index lives. Binding
      document_id in the closure keeps the LLM-visible schema minimal and prevents
      the model from second-guessing which document to query.
    """
    description = (
        f"Search {document_description} for information relevant to the query. "
        "Use this when the question is about THIS document's specific content — "
        "its systems, data, decisions, or anything documented in the uploaded file. "
        "Do NOT use this for questions about external sources or general knowledge. "
        "Returns relevant text excerpts from the document, separated by ---"
    )

    async def rag_retrieve(query: str, top_k: int = 5) -> str:
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

    return StructuredTool.from_function(
        coroutine=rag_retrieve,
        name="rag_retrieve",
        description=description,
        args_schema=_RagInput,
    )
