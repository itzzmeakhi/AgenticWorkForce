import json
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from agent.contact_center_agent import CallCenterAgent
from agent.fulfillment_client import check_fulfillment_api_health
from api.schemas import ChatRequest, ChatResponse, HealthResponse, ReindexResponse, SpeakRequest, TranscribeResponse, VoiceStatus
from voice import deepgram_voice as dv

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


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Server-sent events: `token` frames as the model writes, then one `done`
    frame with the same payload /chat returns. Lets the UI show (and speak) the
    reply before the full turn has finished."""
    session_id = req.session_id or str(uuid.uuid4())
    agent = _get_agent(session_id)

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
