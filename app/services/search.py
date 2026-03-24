from __future__ import annotations

import asyncio
import json
import os
from typing import Any, List

from langchain_community.tools.tavily_search import TavilySearchResults

from app.core.config import Settings
from app.core.schemas import SourceRef


def ensure_search_env(settings: Settings) -> None:
    if settings.tavily_api_key:
        os.environ.setdefault("TAVILY_API_KEY", settings.tavily_api_key)


def run_tavily_search(queries: List[str], settings: Settings) -> List[SourceRef]:
    ensure_search_env(settings)
    if not settings.tavily_api_key:
        raise ValueError("TAVILY_API_KEY is required for web search.")

    tool = TavilySearchResults(max_results=settings.max_results_per_query)
    sources: List[SourceRef] = []
    for query in queries:
        results = _normalize_results(tool.invoke({"query": query}))
        for result in results:
            sources.append(
                SourceRef(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    snippet=result.get("content"),
                    query=query,
                )
            )
    return sources


async def run_tavily_search_async(queries: List[str], settings: Settings) -> List[SourceRef]:
    ensure_search_env(settings)
    if not settings.tavily_api_key:
        raise ValueError("TAVILY_API_KEY is required for web search.")

    semaphore = asyncio.Semaphore(settings.search_concurrency)

    async def _search_one(query: str) -> List[SourceRef]:
        async with semaphore:
            def _invoke() -> List[SourceRef]:
                tool = TavilySearchResults(max_results=settings.max_results_per_query)
                results = _normalize_results(tool.invoke({"query": query}))
                return [
                    SourceRef(
                        title=result.get("title", ""),
                        url=result.get("url", ""),
                        snippet=result.get("content"),
                        query=query,
                    )
                    for result in results
                ]

            return await asyncio.to_thread(_invoke)

    batches = await asyncio.gather(*[_search_one(query) for query in queries])
    sources: List[SourceRef] = []
    for batch in batches:
        sources.extend(batch)
    return sources


def _normalize_results(raw: Any) -> List[dict]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        if "results" in raw and isinstance(raw["results"], list):
            return [item for item in raw["results"] if isinstance(item, dict)]
        if "data" in raw and isinstance(raw["data"], list):
            return [item for item in raw["data"] if isinstance(item, dict)]
        return [raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return _normalize_results(parsed)
        except json.JSONDecodeError:
            return []
    return []
