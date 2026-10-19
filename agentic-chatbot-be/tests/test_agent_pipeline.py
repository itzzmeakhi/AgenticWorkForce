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

    def test_cancel_order_requires_confirmation_then_cancels(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent
        from fulfillment_api import mock_data

        agent = CallCenterAgent()
        first = agent.chat("Please cancel order ORD1003")
        assert any(tc["tool"] == "cancel_order" for tc in first["tool_calls"])
        assert "confirmation needed" in first["reply"].lower()
        assert mock_data.ORDERS["ORD1003"].status.value == "processing"  # nothing cancelled yet

        second = agent.chat("Yes, please cancel order ORD1003")
        assert "has been cancelled" in second["reply"].lower()
        assert mock_data.ORDERS["ORD1003"].status.value == "cancelled"


class TestCancelConfirmation:
    """cancel_order is destructive: it must never run on the first request, and
    only runs when the customer's very next message is a clear yes for the
    same order. Enforced in code, so it holds regardless of the LLM."""

    @staticmethod
    def _status(order_id):
        from fulfillment_api import mock_data

        return mock_data.ORDERS[order_id].status.value

    def test_first_request_never_cancels(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        agent.chat("Cancel order ORD1003")
        assert self._status("ORD1003") == "processing"
        assert agent.pending_cancellation == {"order_id": "ORD1003", "turn": 1}

    def test_negative_reply_does_not_cancel(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        agent.chat("Cancel order ORD1003")
        result = agent.chat("No, don't cancel order ORD1003")
        assert "confirmation needed" in result["reply"].lower()
        assert self._status("ORD1003") == "processing"

    def test_confirmation_must_come_on_the_next_turn(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        agent.chat("Cancel order ORD1003")
        agent.chat("What is your refund policy?")  # an unrelated turn in between
        agent.chat("Yes, cancel order ORD1003")
        assert self._status("ORD1003") == "processing"  # old confirmation request expired, so asked again

    def test_confirmation_for_a_different_order_does_not_cancel(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        agent.chat("Cancel order ORD1003")
        agent.chat("Yes, cancel order ORD1002")
        assert self._status("ORD1003") == "processing"
        assert self._status("ORD1002") == "shipped"

    def test_pending_state_cleared_after_cancellation(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        agent.chat("Cancel order ORD1003")
        agent.chat("Yes, cancel order ORD1003")
        assert agent.pending_cancellation is None
        again = agent.chat("Cancel order ORD1003")  # already cancelled: a fresh request asks again
        assert agent.pending_cancellation == {"order_id": "ORD1003", "turn": 3}
        assert "confirmation needed" in again["reply"].lower()

    @pytest.mark.parametrize("text", ["yes", "Yes please", "yeah, go ahead", "Confirm", "ok do it", "Yes, cancel it"])
    def test_clear_yes_is_affirmative(self, text):
        from agent.contact_center_agent import _is_affirmative

        assert _is_affirmative(text)

    @pytest.mark.parametrize(
        "text", ["no", "No, keep it", "don't cancel", "yes but wait", "I'm not sure", "maybe later", "cancel order ORD1003", ""]
    )
    def test_negative_or_ambiguous_is_not_affirmative(self, text):
        from agent.contact_center_agent import _is_affirmative

        assert not _is_affirmative(text)


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


class TestToolTracePerTurn:
    """The tool trace returned by chat() must describe only the current turn,
    not every tool call accumulated in the conversation history."""

    def test_trace_contains_only_current_turn(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        first = agent.chat("What is the status of order ORD1001?")
        assert [tc["tool"] for tc in first["tool_calls"]] == ["get_order_status"]

        second = agent.chat("Can you track order ORD1002 for me?")
        assert [tc["tool"] for tc in second["tool_calls"]] == ["track_package"]

        third = agent.chat("Now tell me about my insurance policy")
        assert [tc["tool"] for tc in third["tool_calls"]] == ["insurance_status_wip"]

    def test_same_tool_in_consecutive_turns_keeps_own_output(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        first = agent.chat("What is the status of order ORD1001?")
        second = agent.chat("What is the status of order ORD1003?")

        assert len(first["tool_calls"]) == 1 and len(second["tool_calls"]) == 1
        assert second["tool_calls"][0]["args"] == {"order_id": "ORD1003"}
        assert "ORD1003" in second["tool_calls"][0]["output"]
        assert "ORD1001" not in second["tool_calls"][0]["output"]

    def test_turn_without_tools_has_empty_trace_and_no_stale_reply(self, fulfillment_wired):
        from agent.contact_center_agent import CallCenterAgent

        agent = CallCenterAgent()
        agent.chat("What is the status of order ORD1001?")
        result = agent.chat("hello there")

        assert result["tool_calls"] == []
        assert "ORD1001" not in result["reply"]


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
