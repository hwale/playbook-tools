"""
PDF text extraction with table support and OCR fallback.

Three-tier extraction pipeline:
  1. pdfplumber (primary) — extracts text + tables with layout awareness.
     Tables are converted to markdown format for LLM readability.
  2. AWS Textract (fallback) — for scanned PDFs where pdfplumber finds
     no extractable text. Sends raw bytes to Textract's AnalyzeDocument API,
     which returns OCR'd text + structured table data in one call.
     On EC2, auth is automatic via IAM instance role — no keys needed.
  3. pypdf (lightweight) — last resort fallback.

Why pdfplumber over pypdf for the main pipeline:
  pypdf extracts raw text but has no table awareness — table cells get
  concatenated into unreadable strings. pdfplumber understands table
  structure and returns rows/columns that we format as markdown tables.

Why Textract over Tesseract:
  Tesseract requires system binaries (tesseract-ocr, poppler-utils) which
  bloat the Docker image. Textract is an API call — no binaries, native
  table detection, and on EC2 the auth is free via IAM roles.

Interview note: "This is a cascading extraction strategy — try the
cheapest/fastest method first, fall back to more expensive methods.
Same principle as CDN → origin → cold storage in a caching hierarchy."
"""
import logging
from io import BytesIO

from pypdf import PdfReader

