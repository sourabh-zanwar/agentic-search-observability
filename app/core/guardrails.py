from __future__ import annotations

from typing import Any, Iterable

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain.messages import AIMessage


class ContentFilterMiddleware(AgentMiddleware):
    """Deterministic guardrail: block requests containing banned keywords."""

    def __init__(self, banned_keywords: Iterable[str]):
        super().__init__()
        self._banned = {kw.lower() for kw in banned_keywords}

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: object) -> dict[str, Any] | None:
        text = " ".join(
            message.content
            for message in state["messages"]
            if hasattr(message, "content") and isinstance(message.content, str)
        ).lower()
        if any(keyword in text for keyword in self._banned):
            return {
                "messages": [AIMessage("Request blocked by guardrails.")],
                "jump_to": "end",
            }
        return None
