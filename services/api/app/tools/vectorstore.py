from pathlib import Path
import chromadb

DATA_DIR = Path("/repo/.data/chroma")
DATA_DIR.mkdir(parents=True, exist_ok=True)

_client = chromadb.PersistentClient(path=str(DATA_DIR))

def get_collection(name: str = "documents_v1"):
    return _client.get_or_create_collection(name=name)

def upsert_document_chunks(
    *,
    document_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
):
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must be the same length")

    col = get_collection()

    ids = [f"{document_id}:{i}" for i in range(len(chunks))]
    metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]

    col.upsert(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)

def search_document_chunks(
    *,
    document_id: str,
    query_embedding: list[float],
    top_k: int = 5,
):
    col = get_collection()

    res = col.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"document_id": document_id},
        include=["documents", "distances", "metadatas"],
    )

    # Chroma returns lists-of-lists (one list per query)
    docs = (res.get("documents") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    results = []
    for text, dist in zip(docs, dists):
        # distance - lower is closer
        results.append({"text": text, "distance": float(dist)})

    return results