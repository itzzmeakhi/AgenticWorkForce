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


def test_insurance_documents_are_indexed_under_the_insurance_domain(isolated_chroma_store):
    from agent.knowledge_search import get_backend

    build_local_index(force=True)
    hits = get_backend().retrieve("how long does a claim take to be reviewed", top_k=5, domain="insurance")
    assert hits and all(h["source"].startswith(("insurance_", "general_")) for h in hits)
    assert any(h["source"] == "insurance_claims_process.md" for h in hits)


def test_ecommerce_questions_do_not_pull_insurance_documents(isolated_chroma_store):
    from agent.knowledge_search import get_backend

    build_local_index(force=True)
    hits = get_backend().retrieve("how long does a refund take", top_k=5, domain="ecommerce")
    assert hits and not any(h["source"].startswith("insurance_") for h in hits)


def test_premium_and_coverage_topics_are_retrievable(isolated_chroma_store):
    from agent.knowledge_search import get_backend

    build_local_index(force=True)
    backend = get_backend()
    grace = backend.retrieve("grace period for missed premium", top_k=3, domain="insurance")
    assert any(h["source"] == "insurance_premiums_and_renewals.md" for h in grace)
    excl = backend.retrieve("what is excluded from coverage", top_k=3, domain="insurance")
    assert any(h["source"] == "insurance_coverage_and_exclusions.md" for h in excl)
