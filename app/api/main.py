from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.core.config import get_settings
from app.core.schemas import JobInput, JobResult
from app.core.observability import run_langfuse_smoke_test
from app.pipelines.graph import run_job

app = FastAPI(title="Agentic Search API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/jobs", response_model=JobResult)
async def create_job(payload: JobInput) -> JobResult:
    settings = get_settings()
    try:
        return await run_job(payload, settings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/debug/langfuse")
def debug_langfuse() -> dict:
    settings = get_settings()
    try:
        trace_url = run_langfuse_smoke_test(settings)
        return {"status": "ok", "trace_url": trace_url}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
