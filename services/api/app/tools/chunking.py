"""
Semantic chunking — splits text on natural boundaries (sections, paragraphs,
sentences) instead of at arbitrary character positions.

Why semantic over character-based:
  Character splits can land mid-sentence ("The total revenue was $4" | "2.3B"),
  producing embeddings that misrepresent the content. Semantic chunking keeps
  coherent units together, improving retrieval precision.

Strategy (split-then-merge):
  1. Split on strong boundaries (double newlines = paragraphs/sections)
  2. Split oversized segments on sentence endings (. ! ?)
  3. Merge small consecutive segments until they approach the target size
  4. Add overlap by repeating the last sentence(s) of the previous chunk

Interview note: "This is a two-pass approach — split coarse, then merge.
It's deterministic, requires no ML model, and handles 90% of real documents
well. The tradeoff vs. model-based chunking (e.g. embedding similarity
between sentences) is speed and simplicity at the cost of missing subtle
topic shifts within a paragraph."
"""
import re


def chunk_text(
    text: str,
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[str]:
    """
    Semantically chunk text by splitting on natural boundaries, then merging
    small segments up to chunk_size. Overlap is created by repeating trailing
    sentences from the previous chunk.
    """
    text = (text or "").strip()
    if not text:
        return []

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    # --- Pass 1: split on strong boundaries (paragraphs / section breaks) ---
    segments = _split_paragraphs(text)

    # --- Pass 2: break oversized segments on sentence boundaries ---
    segments = _split_long_segments(segments, chunk_size)

    # --- Pass 3: merge small consecutive segments up to chunk_size ---
    chunks = _merge_segments(segments, chunk_size)

    # --- Pass 4: add overlap by prepending trailing context from prev chunk ---
    if overlap > 0 and len(chunks) > 1:
        chunks = _add_overlap(chunks, overlap)

    return chunks


def _split_paragraphs(text: str) -> list[str]:
    """Split on double newlines (paragraph / section boundaries)."""
    raw = re.split(r"\n\s*\n", text)
    return [seg.strip() for seg in raw if seg.strip()]


def _split_sentences(text: str) -> list[str]:
    """
    Split on sentence endings (. ! ?) followed by whitespace or end-of-string.
    Keeps the delimiter attached to the sentence.
    """
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in parts if s.strip()]


def _split_long_segments(segments: list[str], max_size: int) -> list[str]:
    """Break any segment longer than max_size into sentence-level pieces."""
    result = []
    for seg in segments:
        if len(seg) <= max_size:
            result.append(seg)
        else:
            sentences = _split_sentences(seg)
            for sent in sentences:
                if len(sent) <= max_size:
                    result.append(sent)
                else:
                    # Last resort: hard split on max_size for very long
                    # run-on text (e.g. tables with no punctuation).
                    for i in range(0, len(sent), max_size):
                        piece = sent[i : i + max_size].strip()
                        if piece:
                            result.append(piece)
    return result


def _merge_segments(segments: list[str], max_size: int) -> list[str]:
    """Greedily merge consecutive segments until adding the next would exceed max_size."""
    if not segments:
        return []

    chunks: list[str] = []
    current = segments[0]

    for seg in segments[1:]:
        combined = current + "\n\n" + seg
        if len(combined) <= max_size:
            current = combined
        else:
            chunks.append(current.strip())
            current = seg

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _add_overlap(chunks: list[str], overlap: int) -> list[str]:
    """
    Prepend the trailing ~overlap characters of the previous chunk, breaking
    at a sentence boundary so we don't start mid-word.
    """
    result = [chunks[0]]

    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        if len(prev) <= overlap:
            tail = prev
        else:
            # Take the last `overlap` chars, then find the first sentence
            # start (after a period+space) to avoid a partial sentence.
            tail_raw = prev[-overlap:]
            sent_break = re.search(r"[.!?]\s+", tail_raw)
            if sent_break:
                tail = tail_raw[sent_break.end():]
            else:
                # No sentence break found — use a word boundary instead.
                word_break = tail_raw.find(" ")
                tail = tail_raw[word_break + 1:] if word_break != -1 else tail_raw

        if tail.strip():
            result.append(tail.strip() + "\n\n" + chunks[i])
        else:
            result.append(chunks[i])

    return result
