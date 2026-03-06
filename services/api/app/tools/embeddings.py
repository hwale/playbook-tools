from app.core.config import get_openai_client


async def embed_texts(
    texts: list[str],
    *,
    model: str = "text-embedding-3-small",
) -> list[list[float]]:
    """
    Returns one embedding vector per input string.

    Batches all texts in a single API call — OpenAI supports up to 2048 inputs
    per request, so this is efficient for typical document chunk counts.
    """
    if not texts:
        return []

    client = get_openai_client()
    resp = await client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in resp.data]


async def embed_query(
    text: str,
    *,
    model: str = "text-embedding-3-small",
) -> list[float]:
    vecs = await embed_texts([text], model=model)
    return vecs[0]
