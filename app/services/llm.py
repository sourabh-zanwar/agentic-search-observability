from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

from app.core.config import Settings


def ensure_env(settings: Settings) -> None:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)


def build_llm(settings: Settings, *, temperature: float = 0) -> ChatOpenAI:
    ensure_env(settings)
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=temperature,
        timeout=settings.request_timeout_seconds,
    )
