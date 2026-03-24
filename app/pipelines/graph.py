from __future__ import annotations

import json
from typing import List

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.observability import build_langfuse_handler, flush_langfuse
from app.core.schemas import EntityResult, JobInput, JobResult, SourceRef
from app.pipelines.query_planner import plan_queries
from app.services.llm import build_llm
from app.services.search import run_tavily_search_async


class ExtractionResult(BaseModel):
    results: List[EntityResult]


class GraphState(BaseModel):
    job: JobInput
    queries: List[str] = Field(default_factory=list)
    sources: List[SourceRef] = Field(default_factory=list)
    results: List[EntityResult] = Field(default_factory=list)


def _get_callbacks(settings: Settings):
    handler = build_langfuse_handler(settings)
    return [handler] if handler else []


def plan_queries_node(state: GraphState, settings: Settings) -> dict:
    callbacks = _get_callbacks(settings)
    queries = plan_queries(state.job, settings, callbacks)
    return {"queries": queries}


async def run_search_node(state: GraphState, settings: Settings) -> dict:
    sources = await run_tavily_search_async(state.queries, settings)
    return {"sources": sources}


def extract_facts_node(state: GraphState, settings: Settings) -> dict:
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

    llm = build_llm(settings, temperature=0)
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
    async def run_search_node_bound(state: GraphState) -> dict:
        return await run_search_node(state, settings)

    builder = StateGraph(GraphState)
    builder.add_node("plan_queries", lambda state: plan_queries_node(state, settings))
    builder.add_node("run_search", run_search_node_bound)
    builder.add_node("extract_facts", lambda state: extract_facts_node(state, settings))

    builder.set_entry_point("plan_queries")
    builder.add_edge("plan_queries", "run_search")
    builder.add_edge("run_search", "extract_facts")
    builder.add_edge("extract_facts", END)

    return builder.compile()


async def run_job(job: JobInput, settings: Settings) -> JobResult:
    graph = build_graph(settings)
    callbacks = _get_callbacks(settings)
    state = await graph.ainvoke({"job": job}, config={"callbacks": callbacks})

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
