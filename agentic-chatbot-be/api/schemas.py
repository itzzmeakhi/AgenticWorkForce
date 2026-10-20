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


class SpeakRequest(BaseModel):
    text: str
    voice: Optional[str] = None


class TranscribeResponse(BaseModel):
    text: str


class VoiceStatus(BaseModel):
    enabled: bool
    voices: dict
    default_voice: str


class LoginRequest(BaseModel):
    domain: str   # 'ecommerce' | 'insurance'
    email: str
    password: str


class LoginUser(BaseModel):
    customer_id: str
    email: str
    name: str
    domain: str


class LoginResponse(BaseModel):
    token: str
    user: LoginUser
