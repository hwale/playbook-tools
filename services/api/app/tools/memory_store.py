"""
FAISS vector store for cross-session Q&A memory.

Separate from the document chunk index (vectorstore.py) because the metadata
schemas are fundamentally different: document chunks have (text, doc_id),
while Q&A memories have (question, user_id, session_id, msg_ids).

Same architecture: FAISS IndexFlatL2 + JSON metadata sidecar.
Same post-filter pattern: over-fetch, then filter by user_id.

Interview note: "This is retrieval-augmented memory — the same principle as
RAG for documents, but applied to the user's own conversation history.
The vector index acts as a semantic cache of past interactions, enabling
cross-session context without loading all prior conversations."
"""
import json
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np

from app.core.config import get_settings

_EMBEDDING_DIM = 1536


class _MemoryStore:
    """In-process FAISS index for Q&A memory vectors + JSON metadata sidecar."""

    def __init__(self, data_dir: Path, dimension: int = _EMBEDDING_DIM):
        self.data_dir = data_dir
        self.dimension = dimension
        self.index_path = data_dir / "index.faiss"
        self.meta_path = data_dir / "metadata.json"
        self._load()

    def _load(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if self.index_path.exists() and self.meta_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            self.meta = json.loads(self.meta_path.read_text())
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.meta = {
                "questions": [],
                "user_ids": [],
                "session_ids": [],
                "user_msg_ids": [],
                "asst_msg_ids": [],
            }

    def _save(self) -> None:
        faiss.write_index(self.index, str(self.index_path))
        self.meta_path.write_text(json.dumps(self.meta))

    def add(
        self,
        *,
        user_id: str,
        session_id: str,
        question: str,
        user_msg_id: str,
        asst_msg_id: str,
        embedding: list[float],
    ) -> None:
        vector = np.array([embedding], dtype=np.float32)
        self.index.add(vector)

        self.meta["questions"].append(question)
        self.meta["user_ids"].append(user_id)
        self.meta["session_ids"].append(session_id)
        self.meta["user_msg_ids"].append(user_msg_id)
        self.meta["asst_msg_ids"].append(asst_msg_id)
        self._save()

    def search(
        self,
        query_embedding: list[float],
        user_id: str,
        top_k: int = 3,
        max_distance: float = 0.8,
    ) -> list[dict]:
        """
        Return up to top_k Q&A memories for user_id whose L2 distance is
        <= max_distance.

        Tighter threshold than document search (0.8 vs 1.0) because we want
        only genuinely similar past questions, not vaguely related ones.
        """
        if self.index.ntotal == 0:
            return []

        qvec = np.array([query_embedding], dtype=np.float32)

        # Over-fetch to account for post-filtering by user_id.
        n_search = min(self.index.ntotal, top_k * 20)
        distances, indices = self.index.search(qvec, n_search)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            if float(dist) > max_distance:
                break
            if self.meta["user_ids"][idx] == user_id:
                results.append({
                    "question": self.meta["questions"][idx],
                    "session_id": self.meta["session_ids"][idx],
                    "user_msg_id": self.meta["user_msg_ids"][idx],
                    "asst_msg_id": self.meta["asst_msg_ids"][idx],
                    "distance": float(dist),
                })
                if len(results) >= top_k:
                    break

        return results


@lru_cache
def _get_store() -> _MemoryStore:
    settings = get_settings()
    return _MemoryStore(data_dir=settings.faiss_memory_dir)


# --- Public API ---


def upsert_memory(
    *,
    user_id: str,
    session_id: str,
    question: str,
    user_msg_id: str,
    asst_msg_id: str,
    embedding: list[float],
) -> None:
    _get_store().add(
        user_id=user_id,
        session_id=session_id,
        question=question,
        user_msg_id=user_msg_id,
        asst_msg_id=asst_msg_id,
        embedding=embedding,
    )


def search_memory(
    *,
    user_id: str,
    query_embedding: list[float],
    top_k: int = 3,
) -> list[dict]:
    return _get_store().search(query_embedding, user_id, top_k)
