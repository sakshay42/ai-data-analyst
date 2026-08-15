"""Application settings via Pydantic BaseSettings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_", extra="ignore")

    url: str = Field("postgresql://postgres:postgres@localhost:5432/ecommerce", alias="DATABASE_URL")
    pool_min: int = 2
    pool_max: int = 10
    statement_timeout: str = "30s"
    max_rows: int = 10_000


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENAI_", extra="ignore")

    api_key: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4096
    request_timeout: int = 60


class LangSmithSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LANGSMITH_", extra="ignore")

    enabled: bool = False
    api_key: str = Field("", alias="LANGCHAIN_API_KEY")
    project: str = Field("ai-data-analyst", alias="LANGCHAIN_PROJECT")
    tracing_v2: bool = Field(True, alias="LANGCHAIN_TRACING_V2")


class LangfuseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LANGFUSE_", extra="ignore")

    enabled: bool = False
    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"


class HeliconeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HELICONE_", extra="ignore")

    enabled: bool = False
    api_key: str = ""


class BraintrustSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BRAINTRUST_", extra="ignore")

    enabled: bool = False
    api_key: str = ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ai-data-analyst"
    log_level: str = "INFO"
    output_dir: str = "output"

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    langsmith: LangSmithSettings = Field(default_factory=LangSmithSettings)
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)
    helicone: HeliconeSettings = Field(default_factory=HeliconeSettings)
    braintrust: BraintrustSettings = Field(default_factory=BraintrustSettings)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
