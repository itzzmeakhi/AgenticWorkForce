"""Streaming chat: /chat/stream must end in the same result /chat gives."""
import json

import pytest

from fastapi.testclient import TestClient

from api.main import SESSIONS, app

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    # The dev .env may point at a real provider; these tests must be offline.
    monkeypatch.setenv("LLM_PROVIDER", "mock")


def _frames(resp):
    out = []
    for block in resp.text.strip().split("\n\n"):
        ev, data = block.split("\n", 1)
        out.append((ev.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


def test_stream_ends_with_done_matching_chat():
    r = client.post("/chat/stream", json={"message": "hello", "session_id": "s-stream"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    frames = _frames(r)
    assert frames[-1][0] == "done"
    done = frames[-1][1]
    assert done["session_id"] == "s-stream" and done["reply"] and "tool_calls" in done and "domain" in done
    assert all(ev == "token" for ev, _ in frames[:-1])


def test_stream_with_tool_call_reports_trace():
    r = client.post("/chat/stream", json={"message": "How long does a refund take?", "session_id": "s-stream-2"})
    done = _frames(r)[-1][1]
    assert any(t["tool"] for t in done["tool_calls"])


def test_stream_keeps_history_like_chat():
    sid = "s-stream-3"
    client.post("/chat/stream", json={"message": "hello", "session_id": sid})
    n = len(SESSIONS[sid].conversation_history)
    client.post("/chat", json={"message": "hello again", "session_id": sid})
    assert len(SESSIONS[sid].conversation_history) > n


def test_stream_error_becomes_error_frame(monkeypatch):
    def boom(self, message, customer_context=None):
        raise RuntimeError("llm down")
        yield  # pragma: no cover

    monkeypatch.setattr("agent.contact_center_agent.CallCenterAgent.chat_stream", boom)
    frames = _frames(client.post("/chat/stream", json={"message": "x", "session_id": "s-stream-4"}))
    assert frames[-1] == ("error", {"detail": "llm down"})
