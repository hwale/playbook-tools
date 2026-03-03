from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import uuid

from app.tools.pdf import extract_text_from_pdf_bytes
from app.tools.chunking import chunk_text
from app.tools.embeddings import embed_texts
from app.tools.vectorstore import upsert_document_chunks

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = Path("/repo/.data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf is supported in v1")

    document_id = str(uuid.uuid4())
    pdf_path = UPLOAD_DIR / f"{document_id}.pdf"

    pdf_bytes = await file.read()
    pdf_path.write_bytes(pdf_bytes)

    text = extract_text_from_pdf_bytes(pdf_bytes)
    if not text:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found. This may be a scanned PDF (OCR not implemented yet).",
        )

    chunks = chunk_text(text, chunk_size=1200, overlap=200)
    if not chunks:
        raise HTTPException(status_code=422, detail="Chunking produced no chunks")

    vectors = embed_texts(chunks)
    upsert_document_chunks(document_id=document_id, chunks=chunks, embeddings=vectors)

    return {
        "document_id": document_id,
        "chunks_indexed": len(chunks),
    }