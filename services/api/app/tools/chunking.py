def chunk_text(text: str, *, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    """
    Simple character-based chunking.
    - chunk_size: max chars per chunk
    - overlap: chars to overlap for context continuity
    """
    text = (text or "").strip()
    if not text:
        return []

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = end - overlap

    return chunks