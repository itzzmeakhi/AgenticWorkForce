import logging
import re
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

# Real insurance operations aren't developed yet
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


# --------------------------------------------------------------------------- cancel confirmation
# cancel_order is destructive, so the agent never runs it on the first request.
# The first call is intercepted and answered with a confirmation prompt; the
# cancellation only runs if the customer's very next message is a clear "yes".
# This is enforced here in code, so it does not depend on the LLM following the prompt.
_AFFIRM = re.compile(r"\b(yes|yeah|yep|yup|sure|ok|okay|confirm|confirmed|proceed|go ahead|do it|please do)\b", re.I)
_NEGATE = re.compile(r"\b(no|nope|dont|don'?t|do not|not|never ?mind|keep|stop|wait|actually)\b", re.I)


def _is_affirmative(text: str) -> bool:
    """True for a clear yes ("yes", "yes please cancel it", "confirm"), False for
    anything negated or ambiguous ("no", "yes but wait", "I'm not sure")."""
    return bool(_AFFIRM.search(text)) and not _NEGATE.search(text)


class CallCenterAgent:
    """LangGraph-based contact center agent with offline knowledge search
    and e-commerce fulfillment tool integration."""

    def __init__(self):
        self.llm = get_llm()
        self.conversation_history: List[BaseMessage] = []
        self.domain = "general"
        self.customer_context: Dict[str, Any] = {}
        self.turn_count = 0
        # Set when cancel_order has been intercepted and the customer was asked
        # to confirm: {"order_id": ..., "turn": <turn the question was asked>}.
        self.pending_cancellation: Optional[Dict[str, Any]] = None

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
        logger.info("Contact Center Agent initialized")

    def _gate_cancel_order(self, args: Dict[str, Any], state: AgentState) -> Optional[str]:
        """Confirmation gate for cancel_order. Returns None when the cancellation
        may run, or the text to hand back to the model instead of running it."""
        order_id = str(args.get("order_id", "")).strip().upper()

        last_human = ""
        for m in reversed(state["messages"]):
            if getattr(m, "type", None) == "human":
                last_human = str(m.content)
                break

        pending = self.pending_cancellation
        confirmed = (
            pending is not None
            and pending["order_id"] == order_id
            and pending["turn"] == self.turn_count - 1  # asked on the previous turn, so this is the reply
            and _is_affirmative(last_human)
        )
        if confirmed:
            self.pending_cancellation = None
            return None

        self.pending_cancellation = {"order_id": order_id, "turn": self.turn_count}
        return (
            f"Confirmation needed before cancelling order {order_id} -- nothing has been "
            f"cancelled yet. Ask the customer to reply 'yes' to confirm; a cancellation "
            f"cannot be undone. Only call cancel_order again after they confirm in their next message."
        )

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
                    elif name == "cancel_order":
                        held = self._gate_cancel_order(tool_call["args"], state)
                        result = held if held is not None else tool_fn.invoke(tool_call["args"])
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

    def _begin_turn(self, message: str, customer_context: Optional[Dict[str, Any]]):
        self.turn_count += 1
        if customer_context:
            self.customer_context.update(customer_context)
        self.conversation_history.append(HumanMessage(content=message))
        # Messages up to here are history (including this turn's human message);
        # anything after this index was produced during this turn.
        turn_start = len(self.conversation_history)
        graph_input = {"messages": self.conversation_history, "domain": self.domain, "customer_context": self.customer_context}
        return graph_input, turn_start

    def _finish_turn(self, result: Dict[str, Any], turn_start: int) -> Dict[str, Any]:
        self.conversation_history = result["messages"]
        self.domain = result["domain"]

        final_reply = ""
        tool_trace = []
        pending = {}
        # Only walk this turn's messages so the reply and tool trace never include
        # tool calls (or a stale reply) carried over from earlier turns.
        for m in result["messages"][turn_start:]:
            if isinstance(m, AIMessage) and m.text:
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

    def chat(self, message: str, customer_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run one turn. Returns {reply, domain, tool_calls} -- the same
        shape api/main.py's /chat endpoint hands back over HTTP."""
        graph_input, turn_start = self._begin_turn(message, customer_context)
        result = self.app.invoke(graph_input, config={"recursion_limit": 15})
        return self._finish_turn(result, turn_start)

    def chat_stream(self, message: str, customer_context: Optional[Dict[str, Any]] = None):
        """Same turn as chat(), but yields events as the graph runs:
        ("token", text) for each piece of model text from the agent node, then a
        single ("done", {reply, domain, tool_calls}). The "done" payload is the
        authoritative result; tokens are only a live preview (a model may emit
        text before a tool call that is not part of the final reply)."""
        graph_input, turn_start = self._begin_turn(message, customer_context)
        final_state = None
        for mode, payload in self.app.stream(
            graph_input, config={"recursion_limit": 15}, stream_mode=["messages", "values"]
        ):
            if mode == "messages":
                chunk, meta = payload
                if meta.get("langgraph_node") == "agent" and isinstance(chunk, AIMessage):
                    text = chunk.text
                    if text and not getattr(chunk, "tool_calls", None):
                        yield "token", text
            else:
                final_state = payload
        yield "done", self._finish_turn(final_state, turn_start)

    def clear_conversation_history(self):
        self.conversation_history = []
        self.domain = "general"
        self.pending_cancellation = None
