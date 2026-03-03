from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.tools.embeddings import embed_query
from app.tools.vectorstore import search_document_chunks
from app.tools.llm import answer_with_context

router = APIRouter(prefix="/query", tags=["query"])

class QueryRequest(BaseModel):
    document_id: str
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)

@router.post("")
def query(req: QueryRequest):
    qvec = embed_query(req.question)

    hits = search_document_chunks(
        document_id=req.document_id,
        query_embedding=qvec,
        top_k=req.top_k,
    )

    chunks = [h["text"] for h in hits]
    answer = answer_with_context(question=req.question, chunks=chunks)

    return {
        "answer": answer,
        "chunks_used": hits,
    }