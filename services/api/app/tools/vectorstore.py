"""
FAISS vector store with JSON metadata sidecar.

FAISS is a C++ library for similarity search — it stores vectors and finds
nearest neighbors, but has zero concept of metadata, document IDs, or filtering.
We manage chunk text and document_id mapping in a JSON file alongside the index.

Key limitation: FAISS can't filter by document_id during search. We over-fetch
results across ALL documents, then post-filter to keep only the requested doc's
chunks. This works well at small-to-medium scale (<100K vectors). At larger scale,
you'd switch to per-document indexes, a native filtering vector DB (pgvector,
Qdrant), or FAISS's IDSelector API.

Interview note: "FAISS trades metadata awareness for raw search speed. In a
single-node deployment it's excellent. The constraint is post-hoc filtering —
you pay for searching vectors you'll discard. At scale, you either partition
the index or move to a vector database with native filtering."
"""
import json
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np

from app.core.config import get_settings

# OpenAI text-embedding-3-small produces 1536-dimensional vectors.
_EMBEDDING_DIM = 1536


class _FAISSStore:
    """In-process FAISS index + JSON metadata, persisted to disk."""

    def __init__(self, data_dir: Path, dimension: int = _EMBEDDING_DIM):
        self.data_dir = data_dir
        self.dimension = dimension
        self.index_path = data_dir / "index.faiss"
        self.meta_path = data_dir / "metadata.json"
        self._load()

    def _load(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if self.index_path.exists() and self.meta_path.exists():
            # Restore from disk — picks up where we left off after a restart.
            self.index = faiss.read_index(str(self.index_path))
            self.meta = json.loads(self.meta_path.read_text())
        else:
            # IndexFlatL2 = brute-force L2 (Euclidean) distance search.
            # No approximation — compares the query against every vector.
            # Fast enough for <100K vectors. For larger indexes, switch to
            # IndexIVFFlat (partitioned search) or IndexHNSW (graph-based).
            self.index = faiss.IndexFlatL2(self.dimension)
            self.meta = {"chunks": [], "doc_ids": []}

    def _save(self) -> None:
        faiss.write_index(self.index, str(self.index_path))
        self.meta_path.write_text(json.dumps(self.meta))

    def add(
        self,
        document_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        # numpy array with float32 — FAISS requires this exact dtype.
        vectors = np.array(embeddings, dtype=np.float32)
        self.index.add(vectors)

        # Mirror the metadata — position N in the FAISS index corresponds
        # to position N in these lists. This is the "sidecar" pattern:
        # FAISS owns the vectors, we own the text + metadata.
        self.meta["chunks"].extend(chunks)
        self.meta["doc_ids"].extend([document_id] * len(chunks))
        self._save()

    def search(
        self,
        query_embedding: list[float],
        document_id: str,
        top_k: int = 5,
    ) -> list[dict]:
        if self.index.ntotal == 0:
            return []

        qvec = np.array([query_embedding], dtype=np.float32)

        # Over-fetch because we need to post-filter by document_id.
        # If the index has chunks from 10 documents and we want 5 from one doc,
        # we might need to scan deep to find enough matches.
        n_search = min(self.index.ntotal, top_k * 20)
        distances, indices = self.index.search(qvec, n_search)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                # FAISS returns -1 for empty result slots.
                continue
            if self.meta["doc_ids"][idx] == document_id:
                results.append({
                    "text": self.meta["chunks"][idx],
                    "distance": float(dist),
                })
                if len(results) >= top_k:
                    break

        return results


@lru_cache
def _get_store() -> _FAISSStore:
    settings = get_settings()
    return _FAISSStore(data_dir=settings.faiss_dir)


# --- Public API (same signatures as the old ChromaDB version) ---
# documents.py and query.py call these functions and don't know or care
# whether the backend is ChromaDB, FAISS, or pgvector.


def upsert_document_chunks(
    *,
    document_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must be the same length")
    _get_store().add(document_id, chunks, embeddings)


def search_document_chunks(
    *,
    document_id: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    return _get_store().search(query_embedding, document_id, top_k)
