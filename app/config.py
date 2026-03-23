from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field(..., alias="OPENAI_MODEL")

    tavily_api_key: Optional[str] = Field(default=None, alias="TAVILY_API_KEY")
    max_results_per_query: int = Field(
        default=5, ge=1, le=10, alias="MAX_RESULTS_PER_QUERY"
    )

    langfuse_enabled: bool = Field(default=False, alias="LANGFUSE_ENABLED")
    langfuse_public_key: Optional[str] = Field(
        default=None, alias="LANGFUSE_PUBLIC_KEY"
    )
    langfuse_secret_key: Optional[str] = Field(
        default=None, alias="LANGFUSE_SECRET_KEY"
    )
    langfuse_host: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL"),
    )

    request_timeout_seconds: int = Field(
        default=60, ge=1, le=600, alias="REQUEST_TIMEOUT_SECONDS"
    )
    guardrails_enabled: bool = Field(default=True, alias="GUARDRAILS_ENABLED")
    langfuse_flush_each_job: bool = Field(
        default=False, alias="LANGFUSE_FLUSH_EACH_JOB"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
