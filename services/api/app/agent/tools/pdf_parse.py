import asyncio
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.config import settings
from app.tools.pdf import extract_pages_from_pdf_bytes


class _PdfParseInput(BaseModel):
    pages: list[int] | None = Field(
        default=None,
        description=(
            "1-indexed page numbers to extract (e.g. [1, 2, 3]). "
            "Omit or pass null to extract all pages."
        ),
    )


def make_pdf_parse_tool(document_id: str) -> StructuredTool:
    """
    Returns a LangChain StructuredTool that extracts raw text from an uploaded PDF.

    When to use vs rag_retrieve:
      - rag_retrieve: semantic search — best for "find sections relevant to X"
      - pdf_parse: structural access — best for "give me the exact content of page 3"
        or when the document is short enough to pass directly into context.

    The document_id is bound via closure (same pattern as make_rag_tool) so the
    LLM schema stays minimal — the agent only decides which pages to read.
    """
    upload_dir: Path = settings.upload_dir

    async def pdf_parse(pages: list[int] | None = None) -> str:
        pdf_path = upload_dir / f"{document_id}.pdf"

        if not pdf_path.exists():
            return "The uploaded document is not a PDF or could not be found."

        pdf_bytes = await asyncio.to_thread(pdf_path.read_bytes)
        return await asyncio.to_thread(extract_pages_from_pdf_bytes, pdf_bytes, pages)

    return StructuredTool.from_function(
        coroutine=pdf_parse,
        name="pdf_parse",
        description=(
            "Extract raw text from specific pages of the uploaded PDF. "
            "Use this when you need the exact content of a particular page or section "
            "rather than a semantic search. "
            "Specify page numbers (1-indexed) or omit to get the full document."
        ),
        args_schema=_PdfParseInput,
    )
