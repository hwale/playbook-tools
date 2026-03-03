import os
from openai import OpenAI

_api_key = os.environ.get("OPENAI_API_KEY")
if not _api_key:
    raise RuntimeError("OPENAI_API_KEY is not set")

_client = OpenAI(api_key=_api_key)

def answer_with_context(
    *,
    question: str,
    chunks: list[str],
    model: str = "gpt-4o-mini",
) -> str:
    context = "\n\n---\n\n".join(chunks)

    system = (
        "You are a helpful assistant. Answer using ONLY the provided context. "
        "If the answer is not in the context, say you don't know."
    )

    user = f"""CONTEXT:
{context}

QUESTION:
{question}
"""

    resp = _client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )

    return resp.choices[0].message.content or ""