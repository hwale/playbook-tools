from io import BytesIO

from pypdf import PdfReader


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Extract text from a PDF (digital PDFs).
    Note: scanned PDFs require OCR later (phase 2).
    """
    reader = PdfReader(BytesIO(pdf_bytes))
    parts: list[str] = []

    for page in reader.pages:
        txt = page.extract_text() or ""
        if txt.strip():
            parts.append(txt)

    return "\n\n".join(parts).strip()


def extract_pages_from_pdf_bytes(pdf_bytes: bytes, pages: list[int] | None = None) -> str:
    """
    Extract text from specific pages of a PDF (1-indexed).

    Args:
        pdf_bytes: Raw PDF bytes.
        pages: 1-indexed page numbers to extract. None means all pages.

    Returns:
        Extracted text with page headers, e.g. "--- Page 2 ---\n<text>"
    """
    reader = PdfReader(BytesIO(pdf_bytes))
    total = len(reader.pages)

    if pages is None:
        indices = range(total)
    else:
        # Clamp and convert from 1-indexed to 0-indexed
        indices = [p - 1 for p in pages if 1 <= p <= total]

    parts: list[str] = []
    for i in indices:
        txt = reader.pages[i].extract_text() or ""
        if txt.strip():
            parts.append(f"--- Page {i + 1} ---\n{txt.strip()}")

    return "\n\n".join(parts) if parts else "No text found on the requested pages."