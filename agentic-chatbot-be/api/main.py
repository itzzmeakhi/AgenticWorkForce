import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.contact_center_agent import CallCenterAgent
from agent.fulfillment_client import check_fulfillment_api_health
from api.schemas import ChatRequest, ChatResponse, HealthResponse, ReindexResponse

app = FastAPI(title="Contact Center Agent API", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory per-session agent store. Each session gets its own
# CallCenterAgent instance (its own conversation_history/domain state).
SESSIONS: dict = {}


def _get_agent(session_id: str) -> CallCenterAgent:
    if session_id not in SESSIONS:
        SESSIONS[session_id] = CallCenterAgent()
    return SESSIONS[session_id]


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        fulfillment_api=check_fulfillment_api_health(),
        knowledge_backend="chroma (offline)",
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    agent = _get_agent(session_id)
    result = agent.chat(req.message)
    return ChatResponse(session_id=session_id, reply=result["reply"], domain=result["domain"], tool_calls=result["tool_calls"])


@app.post("/admin/reindex", response_model=ReindexResponse)
def reindex():
    from ingestion.local_index import build_local_index

    n = build_local_index(force=True)
    return ReindexResponse(chunks_indexed=n)
