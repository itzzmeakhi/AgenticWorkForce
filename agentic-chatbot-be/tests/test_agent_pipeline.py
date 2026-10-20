"""
End-to-end tests of the LangGraph pipeline (CallCenterAgent.chat()) running
on MockChatModel -- no LLM API key needed.

The `fulfillment_wired` / `make_agent` fixtures (tests/conftest.py) send the
agent's tool calls to the real Fulfillment API app in-process, so these tests
go through genuine sign-in tokens and ownership checks. Customers used:
  abc@gmail.com    (e-commerce) ORD1001 shipped, ORD1005 delivered
  rahul@gmail.com  (e-commerce) ORD1002 shipped
  akhil@gmail.com  (e-commerce) ORD1003, ORD1004 processing
  neha@gmail.com   (insurance)  POL2001, POL2005, CLM3001
"""
import pytest


class TestOrderFlow:
    def test_order_status_lookup(self, make_agent):
        agent = make_agent("abc@gmail.com")
        result = agent.chat("What is the status of order ORD1001?")
        assert result["domain"] == "ecommerce"
        assert any(tc["tool"] == "get_order_status" for tc in result["tool_calls"])
        assert "shipped" in result["reply"].lower()

    def test_track_package(self, make_agent):
        agent = make_agent("rahul@gmail.com")
        result = agent.chat("Can you track order ORD1002 for me?")
        assert any(tc["tool"] == "track_package" for tc in result["tool_calls"])
        assert "TRK7841002298" in result["reply"]

    def test_cancel_order_requires_confirmation_then_cancels(self, make_agent):
        from fulfillment_api import mock_data

        agent = make_agent("akhil@gmail.com")
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

    def test_first_request_never_cancels(self, make_agent):
        agent = make_agent("akhil@gmail.com")
        agent.chat("Cancel order ORD1003")
        assert self._status("ORD1003") == "processing"
        assert agent.pending_cancellation == {"order_id": "ORD1003", "turn": 1}

    def test_negative_reply_does_not_cancel(self, make_agent):
        agent = make_agent("akhil@gmail.com")
        agent.chat("Cancel order ORD1003")
        result = agent.chat("No, don't cancel order ORD1003")
        assert "confirmation needed" in result["reply"].lower()
        assert self._status("ORD1003") == "processing"

    def test_confirmation_must_come_on_the_next_turn(self, make_agent):
        agent = make_agent("akhil@gmail.com")
        agent.chat("Cancel order ORD1003")
        agent.chat("What is your refund policy?")  # an unrelated turn in between
        agent.chat("Yes, cancel order ORD1003")
        assert self._status("ORD1003") == "processing"  # old confirmation request expired, so asked again

    def test_confirmation_for_a_different_order_does_not_cancel(self, make_agent):
        agent = make_agent("akhil@gmail.com")
        agent.chat("Cancel order ORD1003")
        agent.chat("Yes, cancel order ORD1004")
        assert self._status("ORD1003") == "processing"
        assert self._status("ORD1004") == "processing"

    def test_pending_state_cleared_after_cancellation(self, make_agent):
        agent = make_agent("akhil@gmail.com")
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


class TestInsuranceFlow:
    def test_signed_in_customer_sees_own_policies(self, make_agent):
        agent = make_agent("neha@gmail.com", domain="insurance")
        result = agent.chat("Show me my policies")
        assert result["domain"] == "insurance"
        assert [tc["tool"] for tc in result["tool_calls"]] == ["get_my_policies"]
        assert "POL2001" in result["reply"] and "POL2005" in result["reply"]
        assert "POL2002" not in result["reply"]

    def test_claim_status_lookup(self, make_agent):
        agent = make_agent("neha@gmail.com", domain="insurance")
        result = agent.chat("What is the status of claim CLM3001?")
        assert "under_review" in result["reply"]


class TestDomainSwitching:
    def test_switches_domain_mid_conversation(self, make_agent):
        agent = make_agent("abc@gmail.com")
        first = agent.chat("What is the status of order ORD1001?")
        assert first["domain"] == "ecommerce"
        second = agent.chat("Now tell me about my policies")
        assert second["domain"] == "insurance"
        assert any(tc["tool"] == "get_my_policies" for tc in second["tool_calls"])
        # ...but an e-commerce sign-in does not unlock insurance data
        assert "ACCESS_DENIED" in second["reply"]


class TestToolTracePerTurn:
    """The tool trace returned by chat() must describe only the current turn,
    not every tool call accumulated in the conversation history."""

    def test_trace_contains_only_current_turn(self, make_agent):
        agent = make_agent("abc@gmail.com")
        first = agent.chat("What is the status of order ORD1001?")
        assert [tc["tool"] for tc in first["tool_calls"]] == ["get_order_status"]

        second = agent.chat("Can you track order ORD1001 for me?")
        assert [tc["tool"] for tc in second["tool_calls"]] == ["track_package"]

        third = agent.chat("Now tell me about my policies")
        assert [tc["tool"] for tc in third["tool_calls"]] == ["get_my_policies"]

    def test_same_tool_in_consecutive_turns_keeps_own_output(self, make_agent):
        agent = make_agent("abc@gmail.com")
        first = agent.chat("What is the status of order ORD1001?")
        second = agent.chat("What is the status of order ORD1005?")

        assert len(first["tool_calls"]) == 1 and len(second["tool_calls"]) == 1
        assert second["tool_calls"][0]["args"] == {"order_id": "ORD1005"}
        assert "ORD1005" in second["tool_calls"][0]["output"]
        assert "ORD1001" not in second["tool_calls"][0]["output"]

    def test_turn_without_tools_has_empty_trace_and_no_stale_reply(self, make_agent):
        agent = make_agent("abc@gmail.com")
        agent.chat("What is the status of order ORD1001?")
        result = agent.chat("hello there")

        assert result["tool_calls"] == []
        assert "ORD1001" not in result["reply"]


class TestKnowledgeGrounding:
    def test_knowledge_question_uses_rag(self, make_agent, knowledge_ready):
        agent = make_agent()  # anonymous: the knowledge base needs no sign-in
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
