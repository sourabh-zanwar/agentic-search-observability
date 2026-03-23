from __future__ import annotations

import json
import os
from typing import List

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from .agent import build_guardrailed_planner
from .config import Settings
from .models import EntityResult, JobInput, JobResult, SourceRef
from .observability import build_langfuse_handler, flush_langfuse


class QueryPlan(BaseModel):
    queries: List[str] = Field(..., min_length=1)


class ExtractionResult(BaseModel):
    results: List[EntityResult]


class GraphState(BaseModel):
    job: JobInput
    queries: List[str] = Field(default_factory=list)
    sources: List[SourceRef] = Field(default_factory=list)
    results: List[EntityResult] = Field(default_factory=list)


def _ensure_env(settings: Settings) -> None:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    if settings.tavily_api_key:
        os.environ.setdefault("TAVILY_API_KEY", settings.tavily_api_key)


def _get_callbacks(settings: Settings):
    handler = build_langfuse_handler(settings)
    return [handler] if handler else []


def _extract_text(agent_response: object) -> str:
    if isinstance(agent_response, dict):
        messages = agent_response.get("messages") or agent_response.get("output")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            return getattr(last, "content", str(last))
        if isinstance(messages, str):
            return messages
    if hasattr(agent_response, "content"):
        return getattr(agent_response, "content")
    return str(agent_response)


def plan_queries(state: GraphState, settings: Settings) -> dict:
    _ensure_env(settings)
    callbacks = _get_callbacks(settings)

    parser = PydanticOutputParser(pydantic_object=QueryPlan)
    user_template = (
        "Entities: {entities}\n"
        "Properties: {properties}\n"
        "Locale: {locale}\n\n"
        "Generate a list of 3 search queries that will help find the requested properties for the entities.\n"
        "{format_instructions}\n"
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You generate 3 precise web search queries. Return only JSON that matches the schema.",
            ),
            ("user", user_template),
        ]
    )

    if settings.guardrails_enabled:
        agent = build_guardrailed_planner(
            settings, banned_keywords=["password", "ssn", "credit card"]
        )
        content = user_template.format(
            entities=state.job.entities,
            properties=state.job.properties,
            locale=state.job.locale,
            format_instructions=parser.get_format_instructions(),
        )
        response = agent.invoke(
            {"messages": [{"role": "user", "content": content}]},
            config={"callbacks": callbacks},
        )
        content = _extract_text(response)
        plan = QueryPlan.model_validate_json(content)
    else:
        llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0,
            timeout=settings.request_timeout_seconds,
        )
        chain = prompt | llm | parser
        plan = chain.invoke(
            {
                "entities": state.job.entities,
                "properties": state.job.properties,
                "locale": state.job.locale,
                "format_instructions": parser.get_format_instructions(),
            },
            config={"callbacks": callbacks},
        )

    return {"queries": plan.queries}


def run_search(state: GraphState, settings: Settings) -> dict:
    _ensure_env(settings)
    if not settings.tavily_api_key:
        raise ValueError("TAVILY_API_KEY is required for web search.")

    tool = TavilySearchResults(max_results=settings.max_results_per_query)
    sources: List[SourceRef] = []
    for query in state.queries:
        results = tool.invoke({"query": query})
        for result in results:
            sources.append(
                SourceRef(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    snippet=result.get("content"),
                    query=query,
                )
            )
    return {"sources": sources}


def extract_facts(state: GraphState, settings: Settings) -> dict:
    _ensure_env(settings)
    callbacks = _get_callbacks(settings)

    parser = PydanticOutputParser(pydantic_object=ExtractionResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You extract structured facts from web snippets. Return only JSON matching the schema.",
            ),
            (
                "user",
                """
Entities: {entities}
Properties: {properties}

Sources (JSON list): {sources}

Extract property values for each entity. For each property, include a best-effort value and cite supporting sources.
If you cannot find a value, return null and confidence 0.
{format_instructions}
""",
            ),
        ]
    )

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
        timeout=settings.request_timeout_seconds,
    )
    chain = prompt | llm | parser
    extraction = chain.invoke(
        {
            "entities": state.job.entities,
            "properties": state.job.properties,
            "sources": json.dumps(
                [s.model_dump() for s in state.sources], ensure_ascii=True
            ),
            "format_instructions": parser.get_format_instructions(),
        },
        config={"callbacks": callbacks},
    )

    return {"results": extraction.results}


def build_graph(settings: Settings):
    builder = StateGraph(GraphState)
    builder.add_node("plan_queries", lambda state: plan_queries(state, settings))
    builder.add_node("run_search", lambda state: run_search(state, settings))
    builder.add_node("extract_facts", lambda state: extract_facts(state, settings))

    builder.set_entry_point("plan_queries")
    builder.add_edge("plan_queries", "run_search")
    builder.add_edge("run_search", "extract_facts")
    builder.add_edge("extract_facts", END)

    return builder.compile()


def run_job(job: JobInput, settings: Settings) -> JobResult:
    graph = build_graph(settings)
    callbacks = _get_callbacks(settings)
    state = graph.invoke({"job": job}, config={"callbacks": callbacks})

    if isinstance(state, dict):
        queries = state.get("queries", [])
        results = state.get("results", [])
    else:
        queries = getattr(state, "queries", [])
        results = getattr(state, "results", [])

    result = JobResult(results=results, queries=queries)
    if settings.langfuse_flush_each_job:
        flush_langfuse(settings)
    return result
