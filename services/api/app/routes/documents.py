import asyncio
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db import get_db
from app.models.document import Document
from app.tools.chunking import chunk_text
from app.tools.embeddings import embed_texts
from app.tools.pdf import extract_text_from_pdf_bytes
from app.tools.vectorstore import upsert_document_chunks

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are supported.")

    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    document_id = uuid.uuid4()

    # --- Create the DB record immediately as "processing" ---
    # This means the frontend can poll for status right away,
    # and if anything below fails, the record shows "failed" with an error
    # rather than just disappearing.
    doc = Document(
        id=document_id,
        filename=file.filename,
        status="processing",
    )
    db.add(doc)
    await db.commit()

    # --- Process the PDF — update status on success or failure ---
    try:
        pdf_bytes = await file.read()
        pdf_path = upload_dir / f"{document_id}.pdf"
        await asyncio.to_thread(pdf_path.write_bytes, pdf_bytes)

        text = extract_text_from_pdf_bytes(pdf_bytes)
        if not text:
            raise ValueError(
                "No extractable text found. This may be a scanned PDF (OCR not implemented yet)."
            )

        chunks = chunk_text(text, chunk_size=1200, overlap=200)
        if not chunks:
            raise ValueError("Chunking produced no chunks.")

        vectors = await embed_texts(chunks)

        await asyncio.to_thread(
            upsert_document_chunks,
            document_id=str(document_id),
            chunks=chunks,
            embeddings=vectors,
        )

        # Success — update the record.
        doc.status = "complete"
        doc.chunks_indexed = len(chunks)
        await db.commit()

    except Exception as exc:
        # Failure — persist the error so the user knows what went wrong.
        doc.status = "failed"
        doc.error = str(exc)
        await db.commit()
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "document_id": str(document_id),
        "chunks_indexed": len(chunks),
        "status": "complete",
    }


@router.get("")
async def list_documents(db: AsyncSession = Depends(get_db)):
    """
    List all uploaded documents, newest first.
    The frontend renders this as the main document list / landing page.
    """
    from sqlalchemy import select

    stmt = select(Document).order_by(Document.created_at.desc())
    result = await db.execute(stmt)
    docs = result.scalars().all()

    return [
        {
            "document_id": str(d.id),
            "filename": d.filename,
            "status": d.status,
            "chunks_indexed": d.chunks_indexed,
            "created_at": str(d.created_at),
        }
        for d in docs
    ]


@router.get("/{document_id}")
async def get_document_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Poll this endpoint to check processing status.
    Frontend calls this after upload to know when the document is ready to query.
    """
    doc = await db.get(Document, uuid.UUID(document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    return {
        "document_id": str(doc.id),
        "filename": doc.filename,
        "status": doc.status,
        "chunks_indexed": doc.chunks_indexed,
        "error": doc.error,
        "created_at": str(doc.created_at),
    }
