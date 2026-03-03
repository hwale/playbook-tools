import os
from openai import OpenAI

_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def embed_texts(texts: list[str], *, model: str = "text-embedding-3-small") -> list[list[float]]:
    """
    Returns one embedding vector per input string.
    """
    if not texts:
        return []

    resp = _client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in resp.data]

def embed_query(text: str, *, model: str = "text-embedding-3-small") -> list[float]:
    vecs = embed_texts([text], model=model)
    return vecs[0]