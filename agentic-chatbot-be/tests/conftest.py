"""
Shared pytest fixtures for the midsem (~60%) build. Same isolation
concerns as the full build's tests/conftest.py, scoped to what this build
actually has: an in-memory e-commerce dataset to reset between tests, and
an isolated offline Chroma store per test.
"""
import os

import pytest

os.environ["LLM_PROVIDER"] = "mock"
os.environ["JWT_SECRET"] = "test-secret-for-the-test-suite-only-0123456789"
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
    policies, claims = mock_data.initialize_insurance_data()
    mock_data.POLICIES.clear()
    mock_data.POLICIES.update(policies)
    mock_data.CLAIMS.clear()
    mock_data.CLAIMS.update(claims)
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


@pytest.fixture(autouse=True)
def reset_login_throttle():
    """Failed-login counters are module state; never let one test lock out another."""
    from fulfillment_api import server

    server._failures.clear()
    yield
    server._failures.clear()


@pytest.fixture
def login(fulfillment_test_client):
    """login(domain, email, password="demo1234") -> JWT, via the real /auth/login."""

    def _login(domain, email, password="demo1234"):
        resp = fulfillment_test_client.post("/auth/login", json={"domain": domain, "email": email, "password": password})
        assert resp.status_code == 200, resp.text
        return resp.json()["token"]

    return _login


def auth(token):
    """Authorization header for a token."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fulfillment_wired(monkeypatch, fulfillment_test_client):
    """Point every httpx call aimed at the Fulfillment API (the agent's tools and
    the Agent API's /auth/login proxy) at the real Fulfillment app running
    in-process -- so tests exercise the genuine auth/ownership code, with no
    sockets -- and report the Fulfillment API as reachable."""
    import httpx

    from agent import contact_center_agent
    from agent.fulfillment_client import FULFILLMENT_API_URL

    monkeypatch.setattr(contact_center_agent, "check_fulfillment_api_health", lambda: True)
    real_get, real_post = httpx.get, httpx.post

    def route(real, method):
        def call(url, **kw):
            if str(url).startswith(FULFILLMENT_API_URL):
                kw.pop("timeout", None)
                return getattr(fulfillment_test_client, method)(str(url)[len(FULFILLMENT_API_URL):], **kw)
            return real(url, **kw)

        return call

    monkeypatch.setattr(httpx, "get", route(real_get, "get"))
    monkeypatch.setattr(httpx, "post", route(real_post, "post"))
    yield


@pytest.fixture
def make_agent(fulfillment_wired, login):
    """make_agent(email=None, domain="ecommerce") -> a CallCenterAgent signed in
    as that customer (anonymous when email is None)."""
    from agent.contact_center_agent import CallCenterAgent
    from security.tokens import verify_token

    def _make(email=None, domain="ecommerce"):
        agent = CallCenterAgent()
        if email:
            token = login(domain, email)
            agent.set_auth(verify_token(token), token)
        return agent

    return _make


@pytest.fixture
def knowledge_ready(isolated_chroma_store):
    from ingestion.local_index import build_local_index

    build_local_index(force=True)
    yield
