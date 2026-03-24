from __future__ import annotations

from typing import Iterable, List

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.schemas import JobInput
from app.pipelines.agent_planner import build_guardrailed_planner
from app.services.llm import build_llm


class QueryPlan(BaseModel):
    queries: List[str] = Field(..., min_length=1)


def _chunk(items: List, size: int) -> List[List]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def batched_query_plan(job: JobInput, settings: Settings) -> List[str]:
    entity_chunks = _chunk(job.entities, settings.entities_per_query)
    property_chunks = _chunk(job.properties, settings.properties_per_query)

    queries: List[str] = []
    for prop_chunk in property_chunks:
        prop_part = " OR ".join(f"\"{prop.name}\"" for prop in prop_chunk)
        for ent_chunk in entity_chunks:
            ent_part = " OR ".join(f"\"{entity.name}\"" for entity in ent_chunk)
            query = f"({ent_part}) ({prop_part})"
            if job.locale:
                query = f"{query} {job.locale}"
            queries.append(query)

    if settings.max_queries and len(queries) > settings.max_queries:
        queries = queries[: settings.max_queries]
    return queries


def llm_query_plan(job: JobInput, settings: Settings, callbacks: list) -> List[str]:
    parser = PydanticOutputParser(pydantic_object=QueryPlan)
    user_template = (
        "Entities: {entities}\n"
        "Properties: {properties}\n"
        "Locale: {locale}\n"
        "Query budget: {budget}\n\n"
        "Generate a compact list of search queries that will help find the requested properties for the entities."
        "\n{format_instructions}\n"
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You generate precise web search queries. Return only JSON that matches the schema.",
            ),
            ("user", user_template),
        ]
    )

    if settings.guardrails_enabled:
        agent = build_guardrailed_planner(
            settings, banned_keywords=["password", "ssn", "credit card"]
        )
        content = user_template.format(
            entities=job.entities,
            properties=job.properties,
            locale=job.locale,
            budget=settings.max_queries,
            format_instructions=parser.get_format_instructions(),
        )
        response = agent.invoke(
            {"messages": [{"role": "user", "content": content}]},
            config={"callbacks": callbacks},
        )
        if isinstance(response, dict):
            messages = response.get("messages") or []
            content = messages[-1].content if messages else ""
        else:
            content = getattr(response, "content", str(response))
        plan = QueryPlan.model_validate_json(content)
    else:
        llm = build_llm(settings, temperature=0)
        chain = prompt | llm | parser
        plan = chain.invoke(
            {
                "entities": job.entities,
                "properties": job.properties,
                "locale": job.locale,
                "budget": settings.max_queries,
                "format_instructions": parser.get_format_instructions(),
            },
            config={"callbacks": callbacks},
        )

    return plan.queries


def refine_queries(queries: Iterable[str], settings: Settings, callbacks: list) -> List[str]:
    parser = PydanticOutputParser(pydantic_object=QueryPlan)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Rewrite each query to be concise and web-search friendly. Return only JSON matching the schema.",
            ),
            (
                "user",
                "Queries: {queries}\n{format_instructions}",
            ),
        ]
    )
    llm = build_llm(settings, temperature=0)
    chain = prompt | llm | parser
    plan = chain.invoke(
        {"queries": list(queries), "format_instructions": parser.get_format_instructions()},
        config={"callbacks": callbacks},
    )
    return plan.queries


def plan_queries(job: JobInput, settings: Settings, callbacks: list) -> List[str]:
    mode = settings.query_plan_mode.lower()
    if mode == "llm":
        return llm_query_plan(job, settings, callbacks)
    if mode == "hybrid":
        base = batched_query_plan(job, settings)
        return refine_queries(base, settings, callbacks) if settings.query_refine_with_llm else base
    return batched_query_plan(job, settings)
