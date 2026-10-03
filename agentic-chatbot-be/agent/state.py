from typing import Annotated, Any, Dict, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    domain: str  # 'ecommerce' | 'insurance' | 'general'
    customer_context: Dict[str, Any]
