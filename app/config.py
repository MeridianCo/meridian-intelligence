"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service-wide settings resolved from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App metadata ---
    app_name: str = "AI Profile Intelligence"
    app_version: str = "0.1.0"
    debug: bool = False

    # --- HTTP client ---
    http_timeout: float = 15.0
    http_max_retries: int = 3

    # --- Optional API keys for enrichment providers ---
    # Set these in .env or as environment variables.
    proxycurl_api_key: str = ""   # https://nubela.co/proxycurl (LinkedIn enrichment)
    clearbit_api_key: str = ""    # https://clearbit.com (company/person enrichment)

    # --- Caching ---
    cache_ttl_seconds: int = 3600   # 1 hour TTL for in-process cache
    cache_max_size: int = 256        # maximum number of cached profiles


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
