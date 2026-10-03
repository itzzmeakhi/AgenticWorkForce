"""
Shared pytest fixtures for the midsem (~60%) build. Same isolation
concerns as the full build's tests/conftest.py, scoped to what this build
actually has: an in-memory e-commerce dataset to reset between tests, and
an isolated offline Chroma store per test.
"""
import os

import pytest

os.environ["LLM_PROVIDER"] = "mock"
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)


@pytest.fixture(autouse=True)
def reset_mock_data():
    """Reset fulfillment_api's in-memory mock dataset before every test so
    a cancel_order in one test never leaks into the next."""
    from fulfillment_api import mock_data

    products, orders = mock_data.initialize_mock_data()
    mock_data.PRODUCTS.clear()
    mock_data.PRODUCTS.update(products)
    mock_data.ORDERS.clear()
    mock_data.ORDERS.update(orders)
    yield


@pytest.fixture
def isolated_chroma_store(tmp_path, monkeypatch):
    """Point the offline knowledge backend at a fresh tmp directory and
    clear its cached singleton, so tests never share index state."""
    import config
    from agent import knowledge_search

    store_dir = tmp_path / "chroma_store"
    monkeypatch.setattr(config, "CHROMA_STORE_DIR", store_dir)
    monkeypatch.setattr(knowledge_search, "_backend", None)
    yield store_dir
    monkeypatch.setattr(knowledge_search, "_backend", None)


@pytest.fixture
def fulfillment_test_client():
    """A Starlette TestClient bound directly to the fulfillment_api FastAPI
    app -- exercises the real REST server code with no network socket."""
    from fastapi.testclient import TestClient

    from fulfillment_api.server import app

    return TestClient(app)
