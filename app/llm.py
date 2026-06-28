"""LLM factory. Returns a LangChain chat model for whichever provider is active.

Keeping this behind one function means the agents never care which vendor is in
use, and structured-output calls work the same way on both.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from .config import get_settings

# Faster/cheaper models used for evaluator & code_reviewer to cut latency.
_FAST_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
_FAST_OPENAI_MODEL = "gpt-4o-mini"


@lru_cache
def get_llm(temperature: float | None = None) -> BaseChatModel:
    s = get_settings()
    provider = s.resolved_llm_provider()
    temp = s.llm_temperature if temperature is None else temperature

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=s.anthropic_model,
            temperature=temp,
            max_tokens=4096,
            api_key=s.anthropic_api_key,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=s.openai_model,
            temperature=temp,
            api_key=s.openai_api_key,
        )

    raise RuntimeError(f"Unknown LLM provider: {provider}")


@lru_cache
def get_fast_llm(temperature: float | None = None) -> BaseChatModel:
    """Faster, cheaper model for scoring/review tasks that don't need top-tier reasoning."""
    s = get_settings()
    provider = s.resolved_llm_provider()
    temp = 0.2 if temperature is None else temperature

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=_FAST_ANTHROPIC_MODEL,
            temperature=temp,
            max_tokens=2048,
            api_key=s.anthropic_api_key,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=_FAST_OPENAI_MODEL,
            temperature=temp,
            api_key=s.openai_api_key,
        )

    raise RuntimeError(f"Unknown LLM provider: {provider}")
