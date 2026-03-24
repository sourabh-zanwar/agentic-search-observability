# Agentic Search API

Agentic web search service built with FastAPI, LangGraph, and LangChain. You send a JSON list of entities and properties, and the service plans queries, searches the web, and returns structured results with sources.

## Features
- FastAPI JSON interface (no chat UI)
- LangGraph orchestration (plan → search → extract)
- LangChain agent middleware for guardrails
- Optional Langfuse tracing/observability
- Docker deployment + uv for Python envs

## Quickstart (uv)
1. Create a virtual environment and install deps:

```bash
uv sync
```

2. Copy `.env.example` to `.env` and fill in the required keys. The OpenAI Python SDK uses `OPENAI_API_KEY` from the environment. citeturn3search0

3. Run the API:

```bash
uv run uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

## Running with Docker
```bash
docker compose up --build
```

## Langfuse (local observability)
Langfuse provides LangChain/LangGraph tracing via a callback handler and supports self-hosting with Docker Compose. citeturn7view0

1. Start Langfuse locally:

```bash
# Get a copy of the latest Langfuse repository

git clone https://github.com/langfuse/langfuse.git
cd langfuse

# Run the langfuse docker compose

docker compose up
```

Langfuse documents local Docker Compose usage and the LangChain callback integration (including required `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST`). citeturn6view0turn7view0

2. In this project’s `.env`, set:

```
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_FLUSH_EACH_JOB=false
```

### Langfuse smoke test
Call the debug endpoint to force a trace and return a `trace_url`:

```
GET /debug/langfuse
```

## API
### `POST /jobs`
**Input**
```json
{
  "properties": [
    {"name": "official website", "type": "url"},
    {"name": "headquarters", "type": "string"}
  ],
  "entities": [
    {"name": "OpenAI", "type": "organization"},
    {"name": "Anthropic", "type": "organization"}
  ],
  "locale": "en-US"
}
```

**Output (shape)**
```json
{
  "queries": ["..."],
  "results": [
    {
      "entity": {"name": "...", "type": "organization"},
      "properties": [
        {
          "name": "official website",
          "value": "https://...",
          "confidence": 0.82,
          "sources": [
            {"title": "...", "url": "https://...", "snippet": "..."}
          ]
        }
      ]
    }
  ]
}
```

## Guardrails middleware
The query planning step uses LangChain’s agent middleware API, which allows custom guardrails to run before the agent executes. You can add additional middleware in `app/core/guardrails.py` and toggle with `GUARDRAILS_ENABLED`. citeturn1search8turn1search10

## Notes
- Web search uses Tavily by default. Set `TAVILY_API_KEY` or swap out the tool in `app/services/search.py`.
- Choose a valid OpenAI model name and set `OPENAI_MODEL` accordingly in `.env`.
- If the API runs in Docker and Langfuse runs on your host, set `LANGFUSE_HOST` to `http://host.docker.internal:3000` (Mac/Windows) or to the Langfuse service name if they share a Docker network.

## Query Planning Controls
The query planner can batch entities and properties to reduce total web searches while preserving coverage. Configure with:
- `ENTITIES_PER_QUERY` (default 3)
- `PROPERTIES_PER_QUERY` (default 2)
- `MAX_QUERIES` (default 50)
- `QUERY_PLAN_MODE` = `batched` | `llm` | `hybrid`
- `QUERY_REFINE_WITH_LLM` (default false; only for `hybrid`)

## Search Concurrency
Web searches run in parallel with a concurrency limit:
- `SEARCH_CONCURRENCY` (default 5)
