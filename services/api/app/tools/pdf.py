from pypdf import PdfReader
from io import BytesIO

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