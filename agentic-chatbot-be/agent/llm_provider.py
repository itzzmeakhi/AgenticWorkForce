import os
import re
from typing import List, Optional

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

load_dotenv()


class MockChatModel(BaseChatModel):
    """Zero-dependency stand-in LLM: ordered keyword-matching candidates
    decide whether to call a tool or answer directly, so the full pipeline
    (LangGraph loop, real tool execution, real knowledge retrieval) runs
    end to end with no API key at all."""

    tools_bound: list = []
    domain_hint: str = "general"

    @property
    def _llm_type(self) -> str:
        return "mock-chat-model"

    def bind_tools(self, tools, domain: str = "general", **kwargs):
        bound = MockChatModel()
        bound.tools_bound = tools
        bound.domain_hint = domain
        return bound

    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        last_human = ""
        for m in reversed(messages):
            if m.type == "human":
                last_human = m.content
                break
        text = last_human.lower()

        tool_results_this_turn = []
        for m in reversed(messages):
            if m.type == "human":
                break
            if isinstance(m, ToolMessage):
                tool_results_this_turn.append(m)
        tool_results_this_turn.reverse()

        if tool_results_this_turn:
            summary = " ".join(str(m.content) for m in tool_results_this_turn)
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=summary))])

        bound_by_name = {t.name: t for t in self.tools_bound} if self.tools_bound else {}

        def want(name: str) -> bool:
            return name in bound_by_name

        def try_cancel_order():
            if want("cancel_order") and "cancel" in text:
                oid = _extract_id(text, "ord")
                if oid:
                    return "cancel_order", {"order_id": oid, "reason": "customer requested"}
            return None

        def try_track_package():
            if want("track_package") and "track" in text:
                oid = _extract_id(text, "ord")
                if oid:
                    return "track_package", {"order_id": oid}
            return None

        def try_order_status():
            if want("get_order_status") and any(k in text for k in ["order", "delivery", "shipped", "status"]):
                oid = _extract_id(text, "ord")
                if oid:
                    return "get_order_status", {"order_id": oid}
            return None

        def try_my_orders():
            if want("get_my_orders") and "@" in text and ("order" in text or "my order" in text):
                email = _extract_email(text)
                if email:
                    return "get_my_orders", {"customer_email": email}
            return None

        def try_products():
            keywords = ["search", "find", "looking for", "show me", "under ", "in stock", "laptop", "phone", "watch"]
            if want("search_products") and any(k in text for k in keywords):
                max_price = _extract_amount(text) if any(k in text for k in ["under ", "below ", "less than"]) else 0
                return "search_products", {"query": "", "category": "", "max_price": max_price}
            return None

        def try_insurance_wip():
            if want("insurance_status_wip") and any(k in text for k in ["policy", "claim", "premium", "coverage", "insurance"]):
                return "insurance_status_wip", {}
            return None

        def try_knowledge():
            keywords = ["how long", "refund", "eligib", "timeline", "policy", "faq", "how do i"]
            if want("search_comprehensive_knowledge") and any(k in text for k in keywords):
                return "search_comprehensive_knowledge", {"query": last_human, "domain": self.domain_hint}
            return None

        candidates = [
            try_cancel_order, try_track_package, try_order_status, try_my_orders,
            try_insurance_wip, try_products, try_knowledge,
        ]

        tool_calls = []
        for candidate in candidates:
            result = candidate()
            if result:
                name, args = result
                tool_calls = [{"name": name, "args": args, "id": f"mock-{name}"}]
                break

        if tool_calls:
            msg = AIMessage(content="", tool_calls=tool_calls)
        else:
            msg = AIMessage(
                content=(
                    "[MOCK LLM RESPONSE -- no LLM_PROVIDER/API key configured] I'd normally answer "
                    f"this using the knowledge base and tools. You asked: \"{last_human}\". "
                    "Configure a real provider in .env to get a live answer."
                )
            )
        return ChatResult(generations=[ChatGeneration(message=msg)])


def _extract_id(text: str, prefix: str) -> Optional[str]:
    match = re.search(rf"{prefix}[- ]?\d+", text, re.IGNORECASE)
    if match:
        return match.group(0).upper().replace(" ", "").replace("-", "")
    return None


def _extract_email(text: str) -> Optional[str]:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return match.group(0) if match else None


def _extract_amount(text: str) -> float:
    keyworded = re.search(r"(?:amount|inr|rs\.?|rupees)\D{0,5}(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if keyworded:
        return float(keyworded.group(1))
    for match in re.finditer(r"(?<![a-zA-Z])(\d{3,})(?!\w)", text):
        return float(match.group(1))
    return 0.0


def get_llm() -> BaseChatModel:
    provider = os.getenv("LLM_PROVIDER", "mock").lower()

    if provider == "gemini" and os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        from agent.gemini_thought_signature_patch import apply as _apply_thought_sig_patch
        _apply_thought_sig_patch()

        return ChatGoogleGenerativeAI(
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            temperature=0.3,
        )

    if provider == "openai" and os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
            temperature=0.3,
        )

    if provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"), temperature=0.1)

    return MockChatModel()
