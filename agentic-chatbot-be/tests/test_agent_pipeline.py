"""
End-to-end tests of the LangGraph pipeline (CallCenterAgent.chat()) running
on MockChatModel -- no LLM API key needed.

`fulfillment_wired` monkeypatches agent.fulfillment_client so its tools
call straight into fulfillment_api.operations in-process (no real HTTP
server on :8010 needs to be running) and reports the Fulfillment API as
reachable, so CUSTOMER_FACING_TOOLS/PRODUCT_TOOLS/INSURANCE_TOOLS (the WIP
stub) all get bound.
"""
import pytest


@pytest.fixture
def fulfillment_wired(monkeypatch):
    from agent import contact_center_agent, fulfillment_client
    from fulfillment_api import operations as ops

    monkeypatch.setattr(contact_center_agent, "check_fulfillment_api_health", lambda: True)

    def fake_get(path: str, **params) -> str:
        if path.startswith("/orders/") and path.endswith("/track"):
            return ops.track_package(path.split("/")[2])
        if path.startswith("/orders/"):
            return ops.get_order_status(path.split("/")[2])
        if path == "/orders":
            return ops.get_my_orders(params["customer_email"])
        if path.startswith("/products/"):
            return ops.get_product_details(path.split("/")[2])
        if path == "/products":
            return ops.search_products(params.get("query", ""), params.get("category", ""), params.get("max_price", 0))
        if path == "/insurance/status":
            return ops.insurance_status_wip()
        raise AssertionError(f"unexpected GET {path}")

    def fake_post(path: str, **body) -> str:
        if path.endswith("/cancel"):
            return ops.cancel_order(path.split("/")[2], body.get("reason", "customer requested"))
        raise AssertionError(f"unexpected POST {path}")

    monkeypatch.setattr(fulfillment_client, "_get", fake_get)
    monkeypatch.setattr(fulfillment_client, "_post", fake_post)
    yield


@pytest.fixture
def knowledge_ready(isolated_chroma_store):
    from ingestion.local_index import build_local_index

    build_local_index(force=True)
    yield


class TestOrderFlow:
    def test_order_status_lookup(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        result = agent.chat("What is the status of order ORD1001?")
        assert result["domain"] == "ecommerce"
        assert any(tc["tool"] == "get_order_status" for tc in result["tool_calls"])
        assert "shipped" in result["reply"].lower()

    def test_track_package(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        result = agent.chat("Can you track order ORD1002 for me?")
        assert any(tc["tool"] == "track_package" for tc in result["tool_calls"])
        assert "TRK7841002298" in result["reply"]

    def test_cancel_order(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        result = agent.chat("Please cancel order ORD1003")
        assert any(tc["tool"] == "cancel_order" for tc in result["tool_calls"])
        assert "cancelled" in result["reply"].lower()


class TestInsuranceWipFlow:
    def test_insurance_question_routes_and_returns_honest_stub(self, fulfillment_wired):
        """The core proof-point for this milestone's insurance handling:
        domain routing correctly detects an insurance question, and the
        agent calls the WIP stub tool rather than fabricating a policy
        answer."""
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        result = agent.chat("What's the status of my insurance policy?")
        assert result["domain"] == "insurance"
        assert any(tc["tool"] == "insurance_status_wip" for tc in result["tool_calls"])
        assert "development" in result["reply"].lower()


class TestDomainSwitching:
    def test_switches_domain_mid_conversation(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        first = agent.chat("What is the status of order ORD1001?")
        assert first["domain"] == "ecommerce"
        second = agent.chat("Now tell me about my insurance policy")
        assert second["domain"] == "insurance"
        assert any(tc["tool"] == "insurance_status_wip" for tc in second["tool_calls"])


class TestKnowledgeGrounding:
    def test_knowledge_question_uses_rag(self, fulfillment_wired, knowledge_ready):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        result = agent.chat("What is your refund policy?")
        assert any(tc["tool"] == "search_comprehensive_knowledge" for tc in result["tool_calls"])
        assert result["reply"]

    def test_runs_without_fulfillment_api(self, knowledge_ready):
        """With no fulfillment API reachable, the agent still answers
        knowledge-base questions -- the graceful-degradation path."""
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        assert agent.fulfillment_available is False
        result = agent.chat("What is your refund policy?")
        assert result["reply"]
