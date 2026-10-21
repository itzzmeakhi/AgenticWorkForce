"""Voice (Deepgram STT/TTS) tests -- Deepgram is mocked, no network or key needed."""
import httpx
import pytest
from fastapi.testclient import TestClient

from api.main import app
from voice import deepgram_voice as dv

client = TestClient(app)


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)


class TestTextPrep:
    def test_strips_markdown(self):
        out = dv.clean_text_for_speech("## Status\n- **Order** ORD1001 is `shipped`\n[track](http://x.y)")
        assert "#" not in out and "*" not in out and "`" not in out and "http" not in out
        assert "O R D, 1 0 0 1" in out and "shipped" in out and "track" in out

    def test_short_text_unchanged(self):
        assert dv.shorten_for_voice("Your order has shipped.") == "Your order has shipped."

    def test_long_text_cut_on_sentence_boundary(self):
        text = " ".join(f"Sentence number {i} is here." for i in range(60))
        out = dv.shorten_for_voice(text)
        assert len(out) <= dv.MAX_SPOKEN_CHARS and out.endswith(".")


class TestStatus:
    def test_disabled_without_key(self, no_key):
        body = client.get("/voice/status").json()
        assert body["enabled"] is False and body["default_voice"] in body["voices"]

    def test_enabled_with_key(self, key):
        assert client.get("/voice/status").json()["enabled"] is True


class TestEndpoints:
    def test_transcribe_503_without_key(self, no_key):
        r = client.post("/voice/transcribe", content=b"abc", headers={"content-type": "audio/webm"})
        assert r.status_code == 503

    def test_speak_503_without_key(self, no_key):
        assert client.post("/voice/speak", json={"text": "hello"}).status_code == 503

    def test_transcribe_empty_body_400(self, key):
        assert client.post("/voice/transcribe", content=b"", headers={"content-type": "audio/webm"}).status_code == 400

    def test_transcribe_returns_text(self, key, monkeypatch):
        seen = {}

        def fake_post(url, **kw):
            seen.update(url=url, **kw)
            return httpx.Response(200, request=httpx.Request("POST", url),
                                  json={"results": {"channels": [{"alternatives": [{"transcript": " status of ORD1001 "}]}]}})

        monkeypatch.setattr(dv.httpx, "post", fake_post)
        r = client.post("/voice/transcribe", content=b"audio-bytes", headers={"content-type": "audio/webm"})
        assert r.status_code == 200 and r.json() == {"text": "status of ORD1001"}
        assert seen["url"].endswith("/listen") and seen["params"]["model"] == "nova-3"
        assert seen["headers"]["Authorization"] == "Token test-key"

    def test_transcribe_no_speech_returns_empty(self, key, monkeypatch):
        monkeypatch.setattr(dv.httpx, "post", lambda url, **kw: httpx.Response(
            200, request=httpx.Request("POST", url), json={"results": {"channels": []}}))
        assert client.post("/voice/transcribe", content=b"x").json() == {"text": ""}

    def test_upstream_error_is_502(self, key, monkeypatch):
        monkeypatch.setattr(dv.httpx, "post", lambda url, **kw: httpx.Response(401, request=httpx.Request("POST", url)))
        assert client.post("/voice/transcribe", content=b"x").status_code == 502

    def test_speak_returns_wav_and_caches(self, key, monkeypatch):
        calls = []

        def fake_post(url, **kw):
            calls.append(kw)
            return httpx.Response(200, request=httpx.Request("POST", url), content=b"RIFF" + b"\0" * 200)

        monkeypatch.setattr(dv.httpx, "post", fake_post)
        dv.voice_service._cache.clear()
        for _ in range(2):
            r = client.post("/voice/speak", json={"text": "**Your order** has shipped.", "voice": "aura-luna-en"})
            assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content.startswith(b"RIFF")
        assert len(calls) == 1                                  # second call served from cache
        assert calls[0]["json"] == {"text": "Your order has shipped."}
        assert calls[0]["params"]["model"] == "aura-luna-en"

    def test_unknown_voice_falls_back_to_default(self, key, monkeypatch):
        seen = {}
        monkeypatch.setattr(dv.httpx, "post", lambda url, **kw: seen.update(kw) or httpx.Response(
            200, request=httpx.Request("POST", url), content=b"\0" * 200))
        dv.voice_service._cache.clear()
        client.post("/voice/speak", json={"text": "hi there", "voice": "nope"})
        assert seen["params"]["model"] == dv.DEFAULT_VOICE


class TestIdsAreSpelledOutForSpeech:
    @pytest.mark.parametrize("text,spoken", [
        ("Claim ID: CLM3003", "Claim ID: C L M, 3 0 0 3"),
        ("Policy: POL2003", "Policy: P O L, 2 0 0 3"),
        ("Order ORD1001 has shipped", "Order O R D, 1 0 0 1 has shipped"),
        ("Refund REF5001 is processing", "Refund R E F, 5 0 0 1 is processing"),
        ("tracking TRK7841002298", "tracking T R K, 7 8 4 1, 0 0 2 2, 9 8"),
        ("SKU-LT-201", "S K U, L T, 2 0 1"),
        ("order ord1001", "order O R D, 1 0 0 1"),
    ])
    def test_ids_are_spelled_letter_by_letter_and_digit_by_digit(self, text, spoken):
        assert dv.clean_text_for_speech(text) == spoken

    def test_every_digit_survives(self):
        out = dv.clean_text_for_speech("Claim CLM3003 on policy POL2003")
        assert out.replace(" ", "").replace(",", "").count("3003") == 1 and "2003" in out.replace(" ", "")

    def test_ordinary_words_and_numbers_are_untouched(self):
        text = "Your order total is INR 42999 and the policy covers 3 members in 2026."
        assert dv.clean_text_for_speech(text) == text

    def test_ids_inside_markdown_are_spelled_too(self):
        out = dv.clean_text_for_speech("- **CLM3003** on `POL2003`\n- ORD1001")
        assert "C L M, 3 0 0 3" in out and "P O L, 2 0 0 3" in out and "O R D, 1 0 0 1" in out

    def test_speak_endpoint_sends_the_spelled_out_text_to_deepgram(self, key, monkeypatch):
        sent = {}

        def fake_post(url, **kw):
            sent.update(kw)
            return httpx.Response(200, request=httpx.Request("POST", url), content=b"RIFF" + b"\0" * 200)

        monkeypatch.setattr(dv.httpx, "post", fake_post)
        dv.voice_service._cache.clear()
        client.post("/voice/speak", json={"text": "Your claim CLM3003 is under review."})
        assert sent["json"]["text"] == "Your claim C L M, 3 0 0 3 is under review."
