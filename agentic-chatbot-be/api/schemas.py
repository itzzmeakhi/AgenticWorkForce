from typing import List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ToolTraceEntry(BaseModel):
    tool: str
    args: dict
    output: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    domain: str
    tool_calls: List[ToolTraceEntry]


class HealthResponse(BaseModel):
    status: str
    fulfillment_api: bool
    knowledge_backend: str


class ReindexResponse(BaseModel):
    chunks_indexed: int
