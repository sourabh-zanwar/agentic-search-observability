from __future__ import annotations

from typing import Iterable

from langchain.agents import create_agent
from app.core.config import Settings
from app.core.guardrails import ContentFilterMiddleware
from app.services.llm import build_llm


def build_guardrailed_planner(settings: Settings, banned_keywords: Iterable[str]):
    """Build a middleware-enabled agent used for query planning."""
    llm = build_llm(settings, temperature=0)
    middleware = [ContentFilterMiddleware(banned_keywords=banned_keywords)]
    return create_agent(
        model=llm,
        tools=[],
        middleware=middleware,
        system_prompt=(
            "You are a planning assistant. Produce ONLY valid JSON that matches the given schema."
        ),
    )
