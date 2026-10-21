from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    domain: str  # 'ecommerce' | 'insurance' | 'general'
