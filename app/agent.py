from __future__ import annotations

from typing import Iterable

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from .config import Settings
from .guardrails import ContentFilterMiddleware


def build_guardrailed_planner(settings: Settings, banned_keywords: Iterable[str]):
    """Build a middleware-enabled agent used for query planning."""
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
        timeout=settings.request_timeout_seconds,
    )
    middleware = [ContentFilterMiddleware(banned_keywords=banned_keywords)]
    return create_agent(
        model=llm,
        tools=[],
        middleware=middleware,
        system_prompt=(
            "You are a planning assistant. Produce ONLY valid JSON that matches the given schema."
        ),
    )
