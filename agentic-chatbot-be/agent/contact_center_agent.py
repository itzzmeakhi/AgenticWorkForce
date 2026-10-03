import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from agent.domain_router import classify_domain
from agent.fulfillment_client import (
    CUSTOMER_FACING_TOOLS, INSURANCE_TOOLS, PRODUCT_TOOLS,
    check_fulfillment_api_health,
)
from agent.knowledge_tools import KNOWLEDGE_TOOLS
from agent.llm_provider import get_llm
from agent.state import AgentState
from agent.system_prompt_config import get_system_prompt

logger = logging.getLogger(__name__)

# Real insurance operations aren't wired up in this milestone -- see
# fulfillment_api/operations.py's insurance_status_wip() and README
# "What's WIP". Passed into get_system_prompt() so the agent is instructed
# to use the honest WIP tool rather than guess at policy/claim data.
INSURANCE_AVAILABLE = False


def _domain_tools(domain: str, fulfillment_available: bool):
    """Re-derive the bound tool list from the current domain -- the
    mechanism behind domain fluidity. Insurance gets only the WIP stub
    tool + knowledge search in this build."""
    knowledge = KNOWLEDGE_TOOLS
    if not fulfillment_available:
        return knowledge
    if domain == "ecommerce":
        return CUSTOMER_FACING_TOOLS + PRODUCT_TOOLS + knowledge
    if domain == "insurance":
        return INSURANCE_TOOLS + knowledge
    return CUSTOMER_FACING_TOOLS + PRODUCT_TOOLS + INSURANCE_TOOLS + knowledge


class CallCenterAgent:
    """LangGraph-based contact center agent with offline knowledge search
    and e-commerce fulfillment tool integration. Same public shape as the
    full build: construct once, then call .chat(message)."""

    def __init__(self):
        self.llm = get_llm()
        self.conversation_history: List[BaseMessage] = []
        self.domain = "general"
        self.customer_context: Dict[str, Any] = {}

        self.fulfillment_available = check_fulfillment_api_health()
        if self.fulfillment_available:
            logger.info("Fulfillment API is reachable -- customer-facing/product tools enabled")
        else:
            logger.warning(
                "Fulfillment API is not reachable -- start it with "
                "`uvicorn fulfillment_api.server:app --port 8010`. Running with knowledge search only."
            )

        all_tools = CUSTOMER_FACING_TOOLS + PRODUCT_TOOLS + INSURANCE_TOOLS + KNOWLEDGE_TOOLS
        self.available_tools = {t.name: t for t in all_tools}

        self.graph = self._create_graph()
        self.app = self.graph.compile()
        logger.info("Contact Center Agent initialized (midsem build)")

    def _create_graph(self) -> StateGraph:
        def agent_node(state: AgentState) -> Dict[str, Any]:
            domain = state.get("domain", "general")
            tools = _domain_tools(domain, self.fulfillment_available)

            system_prompt_text = get_system_prompt(domain, self.fulfillment_available, INSURANCE_AVAILABLE)
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt_text), ("placeholder", "{messages}"),
            ])

            if self.llm.__class__.__name__ == "MockChatModel":
                llm_with_tools = self.llm.bind_tools(tools, domain=domain)
            else:
                llm_with_tools = self.llm.bind_tools(tools)

            try:
                formatted = prompt.invoke({"messages": state["messages"]})
                response = llm_with_tools.invoke(formatted)
                return {"messages": [response]}
            except Exception as e:
                logger.error(f"Error in agent_node: {e}")
                return {"messages": [AIMessage(content=f"I apologize, I hit an error: {e}. Please try again.")]}

        def tool_node(state: AgentState) -> Dict[str, Any]:
            last_message = state["messages"][-1]
            if not getattr(last_message, "tool_calls", None):
                return {"messages": []}

            tool_messages = []
            for tool_call in last_message.tool_calls:
                name = tool_call["name"]
                try:
                    tool_fn = self.available_tools.get(name)
                    if tool_fn is None:
                        result = f"Error: unknown tool '{name}'."
                    else:
                        result = tool_fn.invoke(tool_call["args"])
                    tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
                except Exception as e:
                    logger.error(f"Error executing tool {name}: {e}")
                    tool_messages.append(ToolMessage(content=f"Error executing tool: {e}", tool_call_id=tool_call["id"]))
            return {"messages": tool_messages}

        def classify_domain_node(state: AgentState) -> Dict[str, Any]:
            last_user_msg = ""
            for m in reversed(state["messages"]):
                if getattr(m, "type", None) == "human":
                    last_user_msg = m.content
                    break
            previous = state.get("domain", "general")
            return {"domain": classify_domain(last_user_msg, previous_domain=previous)}

        def should_continue(state: AgentState) -> str:
            last_message = state["messages"][-1]
            return "tools" if getattr(last_message, "tool_calls", None) else "end"

        workflow = StateGraph(AgentState)
        workflow.add_node("classify_domain", classify_domain_node)
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)

        workflow.add_edge(START, "classify_domain")
        workflow.add_edge("classify_domain", "agent")
        workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
        workflow.add_edge("tools", "agent")

        return workflow

    def chat(self, message: str, customer_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run one turn. Returns {reply, domain, tool_calls} -- the same
        shape api/main.py's /chat endpoint hands back over HTTP."""
        if customer_context:
            self.customer_context.update(customer_context)

        self.conversation_history.append(HumanMessage(content=message))
        result = self.app.invoke(
            {"messages": self.conversation_history, "domain": self.domain, "customer_context": self.customer_context},
            config={"recursion_limit": 15},
        )
        self.conversation_history = result["messages"]
        self.domain = result["domain"]

        final_reply = ""
        tool_trace = []
        pending = {}
        for m in result["messages"]:
            if isinstance(m, AIMessage) and m.text:
                # langchain-core >=1.0 can represent AIMessage.content as a
                # list of typed blocks (text/reasoning/tool_call/...) instead
                # of a plain string -- e.g. Gemini 3's thinking output comes
                # back this way. `.text` is the library's own accessor that
                # normalizes either shape (str, or list-of-blocks) down to
                # the concatenated text content as a real `str`, which is
                # what ChatResponse.reply (a Pydantic str field) requires.
                final_reply = m.text
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    entry = {"tool": tc["name"], "args": tc["args"], "output": None}
                    tool_trace.append(entry)
                    pending[tc["id"]] = entry
            if isinstance(m, ToolMessage):
                entry = pending.get(getattr(m, "tool_call_id", None))
                if entry is not None:
                    entry["output"] = str(m.content)[:500]

        return {"reply": final_reply, "domain": result["domain"], "tool_calls": tool_trace}

    def clear_conversation_history(self):
        self.conversation_history = []
        self.domain = "general"
