"""Central configuration, read from environment variables.

Crucible runs with two providers:
  - An LLM provider for reasoning (the agents). Anthropic Claude by default,
    OpenAI as fallback.
  - An audio provider for speech-to-text and text-to-speech. OpenAI by default.

Only the keys you actually set are required. If no OPENAI_API_KEY is present the
server-side audio endpoints return 503 and the web client falls back to the
browser's built-in speech engine.
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    return val.strip()


class Settings:
    # --- LLM (reasoning) ---
    anthropic_api_key: str | None = _get("ANTHROPIC_API_KEY")
    openai_api_key: str | None = _get("OPENAI_API_KEY")

    # Which provider drives the agents. "auto" picks Anthropic if its key exists,
    # otherwise OpenAI.
    llm_provider: str = _get("LLM_PROVIDER", "auto")  # auto | anthropic | openai
    anthropic_model: str = _get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    openai_model: str = _get("OPENAI_MODEL", "gpt-4o")
    llm_temperature: float = float(_get("LLM_TEMPERATURE", "0.6"))

    # --- Audio ---
    audio_provider: str = _get("AUDIO_PROVIDER", "openai")  # openai | none
    stt_model: str = _get("STT_MODEL", "gpt-4o-transcribe")
    stt_fallback_model: str = _get("STT_FALLBACK_MODEL", "whisper-1")
    tts_model: str = _get("TTS_MODEL", "gpt-4o-mini-tts")

    # --- App ---
    app_name: str = "Crucible"
    db_path: str = _get("CRUCIBLE_DB", "crucible.db")
    port: int = int(_get("PORT", "8000"))
    # Optional shared secret to gate the API for a personal deployment.
    access_token: str | None = _get("CRUCIBLE_ACCESS_TOKEN")

    def resolved_llm_provider(self) -> str:
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        raise RuntimeError(
            "No LLM key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY."
        )

    def audio_enabled(self) -> bool:
        return self.audio_provider == "openai" and bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
