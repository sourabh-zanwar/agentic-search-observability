from __future__ import annotations

import os
from typing import Optional

from langfuse import get_client
from langfuse.langchain import CallbackHandler

from .config import Settings


def build_langfuse_handler(settings: Settings) -> Optional[CallbackHandler]:
    if not settings.langfuse_enabled:
        return None
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        raise ValueError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required when Langfuse is enabled.")

    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    if settings.langfuse_host:
        os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
        os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_host)

    get_client()
    return CallbackHandler()


def flush_langfuse(settings: Settings) -> None:
    if not settings.langfuse_enabled:
        return
    get_client().flush()


def run_langfuse_smoke_test(settings: Settings) -> str:
    if not settings.langfuse_enabled:
        raise ValueError("Langfuse is disabled. Set LANGFUSE_ENABLED=true.")
    client = get_client()
    with client.start_as_current_observation(name="langfuse-smoke-test", as_type="span") as span:
        span.update(output="ok")
    client.flush()
    trace_url = client.get_trace_url()
    return trace_url or "trace created, URL unavailable"
