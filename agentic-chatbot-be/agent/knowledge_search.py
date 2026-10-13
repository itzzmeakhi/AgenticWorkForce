import hashlib
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _kb_fingerprint() -> str:
    """Short hash of the knowledge-base files (name, size, last-modified).
    It changes whenever a file in data/knowledge_base/ is edited, added or removed."""
    from config import KNOWLEDGE_BASE_DIR

    h = hashlib.sha1()
    for f in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        st = f.stat()
        h.update(f"{f.name}:{st.st_size}:{st.st_mtime_ns}".encode())
    return h.hexdigest()


class ChromaBackend:
    """Offline knowledge search backend -- zero API keys needed. See
    agent/offline_embeddings.py for why this is a hashed bag-of-words
    embedding rather than a downloaded sentence-transformers model."""

    def __init__(self):
        import chromadb

        from agent.offline_embeddings import HashedBagOfWordsEmbedding
        from config import CHROMA_STORE_DIR

        CHROMA_STORE_DIR.mkdir(parents=True, exist_ok=True)
        self._fingerprint_file = CHROMA_STORE_DIR / "kb_fingerprint.txt"
        self._client = chromadb.PersistentClient(path=str(CHROMA_STORE_DIR))
        self._embed_fn = HashedBagOfWordsEmbedding()
        self._collection = self._client.get_or_create_collection(
            name="knowledge_base", embedding_function=self._embed_fn
        )

    def index_chunks(self, ids, docs, metadatas, force: bool = False):
        if force:
            try:
                self._client.delete_collection("knowledge_base")
            except Exception:
                pass
            self._collection = self._client.get_or_create_collection(
                name="knowledge_base", embedding_function=self._embed_fn
            )
        if self._collection.count() > 0 and not force:
            return self._collection.count()
        if ids:
            self._collection.add(ids=ids, documents=docs, metadatas=metadatas)
        # Remember which version of the knowledge files this index was built from.
        self._fingerprint_file.write_text(_kb_fingerprint())
        return len(ids)

    def _reindex_if_files_changed(self):
        """Auto-refresh: rebuild the index if the knowledge files changed since
        it was last built (or if the index is empty). Cheap: just a few file stats."""
        saved = self._fingerprint_file.read_text() if self._fingerprint_file.exists() else ""
        if saved == _kb_fingerprint() and self._collection.count() > 0:
            return
        from ingestion.local_index import build_local_index

        logger.info("Knowledge base changed - re-indexing")
        build_local_index(force=True)

    def retrieve(self, query: str, top_k: int = 5, domain: Optional[str] = None) -> List[Dict]:
        self._reindex_if_files_changed()
        where = {"domain": {"$in": [domain, "general"]}} if domain in ("ecommerce", "insurance") else None
        results = self._collection.query(query_texts=[query], n_results=top_k, where=where)
        hits = []
        if not results["documents"] or not results["documents"][0]:
            return hits
        for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
            hits.append({"text": doc, "source": meta["source"], "domain": meta["domain"], "score": 1 - dist})
        return hits


_backend = None


def get_backend() -> ChromaBackend:
    """Return the process-wide cached knowledge backend. Cached at module
    level for the same reason the full build caches its backend: a fresh
    PersistentClient() on every call is wasteful and, on some platforms,
    crashes on repeated construction (the bug fixed in the earlier
    mid-sem build's app/rag/retriever.py, applied here from the start)."""
    global _backend
    if _backend is None:
        logger.info("Using offline ChromaDB knowledge backend")
        _backend = ChromaBackend()
    return _backend
