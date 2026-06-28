"""Speech-to-text and text-to-speech.

Both go through OpenAI's audio endpoints. STT accepts whatever the browser's
MediaRecorder produced (usually webm/opus). TTS returns mp3 bytes shaped by the
persona's delivery instructions. If audio is disabled, callers get a clear error
and the web client falls back to the browser's own speech engine.
"""
from __future__ import annotations

import io
from functools import lru_cache

from .config import get_settings
from .persona import TTS_DELIVERY


class AudioUnavailable(RuntimeError):
    pass


@lru_cache
def _client():
    s = get_settings()
    if not s.audio_enabled():
        raise AudioUnavailable(
            "Server audio is disabled. Set OPENAI_API_KEY to enable speech."
        )
    from openai import OpenAI

    return OpenAI(api_key=s.openai_api_key)


def transcribe(audio_bytes: bytes, filename: str = "answer.webm") -> str:
    """Transcribe a candidate's recorded answer to text."""
    s = get_settings()
    client = _client()
    buf = io.BytesIO(audio_bytes)
    buf.name = filename
    try:
        resp = client.audio.transcriptions.create(model=s.stt_model, file=buf)
    except Exception:
        # Some accounts may not have the newer transcribe model; fall back.
        buf.seek(0)
        resp = client.audio.transcriptions.create(
            model=s.stt_fallback_model, file=buf
        )
    return (resp.text or "").strip()


def synthesize(text: str, voice: str) -> bytes:
    """Render the interviewer's line to mp3 audio with persona delivery."""
    s = get_settings()
    client = _client()
    kwargs = dict(model=s.tts_model, voice=voice, input=text, response_format="mp3")
    # gpt-4o-mini-tts supports `instructions` to steer delivery; older tts-1 does not.
    if "4o" in s.tts_model:
        kwargs["instructions"] = TTS_DELIVERY
    resp = client.audio.speech.create(**kwargs)
    return resp.read()
