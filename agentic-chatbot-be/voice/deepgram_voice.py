"""Speech services for the contact-center agent (Deepgram STT + TTS).

Modelled on the demo project's VoiceApp: Deepgram Nova-3 for speech-to-text,
Deepgram Aura for text-to-speech, replies cleaned/shortened for voice, and an
LRU cache of synthesised audio. Differences: it talks to Deepgram's REST API
through httpx (already a dependency), so no extra SDK is needed, and audio
arrives from the browser microphone instead of PyAudio.

The key is read from DEEPGRAM_API_KEY at call time. With no key the service
reports itself unavailable and the endpoints return 503 -- the rest of the
app keeps working.
"""
import os
import re
from collections import OrderedDict
from typing import Optional

import httpx

DEEPGRAM_BASE_URL = "https://api.deepgram.com/v1"
STT_MODEL = "nova-3"
DEFAULT_VOICE = "aura-asteria-en"
TTS_SAMPLE_RATE = 16000
MAX_SPOKEN_CHARS = 400        # replies longer than this are shortened for voice
MAX_AUDIO_BYTES = 10 * 1024 * 1024
CACHE_SIZE = 50
TIMEOUT = 30.0

# Aura voices offered by the demo project (id -> description).
VOICES = {
    "aura-asteria-en": "Asteria - warm & professional (female)",
    "aura-luna-en": "Luna - calm & friendly (female)",
    "aura-stella-en": "Stella - clear & energetic (female)",
    "aura-athena-en": "Athena - authoritative & confident (female)",
    "aura-orion-en": "Orion - deep & commanding (male)",
    "aura-arcas-en": "Arcas - professional & articulate (male)",
    "aura-angus-en": "Angus - friendly & approachable (male)",
    "aura-helios-en": "Helios - bright & enthusiastic (male)",
}


class VoiceUnavailable(RuntimeError):
    """No DEEPGRAM_API_KEY configured."""


class VoiceError(RuntimeError):
    """Deepgram rejected the request or could not be reached."""


def _api_key() -> Optional[str]:
    return os.getenv("DEEPGRAM_API_KEY") or None


def is_configured() -> bool:
    return _api_key() is not None


def clean_text_for_speech(text: str) -> str:
    """Strip markdown/formatting so the TTS does not read symbols aloud."""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)          # [label](url) -> label
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)      # headings
    t = re.sub(r"^\s*[-*•]\s+", "", t, flags=re.M)           # bullets
    t = re.sub(r"[*_~>|]+", "", t)                            # emphasis etc.
    t = re.sub(r"\s*\n+\s*", ". ", t)
    t = re.sub(r"\.\s*\.", ".", t)
    return re.sub(r"\s+", " ", t).strip()


def shorten_for_voice(text: str, limit: int = MAX_SPOKEN_CHARS) -> str:
    """Clean a reply and, if long, keep whole sentences up to `limit` chars."""
    clean = clean_text_for_speech(text)
    if len(clean) <= limit:
        return clean
    out = ""
    for sentence in re.split(r"(?<=[.!?])\s+", clean):
        if out and len(out) + len(sentence) + 1 > limit:
            break
        out = f"{out} {sentence}".strip()
    return out[:limit].rstrip() if len(out) > limit else out


class DeepgramVoice:
    def __init__(self) -> None:
        self._cache: "OrderedDict[str, bytes]" = OrderedDict()

    def _headers(self, content_type: str) -> dict:
        key = _api_key()
        if not key:
            raise VoiceUnavailable("DEEPGRAM_API_KEY is not set")
        return {"Authorization": f"Token {key}", "Content-Type": content_type}

    def transcribe(self, audio: bytes, content_type: str = "audio/webm") -> str:
        """Speech -> text. Returns "" when no speech was detected."""
        if not audio:
            return ""
        headers = self._headers(content_type or "audio/webm")
        params = {"model": STT_MODEL, "language": "en-US", "smart_format": "true", "punctuate": "true"}
        try:
            r = httpx.post(f"{DEEPGRAM_BASE_URL}/listen", params=params, headers=headers,
                           content=audio, timeout=TIMEOUT)
            r.raise_for_status()
            channels = r.json().get("results", {}).get("channels") or []
            alts = channels[0].get("alternatives") if channels else None
            return (alts[0].get("transcript") or "").strip() if alts else ""
        except httpx.HTTPError as e:
            raise VoiceError(f"speech-to-text failed: {e}") from e

    def synthesize(self, text: str, voice: str = DEFAULT_VOICE) -> bytes:
        """Text -> WAV bytes (reply is cleaned and shortened for voice first)."""
        spoken = shorten_for_voice(text)
        if not spoken:
            raise VoiceError("nothing to speak")
        if voice not in VOICES:
            voice = DEFAULT_VOICE
        key = f"{voice}:{spoken}"
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        headers = self._headers("application/json")
        params = {"model": voice, "encoding": "linear16", "container": "wav", "sample_rate": TTS_SAMPLE_RATE}
        try:
            r = httpx.post(f"{DEEPGRAM_BASE_URL}/speak", params=params, headers=headers,
                           json={"text": spoken}, timeout=TIMEOUT)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise VoiceError(f"text-to-speech failed: {e}") from e
        audio = r.content
        if len(audio) < 100:
            raise VoiceError("text-to-speech returned no audio")
        self._cache[key] = audio
        if len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return audio


voice_service = DeepgramVoice()
