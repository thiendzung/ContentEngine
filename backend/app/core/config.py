from functools import lru_cache
from urllib.parse import unquote, urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_version: str = "0.1.0-ce04"
    database_url: str = (
        "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine"
    )
    test_database_url: str | None = None

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

    @property
    def resolved_database_url(self) -> str:
        """Return the only database URL allowed for the current environment."""
        if self.app_env.strip().lower() == "test":
            if not self.test_database_url or not self.test_database_url.strip():
                raise ValueError("test_database_url_required")
            return self.test_database_url
        return self.database_url

    @staticmethod
    def _database_target(url: str) -> tuple[str, int, str]:
        parsed = urlsplit(url)
        try:
            host = (parsed.hostname or "").lower()
            port = parsed.port or 5432
        except ValueError as exc:
            raise ValueError("unsafe_test_database_name") from exc
        database_name = unquote(parsed.path.lstrip("/"))
        if not host or not database_name or "/" in database_name:
            raise ValueError("unsafe_test_database_name")
        return host, port, database_name

    @model_validator(mode="after")
    def validate_test_database(self) -> "Settings":
        if self.app_env.strip().lower() != "test":
            return self
        if not self.test_database_url or not self.test_database_url.strip():
            raise ValueError("test_database_url_required")

        test_target = self._database_target(self.test_database_url)
        if "test" not in test_target[2].lower():
            raise ValueError("unsafe_test_database_name")

        if test_target == self._database_target(self.database_url):
            raise ValueError("test_database_must_differ_from_application_database")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
