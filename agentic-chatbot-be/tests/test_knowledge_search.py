"""Tests for the offline (ChromaDB) knowledge backend -- the only backend
this milestone has (see README "What's WIP" for the Pinecone production
path added in the full build)."""
from ingestion.local_index import build_local_index


def test_build_local_index_indexes_chunks(isolated_chroma_store):
    n = build_local_index(force=True)
    assert n > 0


def test_retrieve_returns_relevant_hits(isolated_chroma_store):
    from agent.knowledge_search import get_backend

    build_local_index(force=True)
    backend = get_backend()
    hits = backend.retrieve("how long does shipping take", top_k=3)
    assert len(hits) > 0
    assert any("shipping" in h["text"].lower() or "delivery" in h["text"].lower() for h in hits)


def test_get_backend_is_cached_singleton(isolated_chroma_store):
    from agent.knowledge_search import get_backend

    b1 = get_backend()
    b2 = get_backend()
    assert b1 is b2
