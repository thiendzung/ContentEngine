from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_version: str = "0.1.0-ce01"
    database_url: str = (
        "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine"
    )

    serper_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None
    exa_api_key: SecretStr | None = None
    jina_api_key: SecretStr | None = None
    brave_search_api_key: SecretStr | None = None

    research_request_timeout_seconds: float = 20.0
    research_max_provider_calls: int = 8
    research_max_selected_urls: int = 3
    research_max_pages_read: int = 3
    research_max_second_hop_candidates: int = 8
    research_max_raw_excerpt_chars: int = 8000
    research_jina_token_budget: int = Field(default=20_000, gt=0)
    research_jina_max_links: int = Field(default=100, ge=0)

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
