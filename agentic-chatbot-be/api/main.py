import json
import uuid
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from agent.contact_center_agent import CallCenterAgent
from agent.fulfillment_client import FULFILLMENT_API_URL, check_fulfillment_api_health
from api.schemas import ChatRequest, ChatResponse, HealthResponse, LoginRequest, LoginResponse, ReindexResponse, SpeakRequest, TranscribeResponse, VoiceStatus
from security.tokens import Identity, TokenError, bearer_token, verify_token
from voice import deepgram_voice as dv

app = FastAPI(title="Contact Center Agent API", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory per-session agent store. Each session gets its own
# CallCenterAgent instance (its own conversation_history/domain state), and is
# bound to the customer it was created for (None = anonymous).
SESSIONS: dict = {}
SESSION_OWNERS: dict = {}


def _owner_key(identity: Optional[Identity]) -> Optional[str]:
    return f"{identity.domain}:{identity.customer_id}" if identity else None


def _identity_from_header(authorization: Optional[str]) -> tuple:
    """(identity, token) from an Authorization header; (None, None) when anonymous.
    A token that is present but invalid/expired is a 401, never silently anonymous."""
    token = bearer_token(authorization)
    if token is None:
        return None, None
    try:
        return verify_token(token), token
    except TokenError as e:
        raise HTTPException(status_code=401, detail=str(e))


def _get_agent(session_id: str, identity: Optional[Identity] = None, token: Optional[str] = None) -> tuple:
    """(agent, session_id) for this caller. A session id that belongs to a different
    customer (or to a signed-in customer when the caller is anonymous) is never
    reused: the caller gets a fresh session instead, so no history can leak."""
    owner = _owner_key(identity)
    if session_id in SESSIONS and SESSION_OWNERS.get(session_id) != owner:
        session_id = str(uuid.uuid4())
    if session_id not in SESSIONS:
        SESSIONS[session_id] = CallCenterAgent()
        SESSION_OWNERS[session_id] = owner
    agent = SESSIONS[session_id]
    agent.set_auth(identity, token)
    return agent, session_id


@app.post("/auth/login", response_model=LoginResponse)
def auth_login(req: LoginRequest):
    """Sign in to one domain ('ecommerce' or 'insurance'). Credentials are checked
    by the Fulfillment API against that domain's own customer store."""
    try:
        resp = httpx.post(f"{FULFILLMENT_API_URL}/auth/login", json=req.model_dump(), timeout=5.0)
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Sign-in service is unavailable. Is the Fulfillment API running on port 8010?")
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", "Sign-in failed")
        except ValueError:
            detail = "Sign-in failed"
        raise HTTPException(status_code=resp.status_code if resp.status_code in (400, 401, 429) else 502, detail=detail)
    return resp.json()


@app.get("/auth/me")
def auth_me(authorization: Optional[str] = Header(default=None)):
    identity, _ = _identity_from_header(authorization)
    if identity is None:
        raise HTTPException(status_code=401, detail="Sign in required")
    return identity.public()


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        fulfillment_api=check_fulfillment_api_health(),
        knowledge_backend="chroma (offline)",
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, authorization: Optional[str] = Header(default=None)):
    identity, token = _identity_from_header(authorization)
    agent, session_id = _get_agent(req.session_id or str(uuid.uuid4()), identity, token)
    result = agent.chat(req.message)
    return ChatResponse(session_id=session_id, reply=result["reply"], domain=result["domain"], tool_calls=result["tool_calls"])


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, authorization: Optional[str] = Header(default=None)):
    """Server-sent events: `token` frames as the model writes, then one `done`
    frame with the same payload /chat returns. Lets the UI show (and speak) the
    reply before the full turn has finished."""
    identity, token = _identity_from_header(authorization)
    agent, session_id = _get_agent(req.session_id or str(uuid.uuid4()), identity, token)

    def frames():
        try:
            for kind, data in agent.chat_stream(req.message):
                if kind == "token":
                    yield f"event: token\ndata: {json.dumps({'text': data})}\n\n"
                else:
                    payload = {"session_id": session_id, **data}
                    yield f"event: done\ndata: {json.dumps(payload)}\n\n"
        except Exception as e:  # surface failures to the client instead of a dropped stream
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

    return StreamingResponse(frames(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/admin/reindex", response_model=ReindexResponse)
def reindex():
    from ingestion.local_index import build_local_index

    n = build_local_index(force=True)
    return ReindexResponse(chunks_indexed=n)


# ---------------------------------------------------------------- voice ---
# Browser mic audio -> Deepgram STT -> /chat as usual -> Deepgram TTS -> audio.
# The browser calls these two endpoints around the normal /chat call, so the
# agent itself stays text-only.

@app.get("/voice/status", response_model=VoiceStatus)
def voice_status():
    return VoiceStatus(enabled=dv.is_configured(), voices=dv.VOICES, default_voice=dv.DEFAULT_VOICE)


@app.post("/voice/transcribe", response_model=TranscribeResponse)
async def voice_transcribe(request: Request):
    """Body = raw recorded audio (e.g. audio/webm); returns the transcript."""
    audio = await request.body()
    if not audio:
        raise HTTPException(status_code=400, detail="Empty audio body")
    if len(audio) > dv.MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio too large")
    try:
        text = dv.voice_service.transcribe(audio, request.headers.get("content-type", "audio/webm"))
    except dv.VoiceUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except dv.VoiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return TranscribeResponse(text=text)


@app.post("/voice/speak")
def voice_speak(req: SpeakRequest):
    """Returns the reply spoken aloud as audio/wav."""
    try:
        audio = dv.voice_service.synthesize(req.text, req.voice or dv.DEFAULT_VOICE)
    except dv.VoiceUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except dv.VoiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return Response(content=audio, media_type="audio/wav")
