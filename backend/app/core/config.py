from functools import lru_cache
from urllib.parse import unquote, urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_version: str = "0.1.0-ce05"
    database_url: str = (
        "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine"
    )
    test_database_url: str | None = None
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Operational observability is always available. Development defaults to DEBUG;
    # production clamps DEBUG to INFO unless an operator explicitly opts in.
    log_level: str = "DEBUG"
    log_json: bool = True
    allow_debug_in_production: bool = False

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

    @property
    def resolved_cors_allowed_origins(self) -> tuple[str, ...]:
        """Return the explicit cross-origin browser allowlist; wildcards are forbidden."""
        origins = tuple(
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        )
        if "*" in origins:
            raise ValueError("cors_wildcard_not_allowed")
        for origin in origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("invalid_cors_origin")
            if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
                raise ValueError("invalid_cors_origin")
        return origins

    @property
    def resolved_log_level(self) -> str:
        """Return a validated level while preventing accidental production DEBUG logging."""
        level = self.log_level.strip().upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("invalid_log_level")
        if (
            self.app_env.strip().lower() in {"prod", "production"}
            and level == "DEBUG"
            and not self.allow_debug_in_production
        ):
            return "INFO"
        return level

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