logger = logging.getLogger(__name__)


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Extract text from a PDF using the best available method.
    Tries pdfplumber (with tables) first, falls back to OCR for scanned PDFs.
    """
    # Tier 1: pdfplumber with table extraction
    text = _extract_with_pdfplumber(pdf_bytes)
    if text and len(text.strip()) > 50:
        logger.info("PDF extracted via pdfplumber (%d chars)", len(text))
        return text

    # Tier 2: AWS Textract OCR for scanned PDFs
    ocr_text = _extract_with_ocr(pdf_bytes)
    if ocr_text and len(ocr_text.strip()) > 50:
        logger.info("PDF extracted via Textract OCR (%d chars)", len(ocr_text))
        return ocr_text

    # Tier 3: pypdf as last resort (might get partial text)
    pypdf_text = _extract_with_pypdf(pdf_bytes)
    if pypdf_text:
        logger.info("PDF extracted via pypdf fallback (%d chars)", len(pypdf_text))
        return pypdf_text

    return ""


def extract_pages_from_pdf_bytes(pdf_bytes: bytes, pages: list[int] | None = None) -> str:
    """
    Extract text from specific pages of a PDF (1-indexed).
    Uses pdfplumber for table-aware extraction per page.
    """
    try:
        return _extract_pages_with_pdfplumber(pdf_bytes, pages)
    except Exception:
        logger.warning("pdfplumber page extraction failed, falling back to pypdf")
        return _extract_pages_with_pypdf(pdf_bytes, pages)


# --- Tier 1: pdfplumber (text + tables) ---

def _extract_with_pdfplumber(pdf_bytes: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed, skipping")
        return ""

    try:
        parts: list[str] = []
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                page_parts: list[str] = []

                # Extract tables first, then get remaining text.
                tables = page.extract_tables() or []
                for table in tables:
                    md = _table_to_markdown(table)
                    if md:
                        page_parts.append(md)

                # Extract text (includes non-table text).
                text = page.extract_text() or ""
                if text.strip():
                    page_parts.append(text.strip())

                if page_parts:
                    parts.append(f"--- Page {i + 1} ---\n" + "\n\n".join(page_parts))

        return "\n\n".join(parts).strip()
    except Exception:
        logger.exception("pdfplumber extraction failed")
        return ""


def _extract_pages_with_pdfplumber(pdf_bytes: bytes, pages: list[int] | None = None) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        total = len(pdf.pages)
        if pages is None:
            indices = range(total)
        else:
            indices = [p - 1 for p in pages if 1 <= p <= total]

        for i in indices:
            page = pdf.pages[i]
            page_parts: list[str] = []

            tables = page.extract_tables() or []
            for table in tables:
                md = _table_to_markdown(table)
                if md:
                    page_parts.append(md)

            text = page.extract_text() or ""
            if text.strip():
                page_parts.append(text.strip())

            if page_parts:
                parts.append(f"--- Page {i + 1} ---\n" + "\n\n".join(page_parts))

    return "\n\n".join(parts) if parts else "No text found on the requested pages."


# --- Tier 2: OCR via AWS Textract ---

def _extract_with_ocr(pdf_bytes: bytes) -> str:
    """
    Send the PDF to AWS Textract's AnalyzeDocument API for OCR + table detection.

    Textract accepts raw bytes (up to 10 MB for synchronous API).
    On EC2, boto3 authenticates automatically via the instance's IAM role.
    For local dev, set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY in .env,
    or use `aws configure`.

    Textract limitation: synchronous AnalyzeDocument only handles single-page
    documents. For multi-page PDFs, we use DetectDocumentText which handles
    multi-page but without table structure. For full multi-page + tables,
    you'd need the async StartDocumentAnalysis API (future enhancement).
    """
    try:
        import boto3
    except ImportError:
        logger.warning("boto3 not installed, skipping Textract OCR")
        return ""

    try:
        from app.core.config import get_settings
        settings = get_settings()

        client = boto3.client("textract", region_name=settings.aws_region)

        # Textract synchronous API: supports single-page images or PDFs up to 10MB.
        # For multi-page PDFs, we use detect_document_text which works page-by-page
        # under the hood for simple text extraction.
        response = client.detect_document_text(
            Document={"Bytes": pdf_bytes}
        )

        # Collect LINE blocks (Textract returns WORD and LINE block types).
        lines: list[str] = []
        for block in response.get("Blocks", []):
            if block["BlockType"] == "LINE":
                lines.append(block["Text"])

        text = "\n".join(lines).strip()

        # If we got text, also try AnalyzeDocument for table detection.
        if text and len(pdf_bytes) <= 10 * 1024 * 1024:
            table_text = _extract_tables_with_textract(client, pdf_bytes)
            if table_text:
                text = text + "\n\n" + table_text

        return text

    except Exception:
        logger.exception("Textract OCR extraction failed")
        return ""


def _extract_tables_with_textract(client, pdf_bytes: bytes) -> str:
    """
    Use Textract AnalyzeDocument with TABLES feature to extract structured tables.
    Returns tables formatted as markdown.
    """
    try:
        response = client.analyze_document(
            Document={"Bytes": pdf_bytes},
            FeatureTypes=["TABLES"],
        )

        # Build a map of block IDs for resolving relationships.
        blocks_by_id: dict[str, dict] = {}
        for block in response.get("Blocks", []):
            blocks_by_id[block["Id"]] = block

        tables_md: list[str] = []
        for block in response.get("Blocks", []):
            if block["BlockType"] != "TABLE":
                continue

            # Collect cells for this table.
            cells: dict[tuple[int, int], str] = {}
            max_row = 0
            max_col = 0

            for rel in block.get("Relationships", []):
                if rel["Type"] != "CHILD":
                    continue
                for child_id in rel["Ids"]:
                    child = blocks_by_id.get(child_id, {})
                    if child.get("BlockType") != "CELL":
                        continue

                    row = child.get("RowIndex", 1)
                    col = child.get("ColumnIndex", 1)
                    max_row = max(max_row, row)
                    max_col = max(max_col, col)

                    # Get cell text from WORD children.
                    cell_text = _get_textract_cell_text(child, blocks_by_id)
                    cells[(row, col)] = cell_text

            # Build markdown table.
            if max_row > 0 and max_col > 0:
                rows: list[list[str]] = []
                for r in range(1, max_row + 1):
                    row = [cells.get((r, c), "") for c in range(1, max_col + 1)]
                    rows.append(row)
                md = _table_to_markdown(rows)
                if md:
                    tables_md.append(md)

        return "\n\n".join(tables_md)

    except Exception:
        logger.exception("Textract table analysis failed")
        return ""


def _get_textract_cell_text(cell_block: dict, blocks_by_id: dict) -> str:
    """Extract text from a Textract CELL block by resolving its WORD children."""
    words: list[str] = []
    for rel in cell_block.get("Relationships", []):
        if rel["Type"] != "CHILD":
            continue
        for word_id in rel["Ids"]:
            word_block = blocks_by_id.get(word_id, {})
            if word_block.get("BlockType") == "WORD":
                words.append(word_block.get("Text", ""))
    return " ".join(words)


# --- Tier 3: pypdf (lightweight fallback) ---

def _extract_with_pypdf(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    parts: list[str] = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        if txt.strip():
            parts.append(txt)
    return "\n\n".join(parts).strip()


def _extract_pages_with_pypdf(pdf_bytes: bytes, pages: list[int] | None = None) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    total = len(reader.pages)
    if pages is None:
        indices = range(total)
    else:
        indices = [p - 1 for p in pages if 1 <= p <= total]

    parts: list[str] = []
    for i in indices:
        txt = reader.pages[i].extract_text() or ""
        if txt.strip():
            parts.append(f"--- Page {i + 1} ---\n{txt.strip()}")

    return "\n\n".join(parts) if parts else "No text found on the requested pages."


# --- Table formatting ---

def _table_to_markdown(table: list[list]) -> str:
    """
    Convert a pdfplumber table (list of rows, each row a list of cells)
    to a markdown table string.

    Why markdown: LLMs parse markdown tables natively. They can reference
    specific cells, compute across rows, and compare columns — none of
    which works if table cells are concatenated into a flat string.
    """
    if not table or not table[0]:
        return ""

    # Clean cells — replace None with empty string, strip whitespace.
    cleaned = []
    for row in table:
        cleaned.append([str(cell).strip() if cell else "" for cell in row])

    # First row as header.
    header = cleaned[0]
    separator = ["---"] * len(header)
    body = cleaned[1:]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in body:
        # Pad row if it has fewer cells than header.
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded[:len(header)]) + " |")

    return "\n".join(lines)
